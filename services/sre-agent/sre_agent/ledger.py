"""Hypothesis ledger for the single-loop investigator: the model records each hypothesis and its verdict through two
tools while it works, so the tree grows live (the same `sre.tree.*` events the tree method emits) and can go several
levels deep without sub-agents.

Code, not the model, decides whether a "validated" verdict stands, and tells the model the result at once so it can
fix the evidence in the same run:
  * corroboration: the evidence ids must include a metric-or-trace signal AND a log signal (the evidence_gap rule);
  * freshness: a deciding signal last seen more than STALE_MIN minutes ago is leftover from an earlier event. Minutes
    ago, not clock times, so a replayed fixture is judged like a live run; -1 (unknown) passes with a note.
Ledger calls do not spend the tool budget (toolset.ToolSet routes them here).
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Callable

from .audit import emit
from .evidence import signal_of

MAX_NODES = int(os.getenv("SRE_AGENT_LEDGER_NODES", "12"))
MAX_DEPTH = 3
STALE_MIN = float(os.getenv("SRE_AGENT_STALE_MIN", "5"))
VERDICTS = ("validated", "invalidated", "inconclusive")
NO_ACTION = ("no_action", "inconclusive")
SIGNALS = (("metric_trace", "a metric or trace signal"), ("log", "a log signal"))
SIGNAL_LABEL = {"metric_trace": "metric/trace", "log": "log", "": "unknown"}
NODE_KEYS = ("id", "parent", "depth", "statement", "test_plan", "status", "model_verdict", "checks", "finding", "component",
             "last_seen_min", "independent", "evidence", "seconds")

LEDGER_TOOLS = [
    {"name": "hypothesis_open",
     "description": "Record a hypothesis in the ledger before testing it. Returns its id (H1, H2 ... at the top; H2.1, H2.2 under H2). "
                    "Open the competing top-level hypotheses together in one turn. Under a validated hypothesis, open 1-3 narrower ones that "
                    "would explain WHY (which partner, host, card range, version, setting or change). Does not use the tool budget.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["parent", "statement", "test_plan"], "properties": {
         "parent": {"type": "string", "description": "id of the hypothesis this one narrows, e.g. H2; empty string for a top-level hypothesis"},
         "statement": {"type": "string", "description": "one specific, testable sentence"},
         "test_plan": {"type": "string", "description": "the one or two most discriminating checks (tool and argument)"}}}},
    {"name": "hypothesis_verdict",
     "description": "Record the verdict on a hypothesis after testing it. Code checks a validated verdict (it needs a metric-or-trace signal AND "
                    "a log signal among evidence_ids, and a signal that is still active) and returns the status that stands; when it is "
                    "downgraded, add the missing evidence and record the verdict again. Does not use the tool budget.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "required": ["id", "verdict", "finding", "evidence_ids", "component", "last_seen_min", "independent"], "properties": {
         "id": {"type": "string", "description": "the id returned by hypothesis_open"},
         "verdict": {"type": "string", "enum": list(VERDICTS)},
         "finding": {"type": "string", "description": "one or two sentences with the deciding numbers"},
         "evidence_ids": {"type": "array", "items": {"type": "string"}, "description": "tool_use ids from this investigation or evidence bundle section names"},
         "component": {"type": "string", "description": "the most specific component implicated (service plus partner, host, card range, version, setting), or 'none'"},
         "last_seen_min": {"type": "number", "description": "minutes ago the deciding signal was last seen (minutes_since_last in first_seen; 0 when it is in the latest data point); -1 when unknown or not applicable"},
         "independent": {"type": "boolean", "description": "true only for a separate fault that is not the cause of this alert"}}}},
]
LEDGER_TOOL_NAMES = tuple(t["name"] for t in LEDGER_TOOLS)


def _minutes(value) -> float:
    """Minutes ago as a finite number; anything else (text, null, NaN, infinity) means unknown (-1). The ledger tools
    are not strict, so the model can send any type, and NaN or Infinity would break the audit record."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return -1.0
    return v if math.isfinite(v) else -1.0


def _id_list(value) -> list[str]:
    """Evidence ids as a list: a JSON-encoded or comma-separated string is read as ids, never as characters."""
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text) if text.startswith("[") else None
        except ValueError:
            parsed = None
        value = parsed if isinstance(parsed, list) else [x for x in text.strip("[]").replace('"', "").split(",")]
    if not isinstance(value, (list, tuple)):
        raise TypeError("evidence_ids must be a list of ids")
    return [str(i).strip() for i in value if str(i).strip()]


def _flag(value) -> bool:
    return value.strip().lower() in ("true", "yes", "1") if isinstance(value, str) else bool(value)


def _text(value) -> str:
    return "" if value is None else str(value)


class Ledger:
    def __init__(self, case: dict, tool_log: list[dict] | Callable[[], list[dict]], sections: set[str] | None = None):
        self.case_id = case.get("id")
        self._tool_log = tool_log if callable(tool_log) else (lambda: tool_log)
        self._sections = set(sections) if sections else None   # bundle section names; None = not known (prefix rule only)
        self.nodes: list[dict] = []
        emit("sre.tree.reset", case_id=self.case_id)

    # -- tools ----------------------------------------------------------------------------------------------------
    def handle(self, name: str, args: dict) -> str:
        """The text the model gets back for a ledger tool call. Never raises: a bad call is an error text."""
        try:
            if name == "hypothesis_open":
                out = self.open(_text(args.get("parent")), _text(args["statement"]), _text(args.get("test_plan")))
            elif name == "hypothesis_verdict":
                out = self.verdict(_text(args["id"]), _text(args["verdict"]), _text(args["finding"]), _id_list(args["evidence_ids"]),
                                   _text(args.get("component")), _minutes(args.get("last_seen_min", -1)), _flag(args.get("independent", False)))
            else:
                out = {"error": f"unknown ledger tool {name}"}
        except Exception as e:  # noqa: BLE001 — model-supplied arguments of any type must come back as text, never stop the case
            out = {"error": f"bad arguments for {name}: {type(e).__name__}: {e}"[:200]}
        return json.dumps(out)

    def _kind(self, evidence_id: str, log: list[dict]) -> str:
        """'log', 'metric_trace' or '' for one evidence id. With the bundle sections known, only real evidence counts:
        a tool call of this case that succeeded, a section this bundle has, or a tool or log-template name, read as its
        last successful call (the model often cites the name). A look-alike name or a failed call is not evidence."""
        if self._sections is None:
            return signal_of(evidence_id, log)
        for entry in log:
            if entry.get("id") == evidence_id:
                return signal_of(evidence_id, log) if entry.get("ok", True) else ""
        if evidence_id in self._sections:
            return signal_of(evidence_id, None)
        for entry in reversed(log):
            if entry.get("ok", True) and evidence_id in (entry.get("tool"), (entry.get("args") or {}).get("name")):
                return signal_of(str(entry.get("id")), log)
        return ""

    def open(self, parent: str, statement: str, test_plan: str = "") -> dict:
        parent = (parent or "").strip()
        p = self._get(parent) if parent else None
        if parent and p is None:
            return {"error": f"no hypothesis {parent} in the ledger; use an id returned by hypothesis_open, or an empty parent for a top-level hypothesis"}
        if p and p["status"] == "invalidated":
            return {"error": f"{parent} is ruled out; narrow a hypothesis that is validated or still open"}
        depth = p["depth"] + 1 if p else 1
        if depth > MAX_DEPTH:
            return {"error": f"the tree is {MAX_DEPTH} levels deep at most; record the verdict on {parent} instead"}
        statement = " ".join(str(statement).split())[:400]
        siblings = [n for n in self.nodes if n["parent"] == (parent or None)]
        for n in siblings:
            if n["statement"] == statement:
                return {"id": n["id"], "status": n["status"]}
        if len(self.nodes) >= MAX_NODES:
            return {"error": f"the ledger is full ({MAX_NODES} hypotheses): record the open verdicts and conclude"}
        nid = f"{parent}.{len(siblings) + 1}" if parent else f"H{len(siblings) + 1}"
        n = {"id": nid, "parent": parent or None, "depth": depth, "statement": statement, "test_plan": str(test_plan)[:400], "status": "open",
             "model_verdict": None, "checks": [], "finding": "", "component": "", "last_seen_min": None, "independent": False, "evidence": [],
             "seconds": 0, "_t0": time.time()}
        self.nodes.append(n)
        emit("sre.tree.branch", case_id=self.case_id, node=nid, parent=n["parent"], depth=depth, statement=statement, test_plan=n["test_plan"])
        return {"id": nid, "status": "open"}

    def verdict(self, node_id: str, verdict: str, finding: str, evidence_ids: list, component: str = "", last_seen_min: float = -1,
                independent: bool = False) -> dict:
        n = self._get((node_id or "").strip())
        if n is None:
            return {"error": f"no hypothesis {node_id} in the ledger; open it with hypothesis_open first"}
        if verdict not in VERDICTS:
            return {"error": f"verdict must be one of {', '.join(VERDICTS)}"}
        ids = [str(i)[:80] for i in evidence_ids if str(i).strip()][:8]
        log = self._tool_log()
        kinds = [self._kind(i, log) for i in ids]
        last_seen_min = _minutes(last_seen_min)
        status, checks, hint = self._check(verdict, set(kinds), last_seen_min)
        n.update(model_verdict=verdict, status=status, checks=checks, finding=str(finding)[:600], component=str(component)[:120],
                 last_seen_min=last_seen_min, independent=bool(independent), seconds=round(time.time() - n["_t0"], 1),
                 evidence=[{"signal": SIGNAL_LABEL[k], "finding": "", "evidence_id": i} for i, k in zip(ids, kinds)])
        self._emit_verdict(n)
        out = {"id": n["id"], "status": status, "checks": checks}
        if hint:
            out["hint"] = hint
        return out

    @staticmethod
    def _check(verdict: str, kinds: set, last_seen_min: float) -> tuple[str, list[str], str]:
        if verdict != "validated":
            return verdict, [], ""
        missing = [label for k, label in SIGNALS if k not in kinds]
        if missing:
            what = " and ".join(missing)
            return "inconclusive", [f"not corroborated by {what}"], (
                f"Cite {what} in evidence_ids (a tool_use id from this investigation, or a bundle section name such as spl_first_seen or "
                "services_summary), testing further if needed, then record the verdict again.")
        if last_seen_min > STALE_MIN:
            return "invalidated", [f"stale: deciding signal last seen {round(last_seen_min)} min ago (leftover from an earlier event)"], (
                "This is not the cause of the current alert. Mention it as a separate, resolved finding and test the other hypotheses.")
        if last_seen_min < 0:
            return "validated", ["corroborated (metric/trace + log); freshness not stated"], ""
        return "validated", ["corroborated (metric/trace + log) and still active"], ""

    # -- reading --------------------------------------------------------------------------------------------------
    def _get(self, node_id: str) -> dict | None:
        return next((n for n in self.nodes if n["id"] == node_id), None)

    def _emit_verdict(self, n: dict) -> None:
        emit("sre.tree.verdict", case_id=self.case_id, node=n["id"], parent=n["parent"], depth=n["depth"], statement=n["statement"],
             model_verdict=n["model_verdict"], status=n["status"], checks=n["checks"], component=n["component"],
             last_seen_min=n["last_seen_min"], independent=n["independent"], finding=n["finding"], evidence=n["evidence"], seconds=n["seconds"])

    def tree(self) -> list[dict]:
        return [{k: n[k] for k in NODE_KEYS} for n in self.nodes]

    def gap(self, inv: dict) -> str:
        """'' when the ledger backs the answer, else what is missing (one corrective round is asked for it)."""
        if not self.nodes:
            return "no hypotheses were recorded in the ledger"
        untested = [n["id"] for n in self.nodes if n["status"] in ("open", "not tested")]   # also after close()
        if untested:
            return f"hypotheses {', '.join(untested)} have no verdict"
        if ((inv or {}).get("proposed_action") or {}).get("type", "inconclusive") in NO_ACTION:
            return ""
        validated = [n for n in self.nodes if n["status"] == "validated"]
        if not [n for n in validated if not n["independent"]]:
            return "the proposed action is not backed by a validated hypothesis in the ledger"
        narrowed = any(n["depth"] >= 2 and n["status"] in VERDICTS and (self._get(n["parent"]) or {}).get("status") == "validated"
                       for n in self.nodes)
        if not narrowed:
            return ("no narrower hypothesis was tested one level down from the validated one "
                    "(which partner, host, card range, version, setting or change explains it)")
        return ""

    def close(self) -> None:
        """End of the run: a hypothesis that never got a verdict is shown as not tested."""
        for n in self.nodes:
            if n["status"] == "open":
                n["status"] = "not tested"
                n["seconds"] = round(time.time() - n["_t0"], 1)
                self._emit_verdict(n)


def gap_message(gap: str) -> str:
    return (f"Check by code: {gap}. Bring the ledger up to date with hypothesis_open and hypothesis_verdict (test first where a verdict "
            "needs evidence), then return the complete Investigation JSON object again.")
