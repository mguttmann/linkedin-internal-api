# 01 — Authentication & Cookie Extraction

All LinkedIn API auth hangs off **two cookies** from a logged-in browser session.
There is **no OAuth**, no API key — just the session cookies of a real login.

## The two decisive cookies

| Cookie | Role | Format |
|---|---|---|
| `li_at` | **Session token.** The actual "login". | `AQEDA…` (long opaque string) |
| `JSESSIONID` | **CSRF token.** Must be sent as header `csrf-token`. | `ajax:XXXXXXXXXXXXXXXXX…` |

**Core rule:** the `csrf-token` header = value of `JSESSIONID` **without surrounding quotes**
(the `ajax:` prefix stays). Without this header → **HTTP 403**.

Other cookies (`lidc`, `bcookie`, `liap`, …) are sent along but are not CSRF-critical.

## Key insight: no browser needed for the calls

The browser is used **only** to obtain fresh cookies. Once extracted, the actual API calls
run as **pure `requests` calls** (see `lib/vgreq.py`) — HTTP 200, no browser automation.

> **Historical pitfall:** early tests against `/voyager/api/me` returned a
> **302 redirect loop** → we wrongly suspected bot detection / fingerprinting.
> The real cause: the cookies were **expired** (the user was logged out).
> With **fresh** cookies the pure HTTP path works fine. Browser fingerprint plays NO role.

## Where do the cookies come from?

### The tool: `lib/cookies_extract.py` (via CDP)

When a Chrome with the logged-in profile is running (port 9222), the cookies are pulled
directly over the DevTools Protocol (`Network.getAllCookies`) — **including** `JSESSIONID`,
which is only set after the first page load. `lib/cookies_extract.py` does exactly this:
it loads `/feed/` first (so `JSESSIONID` gets set), then reads all cookies and writes them
to `/tmp/li_cookies.json`.

```python
import json, urllib.request, websocket, time
targets = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list'))
t = next(x for x in targets if x.get('type')=='page')
ws = websocket.create_connection(t['webSocketDebuggerUrl'], origin='http://127.0.0.1:9222')
def call(m,p=None):
    call.i = getattr(call,'i',0)+1
    ws.send(json.dumps({'id':call.i,'method':m,'params':p or {}}))
    while True:
        x=json.loads(ws.recv())
        if x.get('id')==call.i: return x.get('result',{})
# load the feed so JSESSIONID is set:
call('Page.enable'); call('Page.navigate',{'url':'https://www.linkedin.com/feed/'}); time.sleep(7)
cookies = call('Network.getAllCookies')['cookies']
li = {c['name']: c['value'] for c in cookies if 'linkedin' in c.get('domain','')}
json.dump(li, open('/tmp/li_cookies.json','w'))
```

**Chrome start command** (headless for cookie extraction, own automation profile so the
session persists):
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9222 \
  --remote-allow-origins=http://127.0.0.1:9222 \
  --user-data-dir="$HOME/.hermes/chrome-automation" --profile-directory=Default
```

> For **SDUI write actions** the same Chrome is used in **non-headless** (visible) mode,
> because LinkedIn does not render the post/edit modals reliably headless. See
> `docs/04-WRITE-OPERATIONS.md`.

## Session lifetime

- `li_at` stays valid for weeks to months — **no** re-login per call.
- If the session expires, a call lands on the login page (302 → `/uas/login`).
  Then log in **once** in the browser and re-extract cookies.

## Required headers (every call)

```
csrf-token:                 <JSESSIONID without quotes, e.g. ajax:XXXXXXXXXXXXXXXXX>
x-restli-protocol-version:  2.0.0
accept:                     application/vnd.linkedin.normalized+json+2.1
cookie:                     <all linkedin cookies as k=v; separated>
user-agent:                 <a normal desktop Chrome UA>
```

For SDUI calls, additionally: `content-type: application/json` plus various `x-li-*` headers
(see `docs/03-SDUI-API.md`).