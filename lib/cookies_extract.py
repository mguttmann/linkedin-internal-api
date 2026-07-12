#!/usr/bin/env python3
"""cookies_extract.py — Fetch fresh LinkedIn cookies from the running headless Chrome
(via CDP Network.getAllCookies) and write them to /tmp/li_cookies.json.

Loads /feed/ first so that JSESSIONID (CSRF) is set. This is Variant A from
docs/01-AUTH-AND-COOKIES.md (recommended when Chrome is already running).

Prerequisite: headless Chrome with a logged-in profile on port 9222.

Usage: cookies_extract.py [<out_file>]   (default /tmp/li_cookies.json)
"""
import json, sys, time, urllib.request, websocket

CDP_URL = "http://127.0.0.1:9222"
ORIGIN = "http://127.0.0.1:9222"

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/li_cookies.json"
    ts = json.load(urllib.request.urlopen(f"{CDP_URL}/json/list"))
    t = [x for x in ts if x.get("type") == "page"][0]
    ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=40, origin=ORIGIN, max_size=None)
    _id = [0]
    def call(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
        while True:
            x = json.loads(ws.recv())
            if x.get("id") == _id[0]:
                return x.get("result", {})
    # Load feed -> JSESSIONID gets set
    call("Page.enable")
    call("Page.navigate", {"url": "https://www.linkedin.com/feed/"})
    time.sleep(7)
    cookies = call("Network.getAllCookies").get("cookies", [])
    li = {c["name"]: c["value"] for c in cookies if "linkedin" in c.get("domain", "")}
    ws.close()
    if "li_at" not in li:
        print("ERROR: li_at missing — session not logged in?", file=sys.stderr)
        sys.exit(1)
    if "JSESSIONID" not in li:
        print("WARNING: JSESSIONID missing — csrf-token will be absent", file=sys.stderr)
    json.dump(li, open(out, "w"))
    print(f"OK: {len(li)} Cookies -> {out}")
    print(f"   li_at: {'ja' if 'li_at' in li else 'NEIN'} | JSESSIONID: {li.get('JSESSIONID','FEHLT')[:22]}")

if __name__ == "__main__":
    main()
