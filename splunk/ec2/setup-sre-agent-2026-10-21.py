"""One-off, idempotent setup on the EC2 Splunk Enterprise for the SRE agent (agent design, section 7).

Creates, through the web-proxied REST API (splunk/control-tower/stack.py, TUKTUK_STACK=ec2):
  * index tuktukpay_agent_audit                     — the agent's own audit events
  * HEC token sre_agent_audit writing ONLY to that index
  * role sre_agent: capability `search` only, srchIndexesAllowed = srchIndexesDefault = tuktukpay,
    no imported roles, search-window limit 24 h, small job quotas — cannot read the audit index
  * user sre_agent with a random 24-character password
Writes splunk/ec2/sre_agent_creds.txt (mode 600, git-ignored): line 1 user, 2 password, 3 audit HEC token, 4 Splunk Web URL,
5 HEC URL. Never prints the password or the token.

Run:  TUKTUK_STACK=ec2 python3 -I splunk/ec2/setup-sre-agent-2026-10-21.py
"""

import json
import os
import pathlib
import secrets
import string
import sys

os.environ.setdefault("TUKTUK_STACK", "ec2")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "control-tower"))
from stack import S  # noqa: E402

OUT = HERE / "sre_agent_creds.txt"
INDEX = "tuktukpay_agent_audit"
ROLE = USER = "sre_agent"
HEC_NAME = "sre_agent_audit"


def ok(st):
    return st in (200, 201)


def say(msg):
    print(msg, flush=True)


if not S.ok:
    sys.exit("login to the EC2 Splunk failed")

# 1. audit index
st, _ = S.get(f"/services/data/indexes/{INDEX}")
if st == 200:
    say(f"index {INDEX}: exists")
else:
    st, body = S.post("/services/data/indexes", {"name": INDEX, "frozenTimePeriodInSecs": str(400 * 86400)})
    say(f"index {INDEX}: created -> {st}" if ok(st) else f"index {INDEX}: FAILED {st} {body[:200]}")

# 2. HEC token scoped to the audit index only
path = f"/servicesNS/nobody/splunk_httpinput/data/inputs/http/{HEC_NAME}"
st, body = S.get(path)
if st != 200:
    st, body = S.post("/servicesNS/nobody/splunk_httpinput/data/inputs/http",
                      {"name": HEC_NAME, "index": INDEX, "indexes": INDEX, "sourcetype": "sre_agent:audit"})
    say(f"HEC token {HEC_NAME}: created -> {st}" if ok(st) else f"HEC token {HEC_NAME}: FAILED {st} {body[:200]}")
    st, body = S.get(path)
else:
    say(f"HEC token {HEC_NAME}: exists")
content = json.loads(body)["entry"][0]["content"] if st == 200 else {}
hec_token = content.get("token", "")
say(f"HEC token {HEC_NAME}: index={content.get('index')} indexes={content.get('indexes')} disabled={content.get('disabled')}")

# 2b. search-time JSON field extraction for the audit sourcetype (custom sourcetypes default to KV_MODE=auto)
st, _ = S.get("/servicesNS/nobody/search/configs/conf-props/sre_agent%3Aaudit")
if st == 200:
    st, _ = S.post("/servicesNS/nobody/search/configs/conf-props/sre_agent%3Aaudit", {"KV_MODE": "json"})
else:
    st, _ = S.post("/servicesNS/nobody/search/configs/conf-props", {"name": "sre_agent:audit", "KV_MODE": "json"})
say(f"props sre_agent:audit KV_MODE=json -> {st}")
st, body = S.post("/servicesNS/nobody/search/configs/conf-props/sre_agent%3Aaudit/acl", {"sharing": "global", "owner": "nobody", "perms.read": "*", "perms.write": "admin"})
say(f"props sharing global -> {st}")

# 3. least-privilege search role
role_form = {"capabilities": ["search"], "srchIndexesAllowed": ["tuktukpay"], "srchIndexesDefault": ["tuktukpay"],
             "srchJobsQuota": "4", "rtSrchJobsQuota": "0", "cumulativeSrchJobsQuota": "8", "srchTimeWin": "86400",
             "srchDiskQuota": "100"}
st, _ = S.get(f"/services/authorization/roles/{ROLE}")
if st == 200:
    st, body = S.post(f"/services/authorization/roles/{ROLE}", role_form)
    say(f"role {ROLE}: updated -> {st}")
else:
    st, body = S.post("/services/authorization/roles", {"name": ROLE, **role_form})
    say(f"role {ROLE}: created -> {st}" if ok(st) else f"role {ROLE}: FAILED {st} {body[:200]}")
# Splunk 10.6 adds default capabilities (edit_own_objects, list_all_objects, run_collect, run_mcollect, schedule_rtsearch)
# to a new role; a second update with the explicit list disables them (verified 21 Oct 2026).
S.post(f"/services/authorization/roles/{ROLE}", {"capabilities": ["search"], "srchFederatedProvidersAllowed": ""})
st, body = S.get(f"/services/authorization/roles/{ROLE}")
rc = json.loads(body)["entry"][0]["content"]
say(f"role {ROLE}: capabilities={rc.get('capabilities')} imported={rc.get('imported_roles')} indexes={rc.get('srchIndexesAllowed')}")

# 4. user (password generated here, written only to the creds file)
alphabet = string.ascii_letters + string.digits
password = None
st, _ = S.get(f"/services/authentication/users/{USER}")
if st == 200 and OUT.exists():
    password = OUT.read_text().splitlines()[1]
    say(f"user {USER}: exists (password kept from {OUT.name})")
else:
    password = "".join(secrets.choice(alphabet) for _ in range(20)) + "Aa9z"
    if st == 200:
        st, body = S.post(f"/services/authentication/users/{USER}", {"password": password, "roles": ROLE, "force-change-pass": "0"})
        say(f"user {USER}: password reset -> {st}")
    else:
        st, body = S.post("/services/authentication/users", {"name": USER, "password": password, "roles": ROLE, "force-change-pass": "0"})
        say(f"user {USER}: created -> {st}" if ok(st) else f"user {USER}: FAILED {st} {body[:200]}")

web_url = (HERE / "ec2_creds.txt").read_text().splitlines()[3].rstrip("/")
host = web_url.split("//", 1)[1].split(":")[0]
OUT.write_text("\n".join([USER, password, hec_token, web_url, f"https://{host}:8088"]) + "\n")
OUT.chmod(0o600)
say(f"wrote {OUT} (mode 600): user, password, audit HEC token, Splunk Web URL, HEC URL")
