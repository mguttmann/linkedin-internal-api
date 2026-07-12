#!/usr/bin/env python3
"""capture_session.py — Reusable CDP capture helper for the enterprise audit.

Drives the real (visible) LinkedIn client and records EVERY mutation request
(POST/PUT/DELETE on /voyager/api/ or /rsc-action/) with full body + response headers.

Two ways to use:
  - As a library: import CaptureSession, drive the page via .click_dom()/.type()/.nav(),
    read .mutations after each step.
  - The recorder keeps a rolling log; call .clear() before an action and read .mutations
    after to isolate exactly which requests one action fired.

This is the backbone of "click-and-record": we never guess an endpoint, we perform the
real action and capture what the client actually sends.
"""
import json, urllib.request, websocket, time, sys, os, random
import fcntl, contextlib

CDP = "http://127.0.0.1:9222"
_LOCK_PATH = "/tmp/li_browser.lock"

# --- Human pacing (anti-flag) -------------------------------------------------
# Rapid, evenly-spaced, cache-busted requests are the #1 bot tell that gets the
# session force-logged-out. Every navigation/action goes through human_pause():
# randomized think-time, no fixed cadence. Tune globally here.
PACING = True                 # set False only for offline/dry runs
PAUSE_MIN, PAUSE_MAX = 6.0, 14.0     # between page loads / major actions
MICRO_MIN, MICRO_MAX = 0.4, 1.6      # between small UI steps (click, type)

def human_pause(kind="page"):
    """Sleep a randomized, human-like interval. kind='page' (big) or 'micro' (small)."""
    if not PACING:
        return
    lo, hi = (PAUSE_MIN, PAUSE_MAX) if kind == "page" else (MICRO_MIN, MICRO_MAX)
    time.sleep(random.uniform(lo, hi))

@contextlib.contextmanager
def browser_lock(timeout=180):
    """Serialize foreground browser interaction across parallel agents.
    Wrap an open-form -> fill -> save sequence in `with browser_lock():`."""
    f = open(_LOCK_PATH, "w")
    end = time.time() + timeout
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); break
        except BlockingIOError:
            if time.time() > end:
                raise TimeoutError("browser_lock timeout")
            time.sleep(0.5)
    try:
        yield
    finally:
        try: fcntl.flock(f, fcntl.LOCK_UN); f.close()
        except Exception: pass

def _list_pages():
    ts = json.load(urllib.request.urlopen(f"{CDP}/json/list"))
    return [x for x in ts if x.get("type") == "page"]

def _new_tab(url="https://www.linkedin.com/feed/"):
    """Create a fresh tab and return its target dict (parallel-safe)."""
    t = json.load(urllib.request.urlopen(urllib.request.Request(f"{CDP}/json/new?{url}", method="PUT")))
    time.sleep(2)
    return t

def _page_ws():
    pages = _list_pages()
    if not pages:
        _new_tab(); pages = _list_pages()
    return pages[0]["webSocketDebuggerUrl"]

class CaptureSession:
    def __init__(self, new_tab=False):
        """new_tab=True creates its OWN tab so multiple agents can capture in parallel
        without stealing each other's page. Remembers the target id to close it later."""
        self._own_target = None
        if new_tab:
            t = _new_tab()
            self._own_target = t.get("id")
            ws_url = t["webSocketDebuggerUrl"]
        else:
            ws_url = _page_ws()
        self.ws = websocket.create_connection(ws_url, timeout=60, origin=CDP, max_size=None)
        self._id = 0
        self.mutations = {}     # requestId -> {method,url,postData}
        self.reads = {}         # requestId -> {method,url}  (only when capture_reads=True)
        self.capture_reads = False   # set True to also record GET API calls
        self._resp_hdr = {}
        self.call("Network.enable"); self.call("Page.enable")
        self.call("Emulation.setDeviceMetricsOverride",
                  {"width":1440,"height":900,"deviceScaleFactor":1,"mobile":False})

    def call(self, method, params=None, timeout=30):
        self._id += 1; rid = self._id
        self.ws.send(json.dumps({"id":rid,"method":method,"params":params or {}}))
        end = time.time()+timeout
        while time.time() < end:
            m = json.loads(self.ws.recv())
            if m.get("id") == rid:
                return m.get("result", {})
            self._drain(m)
        return {}

    def _drain(self, m):
        meth = m.get("method")
        if meth == "Network.requestWillBeSent":
            p = m["params"]; r = p.get("request", {})
            u = r.get("url","")
            if r.get("method") in ("POST","PUT","DELETE") and ("/voyager/api/" in u or "/rsc-action/" in u):
                # skip pure infra noise
                if not any(k in u for k in ["TrackingPixel","app-config","presenceStatuses",
                                            "realtimeDefaultHandler","cooloff","Metrics","tscp"]):
                    self.mutations[p["requestId"]] = {"method":r["method"],"url":u,
                                                       "postData":r.get("postData")}
            elif self.capture_reads and r.get("method") == "GET" and ("/voyager/api/" in u or "/rsc-action/" in u):
                if not any(k in u for k in ["TrackingPixel","app-config","presenceStatuses",
                                            "realtimeDefaultHandler","cooloff","Metrics","tscp"]):
                    self.reads[p["requestId"]] = {"method":"GET","url":u}
        elif meth == "Network.responseReceived":
            rid = m["params"].get("requestId")
            if rid in self.mutations:
                self._resp_hdr[rid] = m["params"].get("response",{}).get("headers",{})

    def pump(self, seconds):
        """Read events for N seconds (to catch async mutations after an action)."""
        end = time.time()+seconds
        self.ws.settimeout(0.5)
        while time.time() < end:
            try: self._drain(json.loads(self.ws.recv()))
            except Exception: pass
        self.ws.settimeout(60)

    def clear(self):
        self.mutations = {}; self._resp_hdr = {}

    def nav(self, url, wait=9, pace=True):
        """Navigate, wait for load, then a randomized human pause.

        NOTE (anti-flag): do NOT append cache-busting query params like ?nc=<timestamp>.
        Reloading the same URL many times per minute is a bot tell. Navigate to the real URL
        and trust the browser's normal cache. For a post-write freshness check, prefer a
        vgreq read over re-navigating.
        """
        if "nc=" in url or "?fresh=" in url:
            print("  [pacing] warn: cache-bust param in URL — avoid; navigating anyway", file=sys.stderr)
        self.clear(); self.call("Page.navigate", {"url":url}); time.sleep(wait)
        if pace:
            human_pause("page")

    def ev(self, js):
        return self.call("Runtime.evaluate", {"expression":js,"returnByValue":True}).get("result",{}).get("value")

    def click_dom(self, js_finder):
        """js_finder returns an element; we .click() it in-page. Returns status string."""
        return self.ev("(()=>{const el=(" + js_finder + ");if(!el)return 'not-found';el.click();return 'clicked';})()")

    def type_text(self, text, human=True):
        """Type text. When human=True, insert char-by-char with small random delays
        instead of pasting the whole string at once (more natural, less bot-like)."""
        if not human or not PACING:
            self.call("Input.insertText", {"text": text}); return
        for ch in text:
            self.call("Input.insertText", {"text": ch})
            time.sleep(random.uniform(0.04, 0.18))

    def click_xy(self, x, y):
        """Real mouse click at viewport coords (natural interaction, survives portals)."""
        try: self.call("Page.bringToFront")
        except Exception: pass
        human_pause("micro")
        self.call("Input.dispatchMouseEvent", {"type":"mouseMoved","x":x,"y":y})
        time.sleep(random.uniform(0.12, 0.35))
        self.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
        time.sleep(random.uniform(0.05, 0.14))
        self.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})

    def focus_tab(self):
        try: self.call("Page.bringToFront")
        except Exception: pass

    def click_label(self, needle, index=-1, contains=True):
        """Find visible element whose aria-label/innerText matches `needle`, then REAL-mouse-click
        its center. index selects among matches (default last). Returns 'clicked'|'not-found'."""
        js = (
            "(()=>{const n=%s;const c=%s;"
            "const els=[...document.querySelectorAll('button,a,[role=button],[role=menuitem],div[role=button]')]"
            ".filter(e=>{const t=((e.getAttribute('aria-label')||'')+'|'+(e.innerText||'')).trim();"
            "const r=e.getBoundingClientRect();return r.height>0&&r.width>0&&(c?t.includes(n):t.split('|').includes(n));});"
            "if(!els.length)return '';const el=els.at(%d);const r=el.getBoundingClientRect();"
            "el.scrollIntoView({block:'center'});const r2=el.getBoundingClientRect();"
            "return JSON.stringify({x:Math.round(r2.x+r2.width/2),y:Math.round(r2.y+r2.height/2)});})()"
            % (json.dumps(needle, ensure_ascii=False), "true" if contains else "false", index)
        )
        coord = self.ev(js)
        if not coord:
            return "not-found"
        c = json.loads(coord); self.click_xy(c["x"], c["y"]); return "clicked"

    def resp_body(self, rid):
        """Fetch a captured response body by requestId (for documenting reads)."""
        try:
            r = self.call("Network.getResponseBody", {"requestId": rid})
            return r.get("body")
        except Exception:
            return None

    def dump(self, label=""):
        out = []
        for rid, r in list(self.mutations.items()):
            hdr = self._resp_hdr.get(rid, {})
            restli = hdr.get("X-RestLi-Id") or hdr.get("x-restli-id")
            r2 = dict(r); r2["x_restli_id"] = restli; r2["request_id"] = rid
            out.append(r2)
        if label:
            print(f"=== {label}: {len(out)} mutation(s) ===")
            for r in out:
                print(f">>> {r['method']} {r['url'][:120]}")
                if r["postData"]: print(f"    BODY: {r['postData'][:400]}")
                if r["x_restli_id"]: print(f"    X-RestLi-Id: {r['x_restli_id']}")
        return out

    def close(self):
        try: self.ws.close()
        except Exception: pass
        if self._own_target:
            try:
                urllib.request.urlopen(urllib.request.Request(f"{CDP}/json/close/{self._own_target}", method="GET"))
            except Exception: pass

if __name__ == "__main__":
    s = CaptureSession()
    print("CaptureSession ready. Page:", s.ev("location.href"))
    s.close()
