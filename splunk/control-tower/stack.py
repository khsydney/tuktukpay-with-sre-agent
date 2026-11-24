"""Session helper for the Splunk Show stack through Splunk Web (port 443): form login, then the web-proxied
REST API at /en-US/splunkd/__raw/services/... Credentials come from stack_creds.txt (line 1 user, line 2 password)
next to this file; nothing is printed. TUKTUK_STACK=ec2 targets our Splunk Enterprise on EC2 instead
(splunk/ec2/ec2_creds.txt: line 1 user, 2 password, 4 Splunk Web URL; self-signed certificate). Usage: from stack import S; S.get(path), S.post(path, dict), S.search(spl)."""
import http.cookiejar, json, os, pathlib, ssl, time, urllib.parse, urllib.request

EC2 = os.environ.get("TUKTUK_STACK") == "ec2"
CREDS = pathlib.Path(__file__).parent.parent / "ec2" / "ec2_creds.txt" if EC2 else pathlib.Path(__file__).with_name("stack_creds.txt")
BASE = CREDS.read_text().splitlines()[3] if EC2 else "https://example-stack.splunkcloud.com"


class Stack:
    def __init__(self):
        user, password = CREDS.read_text().splitlines()[:2]
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar),
                                             *([urllib.request.HTTPSHandler(context=ssl._create_unverified_context())] if EC2 else []))
        self._req(BASE + "/en-US/account/login")
        cval = next((c.value for c in self.jar if c.name == "cval"), "")
        self._req(BASE + "/en-US/account/login", urllib.parse.urlencode({"username": user, "password": password, "cval": cval}).encode(),
                  {"X-Requested-With": "XMLHttpRequest", "X-Splunk-Form-Key": cval})
        key = next((c.name for c in self.jar if c.name.startswith("splunkweb_csrf_token_")), None)
        self.h = {"X-Splunk-Form-Key": next((c.value for c in self.jar if c.name == key), ""), "X-Requested-With": "XMLHttpRequest"}
        self.ok = any(c.name.startswith("splunkd_") for c in self.jar)

    def _req(self, url, data=None, headers=None, timeout=60):
        r = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            with self.op.open(r, timeout=timeout) as resp:
                return resp.status, resp.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace")
        except Exception as e:  # noqa: BLE001
            return 0, f"{type(e).__name__}: {e}"

    def get(self, path, **params):
        params.setdefault("output_mode", "json")
        return self._req(f"{BASE}/en-US/splunkd/__raw{path}?{urllib.parse.urlencode(params)}", headers=self.h)

    def post(self, path, form):
        form = dict(form); form.setdefault("output_mode", "json")
        return self._req(f"{BASE}/en-US/splunkd/__raw{path}", urllib.parse.urlencode(form, doseq=True).encode(), self.h)

    def search(self, spl, earliest="-24h", app="search", wait=120):
        if not spl.lstrip().startswith("|"):
            spl = "search " + spl
        st, body = self.post(f"/servicesNS/nobody/{app}/search/jobs", {"search": spl, "earliest_time": earliest, "latest_time": "now"})
        if st not in (200, 201):
            return {"error": f"http {st}: {body[:300]}"}
        sid = json.loads(body)["sid"]
        t0 = time.time()
        while time.time() - t0 < wait:
            st, body = self.get(f"/services/search/jobs/{sid}")
            c = json.loads(body)["entry"][0]["content"]
            if c.get("isDone"):
                break
            time.sleep(2)
        st, body = self.get(f"/services/search/jobs/{sid}/results", count=0)
        d = json.loads(body) if st == 200 else {}
        return {"results": d.get("results", []), "messages": d.get("messages", [])}


S = Stack()
