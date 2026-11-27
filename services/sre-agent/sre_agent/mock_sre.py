"""Labelled MOCK investigator: a rules-based reader of the evidence bundle that lets the whole pipeline run without a
model key. It is NOT an AI and every record it produces says `provider=mock (scripted)`. It maps evidence event
names to failure modes with the same knowledge an on-call engineer would apply; it never reads acts.py."""

from __future__ import annotations

import re
import time

from . import catalogue
from .audit import emit
from .investigator import Result, RunStats
from .ledger import Ledger
from .tools import preview_envelope

RULES = [  # (regex over the bundle text, service, failure_mode, action enum, statement)
    (r"acquirer\.timeout|route\.failover|acquirer\.host_unresponsive", "acquirer-sim", "dependency_degraded", "chaos.flag_off:acquirer_kbank_timeout",
     "Acquirer acq-kbank is timing out for a card range; payment-router fails over to a backup acquirer with lower approval"),
    (r"risk\.inference_slow|risk\.canary_inference|wallet_geo_risk_v3", "risk-engine", "config_change", "chaos.flag_off:risk_model_drift",
     "A risk model v3 canary is slow (CPU-bound) and over-declines wallet payments"),
    (r"copilot\.tool_loop_suspected|copilot\.max_iterations", "merchant-copilot", "application_bug", "chaos.flag_off:copilot_tool_loop",
     "The merchant copilot repeats the same tool call until the iteration cap (token burn, latency)"),
    (r"kya\.registry_unavailable|mandate_kya_unavailable", "wallet-sim", "dependency_degraded", "chaos.flag_off:kya_registry_down",
     "The KYA registry behind wallet-sim is unavailable; checkout-api fails closed on every agent payment"),
    (r"db\.pool\.wait|db\.pool\.reconfigured|ledger\.write_slow", "ledger", "config_change", "chaos.flag_off:ledger_db_slow",
     "The ledger connection pool was shrunk; writes queue on the pool"),
    (r"webhook\.dead_lettered|merchant\.webhook_error", "webhook-dispatcher", "dependency_degraded", "chaos.flag_off:webhook_merchant_flaky",
     "A merchant webhook endpoint is failing; deliveries dead-letter"),
    (r"memory\.pressure|memory_limit_near|OOMKilled", "ledger", "resource_exhaustion", "chaos.flag_off:ledger_memory_leak",
     "The ledger leaks memory until its container limit and restarts"),
    (r"service\.crashed|SchemaMigrationError|CrashLoopBackOff", "wallet-sim", "bad_release", "chaos.flag_off:wallet_crash_loop",
     "wallet-sim 1.7.0 crashes at start (missing schema migration)"),
    (r"mandate\.blocked|bot_like_pattern|catalog\.untrusted_listing_served", "checkout-api", "abuse_or_governance", "no_action",
     "Agent mandates are being blocked and unverified agents declined: governance working as designed"),
]


def investigate_mock(case: dict, bundle_text: str, toolset) -> Result:
    t0 = time.time()
    ledger = Ledger(case, lambda: toolset.log)   # the same live tree events as the real investigator, from scripted rules
    hyps, chosen = [], None
    for rx, svc, mode, action, statement in RULES:
        hits = len(re.findall(rx, bundle_text))
        if hits:
            hyps.append({"statement": statement, "status": "validated", "evidence_ids": ["spl_events_by_service", "services_summary"], "independent": True, "_hits": hits})
            if chosen is None or hits > chosen[5]:
                chosen = (svc, mode, action, statement, hyps[-1], hits)
    matched = [f"{h['statement']}" for h in hyps]
    for h in hyps:
        h["_node"] = ledger.open("", h["statement"], "scripted: count the failure signature in the evidence bundle").get("id")   # None when the ledger is full
    if not hyps:
        none_id = ledger.open("", "No known failure signature in the evidence bundle", "scripted: nothing to test")["id"]
    emit("sre.rca.step", case_id=case.get("id"), step=1, model="scripted mock (no AI)", stop_reason="tool_use" if chosen else "end_turn",
         reasoning=("Matched failure signatures in the evidence bundle: " + "; ".join(matched)) if matched else "No known failure signature in the evidence bundle.",
         text="", tool_calls=[{"id": "mock-1", "tool": "spl_template", "args": {"why": "confirm the matched failure signature in the per-service event counts", "name": "events_by_service", "window": "-15m"}}] if chosen else [])
    # one confirmatory tool call so the transcript is realistic
    from .cancel import check
    check(case.get("id"), "mock investigation")
    if chosen:
        out = toolset.dispatch("mock-1", "spl_template", {"why": "confirm the matched failure signature in the per-service event counts", "name": "events_by_service", "window": "-15m"})
        pv = preview_envelope(out)
        emit("sre.rca.tool", case_id=case.get("id"), step=1, id="mock-1", tool="spl_template", args={"why": "confirm the matched failure signature in the per-service event counts", "name": "events_by_service", "window": "-15m"},
             ok=pv["summary"] != "error", summary=pv["summary"], preview=pv["preview"], chars=len(out))
    for h in hyps:
        node = h.pop("_node")
        if node:
            ledger.verdict(node, "validated", f"[scripted mock] signature matched {h['_hits']} time(s) in the evidence bundle", h["evidence_ids"],
                           chosen[0] if chosen and h is chosen[4] else "none", -1, not (chosen and h is chosen[4]))
        h.pop("_hits", None)
    if not hyps:
        ledger.verdict(none_id, "inconclusive", "[scripted mock] no rule matched", [], "none", -1, False)
    if not chosen:
        inv = {"root_cause_service": "none", "failure_mode": "unknown", "confidence": 0.2, "hypotheses": hyps,
               "proposed_action": {"type": "inconclusive", "rationale": "no known failure signature in the evidence"},
               "blast_radius": "none", "narrative": "[mock investigator] No known failure signature was found in the evidence bundle; a human should look at the services summary and recent config changes."}
    else:
        svc, mode, action, statement, _, hits = chosen
        inv = {"root_cause_service": svc, "failure_mode": mode, "confidence": min(0.95, 0.6 + 0.05 * hits), "hypotheses": hyps,
               "proposed_action": {"type": action, "rationale": f"[mock investigator] {statement}; the catalogue action reverts that fault"},
               "blast_radius": svc, "narrative": f"[mock investigator — scripted rules, not an AI] {statement}. Signature matched {hits} time(s) in the evidence bundle (events_by_service, services_summary). Alerting service and root-cause service may differ; see hypotheses."}
    action = inv["proposed_action"]["type"]
    known = catalogue.ACTIONS.get(action)
    first_step = (known.real_world if known else "No action: governance is working as designed" if action == "no_action"
                  else "A human should look at the services summary and recent changes")
    for k, v in (("summary", inv["narrative"][:300]), ("impact", "not measured (scripted mock)"), ("started_at", "unknown"),
                 ("cause_chain", [chosen[3]] if chosen else []), ("evidence", []), ("ruled_out", []),
                 ("title", "[scripted mock] " + (chosen[3] if chosen else "No known failure signature")[:90]),
                 ("mechanism", "[scripted mock, not an AI] " + (chosen[3] if chosen else "no failure signature matched, so no mechanism is claimed")),
                 ("next_steps", [first_step, "Verify: the alerting detector clears and the failure signature stops in the logs"])):
        inv.setdefault(k, v)
    from .branching import render_tree
    inv["tree"] = ledger.tree()
    inv["tree_text"] = render_tree(inv["tree"])
    stats = RunStats(requests=0, provider="mock (scripted)", model="rules", seconds=time.time() - t0, stop_reason="end_turn")
    return Result(inv, stats, [{"id": "mock-1", "tool": "spl_template", "args": {"name": "events_by_service"}}], "")
