# sre-agent — TukTukPay AI SRE agent (prototype)

Alert-triggered investigation and policy-gated remediation over the two Splunk data planes: the Splunk Observability
Cloud MCP (Model Context Protocol) gateway (`o11y_*` tools) and the Splunk platform (`splunk_run_query`, through the
Splunk MCP Server app when installed, otherwise splunkd REST with the same tool names). Design, evidence and the
specialist review (design notes not published).

**What it is not:** it does not poll raw metrics into an LLM. Detectors decide *when*; the model decides *why*; a
static catalogue, a policy engine and a separate executor decide *whether* and *how*; a fixed query decides *whether it
worked*. Default mode is investigate-and-propose (`--policy ask`).

## Run

```bash
cd services/sre-agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# `python -m sre_agent` loads unset names from the repo-root .env and services/sre-agent/.env (both git-ignored),
# e.g. ANTHROPIC_API_KEY=... — put secrets there, never on a command line.
export SPLUNK_O11Y_TOKEN=...                                   # Observability Cloud API token (read use only)
export SPLUNK_PLATFORM_CREDS_FILE=../../splunk/ec2/sre_agent_creds.txt   # least-privilege `sre_agent` user (search on index=tuktukpay only)
export SRE_AUDIT_CREDS_FILE=../../splunk/ec2/sre_agent_creds.txt         # audit events → index tuktukpay_agent_audit (write-only HEC token)
export CHAOS_URL=http://<chaos-controller-lb>                  # remediation back end (stands for config/canary/pool changes)
export SRE_AGENT_PROVIDER=mock                                 # mock (scripted, labelled) | anthropic (ANTHROPIC_API_KEY) | bedrock (AWS creds, ap-southeast-1)
export SRE_AGENT_MODEL=claude-sonnet-5-5                       # default; escalates to SRE_AGENT_ESCALATE_MODEL (claude-opus-5-5) when the answer is weak
export MOCK_JEV=1                                             # or TYPESAFE_API_KEY for the real advisory gate
# TLS is verified by default (the EC2 Splunk has a Let's Encrypt certificate); SPLUNK_PLATFORM_VERIFY_TLS=false opts out and is audited.

.venv/bin/python -m sre_agent tools                                        # what the model may call / choose
.venv/bin/python -m sre_agent investigate --detector "payment-router error rate"   # live incident → case awaiting approval
.venv/bin/python -m sre_agent investigate --act act6 --no-marker            # scenario without a live alert, markers hidden
.venv/bin/python -m sre_agent cases
.venv/bin/python -m sre_agent approve C-… <plan_hash> --dry-run             # then without --dry-run to execute + verify
.venv/bin/python -m sre_agent close C-… --reason "…"                        # operator close (escalated / inconclusive cases)
.venv/bin/python -m sre_agent watch --interval 30                           # poll open incidents, open cases, investigate
.venv/bin/python -m pytest -q tests
```

Every record the agent writes (`sre.case.*`, `sre.llm.call`, `remediation.*`, `approval.*`) is a JSON line on
stderr; set `SRE_AUDIT_HEC_URL` / `SRE_AUDIT_HEC_TOKEN` to send the same records to a dedicated index
(`tuktukpay_agent_audit`). Cases are JSON files under `SRE_AGENT_STATE_DIR` (default `~/.local/share/tuktukpay-sre-agent`).

## Hypothesis ledger (single loop, live tree)

Since 27 Nov 2026 the default loop keeps a ledger (`sre_agent/ledger.py`). The model records each hypothesis with
`hypothesis_open` and its result with `hypothesis_verdict` while it works, so the tree is drawn live (events
`sre.tree.reset`, `sre.tree.branch`, `sre.tree.verdict`) and goes up to three levels deep without sub-agents.

- **Code checks every validated verdict and answers at once:** its evidence ids must include a metric-or-trace signal
  and a log signal, and a deciding signal last seen more than `SRE_AGENT_STALE_MIN` minutes ago is treated as left over
  from an earlier event. The model can add the missing evidence and record the verdict again.
- **One level of "why":** when an action is proposed, at least one narrower hypothesis under the validated one needs a
  verdict (which partner, host, card range, version, setting or change). A missing ledger or level gets one corrective
  round; what is still missing is kept on the case as `tree_gap`.
- **Conclusion fields:** the answer carries `title`, `mechanism` and `next_steps` beside the earlier fields, and
  `tree` with every node.
- Ledger calls do not use the tool budget. A narrower hypothesis left inconclusive does not start the re-run with the
  stronger model; a top-level one still does.

| Setting | Default | Meaning |
| --- | --- | --- |
| `SRE_AGENT_LEDGER` | `on` | `off` brings back the plain loop of before 27 Nov 2026 |
| `SRE_AGENT_LEDGER_NODES` | `12` | most hypotheses per case |
| `SRE_AGENT_STALE_MIN` | `5` | minutes after which a deciding signal counts as left over |
| `SRE_AGENT_MAX_INPUT_TOKENS` | `300000` | prompt tokens per case, cached reads included (60000 before the ledger) |
| `SRE_AGENT_MARKERS` | `hide` | `show` lets the model read config-change events (`config.changed`) and name the change that triggered a fault; the evaluation always hides them |

Two limits of the model API (application programming interface), found on 27 Nov 2026: the strict tools and the answer
schema compile into one grammar, and the request is refused when it grows too large, so `metric_series`,
`spl_template` and the two ledger tools are not strict (code validates their arguments) and the loop retries once with
no strict tool if the refusal comes back; and the growing conversation is cached with a top-level `cache_control`,
which only the Anthropic API accepts (not Amazon Bedrock).

## Alert correlation along the service map

Two levels, both computed by code (no extra agent; the investigator only judges the result):

- **Join** (`trigger.py`): a new alert joins an open case of the last 180 s (`SRE_AGENT_CORRELATION_S`) when its
  services and the case's are on one caller → callee path of at most 2 hops (`SRE_AGENT_TOPOLOGY_HOPS`). Siblings
  (two callers of ledger) and queue hops (Redis) never join. Kubernetes alerts get their service from
  `k8s.container.name` / `k8s.pod.name` / `k8s.deployment.name`; an alert that names no service joins as before
  (`unscoped`). Each joined incident stores `joined` (rule, path, hops, gap); the case stores the furthest-downstream
  alerting services as `topology.root_candidates`, plus `topology.check_next`: silent services downstream of them,
  nearest first (Act 1: `payment-router → acquirer-sim`; the router records the acquirer timeouts, so acquirer-sim
  never alerts). The engine recomputes `topology` for every case, console ones included.
- **Possible ties** (`ties.py`): when an investigation starts, other cases of the last 30 min
  (`SRE_AGENT_TIE_LOOKBACK_S`, any state) on such a path are recorded on both cases as suggestions with a direction
  (`likely_cause_of` / `likely_symptom_of` / `same_service`). Never merged by code: the console brief shows
  **Merge into this case** / **Not related** (`POST /api/tie/merge`, `/api/tie/dismiss`; the verdict is kept and
  audited). Eval cases never tie. The tie box is computed when shown (`GET /api/ties/<case>`): one tie per alert
  set (re-fires collapse into the newest case), the case's current state and whether its alert still fires, and
  open alerts on a related service that no active case owns, with **Add to this case** (`POST /api/tie/attach`).

The graph comes from `o11y_get_apm_service_dependencies` (`topology.py`, cached 10 min, `SRE_AGENT_TOPOLOGY_CACHE_S`),
refreshed by `watch` and the console; investigations only read the cache and fall back to the static map recorded on
EKS (Amazon Elastic Kubernetes Service) on 21 Oct 2026.

## Automatic start (grouped signals)

With `SRE_AGENT_AUTOSTART=1` (default off) the console starts the agent itself (`sre_agent/grouping.py`). Model findings
(Splunk alert "TukTukPay - detection modules write findings", `source=http:tuktuk_detection` in `index=tuktukpay`) and
detector alerts are both signals, and either can start a case. The first signal opens a group; for 60 s
(`SRE_AGENT_GROUP_WAIT_S`) others on the same call path join it; then one case starts with all of them, unless they have
all cleared (a finding counts as live for 600 s, `SRE_AGENT_FINDING_TTL_S`; an alert that cleared in the wait and fires again within 300 s, `SRE_AGENT_FLAP_S`, counts as live too). A later signal on an active case's path is added to
that case once the run has concluded, and the console asks for a re-run. Limits: `SRE_AGENT_MAX_OPEN_CASES` (2),
`SRE_AGENT_COOLDOWN_S` (900) per detector or origin. Alerts already open when the console starts do not start a case.
A signal naming only services in `SRE_AGENT_EVIDENCE_ONLY` (default `shopping-agent`) can join a group or case but cannot open one. The console must be running; the proposal still waits for a human.

## Agent console (war-room view)

Layout (1 Nov 2026): alerts and cases on the left (cases awaiting approval first); centre tabs **Hypothesis tree** (since 27 Nov 2026 a canvas you can drag and zoom, drawn live from the ledger: alert on top, hypotheses with status researching, verified, ruled out, inconclusive or not tested, then a Conclusion and a Next steps node; while a case runs the view follows the hypothesis being worked on, and a drag or scroll hands the view to you; a finished case opens on the path to the root cause; the code checks and evidence of a node on click), **Topology** (service map from `/api/topology`, cached, never calls the gateway, drawn as a tree from the top down: callers above, what they call below; one box per service with a picture, its role, its error rate and p90 (90th percentile) latency from the services summary the agent collected, and a status that comes only from the case's own data; the path from the alerting service to the root cause is highlighted; a click opens the service's card beside the box, and the map does not move) and **Agent trace** (the run as steps on a rail: who acted, what happened, how long; each result on its request with the raw MCP (Model Context Protocol) calls nested under it, which can be hidden; it follows new steps only while you are at the bottom); the brief on the right with the decision first. The page follows the war-room design (colour codes of https://www.splunk.com/). `?facilitator=1` shows the injected faults, hidden by default because the flag names give the answer away. The 👍/👎 under the brief writes `sre.case.feedback` to the audit trail.


The brief redraws itself when a case changes (merge, alert added, close, mitigated), and the sidebar refreshes every
10 s. **Clear** on Open alerts / Recent cases hides finished cases and the alerts open now (cases in an active state
always stay; a new firing shows again); "N hidden · Show" restores. Nothing is deleted (`console-view.json` in the
state directory's parent).

```bash
cd services/sre-agent && .venv/bin/python -m sre_agent --provider anthropic console --port 8790   # always http://127.0.0.1:8790/
```

Open the URL; it stays the same across restarts, so it can be bookmarked (127.0.0.1 only, no token, so any local process can use it; requests from another site or with another Host are refused).
- **Status strip:** approval rate (5 min), checkout-api p90, payment-router error rate, open alerts, faults injected by the war-room panel (refreshed every 30 s).
- **Start an investigation** two ways: type a symptom ("Merchants report card payments failing at checkout…") or pick a preset chip and press **Investigate**; or press **Triage** on an open alert. Symptom words are mapped to services so the evidence includes their dependencies and traces; question cases are never auto-remediated.
- **Agent reasoning (live):** elapsed time on every line; evidence collected by code; every raw MCP (Model Context Protocol) call — `o11y ▸ o11y_get_apm_services_summary`, `splunk ▸ splunk_run_query` — with its exact arguments and milliseconds; each model step with its reasoning summary and the `why` of the next tool; a final "Done: N MCP calls, tokens, $, seconds".
- **War-room brief:** category, headline, customer impact, root cause, onset, **page team** (`catalogue.OWNERS`), cause chain, evidence per signal, ruled out, and the recommended action (real-world wording, policy tier, exact request, verification) with **Approve / Reject**; executor and verification status appear under it.
- **Follow-up questions** below the reasoning (refused while the investigation is still running).
- **Stop** (next to Ask, shown while an investigation or follow-up runs): ends it at the next checkpoint (between evidence sections, before every model and tool call, before the Opus re-run); the call in flight finishes first. The case is closed as "stopped by <user>@console" with the spend so far, nothing proposed or executed. An approved action that is executing is never stopped halfway. Ctrl-C in `investigate` ends the case the same way. Typing `rerun` in the Ask box starts a real re-run.
- **When the Opus re-run fails** the first model's answer is kept and the brief says so; a 403 from the model API is retried once. A case that ends without an answer (stopped, escalated, inconclusive) shows that in the brief instead of "Investigating…".
- Robustness: a case that cannot connect is escalated with the error shown; a second click on the same alert reopens its case; console cases left `open` or `investigating` by a stopped console are closed / escalated at the next start.

## Where to see it

- **Agent console** (above): the live, conversational view; approve or reject there.
- **Terminal:** the same flow from the CLI (`investigate`, `approve <case> <plan_hash>`).
- **Control tower → AI → AI SRE agent** (`#/sre`, app 1.1.0 on the EC2 Splunk): read-only page over `index=tuktukpay_agent_audit` — tiles (cases, awaiting approval, mitigated, escalated, median cost, median time to proposal), the case table, and per case the narrative, hypotheses with verdicts, proposed action with its real-world equivalent, the policy decision, the exact executor request, the verification query and a timeline. Source: `splunk/control-tower/app-src/12c-pages-sre.js`. Needs a user who can read the audit index (admin); the agent's own `sre_agent` user cannot.

## Layout

| File | Role |
|---|---|
| `o11y_mcp.py` | gateway client (JSON-RPC over streamable HTTP; `arguments: {"params": …}`) |
| `splunk_platform.py` | `splunk_run_query` / `splunk_get_indexes` over REST or the MCP Server app |
| `redact.py`, `tools.py` | redaction of string leaves (JSON numbers untouched), SPL guard that pins the index and rebuilds the first stage, injection interceptor, result clipping and row scrubbing, SignalFlow downsampling |
| `evidence.py`, `toolset.py` | code-built evidence bundle; the nine typed tools offered to the model (`metric_series` builds the SignalFlow program in code; windows are an enum), per-case call and search caps |
| `investigator.py`, `mock_sre.py`, `cost.py` | Anthropic SDK loop (adaptive thinking, `output_config.effort`, prompt caching, structured `Investigation`, token and wall-clock budgets); labelled scripted mock; verified 5.5-generation price table with cache pricing |
| `catalogue.py`, `policy.py`, `jev_gate.py` | static action catalogue and tiers; deterministic decision; advisory Jev gate (fails closed) |
| `executor.py`, `engine.py` | typed actions; re-corroboration of state immediately before acting; two-layer verification whose window starts after the fix and needs two clean passes; fail-closed case flow (errors → `escalated`, write-ahead marker before execution, plan hash and expiry checked on every path) |
| `case.py`, `trigger.py`, `audit.py`, `cli.py` | state machine and store; incident poller (dedupe, two-poll confirmation, cool-down, correlation); audit events; CLI |
| `topology.py`, `ties.py` | service-map graph (live, cached, static fallback; services from Kubernetes dimensions); possible ties between cases, operator merge and dismiss |
| `acts.py` | ground truth per act for evaluation (never shown to the model), accepted root-cause services, baseline case |
| `recorder.py`, `evals.py`, `evals/` | fixture recording with sanitising, replay clients, scorer and pass/fail table; `evals/record_all.sh` records every case live |
| `../../k8s/sre-executor-rbac.yaml` | ServiceAccount and Role for the executor |

## Act-by-act evaluation

Run each act on EKS, wait about 270 s, then investigate it (policy `ask`, nothing executed; use your own state dir):

```bash
curl -s -X POST <war-room URL>/scenarios/act1 && sleep 270
SRE_AGENT_STATE_DIR=/tmp/sre-eval .venv/bin/python -m sre_agent --provider anthropic --policy ask --window=-5m investigate --act act1
```

The last line prints `action check: ... -> PASS/FAIL` against `acts.expected_actions()` (`no_action` for Act 4; the flag
revert or the Kubernetes roll-back for Acts 6 and 7). Put a baseline gap of 2–3 minutes between acts: in the
21 Oct run Act 7 straight after Act 6 blamed the leftover ledger leak. Results of 21 Oct, the detectors that woke the
agent per act and the detector fixes they led to (design notes, section 5.2).

## Replayable evaluation set

One recorded fixture per act plus a healthy baseline in `evals/cases/<case>.json`. A fixture holds every
Observability Cloud and Splunk call one live investigation made, plus probes of the tools and windows the model tends
to choose (every log template at -15m/-30m/-1h, the APM (Application Performance Monitoring) tools per service, common
metric queries). Results are sanitised before they are written (redaction as for the model, plus IP addresses, AWS host
names, account numbers and home paths); the tests fail if a committed fixture still holds any of them.

```bash
# record (live, changes the chaos flags; about 12 minutes per case; not while an act is being shown)
CHAOS=http://<war-room panel> caffeinate -i evals/record_all.sh            # all nine, or CASES="act1 act2"
.venv/bin/python -m sre_agent --provider anthropic --window=-5m eval-record --case act1   # one case, act already running

# replay (offline: no Observability Cloud, no Splunk, no audit records, no panel reads)
.venv/bin/python -m sre_agent --provider mock eval                          # harness check, no model
.venv/bin/python -m sre_agent --provider anthropic -v eval --runs 3 --cases act1,act4   # real model, costs money; -v lists misses
```

PASS = the root-cause service is in the act's accepted set (`acts.root_cause_services`, e.g. acquirer-sim for Act 1,
not the alerting payment-router) **and** the proposed action is in `acts.expected_actions()` (baseline: `no_action` or
`inconclusive`). The table also shows whether the cited evidence contains the act's proof events and how many calls
the fixture could not serve (`misses`: free-form SPL or metric arguments the recording never saw; `-v` lists them).
A mock PASS proves the harness, not the reasoning (its rules encode the answers). Scenario regression results, not
accuracy figures.

The `write-up` column is a separate score that never changes PASS or FAIL (`evals.quality`): yes/no checks on what a
reader sees. Three apply when an action is proposed (the tree has a tested second level; the mechanism quotes two
numbers; the impact has a number and no guess words) and two always (the next steps end with a verify step; the title
has at most 12 words and no guess words). Failed checks are listed in brackets.

## Honest limits of the prototype

- No automatic reversal exists: a failed verification leaves the change in place and escalates (re-enable is deliberately not in the catalogue).
- Approver identity is a CLI flag on the operator's laptop, not an authenticated principal; the design names the production fix.
- Runs on the laptop; Kubernetes actions use `kubectl --as=system:serviceaccount:tuktukpay:sre-executor` so the
  permission boundary is visible, but the underlying credential is the deployer's.
- The Observability Cloud token is the org API token (a dedicated read-only token needs an org administrator).
- The Splunk lane uses the `sre_agent` user (created 21 Oct by `splunk/ec2/setup-sre-agent-2026-10-21.py`: capability `search` only, `index=tuktukpay` only, cannot read `_audit`, `_internal` or the audit index — verified); the SPL guard pins `index=tuktukpay` in code as well.
- The executor's Kubernetes identity exists (`k8s/sre-executor-rbac.yaml` applied 21 Oct; `kubectl auth can-i` verified: patch only the 11 app deployments, no delete, no secrets, no RBAC, no postgres/redis/chaos-controller), but the prototype still runs on the laptop with `--as` impersonation.
- Jev thresholds are untuned; `MOCK_JEV=1` and `--provider mock` force recommend-only mode and are stamped on every record.
- The Anthropic path runs live (21 Oct: every act on tuktukpay-eks, Sonnet 5.5 with escalation to Opus 5.5; see "Act-by-act evaluation"). The Bedrock path is written from the SDK reference but not exercised.
- Any result on the seven acts is a scenario regression result, not an accuracy figure.
