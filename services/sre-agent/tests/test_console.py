import pytest
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

os.environ["SRE_AGENT_QUIET"] = "1"

from sre_agent import audit, catalogue  # noqa: E402
from sre_agent import case as cs  # noqa: E402


def test_mcp_call_events_only_inside_a_case():
    seen = []
    audit.subscribe(seen.append)
    audit.mcp_call("o11y-mcp-gateway", "o11y_x", {"params": {"a": 1}}, time.time(), True, 10)
    assert not [e for e in seen if e["event"] == "sre.mcp.call"]          # no case in context → nothing emitted
    tok = audit.CURRENT_CASE.set("C-test")
    try:
        audit.mcp_call("splunk-mcp-server", "splunk_run_query", {"query": "search index=tuktukpay | stats count"}, time.time() - 0.2, True, 42)
    finally:
        audit.CURRENT_CASE.reset(tok)
    ev = [e for e in seen if e["event"] == "sre.mcp.call"]
    assert ev and ev[-1]["case_id"] == "C-test" and ev[-1]["ms"] >= 150 and "splunk_run_query" == ev[-1]["tool"] and "t" in ev[-1]


def test_owner_map():
    assert catalogue.owner_of("payment-router") == "Acquiring & Routing"
    assert catalogue.owner_of("ledger") == "Ledger & Settlement"
    assert "no owner" in catalogue.owner_of("mystery")


def test_console_refuses_other_sites(tmp_path, monkeypatch):
    from http.server import ThreadingHTTPServer
    from sre_agent import console
    monkeypatch.setattr(cs, "STATE_DIR", tmp_path / "cases")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), console.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        foreign = [{"Host": "evil.example"}, {"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}]
        for headers in foreign:
            for path in ("/", "/api/cases", "/api/status"):
                with pytest.raises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=5)
                assert e.value.code == 403
            req = urllib.request.Request(base + "/api/approve", data=b'{"case_id":"x"}', method="POST", headers=headers)
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req, timeout=5)
            assert e.value.code == 403
        assert urllib.request.urlopen(urllib.request.Request(base + "/api/cases", headers={"Origin": base, "Sec-Fetch-Site": "same-origin"}), timeout=5).status == 200
        ok = urllib.request.urlopen(urllib.request.Request(base + "/api/cases"), timeout=5)
        assert json.loads(ok.read())["cases"] == []
        page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
        assert "War-room brief" in page and "Hypothesis tree" in page
        g = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/api/topology"), timeout=5).read())
        assert "acquirer-sim" in g["edges"]["payment-router"]      # the cached or static map, offline
        try:
            _post(base, "/api/feedback", {"case_id": "C-none", "verdict": "right"})
            raise AssertionError("feedback accepted for a missing case")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.shutdown()


def test_sweep_escalates_cases_abandoned_mid_investigation(tmp_path, monkeypatch):
    from sre_agent import console
    monkeypatch.setattr(cs, "STATE_DIR", tmp_path / "cases")
    c = cs.new_case("tuktukpay-demo", [{"detector": "d", "incident_id": "I9"}], source="console")
    cs.transition(c, "investigating")
    c = cs.load(c["id"]); c["opened_epoch"] = time.time() - 3600; cs.save(c)
    assert console._sweep_abandoned() == [c["id"]] and cs.load(c["id"])["state"] == "escalated"


def _post(base, path, body):
    from sre_agent import console
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def test_triage_opens_existing_case_and_actions(tmp_path, monkeypatch):
    from http.server import ThreadingHTTPServer
    from sre_agent import console
    monkeypatch.setattr(cs, "STATE_DIR", tmp_path / "cases")
    inc = {"detector": "TukTukPay [tuktukpay-demo] copilot guardrail blocked an action", "incident_id": "INC-1", "anomaly_state": "ANOMALOUS"}
    c = cs.new_case("tuktukpay-demo", [inc], source="console")
    cs.transition(c, "investigating"); cs.transition(c, "proposed"); c = cs.load(c["id"])
    c["investigation"] = {"root_cause_service": "merchant-copilot", "summary": "stale alert"}; cs.save(c)
    monkeypatch.setitem(console.INCIDENTS, "data", [inc])
    seen = []
    audit.subscribe(seen.append)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), console.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        r = _post(base, "/api/investigate", {"incident_id": "INC-1"})
        assert r == {"case_id": c["id"], "existing": True}                     # no second RCA
        listed = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/api/incidents"), timeout=5).read())
        assert listed["incidents"][0]["case_id"] == c["id"]
        assert _post(base, "/api/page", {"case_id": c["id"]})["team"] == "AI Platform"
        assert any(e["event"] == "sre.case.paged" and e["case_id"] == c["id"] for e in seen)
        assert _post(base, "/api/ack", {"case_id": c["id"]})["state"] == "closed"
    finally:
        srv.shutdown()


def test_expected_actions_per_act():
    from sre_agent.acts import ACTS, expected_actions
    assert expected_actions(ACTS["act1"]) == {"chaos.flag_off:acquirer_kbank_timeout"}
    assert expected_actions(ACTS["act4"]) == {"no_action"}            # governance working: explain and close
    assert expected_actions(ACTS["act6"]) == {"chaos.flag_off:ledger_memory_leak", "k8s.rollout_undo:ledger"}
    assert expected_actions(ACTS["act7"]) == {"chaos.flag_off:wallet_crash_loop", "k8s.rollout_undo:wallet-sim"}
    from sre_agent import catalogue
    for a in ACTS.values():   # every expected action exists in the catalogue
        for t in expected_actions(a):
            assert t in catalogue.ACTIONS, t


def test_clear_hides_finished_cases_and_current_alerts_until_show(tmp_path, monkeypatch):
    from http.server import ThreadingHTTPServer
    from sre_agent import console
    monkeypatch.setattr(cs, "STATE_DIR", tmp_path / "cases")
    done = cs.new_case("tuktukpay-demo", [{"detector": "x", "incident_id": "A"}]); cs.transition(done, "closed", reason="test")
    pending = cs.new_case("tuktukpay-demo", [{"detector": "y", "incident_id": "B"}]); cs.transition(pending, "investigating"); cs.transition(pending, "proposed")
    monkeypatch.setitem(console.INCIDENTS, "data", [{"detector": "z", "incident_id": "INC-9", "anomaly_state": "ANOMALOUS"}])
    srv = ThreadingHTTPServer(("127.0.0.1", 0), console.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    get = lambda p: json.loads(urllib.request.urlopen(urllib.request.Request(base + p), timeout=5).read())
    try:
        assert _post(base, "/api/clear", {"what": "cases"}) == {"ok": True} and _post(base, "/api/clear", {"what": "alerts"}) == {"ok": True}
        cases, alerts = get("/api/cases"), get("/api/incidents")
        assert [c["id"] for c in cases["cases"]] == [pending["id"]] and cases["hidden"] == 1      # pending work never hides
        assert alerts["incidents"] == [] and alerts["hidden"] == 1
        monkeypatch.setitem(console.INCIDENTS, "data", console.INCIDENTS["data"] + [{"detector": "z", "incident_id": "INC-10", "anomaly_state": "ANOMALOUS"}])
        assert [i["incident_id"] for i in get("/api/incidents")["incidents"]] == ["INC-10"]           # a new firing shows
        _post(base, "/api/unclear", {"what": "cases"})
        assert get("/api/cases")["hidden"] == 0
        with pytest.raises(urllib.error.HTTPError):
            _post(base, "/api/clear", {"what": "x"})
    finally:
        srv.shutdown()


# --------------------------------------------------------------------------- hypothesis tree canvas (27 Nov 2026)
# What a browser does with the page (follow mode, the camera glide, in-place updates, old cases) was checked with
# headless screenshots against a stub; these tests keep the page's contract and its JavaScript from regressing.
def _page_and_script() -> tuple[str, str]:
    from sre_agent.console_page import page
    html = page()
    return html, re.search(r"<script>(.*)</script>", html, re.S).group(1)


def test_tree_canvas_parts_and_events_are_in_the_page():
    html, js = _page_and_script()
    for part in ('id="cv"', 'id="tree"', 'id="secs"', 'id="cvc"', 'id="legend"', 'id="detail"', 'id="treeempty"'):
        assert part in html, part
    for control in ("'zin'", "'zout'", "'zfit'", "'zfollow'"):   # zoom in, zoom out, fit, follow
        assert control in js, control
    for event in ("sre.tree.reset", "sre.tree.branch", "sre.tree.verdict", "sre.case.investigated", "sre.console.history"):
        assert f"case '{event}'" in js, event
    for label in ("Researching", "Verified", "Ruled out", "Inconclusive", "Not tested", "'Alert'", "'Hypotheses'", "'Conclusion'", "'Next steps'", "Root cause"):
        assert label in js, label
    assert "'hypothesis_open', 'hypothesis_verdict'" in js   # ledger tool calls: the tree shows them, the trace prints no "Next:" line
    for field in ("e.title", "e.mechanism", "e.next_steps", "e.tree", "last_seen_min", "independent", "test_plan"):
        assert field in js, field


def test_tree_canvas_follows_the_agreed_design():
    html, js = _page_and_script()
    assert "timeline" not in html                       # no timeline in the conclusion or the brief (27 Nov 2026)
    assert "single-loop method" not in html             # every loop case has a real tree now
    for token in ("--ok:#63B58F", "--bad:#E8707A", "--root:#F0A04B", "--ai:#8FB4F0", "--main:#CE0070"):   # calm scheme, 27 Nov
        assert token in html, token
    assert "prefers-reduced-motion" in html and "REDUCED.matches" in js   # no camera animation when the reader asks for less motion
    assert "MOVE_MS = 500" in js and "1 - Math.pow(1 - t, 3)" in js       # 500 ms, cubic ease-out (measured from a reference recording)
    assert "Math.min(1, w / b.w, h / b.h)" in js                          # a fit never zooms closer than 1:1
    canvas = js[js.index("function paintNode"):js.index("function drawTree")]
    assert " · " not in canvas and not re.search(r"'[A-Z]{4,}[A-Z ]*'", canvas)   # no middle-dot strings, no capital-letter labels in the tree
    outside = set(re.findall(r"https?://[^\s\"'`<>)]+", html)) - {"http://www.w3.org/2000/svg", "https://app.us1.signalfx.com/#/apm/traces/", "https://www.splunk.com/"}
    assert not outside, f"the page must work offline, found {outside}"


def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def test_page_script_parses(tmp_path):
    f = tmp_path / "page.js"
    f.write_text(_page_and_script()[1])
    r = subprocess.run([_node(), "--check", str(f)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]


def test_camera_path_is_the_smooth_zoom(tmp_path):
    """zoomPath is the van Wijk and Nuij interpolation: exact at both ends, and on a zoom-in the pan runs ahead of the zoom."""
    fn = re.search(r"function zoomPath\(p0, p1\) \{.*?\n\}\n", _page_and_script()[1], re.S).group(0)
    f = tmp_path / "zoom.js"
    f.write_text(fn + """
const near = (x, y) => Math.abs(x - y) < 1e-6, path = zoomPath([0, 0, 1000], [300, 200, 500]), s = path(0), e = path(1), q = path(0.25);
if (!(near(s[0], 0) && near(s[1], 0) && near(s[2], 1000) && near(e[0], 300) && near(e[1], 200) && near(e[2], 500))) throw new Error('end points are off');
const pan = Math.hypot(q[0], q[1]) / Math.hypot(300, 200), zoom = Math.log(q[2] / 1000) / Math.log(0.5);
if (!(pan > zoom && pan > 0 && pan < 1)) throw new Error('on a zoom-in the pan should lead the zoom: pan ' + pan + ', zoom ' + zoom);
const still = zoomPath([5, 5, 800], [5, 5, 400])(0.5);
if (!(near(still[0], 5) && near(still[1], 5) && still[2] < 800 && still[2] > 400)) throw new Error('a pure zoom must not move the centre');
""")
    r = subprocess.run([_node(), str(f)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]



def test_follow_up_context_keeps_the_evidence_bundle_in_reach():
    from sre_agent import console
    node = {"id": "H1", "statement": "s" * 400, "finding": "f" * 600, "evidence": [{"signal": "log", "finding": "", "evidence_id": "x" * 80}] * 8}
    case = {"id": "C-ctx", "incidents": [], "investigation": {"summary": "short", "tree_text": "└─ H1 s … ✓ validated", "tree": [node] * 12}, "decision": {}, "state": "closed"}
    console.BUNDLES["C-ctx"] = "### services_summary\nBUNDLE-MARKER"
    try:
        text = console._context(case)
    finally:
        console.BUNDLES.pop("C-ctx", None)
    assert "BUNDLE-MARKER" in text[:24000] and "tree_text" in text and '"tree":' not in text


# --------------------------------------------------------------------------- service map and agent trace (27 Nov 2026)
# How the two tabs look and behave in a browser (zoom, selection without movement, scroll position, layout shift) was
# checked with headless screenshots against a stub; these tests keep the page's contract with the server and its
# layout code from regressing.
EVENTS_THE_TRACE_SHOWS = (
    "sre.tree.reset", "sre.tree.branch", "sre.tree.verdict", "sre.case.opened", "sre.case.incident_attached", "sre.case.tie_suggested",
    "sre.case.incident_added", "sre.case.merged", "sre.case.merged_away", "sre.case.tie_dismissed", "sre.console.starting",
    "sre.case.investigating", "sre.mcp.call", "sre.rca.evidence", "sre.rca.step", "sre.rca.tool", "sre.case.escalated_model",
    "sre.case.investigated", "remediation.proposed", "approval.decided", "remediation.executing", "remediation.refused",
    "remediation.state", "remediation.executed", "remediation.verified", "sre.case.mitigated_awaiting_clear", "sre.case.escalated",
    "sre.audit.write_failed", "sre.case.inconclusive", "sre.case.stop_requested", "sre.case.stopped", "sre.case.escalation_failed",
    "sre.llm.retry", "sre.case.closed", "sre.case.paged", "sre.case.acknowledged", "sre.case.rerun_requested", "sre.chat.question",
    "sre.chat.done", "sre.chat.answer", "sre.console.error", "sre.console.done", "sre.console.history")


def _table(js: str, name: str) -> str:
    return re.search(rf"const {name} = \{{(.*?)\}};", js, re.S).group(1)


def test_map_and_trace_parts_are_in_the_page():
    html, js = _page_and_script()
    for part in ('id="mcv"', 'id="map"', 'id="mapempty"', 'id="mcvc"', 'id="tlegend"', 'id="tdetail"', 'id="toponote"',
                 'id="tlog"', 'id="tstat"', 'id="trawbtn"', 'id="tnew"', 'role="log"'):
        assert part in html, part
    assert "makeCanvas(CV, WORLD" in js and "makeCanvas(MCV, MAPW" in js       # the tree and the map share one pan-and-zoom canvas
    assert "fetch('/api/topology')" not in js and js.count("api('/api/topology')") == 1   # one read of the console's cached map, never the gateway
    assert "faults_on" not in js[js.index("const SVC = "):js.index("function setRun(")]   # injected-fault names stay out of the map
    for event in EVENTS_THE_TRACE_SHOWS:                                        # nothing the old list showed was dropped
        assert f"case '{event}'" in js, event
    for text in ("'Next: '", "Hypothesis tree updated: ", "'Reasoning summary'", "Collected the evidence", "Check by code", "Tool calls on file"):
        assert text in js, text
    actors = dict(re.findall(r"(\w+): \['[a-z0-9-]+', '(\w+)'\]", _table(js, "ACTOR")))
    assert actors == {"code": "Code", "model": "Model", "person": "Person"}     # every step says who acted
    stick = re.search(r"function stick\(fn\) \{.*?\n\}\n", js, re.S).group(0)
    assert "const follow = atBottom()" in stick and "if (follow) TLOG.scrollTop = TLOG.scrollHeight" in stick   # the view follows only a reader who is at the bottom


def test_every_icon_the_page_uses_is_in_its_sprite():
    html, js = _page_and_script()
    have = set(re.findall(r'<symbol id="ic-([a-z0-9-]+)"', html))
    used = set(re.findall(r"\['([a-z0-9-]+)', '[^']*'\]", _table(js, "SVC") + _table(js, "ACTOR")))
    used |= set(re.findall(r"\['[a-z]*', '([a-z0-9-]+)'\]", _table(js, "SVC_PILL"))) | set(re.findall(r": '([a-z]+)'", _table(js, "STATUS_ICON")))
    for call in re.findall(r"\bic\(([^()]*)\)", js) + re.findall(r"\bicon: ([^,}]*)", js):
        used |= set(re.findall(r"'([a-z0-9-]+)'", call))
    used |= set(re.findall(r"\['m?z[a-z]+', '([a-z0-9-]+)'", js)) | set(re.findall(r"pillOf\('[a-z]+', '[^']+', '([a-z0-9-]+)'\)", js))
    used |= set(re.findall(r"\|\| \['([a-z0-9-]+)', ''\]", js))             # the picture for a service the page does not know
    assert len(used) > 25 and used <= have, f"not in the sprite: {sorted(used - have)}"
    assert have <= used, f"in the sprite but never used: {sorted(have - used)}"
    assert not re.search(r"[\U0001F300-\U0001FAFF☀-➿]", html)        # icons, no emoji


def test_service_map_knows_every_service_of_the_kit():
    from sre_agent import topology
    _, js = _page_and_script()
    known = {name: (icon, role) for name, icon, role in re.findall(r"'([a-z-]+)': \['([a-z0-9-]+)', '([^']*)'\]", _table(js, "SVC"))}
    assert topology.SERVICES <= set(known), f"no picture and role for {sorted(topology.SERVICES - set(known))}"
    for name, (icon, role) in known.items():
        assert role and len(role) <= 26 and role[0].isupper() and not role.endswith("."), (name, role)   # one line in the box, never cut off
    assert len({icon for icon, _ in known.values()}) == len(known)             # each service has its own picture


def test_map_and_trace_follow_the_calm_design():
    html, js = _page_and_script()
    assert "text-transform:uppercase" not in html
    for code in (js[js.index("const SVC = "):js.index("function setRun(")], js[js.index("const TLOG = "):js.index("function render1(")]):
        assert " · " not in code and not re.search(r"'[A-Z]{4,}[A-Z ]*'", code)   # no middle-dot strings, no capital-letter labels
    new_css = html[html.index("/* service map:"):html.index("@media (prefers-reduced-motion")] + html[html.index("/* agent trace:"):html.index("details{margin:4px 0}")]
    assert set(re.findall(r"#[0-9A-Fa-f]{3,6}\b", new_css)) <= {"#1A2450", "#232D5C", "#2A3463", "#fff"}   # colour comes from the page's tokens
    assert "@keyframes" not in new_css and "translateY" not in new_css      # no slide-in entrances
    for shadow in re.findall(r"box-shadow:([^;}]*)", new_css):                # no glow: only the light top edge and a plain drop shadow
        assert set(re.findall(r"rgba\((\d+,\d+,\d+),", shadow)) <= {"255,255,255", "0,0,0"} and "var(" not in shadow, shadow
    for token in ("var(--root)", "var(--bad)", "var(--ok)", "var(--ai)"):
        assert token in new_css, token


MAP_LAYOUT_CHECKS = """
const boxes = (L) => L.N.map(n => ({ n, x: L.x[n], y: L.y[n], w: BW, h: BH }));
const apart = (L) => boxes(L).every((a, i, all) => all.every((b, j) => i >= j || a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y));
function rightAngles(d) {   // every straight piece of a line runs along x or along y; corners are small curves
  let p = null; const bad = [];
  for (const m of d.matchAll(/([MLQ])([-\\d.]+),([-\\d.]+)(?: ([-\\d.]+),([-\\d.]+))?/g)) {
    const to = m[1] === 'Q' ? [+m[4], +m[5]] : [+m[2], +m[3]];
    if (m[1] === 'L' && Math.abs(to[0] - p[0]) > 0.2 && Math.abs(to[1] - p[1]) > 0.2) bad.push(m[0]);
    if (m[1] === 'Q' && Math.hypot(to[0] - p[0], to[1] - p[1]) > 15) bad.push(m[0]);
    p = to;
  }
  return bad.length === 0;
}
for (const vert of [false, true]) {
  const L = mapLayout(STATIC, vert), along = vert ? L.y : L.x, across = vert ? L.x : L.y, tag = vert ? 'top to bottom: ' : 'left to right: ';
  if (L.N.length !== 9 || !apart(L)) throw new Error(tag + 'boxes overlap or are missing');
  if (!L.links.every(l => l.fwd && !l.rev && along[l.a] < along[l.b])) throw new Error(tag + 'a caller must come before its callee');
  if (!L.links.every(l => rightAngles(l.d))) throw new Error(tag + 'lines must be right angles');
  if (Math.abs(across['payment-router'] - across['acquirer-sim']) > 0.5) throw new Error(tag + 'a single call should be a straight line');
  if (L.links.length !== 7) throw new Error(tag + 'one line per call, got ' + L.links.length);
}
const loop = mapLayout({ a: ['b'], b: ['a', 'c'] }, false);   // a call back up the chain must not hang the layout
if (!(loop.N.length === 3 && loop.links.some(l => l.fwd && l.rev) && apart(loop))) throw new Error('a two-way call is one line with an arrow at both ends');
const skip = mapLayout({ a: ['b', 'c'], b: ['c'], d: ['c'] }, false), far = skip.links.find(l => l.a === 'a' && l.b === 'c');
if (!(far.via.length === 3 && skip.x.c > skip.x.b && skip.x.b > skip.x.a && rightAngles(far.d))) throw new Error('an edge over two columns gets a waypoint');
const nums = [...far.d.matchAll(/([-\\d.]+),([-\\d.]+)/g)].map(m => [+m[1], +m[2]]), inB = nums.filter(([x, y]) => x > skip.x.b + 1 && x < skip.x.b + BW - 1 && y > skip.y.b + 1 && y < skip.y.b + BH - 1);
if (inB.length) throw new Error('the long line runs under the box in between');
// what a live map can add to the recorded one: a second caller, a call that skips a layer, a call back up the chain
const LIVE = { ...STATIC, 'checkout-api': ['acquirer-sim', 'ledger', 'payment-router', 'risk-engine', 'wallet-sim'], 'wallet-sim': ['checkout-api'], 'merchant-copilot': ['checkout-api', 'ledger'] };
function corners(d) {   // where a line starts, turns and ends
  const v = []; for (const m of d.matchAll(/([MLQ])([-\\d.]+),([-\\d.]+)(?: ([-\\d.]+),([-\\d.]+))?/g)) if (m[1] !== 'L') v.push([+m[2], +m[3]]);
  const z = [...d.matchAll(/L([-\\d.]+),([-\\d.]+)/g)].pop(); v.push([+z[1], +z[2]]); return v;
}
function crossings(L) {   // lines of two different calls that cross in the middle of both; lines that meet at a box or share a run do not count
  const segs = []; L.links.forEach((l, i) => { const v = corners(l.d); for (let k = 1; k < v.length; k++) segs.push([i, v[k - 1], v[k]]); });
  let n = 0; segs.forEach(([i, a, b]) => segs.forEach(([j, c, e]) => { if (i === j || Math.abs(a[1] - b[1]) > 0.2 || Math.abs(c[0] - e[0]) > 0.2) return;   // a to b runs along x, c to e along y
    if (c[0] > Math.min(a[0], b[0]) + 1 && c[0] < Math.max(a[0], b[0]) - 1 && a[1] > Math.min(c[1], e[1]) + 1 && a[1] < Math.max(c[1], e[1]) - 1) n++; })); return n;
}
for (const vert of [false, true]) {
  const tag = vert ? 'top to bottom: ' : 'left to right: ', S = mapLayout(STATIC, vert), L = mapLayout(LIVE, vert), across = vert ? L.x : L.y;
  if (L.N.length !== 9 || !apart(L) || !L.links.every(l => rightAngles(l.d))) throw new Error(tag + 'the live map must draw: nine boxes apart, right-angle lines');
  if (crossings(S) || crossings(L)) throw new Error(tag + `no line may cross another: ${crossings(S)} on the recorded map, ${crossings(L)} on the live one`);
  if (Math.abs(across['payment-router'] - across['acquirer-sim']) > 0.5) throw new Error(tag + 'a box called directly sits in line with its caller, even when a longer line also reaches it');
}
"""


def test_service_map_layout(tmp_path):
    """mapLayout on the recorded service map: callers before callees in both directions, no overlap, right-angle lines,
    the two cases a live map can add (a call back up the chain, a call that skips a column), and no line crossing another."""
    from sre_agent import topology
    _, js = _page_and_script()
    consts = re.search(r"const BW = [^\n]*;", js).group(0)
    fn = re.search(r"function mapLayout\(edges, vert\) \{.*?\n\}\n", js, re.S).group(0)
    f = tmp_path / "layout.js"
    f.write_text(f"{consts}\n{fn}\nconst STATIC = {json.dumps({k: sorted(v) for k, v in topology.STATIC_EDGES.items()})};\n{MAP_LAYOUT_CHECKS}")
    r = subprocess.run([_node(), str(f)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]


def test_service_numbers_come_only_from_whole_rows_of_the_agents_summary(tmp_path):
    """The map shows requests, errors and latency only where the case carries them: the preview of the services summary
    the agent collected (tools.preview_envelope: the first rows as JSON, cut at 700 characters)."""
    from sre_agent.tools import clip, preview_envelope
    row = lambda name, req, err, p90: {"service": name, "health": "Ok", "requests": req, "errors": err, "error_rate": err / req, "p50_ms": 283.256,
                                       "p90_ms": p90, "p99_ms": 2542.541, "link": "https://app.example.invalid/apm/" + name + "?" + "q" * 80}
    rows = [row("payment-router", 9371, 220, 836.77), row("merchant-storefront", 9958, 6, 866.452), row("acquirer-sim", 9987, 0, 805.009), row("ledger", 10038, 0, 4.816)]
    preview = preview_envelope(clip("o11y_get_apm_services_summary", rows).to_text())["preview"]
    assert len(preview) == 700 and '"acquirer-sim"' in preview and not preview.endswith("]")   # the third row is cut in half
    fn = re.search(r"function readSummary\(text\) \{.*?\n\}\n", _page_and_script()[1], re.S).group(0)
    f = tmp_path / "summary.js"
    f.write_text(f"let svcStats = {{}};\n{fn}\nreadSummary({json.dumps(preview)}); readSummary('not json'); readSummary(null);\nconsole.log(JSON.stringify(svcStats));")
    r = subprocess.run([_node(), str(f)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    stats = json.loads(r.stdout)
    assert set(stats) == {"payment-router", "merchant-storefront"}              # whole rows only; nothing for the services the preview lost
    assert stats["payment-router"]["requests"] == 9371 and stats["payment-router"]["errors"] == 220 and stats["payment-router"]["p90_ms"] == 836.77
