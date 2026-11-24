#!/usr/bin/env bash
# One-off install on the EC2 Splunk (30 Oct 2026): Splunk Connect for OTLP (OpenTelemetry Protocol) add-on,
# app `splunk-connect-for-otlp`, from the Splunk OpenTelemetry Collector release assets
# (https://github.com/signalfx/splunk-otel-collector/releases, e.g. v0.163.1/splunk-connect-for-otlp.tgz; the old repo
# splunk/splunk-connect-for-otlp and Splunkbase 8704 stop at 0.4.1). Installing adds the "OTLP" data input type only;
# no listener runs until an input `[splunk-connect-for-otlp://<name>]` is created (ports 4317/4318, SSL on by default,
# auth = existing HEC tokens as "Authorization: Splunk <token>").
# Same mechanics as install-aitk-2026-10-26.sh: package checked, uploaded with a checksum check, staged under
# $SPLUNK_HOME, installed through services/apps/local on 127.0.0.1:8089, admin password via a mode-600 netrc, one restart.
# Usage: splunk/ec2/install-otlp-addon-2026-10-30.sh <splunk-connect-for-otlp.tgz>
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
[ $# -eq 1 ] || { echo "usage: $0 <splunk-connect-for-otlp.tgz>" >&2; exit 2; }
PKG=$1
APP=splunk-connect-for-otlp
CREDS=$DIR/ec2_creds.txt
KEY=$HOME/.ssh/tuktukpay-splunk.pem
NAME=tuktukpay-splunk

top=$(tar -tzf "$PKG" | head -1 | cut -d/ -f1)
[ "$top" = "$APP" ] || { echo "$PKG: contains '$top', expected '$APP'" >&2; exit 1; }
echo "ok $APP  sha256 $(shasum -a 256 "$PKG" | cut -c1-16)…  $(du -h "$PKG" | cut -f1)"

WEB=$(sed -n 4p "$CREDS"); HOST=${WEB#https://}; HOST=${HOST%%[:/]*}
# line 4 may hold the bare IP; the certificate matches only the sslip.io name, so always use that for TLS
if [[ $HOST =~ ^[0-9.]+$ ]]; then PUBIP=$HOST; HOST="$(echo "$HOST" | tr . -).sslip.io"; else PUBIP=$(echo "${HOST%.sslip.io}" | tr - .); fi
ssh_() { ssh -i "$KEY" -o UserKnownHostsFile="$HOME/.ssh/known_hosts.$NAME" -o ConnectTimeout=10 "ec2-user@$PUBIP" "$@"; }

echo "== uploading to $HOST"
ssh_ 'mkdir -p -m 700 /tmp/otlpupload'
rsync --partial --timeout=60 -e "ssh -i $KEY -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME -o ConnectTimeout=10" \
  "$PKG" "ec2-user@$PUBIP:/tmp/otlpupload/$APP.tgz"
want=$(shasum -a 256 "$PKG" | cut -d' ' -f1)
got=$(ssh_ "sha256sum /tmp/otlpupload/$APP.tgz" | cut -d' ' -f1)
[ "$want" = "$got" ] || { ssh_ "rm -f /tmp/otlpupload/$APP.tgz"; echo "checksum mismatch after upload; removed it, run again" >&2; exit 1; }
echo "   uploaded (checksum matches)"
ssh_ 'rm -rf /tmp/otlpstage && mkdir -m 700 /tmp/otlpstage'
{ printf 'machine %s login %s password ' "$HOST" "$(sed -n 1p "$CREDS")"; sed -n 2p "$CREDS"; } \
  | ssh_ 'umask 077; cat > /tmp/otlpstage/netrc'

ssh_ HOST="$HOST" APP="$APP" bash -s <<'REMOTE'
set -euo pipefail
trap 'rm -rf /tmp/otlpstage /tmp/otlpupload' EXIT
STAGE=/opt/splunk/var/run/tuktukpay-stage
sudo install -d -o splunk -g splunk -m 700 $STAGE
C=(curl -sS --fail-with-body --netrc-file /tmp/otlpstage/netrc --resolve "$HOST:8089:127.0.0.1")
sudo install -o splunk -g splunk -m 600 /tmp/otlpupload/$APP.tgz $STAGE/$APP.tgz
echo "== install $APP"
"${C[@]}" -o /dev/null -w "apps/local $APP -> HTTP %{http_code}\n" --max-time 600 "https://$HOST:8089/services/apps/local" \
  --data-urlencode "name=$STAGE/$APP.tgz" -d filename=true -d update=true
sudo rm -f $STAGE/$APP.tgz
echo "== restart Splunkd"
sudo systemctl restart Splunkd
for i in $(seq 90); do
  "${C[@]}" -o /dev/null "https://$HOST:8089/services/server/info" 2>/dev/null && break; sleep 5
done
"${C[@]}" -o /dev/null -w 'server/info -> HTTP %{http_code}\n' "https://$HOST:8089/services/server/info"
"${C[@]}" "https://$HOST:8089/services/apps/local/$APP?output_mode=json" \
  | python3 -c 'import json,sys; e=json.load(sys.stdin)["entry"][0]; c=e["content"]; print(e["name"], c.get("version"), "disabled" if c["disabled"] else "enabled")'
"${C[@]}" -o /dev/null -w 'data/inputs/splunk-connect-for-otlp -> HTTP %{http_code}\n' \
  "https://$HOST:8089/services/data/inputs/splunk-connect-for-otlp?output_mode=json"
REMOTE
