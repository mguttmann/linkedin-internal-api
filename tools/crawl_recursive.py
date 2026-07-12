#!/usr/bin/env python3
"""crawl_recursive.py — SELF-DISCOVERING crawler for the complete LinkedIn API.

Strategy (BFS):
  1. Load a page (headless, logged-in session)
  2. Scroll (trigger lazy-load)
  3. Capture ALL API calls (Voyager REST/GraphQL + SDUI rsc-action)
  4. Extract ALL internal links (a[href]) + menu targets from the DOM
  5. Push new, not-yet-visited links into the queue -> depth+1
  6. Repeat until max_depth / max_pages

Safety:
  - GET navigation ONLY (clicks no buttons, triggers no mutations)
  - Blocklist: logout, /uas/, signout, delete, remove, unfollow, report, block
  - Dedupe by normalized URL

Saves after EVERY page: _captures2/recursive.json (requests) +
_captures2/recursive_urls.json (visited + queue state).

Usage: crawl_recursive.py [start_url] [max_pages] [max_depth]
"""
import json, sys, time, threading, urllib.request, os, subprocess, re
from collections import deque
from urllib.parse import urlparse, urljoin, urldefrag

CDP_URL = "http://127.0.0.1:9222"
ORIGIN = "http://127.0.0.1:9222"
BASE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = os.path.expanduser("~/.hermes/chrome-automation")
OUTDIR = os.path.join(BASE, "_captures2")

BLOCK = re.compile(r"(logout|signout|sign-out|/uas/|/psettings/.*delete|/delete|/remove|"
                   r"unfollow|/report|/block|withdraw|disconnect|trk=public)", re.I)
# Only real LinkedIn app links
def internal(u):
    try:
        p = urlparse(u)
    except Exception:
        return False
    if p.netloc and "linkedin.com" not in p.netloc:
        return False
    if not (p.path.startswith("/")):
        return False
    if BLOCK.search(u):
        return False
    # uninteresting assets
    if re.search(r"\.(png|jpg|jpeg|gif|svg|css|js|pdf|ico)(\?|$)", p.path, re.I):
        return False
    return True

def norm(u):
    u, _ = urldefrag(u)
    return u.rstrip("/")

def chrome_alive():
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3); return True
    except Exception:
        return False

def start_chrome():
    if chrome_alive(): return
    subprocess.Popen([CHROME,"--headless=new","--remote-debugging-port=9222",
        "--remote-allow-origins=http://127.0.0.1:9222",
        f"--user-data-dir={PROFILE}","--profile-directory=Default","--window-size=1440,900"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(1)
        if chrome_alive(): return
    raise RuntimeError("Chrome start fail")

def page_target():
    ts = json.load(urllib.request.urlopen(f"{CDP_URL}/json/list"))
    return [t for t in ts if t.get("type")=="page"][0]

class Conn:
    def __init__(self):
        import websocket
        t = page_target()
        self.ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=60,
                                              origin=ORIGIN, max_size=None)
        self._id=0; self._resp={}; self.events=[]; self._run=True
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        while self._run:
            try: m=json.loads(self.ws.recv())
            except Exception: break
            if "id" in m: self._resp[m["id"]]=m
            elif "method" in m: self.events.append(m)
    def call(self, method, params=None, timeout=30):
        self._id+=1; rid=self._id
        self.ws.send(json.dumps({"id":rid,"method":method,"params":params or {}}))
        end=time.time()+timeout
        while time.time()<end:
            if rid in self._resp: return self._resp.pop(rid).get("result",{})
            time.sleep(0.02)
        return {}
    def close(self):
        self._run=False
        try: self.ws.close()
        except Exception: pass

def is_api(u):
    return ("/voyager/api/" in u or "/graphql" in u or "/rsc-action/" in u or "/sdui" in u.lower())
def layer(u):
    if "/rsc-action/" in u or "/sdui" in u.lower(): return "SDUI"
    if "/voyager/api/" in u or "/graphql" in u: return "VOYAGER"
    return "OTHER"

def main():
    start = sys.argv[1] if len(sys.argv)>1 else "https://www.linkedin.com/feed/"
    max_pages = int(sys.argv[2]) if len(sys.argv)>2 else 60
    max_depth = int(sys.argv[3]) if len(sys.argv)>3 else 3
    os.makedirs(OUTDIR, exist_ok=True)
    rec_file = os.path.join(OUTDIR, "recursive.json")
    url_file = os.path.join(OUTDIR, "recursive_urls.json")

    all_recs = json.load(open(rec_file)) if os.path.exists(rec_file) else []
    state = json.load(open(url_file)) if os.path.exists(url_file) else {"visited":[], "queue":[]}
    visited = set(state["visited"])
    queue = deque(state["queue"] or [[start,0]])
    if not queue: queue.append([start,0])

    start_chrome()
    c = Conn(); c.call("Network.enable"); c.call("Page.enable")

    pages_done = 0
    while queue and pages_done < max_pages:
        url, depth = queue.popleft()
        nu = norm(url)
        if nu in visited: continue
        if not chrome_alive():
            start_chrome(); c=Conn(); c.call("Network.enable"); c.call("Page.enable")
        c.events=[]
        try: c.call("Page.navigate", {"url":url}, timeout=15)
        except Exception: pass
        time.sleep(7)
        for _ in range(2):
            c.call("Runtime.evaluate", {"expression":"window.scrollTo(0,document.body.scrollHeight)"})
            time.sleep(1.8)
        visited.add(nu); pages_done += 1

        # Collect API calls
        reqmap={}
        for ev in c.events:
            if ev.get("method")=="Network.requestWillBeSent":
                p=ev["params"]; r=p.get("request",{}); u=r.get("url","")
                if is_api(u):
                    reqmap[p["requestId"]]={"page":url,"depth":depth,"method":r.get("method"),
                        "url":u,"layer":layer(u),"postData":r.get("postData")}
        for rid,rec in reqmap.items():
            try:
                b=c.call("Network.getResponseBody",{"requestId":rid},timeout=10)
                body=b.get("body","")
                rec["response_len"]=len(body); rec["response_sample"]=body[:1500]
            except Exception: pass
            all_recs.append(rec)

        # Extract links (a[href] + data-* menu targets)
        new_links=0
        if depth < max_depth:
            js = """JSON.stringify([...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href))])"""
            res = c.call("Runtime.evaluate", {"expression":js,"returnByValue":True})
            try:
                hrefs = json.loads(res.get("result",{}).get("value","[]"))
            except Exception:
                hrefs=[]
            for h in hrefs:
                if internal(h):
                    hn=norm(h)
                    if hn not in visited and not any(hn==norm(q[0]) for q in queue):
                        queue.append([h, depth+1]); new_links+=1

        # SAVE after each page
        json.dump(all_recs, open(rec_file,"w"), ensure_ascii=False)
        json.dump({"visited":sorted(visited), "queue":list(queue)}, open(url_file,"w"), ensure_ascii=False)
        v=sum(1 for r in reqmap.values() if r["layer"]=="VOYAGER")
        s=sum(1 for r in reqmap.values() if r["layer"]=="SDUI")
        print(f"[{pages_done}/{max_pages} d{depth}] {url[:52]:52s} api+{len(reqmap):3d}(V{v}/S{s}) links+{new_links} q={len(queue)} tot={len(all_recs)}", flush=True)

    c.close()
    print(f"\nFERTIG. {pages_done} Seiten, {len(all_recs)} API-Requests, {len(visited)} URLs besucht, {len(queue)} in Queue.")

if __name__=="__main__":
    main()
