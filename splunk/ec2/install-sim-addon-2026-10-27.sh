#!/usr/bin/env bash
# One-off install on the EC2 Splunk (27 Oct 2026): Splunk Infrastructure Monitoring Add-on (Splunkbase 5247, 1.3.1,
# app folder splunk_ta_sim; `| sim flow` search command + modular input), then ONE Splunkd restart. Same mechanics as
# install-aitk-2026-10-26.sh (resumable upload, checksum, staged under $SPLUNK_HOME, services/apps/local on
# 127.0.0.1:8089, admin password via a mode-600 netrc removed afterwards). Account (org, realm, token) is set by
# setup-sim-addon-2026-10-27.py afterwards.
# Usage: splunk/ec2/install-sim-addon-2026-10-27.sh <splunk-infrastructure-monitoring-add-on_131.tgz>
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
[ $# -eq 1 ] || { echo "usage: $0 <splunk-infrastructure-monitoring-add-on.tgz>" >&2; exit 2; }
PKGS=("$1")
APPS=(splunk_ta_sim)
CREDS=$DIR/ec2_creds.txt
KEY=$HOME/.ssh/tuktukpay-splunk.pem
NAME=tuktukpay-splunk

for i in 0; do   # right file for each slot: its top-level folder is the expected app
  top=$(tar -tzf "${PKGS[$i]}" | head -1 | cut -d/ -f1)
  [ "$top" = "${APPS[$i]}" ] || { echo "${PKGS[$i]}: contains '$top', expected '${APPS[$i]}'" >&2; exit 1; }
  echo "ok ${APPS[$i]}  sha256 $(shasum -a 256 "${PKGS[$i]}" | cut -c1-16)…  $(du -h "${PKGS[$i]}" | cut -f1)"
done

WEB=$(sed -n 4p "$CREDS"); HOST=${WEB#https://}; HOST=${HOST%%[:/]*}
# line 4 may hold the bare IP; the certificate matches only the sslip.io name, so always use that for TLS
if [[ $HOST =~ ^[0-9.]+$ ]]; then PUBIP=$HOST; HOST="$(echo "$HOST" | tr . -).sslip.io"; else PUBIP=$(echo "${HOST%.sslip.io}" | tr - .); fi
ssh_() { ssh -i "$KEY" -o UserKnownHostsFile="$HOME/.ssh/known_hosts.$NAME" -o ConnectTimeout=10 "ec2-user@$PUBIP" "$@"; }

echo "== uploading to $HOST (resumable: a dropped connection continues where it stopped)"
ssh_ 'mkdir -p -m 700 /tmp/aitkupload && df -h /opt | tail -1'
for i in 0; do
  for try in 1 2 3 4 5 6 7 8; do
    rsync --partial --append --timeout=60 -e "ssh -i $KEY -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME -o ConnectTimeout=10 -o ServerAliveInterval=15" \
      "${PKGS[$i]}" "ec2-user@$PUBIP:/tmp/aitkupload/${APPS[$i]}.tgz" && break
    echo "   upload of ${APPS[$i]} interrupted (try $try); resuming in 20 s"; sleep 20
    [ $try -lt 8 ] || { echo "upload failed 8 times; partial file kept in /tmp/aitkupload for the next run" >&2; exit 1; }
  done
  want=$(shasum -a 256 "${PKGS[$i]}" | cut -d' ' -f1)   # macOS openrsync has --append but no --append-verify: check the result
  got=$(ssh_ "sha256sum /tmp/aitkupload/${APPS[$i]}.tgz" | cut -d' ' -f1)
  [ "$want" = "$got" ] || { ssh_ "rm -f /tmp/aitkupload/${APPS[$i]}.tgz"; echo "checksum mismatch after upload of ${APPS[$i]}; removed it, run again" >&2; exit 1; }
  echo "   uploaded ${APPS[$i]} (checksum matches)"
done
ssh_ 'rm -rf /tmp/aitkstage && mkdir -m 700 /tmp/aitkstage'
{ printf 'machine %s login %s password ' "$HOST" "$(sed -n 1p "$CREDS")"; sed -n 2p "$CREDS"; } \
  | ssh_ 'umask 077; cat > /tmp/aitkstage/netrc'

APPS_CSV=$(IFS=,; echo "${APPS[*]}")   # one word: ssh joins its arguments into a single remote command line
ssh_ HOST="$HOST" APPS_CSV="$APPS_CSV" bash -s <<'REMOTE'
set -euo pipefail
trap 'rm -rf /tmp/aitkstage' EXIT   # the netrc; the uploads in /tmp/aitkupload go once every app is installed
STAGE=/opt/splunk/var/run/tuktukpay-stage
sudo install -d -o splunk -g splunk -m 700 $STAGE
C=(curl -sS --fail-with-body --netrc-file /tmp/aitkstage/netrc --resolve "$HOST:8089:127.0.0.1")
APPS=${APPS_CSV//,/ }
for app in $APPS; do
  sudo install -o splunk -g splunk -m 600 /tmp/aitkupload/$app.tgz $STAGE/$app.tgz
  echo "== install $app"
  "${C[@]}" -o /dev/null -w "apps/local $app -> HTTP %{http_code}\n" --max-time 900 "https://$HOST:8089/services/apps/local" \
    --data-urlencode "name=$STAGE/$app.tgz" -d filename=true -d update=true
  sudo rm -f $STAGE/$app.tgz
done
rm -rf /tmp/aitkupload
echo "== restart Splunkd"
sudo systemctl restart Splunkd
for i in $(seq 90); do
  "${C[@]}" -o /dev/null "https://$HOST:8089/services/server/info" 2>/dev/null && break; sleep 5
done
"${C[@]}" -o /dev/null -w 'server/info -> HTTP %{http_code}\n' "https://$HOST:8089/services/server/info"
for app in $APPS; do
  "${C[@]}" "https://$HOST:8089/services/apps/local/$app?output_mode=json" \
    | python3 -c 'import json,sys; e=json.load(sys.stdin)["entry"][0]; c=e["content"]; print(e["name"], c.get("version"), "disabled" if c["disabled"] else "enabled")'
done
REMOTE
