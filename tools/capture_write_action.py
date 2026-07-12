#!/usr/bin/env python3
"""capture_write_action.py — Runs a real write action in the logged-in client
and records ALL the POST/PUT/DELETE requests it fires (Voyager + SDUI) with full
body + response. This is how we learn the real schema.

Usage: capture_write_action.py <label> <url> <action_js_file>
Saves -> _writes/<label>.json  (full request + response of each mutation)
"""
import json, sys, time, threading, urllib.request, os, websocket

CDP_URL = "http://127.0.0.1:9222"
ORIGIN = "http://127.0.0.1:9222"
BASE = os.path.dirname(os.path.abspath(__file__))

def page_target():
    ts = json.load(urllib.request.urlopen(f"{CDP_URL}/json/list"))
    return [t for t in ts if t.get("type") == "page"][0]

class Conn:
    def __init__(self):
        t = page_target()
        self.ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=60,
                                              origin=ORIGIN, max_size=None)
        self._id = 0; self._resp = {}; self.events = []; self._run = True
        self.req_bodies = {}   # requestId -> request info
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        while self._run:
            try: m = json.loads(self.ws.recv())
            except Exception: break
            if "id" in m:
                self._resp[m["id"]] = m
            elif m.get("method") == "Network.requestWillBeSent":
                p = m["params"]; r = p.get("request", {})
                self.req_bodies[p["requestId"]] = {
                    "method": r.get("method"), "url": r.get("url"),
                    "headers": r.get("headers", {}), "postData": r.get("postData"),
                }
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

def is_mutation(r):
    return r.get("method") in ("POST", "PUT", "DELETE") and \
           ("/voyager/api/" in r.get("url", "") or "/rsc-action/" in r.get("url", ""))

def main():
    label, url, action_file = sys.argv[1], sys.argv[2], sys.argv[3]
    c = Conn()
    c.call("Network.enable"); c.call("Page.enable")
    c.call("Page.navigate", {"url": url}); time.sleep(9)
    c.req_bodies = {}  # collect fresh from here on

    js = open(action_file).read()
    res = c.call("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
    print("Action:", res.get("result", {}).get("value"))
    time.sleep(6)  # wait for mutations

    muts = []
    for rid, r in list(c.req_bodies.items()):
        if is_mutation(r):
            entry = dict(r)
            # try to get the response body
            try:
                b = c.call("Network.getResponseBody", {"requestId": rid}, timeout=8)
                entry["response"] = b.get("body", "")[:2000]
            except Exception:
                entry["response"] = None
            # keep only relevant headers
            hl = {k.lower(): v for k, v in r.get("headers", {}).items()}
            entry["key_headers"] = {k: hl[k] for k in
                ("csrf-token","content-type","x-restli-method","x-li-page-instance",
                 "x-li-pageforestid","x-li-application-instance","x-li-application-version",
                 "x-li-track","x-li-anchor-page-key","x-li-page-instance-tracking-id") if k in hl}
            muts.append(entry)

    outdir = os.path.join(BASE, "..", "api-docs", "_writes")
    os.makedirs(outdir, exist_ok=True)
    outfile = os.path.join(outdir, f"{label}.json")
    json.dump(muts, open(outfile, "w"), ensure_ascii=False, indent=2)
    print(f"\n{len(muts)} Mutation(en) -> {outfile}")
    for m in muts:
        print(f'\n>>> {m["method"]} {m["url"][:110]}')
        if m["postData"]: print(f'    BODY: {m["postData"][:300]}')
        if m.get("response"): print(f'    RESP: {m["response"][:150]}')
    c.close()

if __name__ == "__main__":
    main()
