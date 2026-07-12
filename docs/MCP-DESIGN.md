# MCP Server Design — `linkedin-mcp`

> **Historical design brief.** This captured the rationale *before* the server was built; it is
> kept for the "why," but the shipped implementation is authoritative — see `../mcp/README.md`.
> Sections describing proposed layout/questions are marked as resolved where they diverged.
>
> Goal: expose the reverse-engineered LinkedIn API as an
> **MCP server** so any Claude (Claude Desktop, Cursor, Hermes, the Anthropic API) can read and
> write LinkedIn directly — the thing the official API + Composio can't do.
>
> Built on: **FastMCP** (the tool/transport layer) + **patchright** (the stealth, always-logged-in
> browser that solves our session problem) + **our existing `lib/vgreq.py` + `lib/sdui_replay.py`**
> (the actual API calls).
>
> **STATUS (updated): BUILT.** This started as a design brief; the server now exists under
> `../mcp/` with **26 tools live** (reads + core writes verified, offline tests 4/4 + 19/19).
> The sections below are the original design rationale — kept for the "why". Where the shipped
> code diverges from the early sketch, **the code is authoritative**: see `../mcp/README.md` for
> the real tool list and `../docs/COVERAGE-MAP.md` for per-tool status. Notably the final tool
> names/set differ from the v1 inventory in §4 (e.g. no `get_feed`/`comment`/`mark_read`; the
> real set is the 26 in `../mcp/server.py`).

---

## 1. Why this shape

Two facts from the audit drive the whole design:

1. **Most operations are browserless.** Reads, like, messaging, follow-company, and — proven —
   profile *create* run over pure `requests` with cookies (`lib/vgreq.py`). No browser in the
   hot path → fast, cheap, reliable.
2. **But we still need a browser for two things:** (a) obtaining/refreshing the session cookies,
   and (b) the handful of SDUI writes that a pure-requests replay can't do yet (profile *delete*
   is a no-op without the form's preceding `component` call). Today's crash showed the weak
   spot: when Chrome dies, the session logs out and a human has to log back in.

**patchright fixes exactly that.** Its `launch_persistent_context(user_data_dir=…, channel="chrome")`
gives an **undetected, persistent** Chrome profile that stays logged in across restarts and
passes Cloudflare/bot-detection. So the MCP owns its own long-lived logged-in browser instead of
depending on a hand-started Chrome we babysit.

→ **Design principle: requests-first, browser-fallback.** Every tool tries the browserless path;
the browser is the session source + the fallback executor, not the default.

---

## 2. Architecture (layers)

```
┌───────────────────────────────────────────────────────────────┐
│  MCP client  (Claude Desktop / Cursor / Hermes / Anthropic API)│
└───────────────▲───────────────────────────────────────────────┘
                │  MCP protocol (stdio or HTTP)
┌───────────────┴───────────────────────────────────────────────┐
│  FastMCP server  (server.py)                                   │
│   @mcp.tool  send_dm / create_post / like / add_skill / …      │
│   - schema + validation auto-generated from Python signatures  │
│   - guardrails: own-account-only, destructive-op confirmation  │
└───────────────▲───────────────────────────────────────────────┘
                │  calls
┌───────────────┴───────────────────────────────────────────────┐
│  LinkedInClient  (lib/client.py) — the facade                  │
│   .read()  .write()  — picks the path per operation            │
│      ├─ requests path  → lib/vgreq.py  (browserless, primary)  │
│      └─ browser path   → SessionBrowser (patchright, fallback) │
└──────────▲────────────────────────────▲───────────────────────┘
           │                            │
┌──────────┴─────────┐      ┌───────────┴──────────────────────┐
│ vgreq.py (existing)│      │ SessionBrowser (patchright, NEW)  │
│ pure requests      │      │ persistent context, always logged │
│ Voyager + SDUI     │      │ in; refreshes cookies on demand;   │
│                    │      │ executes SDUI form flows           │
└────────────────────┘      └────────────────────────────────────┘
                                     │ supplies cookies to
                                     └────────► /tmp/li_cookies.json
```

The `docs/` reverse-engineering reference IS the spec: each MCP tool maps to a verified endpoint
already documented (endpoint, body, states[] behaviour). We are not discovering here — we are
wrapping what's proven.

---

## 3. Session / auth strategy (the important part)

**SessionBrowser** (new, `lib/session_browser.py`), built on patchright:

- Launches ONE persistent context: `launch_persistent_context(user_data_dir="~/.hermes/li-mcp-profile", channel="chrome", headless=False, no_viewport=True)` — per patchright best practice (no custom UA/headers, real Chrome).
- **Stays logged in across restarts** (persistent user_data_dir). First-run: human logs in once; after that the profile carries `li_at` for weeks/months.
- Exposes `cookies() -> dict` (dumps fresh cookies for `vgreq`) and `run_form(flow)` (drives an SDUI form for the ops requests can't replay yet).
- **Health check + self-heal:** on `is_logged_in()==False`, surface a clear MCP error/elicitation ("LinkedIn session expired — log in in the browser window") instead of silently failing. patchright's stealth means far fewer forced logouts than our current hand-started Chrome.

This directly removes today's failure mode (crash → logout → blocked on human).

### Session bootstrap — verified findings (2026-07-11)

Live-tested the patchright persistent context. What holds and what doesn't:

- ✅ **patchright launches + CDP works.** `launch_persistent_context(channel="chrome",
  cdp_port=9222)` starts, exposes `/json`, and our `capture_session` can attach — proven
  offline on a throwaway profile, without touching the live session.
- ✅ **Cookie injection + settle writes li_at to the persistent SQLite DB.** `inject_cookies()`
  (add_cookies → then load `/feed` so the server re-affirms via Set-Cookie) DOES land `li_at`
  in `Default/Cookies` — verified by reading the DB directly.
- ❌ **But a fresh restart overwrites it.** On the next clean start, Chrome loads the DB, has no
  live `li_at` in memory yet, and on clean **exit** flushes its in-memory jar back — clobbering
  the persisted `li_at`. So injection-from-outside loses a race with Chrome's shutdown flush.
- ➡️ **Conclusion:** the only robust way to persist `li_at` across restarts is a **real login
  inside the patchright window** (LinkedIn sets the cookie itself; Chrome persists it through
  its normal lifecycle). Injection is a one-shot bridge for the current process only, not a
  durable bootstrap. **Next step:** one human login in the patchright window → then it survives.

### ✅ RESOLVED (2026-07-11): real login persists across restarts

Confirmed the conclusion above. A one-time human login in the patchright stealth window
(`bootstrap_login.py`, profile `~/.hermes/li-mcp-profile`) made `li_at` land in the persistent
SQLite DB *and* survive a full clean restart:
- after login: `/me` → 200, `li_at` present in `Default/Cookies`.
- kill the window → fresh `SessionBrowser().start()` with NO injection → `li_at` loaded from
  disk, `is_logged_in()` True, `/me` → 200.

**The crash→logout failure mode is gone.** The audit + MCP now run on this persistent, stealth
session. Cookie injection stays in the codebase as a same-process bridge, but the durable
bootstrap is the one-time login.

---

## 4. Tool inventory (v1 — all map to verified endpoints)

Grouped; each is a thin wrapper over `LinkedInClient`. Reads + safe writes first.

**Read (browserless):**
- `get_me()` · `get_profile(vanity?)` · `get_my_posts(count)` · `get_feed(count)`
- `get_conversations()` · `get_messages(conversation_urn)` · `get_comments(activity_urn)`

**Posts & engagement (browserless):**
- `create_post(text, visibility)` · `delete_post(urn)`
- `like(urn)` · `unlike(urn)` · `comment(urn, text)` · `delete_comment(comment_urn)`
- `save_post(urn)` · `repost(urn)`

**Messaging (browserless):**
- `send_dm(conversation_urn, text)` · `react_dm(message_urn, emoji)` · `mark_read(conversation_urn)`
  *(recipient-facing sends are gated — see guardrails)*

**Network (browserless + browser):**
- `follow_company(urn)` · `unfollow_company(urn)` · `follow_person(member_id)`
- `send_connection(member_id)` · `accept_invitation(id)` / `ignore_invitation(id)`

**Profile editing (browser form; create also browserless via sdui_replay):**
- `add_skill/language/education/certification/project/course/…` + `delete_*` — the profile-editing
  sections, all following the documented `saveProfile<X>Form` / `deleteProfile<X>` pattern.

Each tool's docstring = the LLM-facing contract; FastMCP turns the Python signature into the
JSON schema automatically (that's the whole point — `@mcp.tool def send_dm(...)` and done).

---

## 5. Guardrails (non-negotiable, baked into tools)

- **Own account only.** No tool takes "act as another user". Reads of other profiles are fine;
  writes target only the owner's account/content.
- **Destructive / people-facing ops require confirmation.** `send_dm`, `send_connection`,
  `delete_post`, bulk anything → use FastMCP **elicitation** (or a `confirm=True` arg) so the
  human okays it. Mirrors how we've been running the audit (clarify before touching real people).
- **No mass automation.** Rate-limit + no loops over strangers. ToS reality stays in the README.
- **Secrets never leave the box.** Cookies live in the persistent profile / tmp, never in tool
  args or responses.

---

## 6. FastMCP wiring + connecting to Claude

Minimal server (real FastMCP API):
```python
from fastmcp import FastMCP
from lib.client import LinkedInClient

mcp = FastMCP("linkedin 🔗")
li = LinkedInClient()          # requests-first, patchright session under the hood

@mcp.tool
def create_post(text: str, visibility: str = "PUBLIC") -> dict:
    """Publish a post on the owner's LinkedIn. Returns the created activity URN."""
    return li.create_post(text, visibility)

@mcp.tool
def send_dm(conversation_urn: str, text: str, confirm: bool = False) -> dict:
    """Send a direct message. Requires confirm=True (people-facing)."""
    if not confirm:
        return {"needs_confirmation": True, "preview": text}
    return li.send_dm(conversation_urn, text)

if __name__ == "__main__":
    mcp.run()   # stdio by default; mcp.run(transport="http", port=…) for remote
```

**Connect to Claude:** FastMCP ships `fastmcp install` for Claude Desktop/Cursor, or add to the
client's MCP config (stdio: command = `python server.py`). For Hermes/remote: run
`mcp.run(transport="http")` and point the client at the URL. Docs:
`gofastmcp.com/integrations` + `cli/install-mcp`.

---

## 7. Proposed repo layout (`linkedin-mcp/`, sibling to the docs repo)

```
linkedin-mcp/
├── server.py                 # FastMCP app: @mcp.tool definitions (thin)
├── lib/
│   ├── client.py             # LinkedInClient facade (requests-first, browser-fallback)
│   ├── session_browser.py    # patchright persistent context + cookie refresh (NEW)
│   ├── vgreq.py              # reused from linkedin-internal-api
│   └── sdui_replay.py        # reused
├── flows/                    # SDUI form flows for ops requests can't replay (profile deletes)
├── tests/                    # tool-schema tests + a live smoke test (get_me → 200)
├── fastmcp.json              # declarative config (portable)
└── README.md
```
Reuse over rewrite: `vgreq.py` and `sdui_replay.py` come straight from the internal-api repo; the
docs there are the endpoint spec.

---

## 8. Phased build plan

- **P0 — session:** `SessionBrowser` on patchright; prove it stays logged in across a restart and
  yields cookies that make `vgreq.get(/me)==200`. (Solves today's blocker.)
- **P1 — read tools:** `get_me/get_profile/get_my_posts/get_feed/get_messages` over requests.
  Smoke test from a real MCP client (Claude Desktop).
- **P2 — safe writes:** `like/unlike/comment/save_post/create_post/delete_post`. Verify + revert.
- **P3 — messaging + network** with confirmation gating.
- **P4 — profile editing:** the 16 sections via the documented pattern (browserless create where
  possible, browser form for delete).
- **P5 — packaging:** `fastmcp.json`, `fastmcp install`, README, remote/HTTP option.

---

## 9. Design questions (resolved during the build)

These were the open decisions when this brief was written; the shipped implementation
resolved them as noted:

1. **Transport:** local stdio first. → shipped stdio (FastMCP); HTTP left for later.
2. **patchright vs. Chrome:** persistent stealth context on patchright. → shipped
   (`session_browser.py`, `launch_persistent_context`).
3. **Scope of v1 tools:** ship everything verified from real traffic. → 26 tools shipped
   (reads + engagement + posts + messaging + network); profile-editing stays reference-only.
4. **Repo layout:** `mcp/` subfolder inside `linkedin-internal-api`. → shipped as such.
