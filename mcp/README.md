# linkedin-mcp

MCP server that exposes the reverse-engineered LinkedIn API (see `../docs/`) as tools any Claude
can call. Built on **FastMCP** (tool/transport) + **patchright** (persistent, stealth,
always-logged-in Chrome) + the repo's proven **`lib/vgreq.py`** (pure-requests Voyager client).

Design + rationale: **`../docs/MCP-DESIGN.md`**.

## Status: working (reads + core writes live-verified)
- ✅ 26 tools registered; schema auto-generated from Python signatures.
- ✅ **Session persistence solved:** `SessionBrowser` (patchright persistent context) survives
  Chrome crashes/restarts and stays logged in — no more "crash → logged out". One human login in
  the stealth window bootstraps it; cookies are dumped for `vgreq` (browserless requests after).
- ✅ **Reads live-verified:** `get_me`, `get_my_posts` (own posts full text — the Composio gap),
  `get_profile`, `get_notifications`, `get_conversations`, `get_connections_summary`,
  `get_post_comments`, `get_link_preview`.
- ✅ **Writes live-verified browserless:** `like` (201), `create_post`/`edit_post`/`create_poll`
  (posted→edited→deleted end-to-end), `save_post`, `send_dm`+`recall_message` (send 200→recall
  204), `follow_company`, `endorse_skill` (200), `connect`, `remove_connection`.
- ⚠️ **`unlike`:** endpoint captured; pure-requests replay returns 500 (needs the browser's
  `currentActor` binding) — the tool reports this honestly, browser path is reliable.
  `repost` shares this limitation (browser-only headless).
- 🔒 Guardrails: people-facing / destructive tools (`create_post`, `edit_post`, `delete_post`,
  `send_dm`, `recall_message`, `repost`, `delete_repost`, `connect`, `remove_connection`)
  require `confirm=True`.
- 🔒 **Read-only mode:** `LINKEDIN_READ_ONLY=1` blocks **every** writing tool outright (it raises;
  reads keep working). Recommended default for cron / unattended agents. Offline-proven, not yet
  live-tested — full reference incl. its honest limit: `../docs/26-READ-ONLY-MODE.md`.

## Layout
```
mcp/
├── server.py              # FastMCP app: @mcp.tool definitions (thin)
├── lib/
│   ├── client.py          # LinkedInClient facade (requests-first, browser-fallback)
│   └── session_browser.py # patchright persistent context + cookie refresh
├── session_daemon.py      # holds the stealth session alive on CDP 9222 for capture tooling
├── bootstrap_login.py     # one-time: open stealth window, wait for human login, persist
├── login_once.py          # one-time: form login from LI_EMAIL/LI_PASS env (gitignored — create locally)
├── tests/
│   ├── conftest.py        # pins the ambient env: removes LINKEDIN_READ_ONLY per test
│   ├── test_server.py     # offline: tool registration + guardrails (4/4)
│   ├── test_readonly.py   # offline: LINKEDIN_READ_ONLY gate — every write blocked, zero calls
│   └── test_client.py     # offline: write bodies + endpoints, mocked vgreq
└── .venv/                 # dedicated venv (gitignored)
```

## Run
```bash
cd mcp
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python fastmcp patchright requests
.venv/bin/patchright install chromium

.venv/bin/python tests/test_server.py     # offline → 4/4
.venv/bin/python tests/test_client.py     # offline → 19/19
.venv/bin/python bootstrap_login.py        # first run: log in once in the stealth window
.venv/bin/python server.py                 # stdio (Claude Desktop/Cursor/Hermes)
.venv/bin/python server.py --http          # HTTP transport (remote/shared)
```

## Connect to Claude
- **Claude Desktop / Cursor:** `fastmcp install` or add a stdio server (command = `python server.py`).
- **Remote/Hermes:** `server.py --http`, point the client at the URL.

## Tools (26)
**Reads** (browserless, live-verified): `get_me`, `get_my_posts`, `get_profile`,
`get_notifications`, `get_conversations`, `get_connections_summary`, `get_post_comments`,
`get_link_preview`.
**Posts:** `create_post` (+`poll_urn`), `edit_post`, `delete_post`, `create_poll`, `save_post`,
`repost`, `delete_repost` — the last one is **not operational**: its `queryId` hash is missing, so it
returns `status: "not_configured"` / `ok: False` / `retryable: False` **without sending the delete
request** — the client method makes no call at all, the tool still runs its `ensure_session()` GET
on `/me` first (`../docs/10-POST-INTERACTIONS.md`, `../docs/BACKLOG.md`).
**Engagement:** `like` (browserless 201), `unlike` (browser-reliable).
**Messaging:** `send_dm`, `recall_message`, `react_to_message`.
**Network:** `follow_company`, `connect`, `endorse_skill`, `remove_connection`.
**Session:** `session_status` (no browser), `refresh_session` (launches Chrome).
Full endpoint map: `../docs/COVERAGE-MAP.md` + `../docs/04-WRITE-OPERATIONS.md`.

### Read-only operation

```bash
LINKEDIN_READ_ONLY=1 .venv/bin/python server.py    # reads only; every write raises
```

Only `0` and `false` (any case) switch it off; unset/empty do too. **Any** other value — including
`off`, `no` or a typo like `ja` — counts as ON (plus a warning on stderr), so a mistyped value can
never hand out write access. `session_status()` reports `read_only: true|false`, so an agent can
check the mode without attempting a write. The flag is an **operating mode of this server**, not a
library guarantee: code that imports `LinkedInClient` directly (`tools/*.py`, tests) bypasses it.
Details, whitelisted `dry_run` path and test evidence: `../docs/26-READ-ONLY-MODE.md`.

> **Design principle — requests-first, browser-fallback:** every tool tries the browserless
> `vgreq` path first (fast/invisible); the patchright browser is only the session source + the
> fallback for the few SDUI deletes requests can't yet reproduce.