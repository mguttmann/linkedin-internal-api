# 05 — Verification Methodology

How this documentation was produced — and how you (Claude or human) capture and verify new
endpoints yourself. Core principle: **real tool output beats speculation.** Every endpoint
here was either captured from real live traffic or confirmed by a real call with documented
HTTP status.

## Toolchain

```
┌──────────────────┐   1. cookies    ┌──────────────────┐
│  Chrome          │ ───────────────▶│  lib/vgreq.py    │  pure requests calls
│  (logged in,     │   (via CDP)     │  (NO browser)    │  against Voyager
│   port 9222)     │                 └──────────────────┘
│                  │
│  CDP Network     │   2. capture live traffic
│  domain          │ ──────────────────────────────────▶  tools/crawl_recursive.py
└──────────────────┘                                       tools/capture_write_action.py
```

## Method 1 — Discover endpoints (recursive crawl)

`tools/crawl_recursive.py` does breadth-first search over the logged-in web app:

1. Load page headless, scroll (trigger lazy-load)
2. Record **all** API traffic — Voyager (`/voyager/api/`) AND SDUI (`/rsc-action/`)
3. Extract all internal links (`a[href]`) → new ones into the queue → depth+1
4. Save after **every** page (survives Chrome crashes)

Safety: the crawler **only navigates** (GET). It clicks no buttons, so it triggers **no**
write operations. A blocklist filters out `logout`, `delete`, `remove`, `unfollow`, `report`.

> **Limit:** because the crawler only navigates, it finds **read** endpoints. Write endpoints
> (POST/DELETE) appear only when actually performing an action → Method 2.

## Method 2 — Capture write operations (click-and-record)

To learn how a mutation *really* works, let the **real LinkedIn client** perform the action
and capture the request it fires:

1. Load the target page (e.g. own post) in a **visible** Chrome (LinkedIn does not render the
   post/edit modals reliably headless)
2. Trigger the real control — most robustly via CDP `Runtime.evaluate` calling
   `document.querySelector(...).click()` (`.click()` in the DOM is more reliable than
   coordinate clicks, which break under Retina scaling)
3. Filter `Network.requestWillBeSent` events for the mutation endpoint
   (`/voyager/api/` or `/rsc-action/`)
4. Extract method, URL, headers, body
5. Immediately reverse the action (delete the test post/comment) and verify it is gone

This is how we found that **unlike runs over SDUI** (not Voyager), and likewise the real
schemas for **create/delete post**, **create/delete comment**, and **profile save** — none of
which could be found by guessing. Every guessed Voyager path returned 400/404; only the
capture revealed the real endpoint.

> **Two DOM realities:** the comment editor is a normal `contenteditable` in the DOM
> (`.click()` + `Input.insertText` work). The **post composer** and **profile edit** editors
> sit in an iframe/shadow-DOM — the modal opens, but the editor is not reachable via normal
> DOM selectors. For those, drive the real client with coordinate/keyboard input, or just
> capture the save request (the endpoint + schema are what we document).

## Method 3 — Direct call + verification (with reversion)

For write ops on the owner's own account:

1. **Save the original** (GET before the change — e.g. headline value, reaction list)
2. **Perform the action** (POST) → document HTTP status + `X-RestLi-Id` header
3. **Verify** (GET after — is the change visible?)
4. **Revert** (delete / restore the original value)
5. **Verify reversion** (GET — is the original state restored?)

Example like: POST → 201 + `X-RestLi-Id`, GET shows own reaction, SDUI delete, GET shows
reaction gone. ✅

## The 302-vs-fresh-cookies fallacy (important lesson)

Early Voyager calls returned **302 redirect loops**. We wrongly concluded bot detection /
TLS fingerprinting and built a stealth browser. **Real cause:** expired cookies (user logged
out). After a fresh login + cookie extraction, the **pure `requests` path** works fine
(HTTP 200).

**Lesson:** on 302/401/403, first check **cookie freshness** (`GET /voyager/api/me` → 200?)
before assuming anything complex.

## Response status cheat sheet

| Status | Meaning | First action |
|---|---|---|
| 200 | OK (GET) | — |
| 201 | Created (POST) | remember `X-RestLi-Id` header = new URN |
| 302 → /uas/login | Session dead | re-login, re-fetch cookies |
| 400 | Wrong schema/key | check body/key format; likely it is SDUI, not Voyager |
| 403 | CSRF missing | set `csrf-token` header = JSESSIONID |
| 429 | Rate limit | slow down, add pauses |