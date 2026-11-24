"""Automatic start of the console (2 Nov 2026): every fired signal, model finding or detector alert, goes through one
grouping step instead of starting a run per alert. The first signal opens a group; for WAIT_S the group collects
others on the same call path; then one case starts with all of them, unless every signal has already cleared. Later
signals on the path of an active case are added to that case when it is not being worked on (the console then asks
for a re-run); they never start a second run. Alerts already open when the console starts do not start anything."""

from __future__ import annotations

import calendar
import os
import time

from . import case as cs
from . import ties, topology
from .audit import emit
from .trigger import COOLDOWN_S, ENV, MAX_OPEN_CASES

AUTOSTART = os.getenv("SRE_AGENT_AUTOSTART", "0").strip() == "1"
WAIT_S = int(os.getenv("SRE_AGENT_GROUP_WAIT_S", "60"))
FINDING_TTL_S = int(os.getenv("SRE_AGENT_FINDING_TTL_S", "600"))   # a finding has no "cleared" state: it counts as live this long
FLAP_S = int(os.getenv("SRE_AGENT_FLAP_S", "300"))   # an alert that cleared in the wait and fires again this soon is a real, flapping one
# these services can add evidence to a group or case but never open one (shopping-agent flags have been traffic bursts)
EVIDENCE_ONLY = {x.strip() for x in os.getenv("SRE_AGENT_EVIDENCE_ONLY", "shopping-agent").split(",") if x.strip()}
FINDINGS_SOURCE = "http:tuktuk_detection"   # written by splunk/ec2/setup-detect-modules-2026-10-28.py, alert FINDINGS_NAME
FINDINGS_SPL = f'index=tuktukpay source="{FINDINGS_SOURCE}" | table _time origin onset evidence flagged'


def finding_signal(row: dict) -> dict:
    """One row of the findings search as an incident the case and the investigator already understand."""
    origin = str(row.get("origin") or "unknown")
    flagged = str(row.get("flagged") or "").split()
    # "business" only summarises payment outcomes, so it may join any group; any other name stays, known to the map or not
    svcs = [s for s in dict.fromkeys([origin] + flagged) if s not in ("business", "unknown")]
    scope = f" [services in scope: {', '.join(svcs)}]" if svcs else ""
    try:
        since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.strptime(str(row.get("onset")), "%Y-%m-%d %H:%M UTC"))
    except ValueError:
        since = None
    return {"detector": f"Model finding: likely origin {origin} ({str(row.get('evidence') or '')[:300]}){scope}",
            "incident_id": f"model-{origin}-{row.get('_time')}", "key": f"model:{origin}", "severity": "Model",
            "anomaly_state": "FLAGGED", "since": since, "dimensions": {}, "kind": "model"}


def fetch_findings(splunk) -> list[dict]:
    r = splunk.splunk_run_query(FINDINGS_SPL, earliest_time="-10m", wait_s=30)
    if r.get("error"):
        raise RuntimeError(str(r["error"])[:200])
    return [finding_signal(x) for x in r.get("results") or []]


def _link(a: list[str], b: list[str], graph: topology.Graph) -> dict | None:
    if not a or not b:
        return {"rule": "unscoped", "path": [], "hops": None}   # no service named: joins, as in trigger.poll_once
    p = graph.related(a, b)
    return {"rule": "same_service" if len(p) == 1 else "call_path", "path": p, "hops": len(p) - 1} if p else None


def _since_epoch(sig: dict, fallback: float) -> float:
    try:
        return float(calendar.timegm(time.strptime(sig.get("since") or "", "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return fallback


class Grouper:
    """Holds the groups waiting to start. One thread calls tick(); `waiting()` may be read from another."""

    def __init__(self, start):
        self.start = start        # start(signals) -> case id
        self.known: set[str] = set()
        self.seeded = False
        self.groups: list[dict] = []
        self.late: list[tuple[str, dict]] = []
        self.woken: dict[str, float] = {}
        self.cleared: dict[str, float] = {}   # key → when a group of it was dropped as cleared

    def waiting(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        return [{"signals": len(g["signals"]), "starts_in_s": max(0, round(g["opened"] + WAIT_S - now)), "held": g["held"]} for g in list(self.groups)]

    def tick(self, alerts: list[dict], findings: list[dict], graph: topology.Graph, now: float | None = None) -> list[str]:
        """One pass over everything firing now. Returns the ids of the cases started."""
        now = now or time.time()
        if not self.seeded:
            self.known |= {a["incident_id"] for a in alerts}
            self.seeded = True
        all_cases = cs.list_cases()
        covered = {i.get("incident_id") for c in all_cases for i in c.get("incidents", [])}
        for s in sorted((x for x in alerts + findings if x["incident_id"] not in self.known),
                        key=lambda x: (0 if x.get("since") else 1, x.get("since") or "")):
            self.known.add(s["incident_id"])
            if s["incident_id"] not in covered:
                self._route(dict(s, services=ties.incident_services(s), first_seen=now), all_cases, graph, now)
        self._add_late(graph)
        return self._start_due({a["incident_id"] for a in alerts}, covered, now)

    def _route(self, sig: dict, all_cases: list[dict], graph: topology.Graph, now: float) -> None:
        for c in all_cases:
            if (c["state"] in cs.ACTIVE_STATES and c.get("source") != "eval" and not c.get("merged_into") and c.get("environment") == ENV
                    and now - ties.opened_epoch(c) <= ties.TIE_LOOKBACK_S and _link(sig["services"], ties.case_services(c), graph)):
                self.late.append((c["id"], sig))
                return
        for g in self.groups:
            link = _link(sig["services"], [s for x in g["signals"] for s in x["services"]], graph)
            if link:
                sig["joined"] = dict(link, gap_s=round(now - g["opened"]), graph=graph.source)
                g["signals"].append(sig)
                emit("sre.group.signal_joined", detector=sig["detector"], incident_id=sig["incident_id"], rule=link["rule"], path=link["path"])
                return
        if sig["services"] and set(sig["services"]) <= EVIDENCE_ONLY:
            emit("sre.trigger.suppressed", reason="evidence_only", detector=sig["detector"], incident_id=sig["incident_id"])
            return
        key = sig.get("key") or sig["incident_id"]
        if now - self.woken.get(key, 0) < COOLDOWN_S:
            emit("sre.trigger.suppressed", reason="cooldown", detector=sig["detector"], incident_id=sig["incident_id"])
            return
        self.groups.append({"opened": now, "signals": [sig], "held": False})
        emit("sre.group.opened", detector=sig["detector"], incident_id=sig["incident_id"], wait_s=WAIT_S)

    def _add_late(self, graph: topology.Graph) -> None:
        keep = []
        for cid, sig in self.late:
            code, out = ties.attach(cid, sig, graph, by="automatic grouping")
            if code == 409 and cs.load(cid)["state"] != "closed":   # still being worked on: add it when the run has concluded
                keep.append((cid, sig))
            elif code != 200:
                emit("sre.trigger.suppressed", reason="case_gone", detector=sig["detector"], incident_id=sig["incident_id"], error=out.get("error"))
        self.late = keep

    def _start_due(self, firing: set[str], covered: set, now: float) -> list[str]:
        started, keep = [], []
        for g in self.groups:
            if now - g["opened"] < WAIT_S:
                keep.append(g)
                continue
            sigs = [s for s in g["signals"] if s["incident_id"] not in covered]   # an operator may have pressed Triage meanwhile
            alive = [s for s in sigs if s["incident_id"] in firing or (s.get("kind") == "model" and now - s["first_seen"] <= FINDING_TTL_S)
                     or now - self.cleared.get(s.get("key") or s["incident_id"], -FLAP_S) <= FLAP_S]
            if not alive:
                emit("sre.trigger.suppressed", reason="cleared_during_wait", detectors=[s["detector"] for s in g["signals"]])
                self.cleared.update({s.get("key") or s["incident_id"]: now for s in g["signals"]})
                continue
            # no slot: stays waiting while it still fires; a case left open from long ago does not take a slot
            if sum(now - ties.opened_epoch(c) <= ties.TIE_LOOKBACK_S for c in cs.list_cases(open_only=True)) >= MAX_OPEN_CASES:
                if not g["held"]:
                    emit("sre.trigger.suppressed", reason="max_open_cases", detectors=[s["detector"] for s in sigs])
                g["held"] = True
                keep.append(g)
                continue
            sigs.sort(key=lambda s: (_since_epoch(s, s["first_seen"]), s["first_seen"]))
            sigs[0].pop("joined", None)
            cid = self.start(sigs)
            for s in sigs:
                self.woken[s.get("key") or s["incident_id"]] = now
            started.append(cid)
        self.groups = keep
        self.woken = {k: v for k, v in self.woken.items() if now - v < COOLDOWN_S}
        self.cleared = {k: v for k, v in self.cleared.items() if now - v <= FLAP_S}
        return started
