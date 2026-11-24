#!/usr/bin/env bash
# Rotate the shared AI Toolkit container token (api_token) on the EC2 Splunk. Run it whenever the token may have been exposed.
# 1 Nov 2026. Three copies must change together: Splunk storage/passwords (dltk_kubernetes:api_token), /root/sreagent/env
# (tuktuk-sre) and /root/detect/env (tuktuk-detect). The new token is generated on the instance and only ever sits in
# root-only files; the admin password reaches the instance on stdin into a mode-600 netrc file. Both containers restart.
# Prints HTTP status codes only. Expect: new=200 old=401 on both ports. Env backups are removed only when that holds.
# Usage: bash splunk/ec2/rotate-container-token-2026-11-01.sh
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd); CREDS=$DIR/ec2_creds.txt; KEY=$HOME/.ssh/tuktukpay-splunk.pem
HOST=splunk.example.com; IP=203.0.113.10
ssh_() { ssh -i "$KEY" -o ConnectTimeout=10 "ec2-user@$IP" "$@"; }
{ printf 'machine %s login %s password ' "$HOST" "$(sed -n 1p "$CREDS")"; sed -n 2p "$CREDS"; } | ssh_ 'umask 077; cat > /tmp/rot.netrc'
ssh_ sudo HOST=$HOST bash -s <<'REMOTE'
set -euo pipefail
umask 077
trap 'rm -f /tmp/rot.netrc /root/.tok-new /root/.tok-new.hdr /root/.tok-old.hdr' EXIT
if docker top tuktuk-sre -o args | grep -q aitk_runner; then echo "an agent run is in flight: try again later" >&2; exit 1; fi
cp -p /root/sreagent/env /root/sreagent/env.bak-rot; cp -p /root/detect/env /root/detect/env.bak-rot
printf 'Authorization: %s\n' "$(grep -E '^api_token=' /root/sreagent/env | cut -d= -f2-)" > /root/.tok-old.hdr
openssl rand -hex 32 | tr -d '\n' > /root/.tok-new
printf 'Authorization: %s\n' "$(cat /root/.tok-new)" > /root/.tok-new.hdr
for f in /root/sreagent/env /root/detect/env; do
  python3 -I - "$f" <<'PY'
import sys
p = sys.argv[1]; t = open("/root/.tok-new").read()
L = [("api_token=" + t) if l.startswith("api_token=") else l for l in open(p).read().split("\n")]
open(p, "w").write("\n".join(L))
PY
done
curl -sS --netrc-file /tmp/rot.netrc --resolve "$HOST:8089:127.0.0.1" -o /dev/null -w "storage/passwords update -> HTTP %{http_code}\n" \
  "https://$HOST:8089/servicesNS/nobody/Splunk_ML_Toolkit/storage/passwords/dltk_kubernetes%3Aapi_token%3A" --data-urlencode password@/root/.tok-new
docker stop -t 20 tuktuk-sre tuktuk-detect >/dev/null; docker rm tuktuk-sre tuktuk-detect >/dev/null
docker run -d --name tuktuk-sre --restart unless-stopped --env-file /root/sreagent/env -v /root/sreagent/creds:/creds:ro -v sre-state:/srv/state \
  --add-host splunk.example.com:host-gateway -p 127.0.0.1:5000:5000 tuktukpay/sre-agent-aitk:2026-11-01 | cut -c1-12
docker run -d --name tuktuk-detect --restart unless-stopped --env-file /root/detect/env -v detect-srv:/srv -p 127.0.0.1:5001:5000 tuktukpay/anomaly-aitk:2026-10-28i | cut -c1-12
sleep 25
docker ps --filter name=tuktuk- --format '{{.Names}} {{.Image}} {{.Status}}'
ok=1
for port in 5000 5001; do
  new=$(curl -sk -o /dev/null -w '%{http_code}' -H @/root/.tok-new.hdr "https://127.0.0.1:$port/summary"); old=$(curl -sk -o /dev/null -w '%{http_code}' -H @/root/.tok-old.hdr "https://127.0.0.1:$port/summary")
  echo "port $port /summary new=$new old=$old"; [ "$new" = 200 ] && [ "$old" = 401 ] || ok=0
done
if [ "$ok" = 1 ]; then rm -f /root/sreagent/env.bak-rot /root/detect/env.bak-rot; echo "rotated; old token rejected; env backups removed"
else echo "CHECK FAILED: env backups kept as /root/*/env.bak-rot" >&2; exit 1; fi
REMOTE
