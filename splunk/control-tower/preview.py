"""Local preview of the control-tower app with live data: serves a page that loads the built tower.js/tower.css and
forwards /en-US/splunkd/__raw/* to the Show stack through the logged-in session in stack.py. Usage: python3 harness.py [port]"""
import http.server, socketserver, sys, os, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack import S, BASE

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app/tuktukpay_control_tower/appserver/static")
PAGE = b"""<!doctype html><html><head><meta charset="utf-8"><title>tower preview</title>
<link rel="stylesheet" href="/static/tower.css"></head><body style="margin:0;background:#0f172a">
<div style="height:40px;background:#1a1c21;color:#ccc;font:12px sans-serif;padding:12px 16px">Splunk app bar (preview)</div>
<div class="dashboard-body"><div id="tower-root"></div></div>
<script>document.cookie="splunkweb_csrf_token_8443=preview; path=/";</script>
<script src="/static/tower.js"></script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = self.path
        if p in ("/", "/en-US/app/tuktukpay_control_tower/control_tower") or p.startswith("/en-US/app/"):
            return self._send(200, PAGE, "text/html")
        if p.startswith("/static/"):
            f = os.path.join(STATIC, p.split("/static/", 1)[1].split("?")[0])
            return self._send(200, open(f, "rb").read(), "text/css" if f.endswith(".css") else "application/javascript")
        if p.startswith("/en-US/splunkd/__raw"):
            st, b = S._req(BASE + p, headers=S.h)
            return self._send(st or 502, b.encode())
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); data = self.rfile.read(n)
        st, b = S._req(BASE + self.path, data, S.h)
        self._send(st or 502, b.encode())


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("127.0.0.1", port), H) as srv:
    print(f"preview on http://127.0.0.1:{port}/en-US/app/tuktukpay_control_tower/control_tower", flush=True)
    srv.serve_forever()
