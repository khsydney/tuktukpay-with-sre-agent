"""Replayable evaluation set: one recorded fixture per war-room act plus a healthy baseline, a runner that replays the
agent's full pipeline (evidence → investigator → escalation → policy) against each fixture, and a deterministic score.

  record:  python -m sre_agent --provider anthropic --window=-5m eval-record --case act1     (live, while the act runs)
  replay:  python -m sre_agent --provider mock eval                                           (offline, no model)
           python -m sre_agent --provider anthropic eval --runs 3 --cases act1,act4           (real model, costs money)

Score per run (design section 9): root-cause service in the act's accepted set (`acts.root_cause_services`) AND the
proposed action in `acts.expected_actions()` → PASS. Also reported: whether the cited evidence contains the act's
proof events, and how many calls the replay could not serve (`misses`; free-form SPL or new metric arguments the
recording never saw). With the scripted mock a PASS proves the harness, not the reasoning (its rules encode the
answers). These are scenario regression results, not accuracy figures.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import tempfile
import time

from .acts import EVAL_CASES, Act, expected_actions

HERE = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = pathlib.Path(os.getenv("SRE_AGENT_EVAL_FIXTURES", str(HERE / "evals" / "cases")))
PROBE_WINDOWS_SPL = ("-15m", "-30m", "-1h")      # the windows the model chose in the 21 Oct cases (-1h most often)
PROBE_SERVICES = ("checkout-api", "risk-engine", "payment-router", "acquirer-sim", "ledger", "merchant-copilot",
                  "wallet-sim", "webhook-dispatcher", "shopping-agent")
PROBE_METRICS = [   # (metric, by, rollup, window, resolution_ms)
    ("tuktukpay.payments.count", ["payment.outcome", "payment.acquirer"], "rate", "-15m", 60000),
    ("tuktukpay.payments.count", ["payment.decline_reason"], "sum", "-15m", 60000),
    ("tuktukpay.payments.count", ["payment.decline_reason", "agent.id"], "delta", "-1h", 300000),
    ("tuktukpay.risk.decisions", ["risk.model_version", "risk.decision"], "sum", "-15m", 60000),
    ("tuktukpay.agent_mandates", ["mandate.block_reason"], "sum", "-15m", 60000),
    ("tuktukpay.copilot.tool_calls", ["gen_ai.tool.name"], "sum", "-15m", 60000),
    ("service.request.duration.ns.p90", ["sf_service"], "average", "-15m", 60000),
    ("service.request.count", ["sf_service"], "sum", "-15m", 60000),
    ("k8s.container.restarts", ["k8s.container.name"], "max", "-15m", 60000),
    ("container.memory.usage", ["k8s.container.name"], "max", "-15m", 60000),
    ("container.cpu.usage", ["k8s.container.name"], "average", "-15m", 60000),
    ("k8s.deployment.available", ["k8s.deployment.name"], "latest", "-15m", 60000),
]


def _quiet_sandbox() -> str:
    """Eval runs are not incidents: no audit records to HEC (HTTP Event Collector), no JSON lines on stderr, cases in a
    throw-away state directory, and no reads of the live war-room panel."""
    from . import audit, engine
    from . import case as cs
    audit._client = None
    audit.QUIET = True
    engine.CHAOS_URL = ""
    d = tempfile.mkdtemp(prefix="sre-eval-")
    cs.STATE_DIR = pathlib.Path(d) / "cases"
    return d


def incidents_for(act: Act) -> list[dict]:
    prefix = os.getenv("SRE_AGENT_DETECTOR_PREFIX", "TukTukPay [tuktukpay-demo]")
    return [{"detector": f"{prefix} {d}", "incident_id": f"manual-{act.name}", "severity": "Manual", "anomaly_state": "ANOMALOUS", "since": None}
            for d in act.detectors[:2]]


def accepted_actions(act: Act) -> set[str]:
    return expected_actions(act) | ({"inconclusive"} if act.name == "baseline" else set())


def _investigate(act: Act, mcp, splunk, provider: str, window: str) -> tuple[dict, dict]:
    from . import case as cs
    from .engine import run_investigation
    c = cs.new_case(os.getenv("DEPLOYMENT_ENVIRONMENT", "tuktukpay-demo"), incidents_for(act), source="eval")
    keep: dict = {}
    c = run_investigation(c, mcp, splunk, provider, "ask", marker_mode=False, window=window, keep=keep)
    return c, keep


# --------------------------------------------------------------------------- recording (live)
def probe(mcp, splunk, window: str) -> int:
    """Drive the same typed tools the model uses over the arguments it tends to choose, so the fixture can serve a
    replayed model's calls. Errors are ignored (a failed probe is simply not served later). The Splunk and the
    Observability Cloud probes run side by side (separate clients); each lane is sequential."""
    from concurrent.futures import ThreadPoolExecutor
    from .evidence import SPL_TEMPLATES
    from .toolset import ToolSet

    def lane(tag, calls_fn):
        ts, n = ToolSet(mcp, splunk, marker_mode=False), 0

        def run(name, args):
            nonlocal n
            ts.calls = ts.spl_calls = 0   # probes are not bound by the per-case budgets
            n += 1
            return ts.dispatch(f"probe-{tag}-{n}", name, {"why": "eval recording probe", **args})
        calls_fn(run)
        return n

    def spl(run):
        for w in sorted({window, *PROBE_WINDOWS_SPL}):
            for name in sorted(SPL_TEMPLATES):
                if name != "config_changes":   # markers are hidden in evaluation
                    run("spl_template", {"name": name, "window": w})

    def o11y(run):
        for w in sorted({window, "-15m"}):
            run("services_summary", {"window": w})
        for svc in PROBE_SERVICES:
            for tool in ("service_dependencies", "apm_errors_by_tag", "apm_latency_by_tag"):
                run(tool, {"service": svc, "window": "-15m"})
            ex = run("exemplar_traces", {"service": svc, "kind": "err", "window": "-15m"})
            try:
                items = json.loads(ex.split("\n", 1)[1].rsplit("\n</tool_data>", 1)[0])["data"].get("items", [])
            except (ValueError, KeyError, IndexError, AttributeError):
                items = []
            for it in items[:2]:
                tid = (it.get("item") or {}).get("traceId")
                if tid:
                    run("trace", {"trace_id": tid})
        for metric, by, rollup, w, res in PROBE_METRICS:
            run("metric_series", {"metric": metric, "by": by, "rollup": rollup, "window": w, "resolution_ms": res})

    with ThreadPoolExecutor(2) as pool:
        return sum(f.result() for f in [pool.submit(lane, "spl", spl), pool.submit(lane, "o11y", o11y)])


def record_case(name: str, provider: str, window: str, out_dir: pathlib.Path = FIXTURES) -> pathlib.Path:
    from .cli import _clients
    from .recorder import Recorder, leaks
    act = EVAL_CASES[name]
    _quiet_sandbox()
    mcp, splunk = _clients()
    rec = Recorder(mcp, splunk)
    t0 = time.time()
    try:   # the live investigation records the calls a model really makes; a failure still leaves the probes
        c, err = _investigate(act, mcp, splunk, provider, window)[0], ""
    except Exception as e:  # noqa: BLE001
        c, err = {}, f"{type(e).__name__}: {e}"[:200]
    t_inv = time.time() - t0
    n_probe = probe(mcp, splunk, window)
    inv, st = c.get("investigation") or {}, c.get("stats") or {}
    fx = rec.fixture({
        "case": act.name, "title": act.title, "window": window, "markers": "hidden",
        "detectors": [i["detector"] for i in incidents_for(act)],
        "recorded_run": {"provider": st.get("provider"), "model": st.get("model"), "root_cause_service": inv.get("root_cause_service"),
                         "proposed_action": (inv.get("proposed_action") or {}).get("type"), "cost_usd": round(st.get("cost_usd") or 0, 4),
                         "investigation_seconds": round(t_inv, 1), "probe_calls": n_probe, "error": err},
    })
    text = json.dumps(fx, indent=1, ensure_ascii=False)
    found = leaks(text)
    if found:   # never write a fixture the public repository must not hold
        raise SystemExit(f"fixture for {name} still contains {found} after sanitising; not written")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    path.write_text(text + "\n")
    return path


# --------------------------------------------------------------------------- replay and scoring
def load_fixture(name: str, fixtures: pathlib.Path = FIXTURES) -> dict:
    return json.loads((fixtures / f"{name}.json").read_text())


def _cited_texts(inv: dict, keep: dict) -> list[str]:
    ids = [e.get("evidence_id", "") for e in inv.get("evidence") or [] if isinstance(e, dict)]
    ids += [i for h in inv.get("hypotheses") or [] if h.get("status") == "validated" for i in h.get("evidence_ids") or []]
    sections, outputs = keep.get("sections") or {}, keep.get("tool_outputs") or {}
    return [sections.get(i) or outputs.get(i) or "" for i in ids]


def score(act: Act, inv: dict, keep: dict) -> dict:
    got_rc = str(inv.get("root_cause_service") or "").strip().lower()
    rc_ok = any(acc == got_rc or (acc != "none" and acc in got_rc) for acc in act.root_cause_services) or (act.name == "baseline" and got_rc == "")
    action = (inv.get("proposed_action") or {}).get("type", "inconclusive")
    action_ok = action in accepted_actions(act)
    proof = [e for e in act.evidence_events if e != "config.changed"]   # markers are hidden in evaluation
    if action in ("no_action", "inconclusive") or not proof:
        evidence = "n/a"
    else:
        texts = _cited_texts(inv, keep)
        evidence = "yes" if any(p in t for t in texts for p in proof) else "no"
    return {"case": act.name, "root_cause": got_rc or "-", "rc_ok": rc_ok, "action": action, "action_ok": action_ok,
            "evidence": evidence, "pass": rc_ok and action_ok}


GUESS_WORDS = re.compile(r"\b(probably|possibly|perhaps|maybe|might|likely|indicative|may have|could be|seems? to|appears? to)\b", re.I)
NUMBER_TOKEN = re.compile(r"[\w.:,/-]*\d[\w.:,/-]*")                                        # every run of characters that holds a digit
QUANTITY = re.compile(r"^\d[\d,]*(?:\.\d+)?(?:ms|s|sec|min|m|h|%|x|k|kb|mb|gb)?$", re.I)   # 1,170 · 2.5s · 15m · 5%; not 14:32, v3, p90 or a date
VERIFY_WORDS = re.compile(r"\b(verify|verif\w+|confirm\w*|check(?:s|ed|ing)?|watch(?:es|ed|ing)?)\b", re.I)   # whole words: not checkout-api


def quantities(text: str) -> int:
    """How many measured numbers a sentence holds. Clock times, dates and names such as v3 or p90 do not count; it
    cannot tell an identifier written as a bare number (a card range) from a count."""
    return sum(1 for tok in NUMBER_TOKEN.findall(str(text or "")) if QUANTITY.match(tok.strip(".,:;/-")))


def quality(inv: dict, fault: bool | None = None) -> dict:
    """Write-up score, beside the PASS/FAIL of `score` and never part of it: yes/no checks on the conclusion a reader
    sees. Three of them only make sense when an action is proposed (a fault was found); the other two always apply.
    Deterministic on purpose (no judge model): it catches a flat tree, a mechanism without numbers, a guessed impact,
    next steps without a verify step and a long or hedged title."""
    inv = inv or {}
    if fault is None:   # no ground truth given: go by the answer itself (a replayed act passes its own, so a missed fault scores low)
        fault = (inv.get("proposed_action") or {}).get("type", "inconclusive") not in ("no_action", "inconclusive")
    title, steps = str(inv.get("title") or ""), [str(x) for x in inv.get("next_steps") or []]
    checks: list[tuple[str, bool]] = []
    if fault:
        impact = str(inv.get("impact") or "")
        checks += [("tree depth", any(int(n.get("depth") or 1) >= 2 and n.get("status") in ("validated", "invalidated", "inconclusive")
                                      for n in inv.get("tree") or [] if isinstance(n, dict))),
                   ("mechanism numbers", quantities(inv.get("mechanism")) >= 2),
                   ("impact", quantities(impact) >= 1 and not GUESS_WORDS.search(impact))]
    checks += [("next steps", len(steps) >= 2 and bool(VERIFY_WORDS.search(steps[-1]))),
               ("title", 0 < len(title.split()) <= 12 and not GUESS_WORDS.search(title))]
    return {"score": sum(ok for _, ok in checks), "of": len(checks), "failed": [name for name, ok in checks if not ok]}


def run_case(name: str, provider: str, fixtures: pathlib.Path = FIXTURES) -> dict:
    from .recorder import ReplayMCP, ReplaySplunk
    fx = load_fixture(name, fixtures)
    act = EVAL_CASES[name]
    mcp, splunk = ReplayMCP(fx), ReplaySplunk(fx)
    t0 = time.time()
    try:
        c, keep = _investigate(act, mcp, splunk, provider, fx.get("window", "-15m"))
        inv, st, err = c.get("investigation") or {}, c.get("stats") or {}, ""
    except Exception as e:  # noqa: BLE001 — one broken case must not stop the table
        inv, st, keep, err = {}, {}, {}, f"{type(e).__name__}: {e}"[:200]
    row = score(act, inv, keep)
    row["quality"] = quality(inv, fault=any(a not in ("no_action", "inconclusive") for a in expected_actions(act)))
    row.update({"model": st.get("model") or provider, "provider": st.get("provider") or provider, "cost_usd": round(st.get("cost_usd") or 0, 4),
                "seconds": round(time.time() - t0, 1), "misses": len(mcp.misses) + len(splunk.misses),
                "miss_detail": (mcp.misses + splunk.misses)[:20], "error": err, "recorded_at": fx.get("recorded_at")})
    if err:
        row["pass"] = False
    return row


def available(fixtures: pathlib.Path = FIXTURES) -> list[str]:
    return [n for n in EVAL_CASES if (fixtures / f"{n}.json").exists()]


def _write_up(q: dict | None) -> str:
    if not q:
        return "-"
    return f"{q['score']}/{q['of']}" + (f" ({', '.join(q['failed'])})" if q["failed"] else "")


def table(rows: list[dict]) -> str:
    head = "| case | expected root cause | got | expected action | got | evidence | misses | model | cost | s | write-up | result |\n|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines = [head]
    for r in rows:
        act = EVAL_CASES[r["case"]]
        lines.append(f"| {r['case']} | {' / '.join(act.root_cause_services)} | {r['root_cause']}{'' if r['rc_ok'] else ' ✗'} | "
                     f"{' or '.join(sorted(accepted_actions(act)))} | {r['action']}{'' if r['action_ok'] else ' ✗'} | {r['evidence']} | "
                     f"{r['misses']} | {str(r['model']).replace('global.anthropic.', '')} | ${r['cost_usd']:.2f} | {r['seconds']} | {_write_up(r.get('quality'))} | "
                     f"{'PASS' if r['pass'] else 'FAIL'}{' (' + r['error'] + ')' if r.get('error') else ''} |")
    n, ok = len(rows), sum(r["pass"] for r in rows)
    cost = sum(r["cost_usd"] for r in rows)
    scored = [r["quality"] for r in rows if r.get("quality")]
    write_up = f" · write-up {sum(q['score'] for q in scored)}/{sum(q['of'] for q in scored)}" if scored else ""
    lines.append(f"\n{ok}/{n} PASS (scenario regression, not accuracy){write_up} · total ${cost:.2f}")
    return "\n".join(lines)


def run_all(provider: str, cases: list[str] | None = None, runs: int = 1, fixtures: pathlib.Path = FIXTURES) -> list[dict]:
    _quiet_sandbox()
    names = cases or available(fixtures)
    missing = [n for n in names if not (fixtures / f"{n}.json").exists()]
    if missing:
        raise SystemExit(f"no fixture for {missing} in {fixtures}; record with eval-record --case <name>")
    return [run_case(n, provider, fixtures) for _ in range(runs) for n in names]
