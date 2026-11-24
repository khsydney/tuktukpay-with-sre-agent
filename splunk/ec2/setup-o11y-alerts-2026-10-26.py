"""One-off (26 Oct 2026): Observability Cloud detector alerts -> the EC2 Splunk (lane 3 of the control-tower design,
pointed at EC2 instead of the Show stack).
  1. EC2 Splunk: HEC (HTTP Event Collector) token `o11y-alerts` that may write only to index tuktukpay
     (sourcetype o11y:detector, no indexer acknowledgement) — created if missing.
  2. Observability Cloud (shared org; create approved 26 Oct): integration of type SplunkPlatform
     "TukTukPay EC2 Splunk alerts (tuktukpay-demo)", URL https://<sslip name>:8088, that token, payload template
     splunk/control-tower/o11y-integration-payload.hbs — created if missing. Prints the integration id.
The HEC token value moves from Splunk to Observability Cloud in memory only; nothing secret is printed.
Port 8088 must admit the us1 notification addresses (security group tuktukpay-splunk) for events to arrive.
Run:  TUKTUK_STACK=ec2 python3 -I splunk/ec2/setup-o11y-alerts-2026-10-26.py
"""
import json, os, pathlib, sys, urllib.error, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "control-tower"))
from stack import S  # noqa: E402

TOKEN_NAME = "o11y-alerts"
NAME = "TukTukPay EC2 Splunk alerts (tuktukpay-demo)"
HEC_URL = "https://splunk.example.com:8088"
TEMPLATE = (HERE.parent / "control-tower" / "o11y-integration-payload.hbs").read_text()
API = "https://api.us1.signalfx.com/v2/integration"
O11Y = os.environ["SPLUNK_O11Y_TOKEN"]

# 1. HEC token on the EC2 Splunk
path = f"/servicesNS/nobody/splunk_httpinput/data/inputs/http/{TOKEN_NAME}"
st, body = S.get(path)
if st == 404:
    st, body = S.post("/servicesNS/nobody/splunk_httpinput/data/inputs/http",
                      {"name": TOKEN_NAME, "index": "tuktukpay", "indexes": "tuktukpay", "sourcetype": "o11y:detector",
                       "useACK": "0", "description": "Observability Cloud detector notifications (SplunkPlatform integration)"})
    print("HEC token create ->", st)
    st, body = S.get(path)
c = json.loads(body)["entry"][0]["content"]
print(f"HEC token {TOKEN_NAME}: index={c.get('index')} indexes={c.get('indexes')} sourcetype={c.get('sourcetype')} disabled={c.get('disabled')}")
hec_token = c["token"]


def o11y(method, url, data=None):
    r = urllib.request.Request(url, method=method, data=json.dumps(data).encode() if data else None,
                               headers={"X-SF-Token": O11Y, "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(r, timeout=60))
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url}: HTTP {e.code} {e.read()[:400].decode()}")


# 2. SplunkPlatform integration in Observability Cloud
existing = [i for i in o11y("GET", API + "?type=SplunkPlatform&limit=200").get("results", []) if i.get("name") == NAME]
if existing:
    integ = existing[0]
    print("integration exists:", integ["id"])
else:
    integ = o11y("POST", API, {"type": "SplunkPlatform", "name": NAME, "enabled": True, "url": HEC_URL,
                               "hecToken": hec_token, "payloadTemplate": TEMPLATE})
    print("integration created:", integ["id"])
print("integration:", integ["id"], "|", integ.get("name"), "| url", integ.get("url"), "| enabled", integ.get("enabled"))
