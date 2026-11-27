import json
import os
import pathlib

import pytest

os.environ["SRE_AGENT_QUIET"] = "1"
os.environ["MOCK_JEV"] = "1"

from sre_agent import audit, engine, evals, recorder  # noqa: E402
from sre_agent import case as cs  # noqa: E402
from sre_agent.acts import EVAL_CASES  # noqa: E402
from sre_agent.o11y_mcp import O11yMCP, ToolResult  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "evals" / "cases"


class LiveMCP:
    """Stands in for the gateway: answers every tool, with private details the recorder must strip."""
    services_summary = O11yMCP.services_summary
    signalflow = O11yMCP.signalflow

    def call(self, name, params):
        if name == "o11y_get_apm_services_summary":
            body = {"services": [{"service": {"name": "payment-router", "link": {"url": "https://app.us1.signalfx.com/#/apm"}},
                                  "requestCount": {"value": 100}, "errorCount": {"value": 30}}]}
        elif name == "o11y_execute_signalflow_program":
            body = {"metadata": {"t1": {"payment.acquirer": "acq-kbank", "k8s.node.name": "ip-10-1-2-3.ap-southeast-1.compute.internal"}},
                    "timeseries": {"1000": {"t1": 5.0}, "2000": {"t1": 9.0}}}
        elif name == "o11y_get_apm_exemplar_traces":
            body = {"items": [{"item": {"traceId": "ab" * 8, "initiatingService": "checkout-api"}}]}
        elif name == "o11y_get_apm_trace_tool":
            body = {"spans": [{"traceID": "ab" * 8, "serviceName": "payment-router", "operationName": "route", "duration": 2500000,
                               "tags": [{"key": "error", "value": "true"}, {"key": "peer.service", "value": "acquirer-sim"},
                                        {"key": "net.peer.ip", "value": "198.51.100.7"}]}]}
        else:
            body = {"image": "123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/tuktukpay/x", "lb": "abc-123.elb.ap-southeast-1.amazonaws.com"}
        return ToolResult(name=name, text=json.dumps(body))


class LiveSplunk:
    def splunk_run_query(self, query, earliest_time="-15m", latest_time="now", wait_s=90, max_results=200):
        rows = [{"source": "payment-router", "event": "acquirer.timeout", "count": "42", "host": "10.0.0.7"},
                {"source": "payment-router", "event": "route.failover", "count": "40"}]
        return {"query": query, "results": rows[:max_results], "result_count": len(rows)}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "_client", None)
    monkeypatch.setattr(audit, "QUIET", True)
    monkeypatch.setattr(engine, "CHAOS_URL", "")
    monkeypatch.setattr(cs, "STATE_DIR", tmp_path / "cases")
    monkeypatch.setattr(evals, "_quiet_sandbox", lambda: str(tmp_path))
    return tmp_path


def _record(tmp_path, name="act1", window="-15m"):
    mcp, splunk = LiveMCP(), LiveSplunk()
    rec = recorder.Recorder(mcp, splunk)
    evals._investigate(EVAL_CASES[name], mcp, splunk, "mock", window)
    evals.probe(mcp, splunk, window)
    fx = rec.fixture({"case": name, "window": window, "recorded_run": {}})
    d = tmp_path / "fx"
    d.mkdir(exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(fx))
    return d, fx


def test_recording_is_sanitised(sandbox):
    _, fx = _record(sandbox)
    text = json.dumps(fx)
    assert recorder.leaks(text) == [], recorder.leaks(text)
    assert "[ACCOUNT]" in text and "[HOST]" in text and "[IP]" in text
    traces = [c for c in fx["calls"] if c.get("tool") == "o11y_get_apm_trace_tool"]
    assert traces and "net.peer.ip" not in traces[0]["text"]        # shrunk to the tags compact_trace reads
    assert all(json.loads(c["text"]) is not None for c in fx["calls"] if c["kind"] == "mcp")   # still valid JSON


def test_replay_with_mock_scores_act1_pass(sandbox):
    d, _ = _record(sandbox)
    row = evals.run_case("act1", "mock", d)
    assert row["error"] == "" and row["misses"] == 0, row
    assert row["rc_ok"] and row["action_ok"] and row["pass"]
    assert row["action"] == "chaos.flag_off:acquirer_kbank_timeout" and row["evidence"] in ("yes", "no")
    assert "PASS" in evals.table([row])


def test_unrecorded_call_is_a_miss_not_a_crash(sandbox):
    d, fx = _record(sandbox)
    rep = recorder.ReplaySplunk(fx)
    with pytest.raises(recorder.NotRecorded):
        rep.splunk_run_query("search index=tuktukpay | stats count by nothing", "-15m")
    assert len(rep.misses) == 1


def test_scoring_rules():
    act1, act4, base = EVAL_CASES["act1"], EVAL_CASES["act4"], EVAL_CASES["baseline"]
    inv = lambda rc, a: {"root_cause_service": rc, "proposed_action": {"type": a}}  # noqa: E731
    assert evals.score(act1, inv("acquirer-sim", "chaos.flag_off:acquirer_kbank_timeout"), {})["pass"]
    assert not evals.score(act1, inv("payment-router", "chaos.flag_off:acquirer_kbank_timeout"), {})["pass"]   # alerting != root cause
    assert not evals.score(act1, inv("acquirer-sim", "no_action"), {})["pass"]
    assert evals.score(act4, inv("none", "no_action"), {})["pass"]
    assert evals.score(base, inv("none", "inconclusive"), {})["pass"] and evals.score(base, inv("none", "no_action"), {})["pass"]
    assert not evals.score(base, inv("ledger", "chaos.flag_off:ledger_db_slow"), {})["pass"]
    cited = {"root_cause_service": "acquirer-sim", "proposed_action": {"type": "chaos.flag_off:acquirer_kbank_timeout"},
             "evidence": [{"evidence_id": "spl_x"}]}
    assert evals.score(act1, cited, {"sections": {"spl_x": "... acquirer.timeout 42 ..."}})["evidence"] == "yes"
    assert evals.score(act1, cited, {"sections": {"spl_x": "nothing"}})["evidence"] == "no"


def test_every_eval_case_has_ground_truth():
    for a in EVAL_CASES.values():
        assert a.root_cause_services, a.name


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")) or [None])
def test_committed_fixtures_hold_nothing_private(path):
    if path is None:
        pytest.skip("no fixtures recorded yet")
    text = path.read_text()
    assert recorder.leaks(text) == [], f"{path.name}: {recorder.leaks(text)}"
    fx = json.loads(text)
    assert fx["case"] in EVAL_CASES and fx["calls"]


GOOD = {"proposed_action": {"type": "chaos.flag_off:acquirer_kbank_timeout"},
        "title": "acq-kbank hang on one card range failed card payments",
        "mechanism": "acq-kbank holds authorisations for 3.2 s, longer than the router's 2.5 s limit.",
        "impact": "573 authorisations timed out in 15 min and 790 payments were declined.",
        "next_steps": ["Route the card range off acq-kbank", "Verify that acquirer.timeout events return to zero"],
        "tree": [{"id": "H1", "depth": 1, "status": "validated"}, {"id": "H1.1", "depth": 2, "status": "validated"}]}


def test_write_up_quality_counts_five_checks_on_a_fault():
    assert evals.quality(GOOD) == {"score": 5, "of": 5, "failed": []}
    weak = dict(GOOD, title="It is probably the acquirer that is " + "really " * 8 + "slow", mechanism="The acquirer is slow.",
                impact="About 573 timeouts, probably more; the amount is indicative.",
                next_steps=["Route the card range off acq-kbank"], tree=[{"id": "H1", "depth": 1, "status": "validated"}, {"id": "H1.1", "depth": 2, "status": "not tested"}])
    q = evals.quality(weak)
    assert q["score"] == 0 and q["of"] == 5 and q["failed"] == ["tree depth", "mechanism numbers", "impact", "next steps", "title"]


def test_write_up_quality_skips_fault_checks_when_no_action_is_proposed():
    quiet = {"proposed_action": {"type": "no_action"}, "title": "Agent mandate blocks are governance working as designed",
             "next_steps": ["No action", "Confirm the blocks follow the mandate limits"], "mechanism": "", "impact": "none", "tree": []}
    assert evals.quality(quiet) == {"score": 2, "of": 2, "failed": []}
    assert evals.quality({}) == {"score": 0, "of": 2, "failed": ["next steps", "title"]}     # an old case without the fields


def test_table_has_a_write_up_column_that_never_changes_the_result():
    row = {"case": "act1", "root_cause": "acquirer-sim", "rc_ok": True, "action": "chaos.flag_off:acquirer_kbank_timeout", "action_ok": True, "evidence": "yes",
           "pass": True, "model": "m", "cost_usd": 0.1, "seconds": 20, "misses": 0, "quality": {"score": 4, "of": 5, "failed": ["impact"]}}
    text = evals.table([row, {k: v for k, v in row.items() if k != "quality"}])
    assert "| write-up |" in text and "| 4/5 (impact) |" in text and text.count("PASS") == 3 and "| - |" in text
    assert "write-up 4/5" in text.splitlines()[-1]                      # summed over the rows that have a score


def test_write_up_quality_is_not_fooled_by_identifiers_times_or_word_prefixes():
    q = lambda **over: evals.quality(dict(GOOD, **over))["failed"]
    assert "next steps" in q(next_steps=["Route the card range off acq-kbank", "Restart checkout-api"])        # "check" inside a service name
    assert "next steps" in q(next_steps=["Route the card range off acq-kbank", "Page the monitoring team"])
    assert "mechanism numbers" in q(mechanism="The acquirer became slow at 14:32 UTC.")                         # a clock time is one fact, not two numbers
    assert "mechanism numbers" in q(mechanism="The v3 model raised p90 latency.")                               # names, not measurements
    assert "mechanism numbers" in q(mechanism="1,234,567 requests queued.")                                     # one number
    assert "impact" in q(impact="Roughly 500 payments may have failed.")
    assert "impact" not in q(impact="acquirer.timeout appears 573 times in 15 min.")                            # "appears" is not a guess here


def test_write_up_quality_scores_a_missed_fault_on_all_five_checks():
    missed = {"proposed_action": {"type": "inconclusive"}, "title": "No clear cause found", "next_steps": ["Look again", "Verify the alert clears"]}
    assert evals.quality(missed) == {"score": 2, "of": 2, "failed": []}                                         # judged alone, it looks fine
    assert evals.quality(missed, fault=True) == {"score": 2, "of": 5, "failed": ["tree depth", "mechanism numbers", "impact"]}
