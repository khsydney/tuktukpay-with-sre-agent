import json
import os
import time
from types import SimpleNamespace as NS

import pytest

os.environ["SRE_AGENT_QUIET"] = "1"
os.environ["MOCK_JEV"] = "1"

from sre_agent import catalogue, executor, investigator  # noqa: E402
from sre_agent.cost import estimate_cost  # noqa: E402
from sre_agent.toolset import ToolSet  # noqa: E402


class FakeSplunk:
    def __init__(self, counts=None):
        self.counts = list(counts or [0])
        self.calls = []

    def splunk_run_query(self, q, earliest_time="-15m", **_):
        self.calls.append((q, earliest_time))
        c = self.counts.pop(0) if len(self.counts) > 1 else self.counts[0]
        return {"query": q, "results": [{"count": str(c), "source": "payment-router", "event": "acquirer.timeout"}], "result_count": 1}


def _usage(i=1000, o=100, cr=0, cw=0):
    return NS(input_tokens=i, output_tokens=o, cache_read_input_tokens=cr, cache_creation_input_tokens=cw)


def _block_text(t):
    return NS(type="text", text=t)


def _block_tool(id_, name, inp):
    return NS(type="tool_use", id=id_, name=name, input=inp)


INV = {"root_cause_service": "acquirer-sim", "failure_mode": "dependency_degraded", "confidence": 1.7, "hypotheses": [],
       "proposed_action": {"type": "chaos.flag_off:acquirer_kbank_timeout", "rationale": "r"}, "blast_radius": "x", "narrative": "n",
       "summary": "s", "impact": "i", "started_at": "unknown", "cause_chain": ["c"], "ruled_out": [],
       "evidence": [{"signal": "metric", "finding": "f", "evidence_id": "payments_by_outcome_acquirer"},
                    {"signal": "log", "finding": "f", "evidence_id": "spl_events_by_service"}]}


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    class messages:  # noqa: N801
        pass

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def _client(responses):
    c = FakeClient(responses)
    c.messages = NS(create=c.create)
    return c


def test_investigator_tool_round_trip_and_cost(monkeypatch):
    monkeypatch.setattr(investigator, "LEDGER_ON", False)   # scripted for the plain loop (no ledger rounds)
    responses = [
        NS(content=[_block_tool("tu1", "spl_template", {"name": "events_by_service", "window": "-15m"})], stop_reason="tool_use", model="claude-opus-5-5", usage=_usage(5000, 200, 0, 4000)),
        NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="claude-opus-5-5", usage=_usage(500, 300, 4000, 0)),
    ]
    client = _client(responses)
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    ts = ToolSet(mcp=None, splunk=FakeSplunk([3]))
    r = investigator.investigate({"id": "C-t", "incidents": []}, "bundle", ts, provider="anthropic", model="claude-opus-5-5")
    assert r.stats.requests == 2 and r.investigation["proposed_action"]["type"].endswith("acquirer_kbank_timeout")
    assert r.investigation["confidence"] == 1.0                       # clamped
    second = client.requests[1]["messages"]
    assert second[1]["role"] == "assistant" and second[2]["content"][0]["type"] == "tool_result" and second[2]["content"][0]["tool_use_id"] == "tu1"
    first = client.requests[0]
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"} and first["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert sum(t["strict"] for t in first["tools"]) == len(first["tools"]) - 2 and "minimum" not in json.dumps(first["output_config"])
    assert r.stats.cache_read_tokens == 4000 and r.stats.cache_write_tokens == 4000
    assert r.stats.cost_usd == estimate_cost("claude-opus-5-5", 5500, 500, 4000, 4000) and r.stats.price_known


def test_investigator_refusal_and_unparsable_are_inconclusive(monkeypatch):
    for resp in (NS(content=[], stop_reason="refusal", model="m", usage=_usage()),
                 NS(content=[_block_text("sorry, no json")], stop_reason="end_turn", model="m", usage=_usage())):
        monkeypatch.setattr(investigator, "_client", lambda provider, resp=resp: _client([resp]))
        r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
        assert r.investigation["proposed_action"]["type"] == "inconclusive"


def test_investigator_budget_forbids_further_tool_calls(monkeypatch):
    monkeypatch.setattr(investigator, "MAX_INPUT_TOKENS", 100)
    responses = [
        NS(content=[_block_tool("tu1", "spl_template", {"name": "events_by_service", "window": "-15m"})], stop_reason="tool_use", model="m", usage=_usage(500, 10)),
        NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="m", usage=_usage(10, 10)),
    ]
    client = _client(responses)
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert r.stats.budget_hit == "tokens" and client.requests[1]["tools"] and client.requests[1]["tool_choice"] == {"type": "none"}
    assert "tool_choice" not in client.requests[0]
    assert any(b.get("type") == "text" and "Budget exhausted" in b["text"] for b in client.requests[1]["messages"][-1]["content"])


def test_cost_table_and_unknown_model():
    assert estimate_cost("claude-opus-5-5", 1_000_000, 0) == 4.0 and estimate_cost("claude-haiku-5-5", 0, 1_000_000) == 0.5
    from sre_agent.cost import price_row
    assert price_row("claude-opus-5-5")[0][0] == 4.0 and price_row("mystery")[1] is False


def test_verify_window_starts_after_fix_and_needs_two_passes(monkeypatch):
    monkeypatch.setattr(executor.time, "sleep", lambda s: None)
    v = catalogue.ACTIONS["chaos.flag_off:acquirer_kbank_timeout"].verification
    sp = FakeSplunk([5, 0, 0])
    ok, last, note = executor.verify(v, None, sp, t_fix=time.time() - 100, grace_s=30, window_s=30)
    assert ok is True and last == 0 and len(sp.calls) == 3
    assert all(str(int(time.time()) - 31) <= e <= str(int(time.time())) for _, e in sp.calls)   # epoch starts after the fix


def test_execute_refuses_when_state_changed(monkeypatch):
    monkeypatch.setattr(executor, "read_flags", lambda url=None: {"acquirer_kbank_timeout": {"enabled": False}})
    d = {"action": "chaos.flag_off:acquirer_kbank_timeout", "plan_hash": "h", "request_preview": {}}
    out = executor.execute(d, "C-x", "tester", None, None)
    assert not out.executed and any("state changed" in x for x in out.detail)


def test_should_escalate_rules():
    good = dict(INV, confidence=0.9, hypotheses=[{"statement": "s", "status": "validated", "evidence_ids": [], "independent": False}])
    assert investigator.should_escalate(good) == ""
    assert "inconclusive" in investigator.should_escalate(dict(good, proposed_action={"type": "inconclusive", "rationale": ""}))
    assert "confidence" in investigator.should_escalate(dict(good, confidence=0.5))
    assert "alternative" in investigator.should_escalate(dict(good, confidence=0.8, hypotheses=[{"statement": "s", "status": "inconclusive", "evidence_ids": [], "independent": False}]))
    assert investigator.DEFAULT_MODEL == "claude-sonnet-5-5"


def test_evidence_gap_uses_ids_not_labels():
    log_only = dict(INV, evidence=[{"signal": "metric", "finding": "mislabelled", "evidence_id": "spl_errors_by_type"}])
    assert "metric or trace" in investigator.evidence_gap(log_only)
    assert investigator.evidence_gap(INV) == ""
    tool_log = [{"id": "tu9", "tool": "metric_series"}]
    assert investigator.evidence_gap(dict(INV, evidence=[{"signal": "log", "finding": "f", "evidence_id": "spl_x"},
                                                         {"signal": "metric", "finding": "f", "evidence_id": "tu9"}]), tool_log) == ""
    assert investigator.evidence_gap(dict(INV, evidence=[], proposed_action={"type": "no_action", "rationale": ""})) == ""
    assert "log" in investigator.should_escalate(dict(INV, confidence=0.9, evidence_gap="root cause not supported by a log signal"))


def test_evidence_gap_gets_one_corrective_round(monkeypatch):
    monkeypatch.setattr(investigator, "LEDGER_ON", False)   # scripted for the plain loop (no ledger rounds)
    weak = dict(INV, evidence=[{"signal": "log", "finding": "f", "evidence_id": "spl_events_by_service"}])
    responses = [NS(content=[_block_text(json.dumps(weak))], stop_reason="end_turn", model="m", usage=_usage()),
                 NS(content=[_block_text(json.dumps(weak))], stop_reason="end_turn", model="m", usage=_usage())]
    client = _client(responses)
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert len(client.requests) == 2 and "Check by code" in client.requests[1]["messages"][-1]["content"]
    assert "metric or trace" in r.investigation["evidence_gap"]          # still weak after one round: kept, escalation reads it


def test_case_message_carries_real_world_actions(monkeypatch):
    monkeypatch.setattr(investigator, "LEDGER_ON", False)   # scripted for the plain loop (no ledger rounds)
    client = _client([NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="m", usage=_usage())])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    first = client.requests[0]["messages"][0]["content"]
    assert "route BIN 457173 / THB off acq-kbank" in first
    assert {"summary", "impact", "started_at", "cause_chain", "evidence", "ruled_out"} <= set(investigator.INVESTIGATION_SCHEMA["required"])


def test_markers_hidden_by_default(monkeypatch):
    from sre_agent import evidence
    assert evidence.MARKERS == "hide" and not evidence.markers_shown(True)
    ts = ToolSet(mcp=None, splunk=FakeSplunk())
    assert ts.marker_mode is False and "hidden" in ts.dispatch("t1", "spl_template", {"why": "w", "name": "config_changes", "window": "-15m"})
    monkeypatch.setattr(evidence, "MARKERS", "show")
    assert evidence.markers_shown(True) and not evidence.markers_shown(False)


def test_compact_trace_keeps_errors_and_slowest():
    from sre_agent.evidence import compact_trace
    spans = [{"traceID": "ab" * 16, "serviceName": f"s{i}", "operationName": "op", "duration": i * 1000, "tags": []} for i in range(30)]
    spans.append({"traceID": "ab" * 16, "serviceName": "payment-router", "operationName": "acq", "duration": 5,
                  "tags": [{"key": "error", "value": True}, {"key": "payment.acquirer", "value": "acq-kbank"}, {"key": "noise", "value": "x"}]})
    t = compact_trace({"spans": spans}, top=5)
    assert t["span_count"] == 31 and len(t["spans"]) == 5
    assert t["spans"][0]["service"] == "payment-router" and t["spans"][0]["payment.acquirer"] == "acq-kbank" and "noise" not in t["spans"][0]
    assert t["spans"][1]["duration_ms"] == 29.0


def test_affected_services_reads_operator_scope():
    from sre_agent.evidence import affected_services
    q = "Reported symptom (operator question): checkout slow [services in scope: ledger, risk-engine, checkout-api]"
    assert affected_services([q])[:3] == ["ledger", "risk-engine", "checkout-api"]
    assert affected_services(["TukTukPay [tuktukpay-demo] payment-router error rate above 5%"]) == ["payment-router"]
    assert affected_services(["x [services in scope: bad name!, risk-engine]"]) == ["risk-engine"]   # malformed hint ignored; name match still applies
    assert affected_services(["x [services in scope: bad name, ledger]"]) == ["ledger"]               # invalid entries dropped one by one


# --------------------------------------------------------------------------- hypothesis ledger on the single loop
def _ledger_script():
    ids = ["tu1", "payments_by_outcome_acquirer"]   # a log tool call and a metric bundle section
    verdict = {"finding": "f", "component": "acquirer-sim/acq-kbank", "last_seen_min": 0, "independent": False}
    turns = [
        [_block_tool("l1", "hypothesis_open", {"parent": "", "statement": "payment-router has a fault of its own", "test_plan": "t"}),
         _block_tool("l2", "hypothesis_open", {"parent": "", "statement": "acquirer-sim is failing", "test_plan": "t"})],
        [_block_tool("tu1", "spl_template", {"why": "w", "name": "events_by_service", "window": "-15m"}),
         _block_tool("l3", "hypothesis_verdict", {"id": "H1", "verdict": "invalidated", "evidence_ids": ["services_summary"], **verdict})],
        [_block_tool("l4", "hypothesis_verdict", {"id": "H2", "verdict": "validated", "evidence_ids": ids, **verdict}),
         _block_tool("l5", "hypothesis_open", {"parent": "H2", "statement": "acq-kbank times out for one card range", "test_plan": "t"})],
        [_block_tool("l6", "hypothesis_verdict", {"id": "H2.1", "verdict": "validated", "evidence_ids": ids, **verdict})],
    ]
    return [NS(content=c, stop_reason="tool_use", model="claude-sonnet-5-5", usage=_usage(1000, 50)) for c in turns] + [
        NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="claude-sonnet-5-5", usage=_usage(1000, 300))]


def test_loop_keeps_a_ledger_and_attaches_the_tree(monkeypatch):
    from sre_agent import audit
    events: list[dict] = []
    audit.subscribe(events.append)
    try:
        client = _client(_ledger_script())
        monkeypatch.setattr(investigator, "_client", lambda provider: client)
        ts = ToolSet(mcp=None, splunk=FakeSplunk([3]))
        r = investigator.investigate({"id": "C-t", "incidents": []}, "bundle", ts, provider="anthropic", model="claude-sonnet-5-5")
    finally:
        audit._SUBSCRIBERS.remove(events.append)
    assert r.stats.requests == 5
    first = client.requests[0]
    names = [t["name"] for t in first["tools"]]
    assert {"hypothesis_open", "hypothesis_verdict"} <= set(names) and names == sorted(names)
    assert [t["name"] for t in first["tools"] if not t["strict"]] == ["hypothesis_open", "hypothesis_verdict", "metric_series", "spl_template"]
    assert first["cache_control"] == {"type": "ephemeral"}            # the growing conversation is cached on the Anthropic API
    assert "hypothesis_open" in first["system"][0]["text"]
    assert ts.calls == 1 and [e["tool"] for e in ts.log] == ["spl_template"]   # ledger calls do not spend the tool budget
    assert [(n["id"], n["status"], n["depth"]) for n in r.investigation["tree"]] == [("H1", "invalidated", 1), ("H2", "validated", 1), ("H2.1", "validated", 2)]
    assert "tree_gap" not in r.investigation and "H2.1" in r.investigation["tree_text"]
    back = client.requests[1]["messages"][2]["content"]             # every ledger call got its result, in one user message
    assert [b["tool_use_id"] for b in back] == ["l1", "l2"] and json.loads(back[0]["content"]) == {"id": "H1", "status": "open"}
    assert not [e for e in events if e["event"] == "sre.rca.tool" and str(e.get("tool", "")).startswith("hypothesis_")]
    assert [e["event"] for e in events].count("sre.tree.reset") == 1
    assert [e["node"] for e in events if e["event"] == "sre.tree.verdict"] == ["H1", "H2", "H2.1"]


def test_loop_asks_once_when_the_ledger_is_missing(monkeypatch):
    final = NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="m", usage=_usage())
    client = _client([final, final])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert r.stats.requests == 2                                      # one corrective round, never a loop
    asked = client.requests[1]["messages"][-1]
    assert asked["role"] == "user" and "no hypotheses were recorded" in asked["content"]
    assert r.investigation["tree"] == [] and "no hypotheses" in r.investigation["tree_gap"]
    assert r.investigation["proposed_action"]["type"].endswith("acquirer_kbank_timeout")   # the answer is kept


def test_ledger_switch_off_restores_the_plain_loop(monkeypatch):
    monkeypatch.setattr(investigator, "LEDGER_ON", False)
    client = _client([NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="m", usage=_usage())])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    ts = ToolSet(mcp=None, splunk=FakeSplunk())
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ts, provider="anthropic", model="claude-sonnet-5-5")
    assert r.stats.requests == 1 and "tree" not in r.investigation and ts.ledger is None
    assert "hypothesis_open" not in json.dumps(client.requests[0]["tools"]) and "hypothesis_open" not in client.requests[0]["system"][0]["text"]


def test_bedrock_requests_have_no_top_level_cache_control(monkeypatch):
    monkeypatch.setattr(investigator, "LEDGER_ON", False)
    client = _client([NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="m", usage=_usage())])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="bedrock", model="claude-sonnet-5-5")
    assert "cache_control" not in client.requests[0]


def test_write_up_schema_has_the_conclusion_fields():
    s = investigator.INVESTIGATION_SCHEMA
    for k in ("title", "mechanism", "next_steps"):
        assert k in s["properties"] and k in s["required"]
    assert "timeline" not in s["properties"]                                           # removed deliberately, 27 Nov 2026
    assert "Method:" in investigator.SYSTEM_PROMPT and investigator.system_prompt(True) != investigator.system_prompt(False)
    assert investigator.system_prompt(False) == investigator.SYSTEM_PROMPT            # branching.py splits this text at "Method:"


class TooLarge(Exception):
    status_code = 400

    def __str__(self):
        return "Error code: 400 - The compiled grammar is too large, which would cause performance issues."


def test_strict_tools_stay_inside_the_grammar_limit_and_fall_back_once(monkeypatch):
    monkeypatch.setattr(investigator, "LEDGER_ON", False)
    ok = NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="m", usage=_usage())
    client = _client([ok])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert sorted(t["name"] for t in client.requests[0]["tools"] if not t["strict"]) == ["metric_series", "spl_template"]   # measured 27 Nov 2026

    class Once(FakeClient):
        def create(self, **kwargs):
            self.requests.append(dict(kwargs))
            if len(self.requests) == 1:
                raise TooLarge()
            return ok
    c2 = Once([])
    c2.messages = NS(create=c2.create)
    monkeypatch.setattr(investigator, "_client", lambda provider: c2)
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert len(c2.requests) == 2 and not any(t["strict"] for t in c2.requests[1]["tools"])    # one retry with no strict tool
    assert r.investigation["proposed_action"]["type"].endswith("acquirer_kbank_timeout")

    class Always(FakeClient):
        def create(self, **kwargs):
            self.requests.append(dict(kwargs))
            raise TooLarge()
    c3 = Always([])
    c3.messages = NS(create=c3.create)
    monkeypatch.setattr(investigator, "_client", lambda provider: c3)
    with pytest.raises(TooLarge):
        investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert len(c3.requests) == 2


def test_escalation_ignores_an_inconclusive_sub_hypothesis_when_a_tree_exists():
    base = {"proposed_action": {"type": "chaos.flag_off:acquirer_kbank_timeout"}, "failure_mode": "dependency_degraded", "confidence": 0.85,
            "hypotheses": [{"statement": "a", "status": "validated"}, {"statement": "narrower, not measurable", "status": "inconclusive"}]}
    assert "inconclusive" in investigator.should_escalate(base)                       # no tree: the old rule
    tree = [{"id": "H1", "depth": 1, "status": "validated"}, {"id": "H1.1", "depth": 2, "status": "validated"}, {"id": "H1.2", "depth": 2, "status": "inconclusive"}]
    assert investigator.should_escalate(dict(base, tree=tree)) == ""                  # a refinement left open is not a competing explanation
    tree[0] = {"id": "H1", "depth": 1, "status": "inconclusive"}
    assert "inconclusive" in investigator.should_escalate(dict(base, tree=tree))      # a top-level alternative left open still is
    assert "inconclusive" in investigator.should_escalate(dict(base, tree=[{"id": "H1", "depth": 1, "status": "validated"}, {"id": "H2", "depth": 1, "status": "not tested"}]))


# --------------------------------------------------------------------------- review findings, 27 Nov 2026
def _turn(*blocks, stop="tool_use"):
    return NS(content=list(blocks), stop_reason=stop, model="claude-sonnet-5-5", usage=_usage(1000, 50))


def _open(i, parent, statement):
    return _block_tool(f"o{i}", "hypothesis_open", {"parent": parent, "statement": statement, "test_plan": "t"})


def test_tree_gap_reports_hypotheses_left_without_a_verdict(monkeypatch):
    ok = {"id": "H1", "verdict": "validated", "finding": "f", "evidence_ids": ["payments_by_outcome_acquirer", "spl_events_by_service"],
          "component": "c", "last_seen_min": 0, "independent": False}
    final = _turn(_block_text(json.dumps(INV)), stop="end_turn")
    client = _client([_turn(_open(1, "", "own fault"), _open(2, "", "dependency")), _turn(_block_tool("v1", "hypothesis_verdict", ok), _open(3, "H1", "narrower")), final, final])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    bundle = "### payments_by_outcome_acquirer\nx\n\n### spl_events_by_service\ny"
    r = investigator.investigate({"id": "C-t", "incidents": []}, bundle, ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert [(n["id"], n["status"]) for n in r.investigation["tree"]] == [("H1", "validated"), ("H2", "not tested"), ("H1.1", "not tested")]
    assert "H2, H1.1" in r.investigation["tree_gap"] and "no verdict" in r.investigation["tree_gap"]     # kept on the case, as the README says


def test_a_refused_corrective_reply_keeps_the_earlier_answer(monkeypatch):
    good = _turn(_block_text(json.dumps(INV)), stop="end_turn")
    client = _client([good, NS(content=[], stop_reason="refusal", model="m", usage=_usage())])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert r.stats.requests == 2 and r.investigation["proposed_action"]["type"].endswith("acquirer_kbank_timeout")
    cut = NS(content=[_block_text('{"root_cause_service": "acq')], stop_reason="max_tokens", model="m", usage=_usage())
    client2 = _client([good, cut])
    monkeypatch.setattr(investigator, "_client", lambda provider: client2)
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    assert r.investigation["root_cause_service"] == "acquirer-sim"


def test_an_error_mid_run_closes_the_open_hypotheses(monkeypatch):
    from sre_agent import audit

    class Boom(FakeClient):
        def create(self, **kwargs):
            self.requests.append(kwargs)
            if len(self.requests) == 2:
                raise RuntimeError("model API unreachable")
            return self.responses.pop(0)
    c = Boom([_turn(_open(1, "", "own fault"), _open(2, "", "dependency"))])
    c.messages = NS(create=c.create)
    monkeypatch.setattr(investigator, "_client", lambda provider: c)
    events: list[dict] = []
    audit.subscribe(events.append)
    try:
        with pytest.raises(RuntimeError):
            investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="anthropic", model="claude-sonnet-5-5")
    finally:
        audit._SUBSCRIBERS.remove(events.append)
    assert [(e["node"], e["status"]) for e in events if e["event"] == "sre.tree.verdict"] == [("H1", "not tested"), ("H2", "not tested")]


def test_uncached_providers_keep_the_small_token_budget(monkeypatch):
    monkeypatch.setattr(investigator, "LEDGER_ON", False)
    monkeypatch.setattr(investigator, "MAX_INPUT_TOKENS_NO_CACHE", 100)
    client = _client([NS(content=[_block_tool("tu1", "spl_template", {"name": "events_by_service", "window": "-15m"})], stop_reason="tool_use", model="m", usage=_usage(500, 10)),
                      NS(content=[_block_text(json.dumps(INV))], stop_reason="end_turn", model="m", usage=_usage(10, 10))])
    monkeypatch.setattr(investigator, "_client", lambda provider: client)
    r = investigator.investigate({"id": "C-t", "incidents": []}, "b", ToolSet(mcp=None, splunk=FakeSplunk()), provider="bedrock", model="claude-sonnet-5-5")
    assert r.stats.budget_hit == "tokens"      # 300,000 applies only where the conversation is read from cache


def test_metric_series_answers_a_bad_split_or_rollup_with_error_text():
    class MCP:
        def signalflow(self, *a, **k):
            return {"series": []}
    ts = ToolSet(mcp=MCP(), splunk=None)
    base = {"why": "w", "metric": "tuktukpay.payments.count", "by": ["payment.acquirer"], "rollup": "sum", "window": "-15m", "resolution_ms": 60000}
    assert "error" not in json.loads(ts.dispatch("c0", "metric_series", base).split("\n", 1)[1].rsplit("\n</tool_data>", 1)[0])
    for i, bad in enumerate(({"by": "payment.acquirer"}, {"by": '["payment.acquirer"]'}, {"by": ["payment.card.bin"]}, {"rollup": "p99"})):
        out = json.loads(ts.dispatch(f"c{i + 1}", "metric_series", {**base, **bad}))
        assert out["tool"] == "metric_series" and ("by must be" in out["error"] or "rollup must be" in out["error"]), out
