import json
import os

import pytest

os.environ["SRE_AGENT_QUIET"] = "1"

from sre_agent import audit  # noqa: E402
from sre_agent.ledger import LEDGER_TOOLS, Ledger  # noqa: E402

METRIC, LOG = "payments_by_outcome_acquirer", "spl_events_by_service"   # bundle sections: metric and log signals
CASE = {"id": "C-ledger", "incidents": []}


@pytest.fixture
def events():
    got: list[dict] = []
    audit.subscribe(got.append)
    yield got
    audit._SUBSCRIBERS.remove(got.append)


def _validated(lg: Ledger, node: str, ids=(METRIC, LOG), last_seen_min: float = 0.0, independent: bool = False) -> dict:
    return lg.verdict(node, "validated", "573 timeouts against a 2.5 s limit", list(ids), "acquirer-sim/acq-kbank", last_seen_min, independent)


def test_tool_schemas_are_strict_ready():
    names = [t["name"] for t in LEDGER_TOOLS]
    assert names == ["hypothesis_open", "hypothesis_verdict"]
    for t in LEDGER_TOOLS:
        s = t["input_schema"]
        assert s["additionalProperties"] is False and sorted(s["required"]) == sorted(s["properties"])


def test_open_assigns_ids_and_emits_reset_then_branch(events):
    lg = Ledger(CASE, [])
    a = lg.open("", "payment-router has a fault of its own", "errors by tag")
    b = lg.open("", "a dependency it calls is failing", "dependencies")
    child = lg.open("H2", "acq-kbank times out for one card range", "timeouts by acquirer and BIN")
    assert (a["id"], b["id"], child["id"]) == ("H1", "H2", "H2.1")
    assert lg.open("H2", "acq-kbank times out for one card range", "again")["id"] == "H2.1"   # same statement: same node
    assert [e["event"] for e in events] == ["sre.tree.reset", "sre.tree.branch", "sre.tree.branch", "sre.tree.branch"]
    last = events[-1]
    assert (last["case_id"], last["node"], last["parent"], last["depth"]) == ("C-ledger", "H2.1", "H2", 2)
    assert last["statement"].startswith("acq-kbank") and last["test_plan"] == "timeouts by acquirer and BIN"


def test_validated_needs_a_metric_or_trace_signal_and_a_log_signal(events):
    lg = Ledger(CASE, [])
    lg.open("", "a dependency is failing", "")
    weak = _validated(lg, "H1", ids=[METRIC])
    assert weak["status"] == "inconclusive" and "log signal" in weak["checks"][-1] and weak["hint"]
    ok = _validated(lg, "H1")
    assert ok["status"] == "validated" and ok["checks"][-1].startswith("corroborated") and "hint" not in ok
    v = [e for e in events if e["event"] == "sre.tree.verdict"]
    assert [e["status"] for e in v] == ["inconclusive", "validated"] and v[-1]["model_verdict"] == "validated"   # a second verdict replaces the first
    assert v[-1]["evidence"] == [{"signal": "metric/trace", "finding": "", "evidence_id": METRIC}, {"signal": "log", "finding": "", "evidence_id": LOG}]
    assert lg.tree()[0]["status"] == "validated" and len(lg.tree()) == 1


def test_signal_kind_comes_from_the_tool_log_for_tool_use_ids():
    log = [{"id": "tu_spl", "tool": "spl"}, {"id": "tu_trace", "tool": "trace"}]
    lg = Ledger(CASE, lambda: log)
    lg.open("", "h", "")
    assert _validated(lg, "H1", ids=["tu_spl", "tu_trace"])["status"] == "validated"
    assert _validated(lg, "H1", ids=["tu_spl", "made-up-id"])["status"] == "inconclusive"


def test_stale_signal_is_leftover_and_unknown_freshness_passes_with_a_note():
    lg = Ledger(CASE, [])
    lg.open("", "wallet-sim restarts", "")
    lg.open("", "acquirer timeouts", "")
    stale = _validated(lg, "H1", last_seen_min=20)
    assert stale["status"] == "invalidated" and "leftover" in stale["checks"][-1] and "20" in stale["checks"][-1]
    unknown = _validated(lg, "H2", last_seen_min=-1)
    assert unknown["status"] == "validated" and "freshness not stated" in unknown["checks"][-1]
    assert _validated(lg, "H2", last_seen_min=4.9)["status"] == "validated"


def test_model_verdicts_other_than_validated_are_kept_as_given():
    lg = Ledger(CASE, [])
    lg.open("", "h", "")
    out = lg.verdict("H1", "invalidated", "0 errors of its own", [METRIC], "none", -1, False)
    assert out["status"] == "invalidated" and out["checks"] == []
    assert lg.tree()[0]["finding"] == "0 errors of its own" and lg.tree()[0]["independent"] is False


def test_limits_and_bad_references_return_error_text_not_exceptions(monkeypatch):
    lg = Ledger(CASE, [])
    assert "error" in lg.open("H9", "child of nothing", "")
    assert "error" in lg.verdict("H9", "validated", "f", [METRIC, LOG], "c", 0, False)
    lg.open("", "top", "")
    assert "error" in lg.verdict("H1", "certain", "f", [], "c", 0, False)
    lg.verdict("H1", "invalidated", "no", [METRIC], "none", -1, False)
    assert "error" in lg.open("H1", "narrowing a ruled-out hypothesis", "")
    lg.open("", "second", "")
    lg.open("H2", "level 2", "")
    lg.open("H2.1", "level 3", "")
    assert "error" in lg.open("H2.1.1", "level 4 is too deep", "")
    import sre_agent.ledger as mod
    monkeypatch.setattr(mod, "MAX_NODES", 4)
    assert "full" in lg.open("", "one too many", "")["error"]
    assert json.loads(lg.handle("hypothesis_open", {"parent": "", "statement": "x", "test_plan": ""}))["error"]
    assert json.loads(lg.handle("hypothesis_verdict", {"id": "H2"}))["error"]   # missing arguments
    assert json.loads(lg.handle("something_else", {}))["error"]


def test_handle_returns_json_for_the_model():
    lg = Ledger(CASE, [])
    opened = json.loads(lg.handle("hypothesis_open", {"parent": "", "statement": "a dependency is failing", "test_plan": "t"}))
    assert opened == {"id": "H1", "status": "open"}
    v = json.loads(lg.handle("hypothesis_verdict", {"id": "H1", "verdict": "validated", "finding": "f", "evidence_ids": [METRIC, LOG],
                                                    "component": "acquirer-sim", "last_seen_min": 0, "independent": False}))
    assert v["id"] == "H1" and v["status"] == "validated"


def test_gap_names_what_is_missing():
    action = {"proposed_action": {"type": "chaos.flag_off:acquirer_kbank_timeout"}}
    lg = Ledger(CASE, [])
    assert "no hypotheses" in lg.gap(action)
    lg.open("", "own fault", "")
    lg.open("", "dependency", "")
    assert "H1" in lg.gap(action) and "no verdict" in lg.gap(action)
    lg.verdict("H1", "invalidated", "f", [METRIC], "none", -1, False)
    lg.verdict("H2", "inconclusive", "f", [METRIC], "none", -1, False)
    assert "not backed by a validated hypothesis" in lg.gap(action)
    _validated(lg, "H2")
    assert "one level down" in lg.gap(action)
    assert lg.gap({"proposed_action": {"type": "no_action"}}) == ""          # nothing to narrow when no action is proposed
    lg.open("H2", "acq-kbank, one card range", "")
    assert "H2.1" in lg.gap(action)
    lg.verdict("H2.1", "inconclusive", "not measurable", [METRIC], "none", -1, False)
    assert lg.gap(action) == ""                                               # a tested sub-hypothesis is enough, validated or not


def test_close_marks_open_nodes_not_tested(events):
    lg = Ledger(CASE, [])
    lg.open("", "tested", "")
    lg.open("", "never tested", "")
    _validated(lg, "H1")
    lg.close()
    assert [n["status"] for n in lg.tree()] == ["validated", "not tested"]
    assert events[-1]["event"] == "sre.tree.verdict" and events[-1]["node"] == "H2" and events[-1]["status"] == "not tested"
    for key in ("id", "parent", "depth", "statement", "status", "model_verdict", "checks", "finding", "component", "last_seen_min",
                "independent", "evidence", "seconds"):
        assert key in lg.tree()[0]


# --------------------------------------------------------------------------- review findings, 27 Nov 2026
def _verdict_args(**over):
    return {"id": "H1", "verdict": "validated", "finding": "f", "evidence_ids": [METRIC, LOG], "component": "c", "last_seen_min": 0, "independent": False, **over}


def test_wrong_typed_arguments_never_raise_and_never_store_nan():
    lg = Ledger(CASE, [])
    lg.open("", "h", "")
    for bad in ("inf", "Infinity", 1e999, float("nan"), "nan", "-inf", None, "unknown"):
        out = json.loads(lg.handle("hypothesis_verdict", _verdict_args(last_seen_min=bad)))
        assert out.get("status") == "validated" and "freshness not stated" in out["checks"][-1], (bad, out)   # not a number: unknown
        json.dumps(lg.tree(), allow_nan=False)                                    # the audit transport refuses NaN and Infinity
    out = json.loads(lg.handle("hypothesis_verdict", _verdict_args(evidence_ids=json.dumps([METRIC, LOG]), independent="false")))
    assert out["status"] == "validated" and [e["evidence_id"] for e in lg.tree()[0]["evidence"]] == [METRIC, LOG]   # not single characters
    assert lg.tree()[0]["independent"] is False                                   # the string "false" is not True
    json.loads(lg.handle("hypothesis_verdict", _verdict_args(evidence_ids=f"{METRIC}, {LOG}", independent="true")))
    assert lg.tree()[0]["status"] == "validated" and lg.tree()[0]["independent"] is True
    assert json.loads(lg.handle("hypothesis_open", {"parent": None, "statement": "top", "test_plan": None}))["id"] == "H2"
    assert "error" in json.loads(lg.handle("hypothesis_verdict", _verdict_args(evidence_ids=7)))


def test_tree_never_leaks_internal_keys():
    lg = Ledger(CASE, [])
    lg.open("", "h", "")
    assert all(not k.startswith("_") for n in lg.tree() for k in n)


def test_only_real_evidence_counts_when_the_bundle_sections_are_known():
    log = [{"id": "tu_ok", "tool": "spl", "ok": True}, {"id": "tu_failed", "tool": "spl", "ok": False}, {"id": "tu_m", "tool": "metric_series", "ok": True},
           {"id": "tu_t", "tool": "spl_template", "args": {"name": "timeouts_by_acquirer_bin"}, "ok": True}]
    lg = Ledger(CASE, log, sections={"services_summary", "spl_first_seen"})
    lg.open("", "h", "")
    assert _validated(lg, "H1", ids=["splendid", "trace_of_nothing"])["status"] == "inconclusive"            # look-alike names are not evidence
    assert _validated(lg, "H1", ids=["tu_failed", "tu_m"])["status"] == "inconclusive"                        # a failed call is not evidence
    assert _validated(lg, "H1", ids=["spl_events_by_service", "services_summary"])["status"] == "inconclusive"  # a section this bundle does not have
    assert _validated(lg, "H1", ids=["services_summary", "spl_first_seen"])["status"] == "validated"          # real bundle sections
    assert _validated(lg, "H1", ids=["metric_series", "timeouts_by_acquirer_bin"])["status"] == "validated"   # a tool or template name means its last good call
    assert _validated(lg, "H1", ids=["tu_ok", "apm_errors_by_tag"])["status"] == "inconclusive"               # that tool was never called


def test_gap_needs_a_tested_child_under_the_validated_hypothesis_and_survives_close():
    action = {"proposed_action": {"type": "chaos.flag_off:acquirer_kbank_timeout"}}
    lg = Ledger(CASE, [])
    lg.open("", "a", "")
    lg.open("", "b", "")
    _validated(lg, "H1")
    lg.verdict("H2", "inconclusive", "f", [METRIC], "none", -1, False)
    lg.open("H2", "narrowing the wrong one", "")
    lg.verdict("H2.1", "invalidated", "f", [METRIC], "none", -1, False)
    assert "one level down" in lg.gap(action)                      # nothing was narrowed under the validated H1
    lg.open("H1", "narrower", "")
    lg.close()
    assert lg.tree()[-1]["status"] == "not tested"
    assert "H1.1" in lg.gap(action) and "no verdict" in lg.gap(action)   # still reported after the run has closed the ledger
    assert "no verdict" in lg.gap({"proposed_action": {"type": "no_action"}})
