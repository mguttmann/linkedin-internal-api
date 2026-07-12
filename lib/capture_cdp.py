#!/usr/bin/env python3
"""capture_cdp.py — Record the live traffic of a LinkedIn action (via Chrome CDP).

Two modes:
  1. NAVIGATE: load a page + capture all API traffic (read endpoints)
       capture_cdp.py navigate <url> [<out.json>]
  2. ACTION: load a page, run a JS snippet (click a real button) and record the
     mutation request it fires (write endpoints).
       capture_cdp.py action <url> <action.js> [<out.json>]

Prerequisite: headless Chrome with a logged-in profile on port 9222.
See docs/01-AUTH-AND-COOKIES.md for the Chrome start command.
"""
import json, sys, time, threading, urllib.request, websocket

CDP_URL = "http://127.0.0.1:9222"
ORIGIN = "http://127.0.0.1:9222"

def page_target():
    ts = json.load(urllib.request.urlopen(f"{CDP_URL}/json/list"))
    return [t for t in ts if t.get("type") == "page"][0]

class Conn:
    def __init__(self):
        t = page_target()
        self.ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=60,
                                              origin=ORIGIN, max_size=None)
        self._id = 0; self._resp = {}; self.events = []; self._run = True
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        while self._run:
            try: m = json.loads(self.ws.recv())
            except Exception: break
            if "id" in m: self._resp[m["id"]] = m
            elif "method" in m: self.events.append(m)
    def call(self, method, params=None, timeout=30):
        self._id += 1; rid = self._id
        self.ws.send(json.dumps({"id": rid, "method": method, "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            if rid in self._resp: return self._resp.pop(rid).get("result", {})
            time.sleep(0.02)
        return {}
    def close(self):
        self._run = False
        try: self.ws.close()
        except Exception: pass

def is_api(u):
    return "/voyager/api/" in u or "/graphql" in u or "/rsc-action/" in u

def main():
    mode = sys.argv[1]
    url = sys.argv[2]
    c = Conn(); c.call("Network.enable"); c.call("Page.enable")
    c.events = []
    c.call("Page.navigate", {"url": url}); time.sleep(9)

    if mode == "action":
        action_file = sys.argv[3]
        out = sys.argv[4] if len(sys.argv) > 4 else "_capture_action.json"
        js = open(action_file).read()
        res = c.call("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
        print("Action-Ergebnis:", res.get("result", {}).get("value"))
        time.sleep(4)
    else:
        out = sys.argv[3] if len(sys.argv) > 3 else "_capture_nav.json"
        for _ in range(3):
            c.call("Runtime.evaluate", {"expression": "window.scrollTo(0,document.body.scrollHeight)"})
            time.sleep(2)

    recs = []
    for ev in c.events:
        if ev.get("method") == "Network.requestWillBeSent":
            r = ev["params"].get("request", {})
            u = r.get("url", "")
            if is_api(u):
                recs.append({"method": r.get("method"), "url": u,
                             "headers": r.get("headers", {}), "postData": r.get("postData")})
    json.dump(recs, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"{len(recs)} API-Requests -> {out}")
    # Highlight mutations (non-GET)
    for r in recs:
        if r["method"] != "GET":
            print(f'  MUTATION: {r["method"]} {r["url"][:90]}')
            if r["postData"]: print(f'    body: {r["postData"][:160]}')
    c.close()

if __name__ == "__main__":
    main()
