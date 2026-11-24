"""One-off, idempotent setup of the Splunk MCP (Model Context Protocol) Server app on the EC2 Splunk, after
install-mcp-server-2026-10-21.sh. Through the web-proxied REST API (stack.py, admin):
  * token authentication on (needed for the app's bearer tokens)
  * role sre_agent gains `mcp_tool_execute` (its other capabilities and index limits stay as they are)
  * mints an encrypted MCP token (audience mcp) for user sre_agent, expiring with the instance (MCP_TOKEN_EXPIRES, default +10d), into
    splunk/ec2/sre_agent_mcp_token.txt (mode 600, git-ignored) — only when that file does not exist yet
  * checks https://<host>:8089/services/mcp end to end: initialize, tools/list, splunk_run_query on index=tuktukpay
Never prints the token. Run:  TUKTUK_STACK=ec2 python3 -I splunk/ec2/setup-mcp-server-2026-10-21.py
"""

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

os.environ.setdefault("TUKTUK_STACK", "ec2")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "control-tower"))
from stack import BASE, S  # noqa: E402

ROLE = USER = "sre_agent"
OUT = HERE / "sre_agent_mcp_token.txt"
_HOST = re.sub(r"^https?://|[:/].*$", "", BASE)
MCP_URL = f"https://{_HOST.replace('.', '-')}.sslip.io:8089/services/mcp" if re.fullmatch(r"[\d.]+", _HOST) else f"https://{_HOST}:8089/services/mcp"

if not S.ok:
    sys.exit("login to the EC2 Splunk failed")

# 1. token authentication
st, body = S.get("/services/admin/Token-auth/tokens_auth")
disabled = json.loads(body)["entry"][0]["content"].get("disabled") if st == 200 else None
if disabled in (False, "0", 0, "false"):
    print("token authentication: already on")
else:
    st, body = S.post("/services/admin/Token-auth/tokens_auth", {"disabled": "false"})
    print(f"token authentication: enabled -> {st}" if st in (200, 201) else f"token authentication: FAILED {st} {body[:200]}")

# 2. role capability (POST replaces the list, so send the current own capabilities plus the new one)
st, body = S.get(f"/services/authorization/roles/{ROLE}")
if st != 200:
    sys.exit(f"role {ROLE} not found ({st}); run setup-sre-agent-2026-10-21.py first")
caps = json.loads(body)["entry"][0]["content"].get("capabilities", [])
if "mcp_tool_execute" in caps:
    print(f"role {ROLE}: already has mcp_tool_execute")
else:
    st, body = S.post(f"/services/authorization/roles/{ROLE}", {"capabilities": caps + ["mcp_tool_execute"]})
    print(f"role {ROLE}: + mcp_tool_execute -> {st}" if st in (200, 201) else f"role {ROLE}: FAILED {st} {body[:200]}")

# 3. encrypted MCP token for sre_agent
if OUT.exists():
    print(f"token: {OUT.name} exists, not re-minted")
else:
    st, body = S.get("/services/mcp_token", username=USER, expires_on=os.getenv("MCP_TOKEN_EXPIRES", "+10d"))
    if st != 200:
        sys.exit(f"token: FAILED {st} {body[:300]}")
    token = json.loads(body)["token"]
    fd = os.open(OUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"{token}\n{MCP_URL}\n")
    print(f"token: minted for {USER} ({os.getenv("MCP_TOKEN_EXPIRES", "+10d")}) -> {OUT.name} (line 1 token, line 2 MCP URL)")

# 4. end-to-end check over 8089 with TLS verification
token = OUT.read_text().splitlines()[0]
sid = None


def rpc(i, method, params):
    global sid
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "Authorization": f"Bearer {token}"}
    if sid:
        h["Mcp-Session-Id"] = sid
    req = urllib.request.Request(MCP_URL, json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}).encode(), h)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            sid = r.headers.get("Mcp-Session-Id", sid)
            raw = r.read().decode()
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode(errors="replace")[:300]}
    if raw.lstrip().startswith("event:") or raw.lstrip().startswith("data:"):
        raw = next(line[5:] for line in raw.splitlines() if line.startswith("data:"))
    return json.loads(raw)


r = rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tuktukpay-setup", "version": "1"}})
print("initialize:", r.get("result", {}).get("serverInfo") or r)
tools = rpc(2, "tools/list", {}).get("result", {}).get("tools", [])
print(f"tools/list: {len(tools)} tools:", ", ".join(sorted(t["name"] for t in tools)))
r = rpc(3, "tools/call", {"name": "splunk_run_query", "arguments": {
    "query": "search index=tuktukpay | stats count by source", "earliest_time": "-15m", "latest_time": "now"}})
print("splunk_run_query:", json.dumps(r.get("result", r))[:600])
