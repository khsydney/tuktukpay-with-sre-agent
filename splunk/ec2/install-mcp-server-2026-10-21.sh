#!/usr/bin/env bash
# One-off install of the Splunk MCP (Model Context Protocol) Server app (Splunkbase 7931, v2.0.0) on the EC2 Splunk.
# Checks the tgz checksum, stages it under $SPLUNK_HOME (splunkd cannot read /tmp), installs it through
# services/apps/local on 127.0.0.1:8089 (TLS verified against the Let's Encrypt name), restarts Splunkd and waits.
# The admin password reaches the instance on stdin into a mode-600 netrc file that is removed afterwards.
# Then run: TUKTUK_STACK=ec2 python3 -I splunk/ec2/setup-mcp-server-2026-10-21.py
# Usage: splunk/ec2/install-mcp-server-2026-10-21.sh [path/to/splunk-mcp-server_200.tgz]
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
TGZ=${1:-$HOME/Downloads/splunk-mcp-server_200.tgz}
SHA=7275e61a685c85b2f60e5249e012d7107a3946c1f504671dc2bad0b10f8fb42c
CREDS=$DIR/ec2_creds.txt
KEY=$HOME/.ssh/tuktukpay-splunk.pem
NAME=tuktukpay-splunk

[ "$(shasum -a 256 "$TGZ" | cut -d' ' -f1)" = "$SHA" ] || { echo "checksum mismatch for $TGZ" >&2; exit 1; }
WEB=$(sed -n 4p "$CREDS"); HOST=${WEB#https://}; HOST=${HOST%%[:/]*}
PUBIP=$(echo "${HOST%.sslip.io}" | tr - .)
ssh_() { ssh -i "$KEY" -o UserKnownHostsFile="$HOME/.ssh/known_hosts.$NAME" -o ConnectTimeout=10 "ec2-user@$PUBIP" "$@"; }

echo "== staging on $HOST"
ssh_ 'rm -rf /tmp/mcpstage && mkdir -m 700 /tmp/mcpstage'
{ printf 'machine %s login %s password ' "$HOST" "$(sed -n 1p "$CREDS")"; sed -n 2p "$CREDS"; } \
  | ssh_ 'umask 077; cat > /tmp/mcpstage/netrc'
scp -q -i "$KEY" -o UserKnownHostsFile="$HOME/.ssh/known_hosts.$NAME" "$TGZ" "ec2-user@$PUBIP:/tmp/mcpstage/app.tgz"

ssh_ HOST="$HOST" bash -s <<'REMOTE'
set -euo pipefail
trap 'rm -rf /tmp/mcpstage' EXIT
STAGE=/opt/splunk/var/run/tuktukpay-stage
sudo install -d -o splunk -g splunk -m 700 $STAGE
sudo install -o splunk -g splunk -m 600 /tmp/mcpstage/app.tgz $STAGE/splunk-mcp-server.tgz
C=(curl -sS --fail-with-body --netrc-file /tmp/mcpstage/netrc --resolve "$HOST:8089:127.0.0.1")
echo "== install app"
"${C[@]}" -o /dev/null -w 'apps/local -> HTTP %{http_code}\n' "https://$HOST:8089/services/apps/local" \
  --data-urlencode "name=$STAGE/splunk-mcp-server.tgz" -d filename=true -d update=true
sudo rm -f $STAGE/splunk-mcp-server.tgz
echo "== restart Splunkd"
sudo systemctl restart Splunkd
for i in $(seq 60); do
  "${C[@]}" -o /dev/null "https://$HOST:8089/services/server/info" 2>/dev/null && break; sleep 5
done
"${C[@]}" -o /dev/null -w 'server/info -> HTTP %{http_code}\n' "https://$HOST:8089/services/server/info"
"${C[@]}" "https://$HOST:8089/services/apps/local/Splunk_MCP_Server?output_mode=json" \
  | python3 -c 'import json,sys; c=json.load(sys.stdin)["entry"][0]["content"]; print("Splunk_MCP_Server", c["version"], "disabled" if c["disabled"] else "enabled")'
REMOTE
