import os

import pytest

os.environ["SRE_AGENT_QUIET"] = "1"

from sre_agent import case as cs  # noqa: E402
from sre_agent import grouping, topology  # noqa: E402
from sre_agent.grouping import Grouper, finding_signal  # noqa: E402

PFX = "TukTukPay [tuktukpay-demo] "
G = topology.static_graph()


def alert(name, iid, since="2026-11-02T01:00:00Z"):
    return {"detector": PFX + name, "incident_id": iid, "key": "k-" + iid, "severity": "Major", "anomaly_state": "ANOMALOUS", "since": since, "dimensions": {}}


def finding(origin="acquirer-sim", flagged="acquirer-sim payment-router", t="1"):
    return finding_signal({"_time": t, "origin": origin, "flagged": flagged, "evidence": "ecod: 9", "onset": "2026-11-02 00:59 UTC"})


@pytest.fixture
def g(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "STATE_DIR", tmp_path / "cases")
    started = []

    def start(sigs):
        started.append(sigs)
        return cs.new_case("tuktukpay-demo", sigs, source="console")["id"]
    x = Grouper(start)
    x.tick([], [], G, 1000)   # first read: nothing open
    x.started = started
    return x


def test_alert_alone_starts_a_case_after_the_wait(g):
    a = [alert("payment-router error rate above 5%", "I1")]
    assert g.tick(a, [], G, 1001) == []
    assert g.waiting(1001)[0]["signals"] == 1
    assert len(g.tick(a, [], G, 1001 + grouping.WAIT_S)) == 1


def test_finding_and_alerts_on_one_path_make_one_case_in_time_order(g):
    a = [alert("payment-router error rate above 5%", "I1")]
    g.tick([], [finding()], G, 1001)
    g.tick(a, [finding()], G, 1021)
    assert len(g.tick(a, [finding()], G, 1001 + grouping.WAIT_S)) == 1
    sigs = g.started[0]
    assert [s["incident_id"] for s in sigs] == ["model-acquirer-sim-1", "I1"]
    assert "joined" not in sigs[0] and sigs[1]["joined"]["hops"] == 0
    assert g.tick(a, [finding()], G, 1200) == []


def test_alert_that_clears_during_the_wait_starts_nothing(g):
    g.tick([alert("payment-router error rate above 5%", "I1")], [], G, 1001)
    assert g.tick([], [], G, 1001 + grouping.WAIT_S) == [] and not g.groups


def test_alerts_open_at_the_first_read_never_start_a_case(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "STATE_DIR", tmp_path / "cases")
    x = Grouper(lambda s: pytest.fail("started"))
    a = [alert("payment-router error rate above 5%", "I1")]
    x.tick(a, [], G, 1000)
    assert x.tick(a, [], G, 2000) == [] and not x.groups


def test_unrelated_signals_become_two_cases(g):
    a = [alert("payment-router error rate above 5%", "I1"), alert("merchant-copilot p90 latency above 2s", "I2")]
    g.tick(a, [], G, 1001)
    assert len(g.tick(a, [], G, 1001 + grouping.WAIT_S)) == 2


def test_late_signal_waits_for_the_run_then_joins_without_a_second_run(g):
    a = [alert("payment-router error rate above 5%", "I1")]
    g.tick(a, [], G, 1001)
    cid = g.tick(a, [], G, 1001 + grouping.WAIT_S)[0]
    c = cs.load(cid)
    cs.transition(c, "investigating")
    assert g.tick(a, [finding()], G, 1100) == []
    assert len(g.late) == 1 and len(cs.load(cid)["incidents"]) == 1   # being worked on: not added yet
    c = cs.load(cid)
    c["investigation"] = {"summary": "test"}
    cs.transition(c, "escalated", reason="test")
    assert g.tick(a, [finding()], G, 1120) == []
    c = cs.load(cid)
    assert not g.late and not g.groups and [i["incident_id"] for i in c["incidents"]] == ["I1", "model-acquirer-sim-1"]
    assert c["unreviewed_alerts"] == [c["incidents"][1]["detector"]]   # the console asks for a re-run


def test_case_cap_holds_the_group_until_a_slot_frees(g, monkeypatch):
    monkeypatch.setattr(grouping, "MAX_OPEN_CASES", 0)
    a = [alert("payment-router error rate above 5%", "I1")]
    g.tick(a, [], G, 1001)
    assert g.tick(a, [], G, 1001 + grouping.WAIT_S) == [] and g.waiting(2000)[0]["held"]
    monkeypatch.setattr(grouping, "MAX_OPEN_CASES", 2)
    assert len(g.tick(a, [], G, 1100)) == 1


def test_cooldown_stops_a_flapping_detector_opening_new_groups(g):
    a = [dict(alert("payment-router error rate above 5%", "I1"), key="same")]
    g.tick(a, [], G, 1001)
    cid = g.tick(a, [], G, 1001 + grouping.WAIT_S)[0]
    c = cs.load(cid)
    cs.transition(c, "investigating")
    cs.transition(c, "escalated", reason="test")
    b = [dict(alert("payment-router error rate above 5%", "I2"), key="same")]
    g.tick(b, [], G, 1100)
    assert not g.groups


def test_finding_signal_names_its_services_for_the_evidence_step():
    from sre_agent.ties import incident_services
    s = finding("acquirer-sim", "acquirer-sim payment-router business")
    assert incident_services(s)[:2] == ["acquirer-sim", "payment-router"] and s["since"] == "2026-11-02T00:59:00Z"


def test_finding_on_a_service_off_the_map_stays_apart_but_business_joins(g):
    a = [alert("payment-router error rate above 5%", "I1")]
    g.tick(a, [finding("mystery-svc", "mystery-svc", "2")], G, 1001)
    assert len(g.groups) == 2
    g.tick(a, [finding("business", "business", "3")], G, 1002)
    assert sorted(len(x["signals"]) for x in g.groups) == [1, 2]


def test_shopping_agent_alone_opens_nothing(g):
    g.tick([], [finding("shopping-agent", "shopping-agent", "2")], G, 1001)
    assert not g.groups and g.tick([], [], G, 1001 + grouping.WAIT_S) == []


def test_shopping_agent_with_another_flagged_service_still_opens(g):
    g.tick([], [finding("shopping-agent", "shopping-agent checkout-api", "2")], G, 1001)
    assert len(g.groups) == 1


def test_shopping_agent_joins_an_open_group_as_evidence(g, monkeypatch):
    monkeypatch.setattr(grouping, "_link", lambda a, b, graph: {"rule": "call_path", "path": ["shopping-agent", "checkout-api"], "hops": 1})
    a = [alert("checkout-api error rate above 5%", "I1")]
    g.tick(a, [], G, 1001)
    g.tick(a, [finding("shopping-agent", "shopping-agent", "2")], G, 1010)
    assert len(g.groups) == 1 and len(g.groups[0]["signals"]) == 2


def test_a_case_left_open_from_long_ago_does_not_take_a_slot(g, monkeypatch):
    monkeypatch.setattr(grouping, "MAX_OPEN_CASES", 1)
    old = cs.new_case("tuktukpay-demo", [{"detector": "x", "incident_id": "old"}], source="console")
    old["opened_epoch"] = 1.0
    cs.save(old)
    a = [alert("merchant-copilot p90 latency above 2s", "I1")]
    g.tick(a, [], G, 5000)
    assert len(g.tick(a, [], G, 5000 + grouping.WAIT_S)) == 1


def test_alert_that_flaps_starts_a_case_the_second_time(g):
    def flap(iid):
        return [dict(alert("ledger p90 latency above 400ms", iid), key="ledger-p90")]
    g.tick(flap("I1"), [], G, 1001)
    assert g.tick([], [], G, 1001 + grouping.WAIT_S) == []          # cleared in the wait: dropped
    g.tick(flap("I2"), [], G, 1100)
    assert len(g.tick([], [], G, 1100 + grouping.WAIT_S)) == 1      # back within FLAP_S: real, even if it cleared again


def test_alert_that_comes_back_long_after_is_a_new_blip(g):
    def blip(iid):
        return [dict(alert("ledger p90 latency above 400ms", iid), key="ledger-p90")]
    g.tick(blip("I1"), [], G, 1001)
    g.tick([], [], G, 1001 + grouping.WAIT_S)
    g.tick(blip("I2"), [], G, 2000)
    assert g.tick([], [], G, 2000 + grouping.WAIT_S) == []
