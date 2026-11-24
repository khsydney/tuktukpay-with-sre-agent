#!/usr/bin/env bash
# Record the replayable eval fixtures live: for each case start the act on the war-room panel, let it build up,
# record (one live investigation plus probes of the tools the model tends to call), then return to baseline and wait.
#
#   CHAOS=http://<war-room panel> caffeinate -i services/sre-agent/evals/record_all.sh
#
# Needs the agent's usual environment (SPLUNK_O11Y_TOKEN, SPLUNK_PLATFORM_CREDS_FILE or SPLUNK_MCP_CREDS_FILE, model
# key in .env). Changes the chaos flags on the live stack: do not run it while an act is being shown.
# Settings: PROVIDER (anthropic), WINDOW (-5m), WARMUP seconds per act (270), GAP seconds of baseline between acts
# (150; Act 7 straight after Act 6 blames the leftover leak), CASES (all nine, baseline first).
set -euo pipefail
: "${CHAOS:?set CHAOS to the war-room panel URL}"
PROVIDER=${PROVIDER:-anthropic}
WINDOW=${WINDOW:--5m}
WARMUP=${WARMUP:-270}
GAP=${GAP:-150}
CASES=${CASES:-"baseline act1 act2 act3 act4 act4b act5 act6 act7"}
cd "$(dirname "$0")/.."

ts() { date -u +%H:%M:%SZ; }
set_scenario() { curl -fsS -m 20 -X POST "$CHAOS/scenarios/$1" >/dev/null; }

trap 'echo "$(ts) interrupted: returning the panel to baseline"; set_scenario baseline || true' INT TERM
for c in $CASES; do
  echo "$(ts) == $c: start scenario, warm up ${WARMUP}s"
  set_scenario "$c"
  sleep "$WARMUP"
  echo "$(ts) == $c: recording"
  .venv/bin/python -m sre_agent --provider "$PROVIDER" --window="$WINDOW" eval-record --case "$c" || echo "$(ts) !! recording $c failed"
  set_scenario baseline
  echo "$(ts) == $c: back to baseline, ${GAP}s gap"
  sleep "$GAP"
done
echo "$(ts) done; panel left at baseline"
