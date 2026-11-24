"""One-off (27 Oct 2026), idempotent: a read-only guest on the EC2 Splunk Enterprise to share the AI Toolkit agent's results.

Creates, through the web-proxied REST API (splunk/control-tower/stack.py, TUKTUK_STACK=ec2):
  * role tuktuk_guest: capability `search` only, no imported roles, srchIndexesAllowed = tuktukpay + _audit, default
    tuktukpay, role search filter so _audit shows only AI Toolkit agent responses (sourcetype ai_agent:response, where the
    toolkit keeps its run history: mlspl.conf agent_run_index), small job quotas. No run_agents, no edit_agent_connections,
    no list_storage_passwords (the toolkit's mltk_* roles carry that, which would expose the stored Observability Cloud token)
  * user tuktuk_guest with a random 24-character password
  * agent TukTukPaySRE shared read-only with role tuktuk_guest (sharing app, read [tuktuk_guest], write unchanged), so it
    appears in AI Toolkit > Agents > Run history; the agent's current definition is saved first to
    splunk/ec2/backup-aitk-agent-TukTukPaySRE-2026-10-27.json (git-ignored folder content: holds no secrets)
Writes splunk/ec2/guest_creds.txt (mode 600, git-ignored): line 1 user, 2 password, 3 Splunk Web URL. Never prints the password.
Then logs in as the guest and checks: run history visible, index=tuktukpay searchable, other _audit events and the
toolkit's stored passwords not visible.

Run:  TUKTUK_STACK=ec2 python3 -I splunk/ec2/setup-guest-viewer-2026-10-27.py
"""

import json
import os
import pathlib
import secrets
import string
import sys
import urllib.request

os.environ.setdefault("TUKTUK_STACK", "ec2")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "control-tower"))
import stack  # noqa: E402
from stack import S, BASE  # noqa: E402

OUT = HERE / "guest_creds.txt"
BACKUP = HERE / "backup-aitk-agent-TukTukPaySRE-2026-10-27.json"
ROLE = USER = "tuktuk_guest"
AGENT = "TukTukPaySRE"
MLTK = BASE + "/en-US/splunkd/__raw/servicesNS/admin/Splunk_ML_Toolkit/mltk/"
JSON_H = {**S.h, "Content-Type": "application/json"}


def ok(st):
    return st in (200, 201)


def say(msg):
    print(msg, flush=True)


if not S.ok:
    sys.exit("login to the EC2 Splunk failed")

# 1. read-only role
role_form = {"capabilities": ["search"], "srchIndexesAllowed": ["tuktukpay", "_audit"], "srchIndexesDefault": ["tuktukpay"],
             "srchFilter": 'index=tuktukpay OR (index=_audit sourcetype="ai_agent:response")',
             "srchJobsQuota": "4", "rtSrchJobsQuota": "0", "cumulativeSrchJobsQuota": "8", "srchDiskQuota": "200"}
st, _ = S.get(f"/services/authorization/roles/{ROLE}")
if st == 200:
    st, body = S.post(f"/services/authorization/roles/{ROLE}", role_form)
    say(f"role {ROLE}: updated -> {st}")
else:
    st, body = S.post("/services/authorization/roles", {"name": ROLE, **role_form})
    say(f"role {ROLE}: created -> {st}" if ok(st) else f"role {ROLE}: FAILED {st} {body[:200]}")
# Splunk 10.6 adds default capabilities (run_collect and others) to a new role; a second update disables them.
S.post(f"/services/authorization/roles/{ROLE}", {"capabilities": ["search"], "srchFederatedProvidersAllowed": ""})
st, body = S.get(f"/services/authorization/roles/{ROLE}")
rc = json.loads(body)["entry"][0]["content"]
say(f"role {ROLE}: capabilities={rc.get('capabilities')} imported={rc.get('imported_roles')} "
    f"indexes={rc.get('srchIndexesAllowed')} filter={rc.get('srchFilter')!r}")

# 2. user (password generated here, written only to the creds file)
alphabet = string.ascii_letters + string.digits
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
        st, body = S.post("/services/authentication/users", {"name": USER, "password": password, "roles": ROLE,
                                                             "realname": "TukTukPay guest (AI Toolkit results, read-only)",
                                                             "force-change-pass": "0"})
        say(f"user {USER}: created -> {st}" if ok(st) else f"user {USER}: FAILED {st} {body[:200]}")
web_url = (HERE / "ec2_creds.txt").read_text().splitlines()[3].rstrip("/")
OUT.write_text("\n".join([USER, password, web_url]) + "\n")
OUT.chmod(0o600)
say(f"wrote {OUT.name} (mode 600): user, password, Splunk Web URL")

# 3. share the agent read-only with the guest role (GET -> backup -> PUT with the same definition and a new acl)
st, b = S._req(MLTK + f"agents?output_mode=json&name={AGENT}", headers=S.h, timeout=60)
d = json.loads(b)
v = (d[0] if isinstance(d, list) else d)["versions"][0]
acl = v.get("acl") or {}
read = (acl.get("perms") or {}).get("read") or []
if ROLE in read and acl.get("sharing") in ("app", "global"):
    say(f"agent {AGENT}: already readable by {ROLE}")
else:
    if not BACKUP.exists():
        BACKUP.write_text(json.dumps(v, indent=2) + "\n")
        say(f"agent {AGENT}: definition saved to {BACKUP.name}")
    new_acl = {**acl, "sharing": "app", "perms": {"read": sorted(set(read) | {ROLE, "admin"}),
                                                 "write": (acl.get("perms") or {}).get("write") or ["admin"]}}
    tools = v.get("tools") or {}   # a stored version keeps mcps / knowledge_bases under "tools"; the PUT takes them top-level
    put_body = {"name": AGENT, "system_prompt": v["system_prompt"], "mcps": tools.get("mcps", []), "llm": v["llm"],
                "knowledge_bases": tools.get("knowledge_bases", []), "acl": new_acl}
    if v.get("description"):
        put_body["description"] = v["description"]
    r = urllib.request.Request(MLTK + "agents", data=json.dumps(put_body).encode(), headers=JSON_H, method="PUT")
    try:
        with S.op.open(r, timeout=180) as x:
            say(f"agent {AGENT}: acl -> {x.status} sharing=app read={new_acl['perms']['read']}")
    except urllib.error.HTTPError as e:
        say(f"agent {AGENT}: acl FAILED {e.code} {e.read().decode(errors='replace')[:300]}")

# 4. check as the guest
stack.CREDS = OUT
G = stack.Stack()
say(f"guest login: {'ok' if G.ok else 'FAILED'}")
if G.ok:
    st, b = G._req(BASE + "/en-US/splunkd/__raw/servicesNS/" + USER + "/Splunk_ML_Toolkit/mltk/run_history",
                   json.dumps({"count": 5, "offset": 0, "earliest": "-7d", "latest": "now"}).encode(),
                   {**G.h, "Content-Type": "application/json"}, timeout=120)
    try:
        hist = json.loads(b)
        rows = hist.get("history", hist if isinstance(hist, list) else [])
        say(f"guest run history: http {st}, {len(rows)} rows" + (f" ({hist.get('message') or hist.get('error')})" if not rows else ""))
    except ValueError:
        say(f"guest run history: http {st} {b[:200]}")
    r = G.search('index=_audit sourcetype="ai_agent:response" earliest=-7d | stats count', earliest="-7d")
    say(f"guest agent responses in _audit: {r.get('results') or r}")
    r = G.search('index=_audit earliest=-1h | stats count by sourcetype', earliest="-1h")
    say(f"guest other _audit events (expect only ai_agent:response): {r.get('results') or r}")
    r = G.search('index=tuktukpay earliest=-15m | stats count', earliest="-15m")
    say(f"guest index=tuktukpay last 15 min: {r.get('results') or r}")
    st, _ = G.get("/servicesNS/nobody/Splunk_ML_Toolkit/storage/passwords")
    st2, b2 = G.get("/servicesNS/nobody/Splunk_ML_Toolkit/storage/passwords")
    n = len(json.loads(b2).get("entry", [])) if st2 == 200 else 0
    say(f"guest stored passwords: http {st}, {n} entries (expect 0)")
