#!/usr/bin/env bash
# Trusted TLS (Transport Layer Security) certificate for the Splunk EC2 instance, so Log Observer Connect accepts
# the management port (it rejects an IP address and Splunk's default self-signed certificate: "Invalid domain").
# Host name <ip-with-dashes>.sslip.io resolves to the Elastic IP; Let's Encrypt issues for it (amazonaws.com
# names are refused). Port 80 is opened to the internet only while certbot runs.
# The certificate goes on 8089 (splunkd) and 8000 (Splunk Web). Lasts 90 days; the instance lives until Friday.
#   splunk/ec2/tls-letsencrypt.sh
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
export AWS_PROFILE=${EKS_AWS_PROFILE:-default}
export AWS_REGION=ap-southeast-1
NAME=tuktukpay-splunk
KEY=$HOME/.ssh/$NAME.pem
PUBIP=$(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query 'Addresses[0].PublicIp' --output text)
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=$NAME --query 'SecurityGroups[0].GroupId' --output text)
HOST=${PUBIP//./-}.sslip.io
SSH="ssh -i $KEY -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME ec2-user@$PUBIP"
echo "== $HOST -> $(dig +short "$HOST" | head -1) (Elastic IP $PUBIP)"

close80() { aws ec2 revoke-security-group-ingress --group-id "$SG" --protocol tcp --port 80 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true; }
trap close80 EXIT
aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 80 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true

$SSH sudo bash -s "$HOST" <<'EOF'
set -euo pipefail
HOST=$1
[ -x /opt/certbot/bin/certbot ] || { python3 -m venv /opt/certbot && /opt/certbot/bin/pip -q install certbot; }
/opt/certbot/bin/certbot certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email \
  --key-type rsa --keep-until-expiring -d "$HOST"
LE=/etc/letsencrypt/live/$HOST
D=/opt/splunk/etc/auth/letsencrypt
install -d -o splunk -g splunk -m 700 $D
cat $LE/cert.pem $LE/privkey.pem $LE/chain.pem > $D/server.pem          # splunkd: cert, key, chain in one file
cp $LE/fullchain.pem $D/fullchain.pem; cp $LE/privkey.pem $D/privkey.pem  # Splunk Web: separate files
chown splunk:splunk $D/*; chmod 600 $D/*
/opt/splunk/bin/splunk cmd python3 - "$D" <<'PY'
import configparser, sys
d = sys.argv[1]
def put(path, section, values):
    lines = open(path).read().splitlines() if __import__("os").path.exists(path) else []
    out, sec, done = [], None, set()
    for l in lines:
        s = l.strip()
        if s.startswith("[") and s.endswith("]"):
            if sec == section:
                out += [f"{k} = {v}" for k, v in values.items() if k not in done]; done |= set(values)
            sec = s[1:-1]
        elif sec == section and "=" in s and s.split("=", 1)[0].strip() in values:
            k = s.split("=", 1)[0].strip(); out.append(f"{k} = {values[k]}"); done.add(k); continue
        out.append(l)
    if sec == section:
        out += [f"{k} = {v}" for k, v in values.items() if k not in done]; done |= set(values)
    if section not in [x.strip()[1:-1] for x in lines if x.strip().startswith("[")]:
        out += ["", f"[{section}]"] + [f"{k} = {v}" for k, v in values.items()]
    open(path, "w").write("\n".join(out) + "\n")
put("/opt/splunk/etc/system/local/server.conf", "sslConfig", {"serverCert": f"{d}/server.pem", "sslPassword": ""})
put("/opt/splunk/etc/system/local/web.conf", "settings", {"enableSplunkWebSSL": "true", "serverCert": f"{d}/fullchain.pem", "privKeyPath": f"{d}/privkey.pem"})
PY
chown splunk:splunk /opt/splunk/etc/system/local/server.conf /opt/splunk/etc/system/local/web.conf
systemctl restart Splunkd
for i in $(seq 60); do curl -s -o /dev/null https://$HOST:8089/services/server/info && break; sleep 5; done
EOF

echo "== certificate on 8089:"; echo | openssl s_client -connect "$HOST:8089" -servername "$HOST" -verify_return_error 2>/dev/null | openssl x509 -noout -subject -issuer -enddate
curl -s -o /dev/null -w "== 8089 verified TLS: http %{http_code}\n" "https://$HOST:8089/services/server/info"
curl -s -o /dev/null -w "== 8000 verified TLS: http %{http_code}\n" "https://$HOST:8000/en-US/account/login"
grep -q "$HOST" "$DIR/ec2_creds.txt" 2>/dev/null || sed -i '' "4s#.*#https://$HOST:8000#" "$DIR/ec2_creds.txt"
echo "Log Observer Connect URL: https://$HOST:8089"
