# Backlog — linkedin-internal-api MCP

Open items, honestly scoped. Verified facts only (✅ done / 🔍 diagnosed / ⏳ todo).

## ⏳ reply_to_comment (nested replies)

**Status:** diagnosed, not implemented (2026-07-16).

`create_comment` posts **top-level comments only** (browserless SDUI createComment, verified).
Replying *to a comment* (nested, e.g. under a specific person) needs a `parentComment` binding
that top-level create does not carry.

**Why it's not built yet:** the existing capture `api-docs/_writes/comment_reply.json` is
**unusable** — it contains no parent-comment reference at all. Its two requests
(`submitCommentButton` + `createComment`) are byte-for-byte identical to the top-level
`comment_create.json` except for the random `trackingId` and the `commentBoxText` token (which
is also identical). The only "parent" strings are `parentSpanId` in the URL, which is a UI span
tracking value, NOT a comment reference. Both captures carry only the post activity id
(`7469679647589412864`) — so the "reply" capture was almost certainly a mislabeled top-level
comment, or the parent binding lives somewhere the capture didn't record.

**To implement:**
1. Self-capture a REAL reply to an OWN test comment via CDP (own comment only — no third party),
   clean up the test comment immediately after.
2. Diff against top-level create to isolate the parent-comment binding (likely inside the
   `commentBoxText` protobuf token, or an extra field in the submit request).
3. Add `reply_to_comment` as a template method (same pattern as unlike / react_to_comment:
   captured body template + minimal headers), confirm-gated, verified live.

Until then, replies must be posted manually — the agent correctly declines to guess.

## ⏳ Stale tool counts in the docs ("26 tools")

**Status:** diagnosed, not fixed — foreign scope of the read-only ticket (2026-07-30).

`README.md` (5×), `docs/MCP-DESIGN.md` (3×), `docs/00-OVERVIEW.md` and `mcp/README.md` still say
**26 tools** (`grep -n '26 tools\|26 MCP tools\|26 @mcp.tool' README.md docs mcp/README.md`). The registry
holds **29** (10 reads + 19 writes) — `create_comment`, `delete_comment` and `react_to_comment`
were added later and never counted. Two tests now hold the exact set
(`mcp/tests/test_server.py` `EXPECTED`, and the read/write split in `mcp/tests/test_readonly.py`),
so the number is no longer guesswork.
**To fix:** replace every occurrence (including the badge line and the mermaid label
`26 @mcp.tool` in `README.md`) with the tested split, and re-check the per-domain tool lists in the
same sections — they omit the three comment tools too.
Same class: `mcp/README.md` states `test_client.py (19/19)`; that file now holds 31 tests.

## ⏳ Seven writing tools have no `confirm` gate

**Status:** observation, deliberately unchanged (2026-07-30) — needs an owner decision.

`like`, `unlike`, `follow_company`, `endorse_skill`, `save_post`, `create_poll` and
`react_to_message` fire a real write on the **first** call; the other twelve writes require
`confirm=True`. `endorse_skill` is the sharpest case: it writes on a **third party's** profile.
`LINKEDIN_READ_ONLY` now covers all seven in unattended operation, but with the flag off they are
still one call away.
**To decide:** whether these get `confirm=True` as well (changes the tool contract for every
existing caller) or stay ungated by intent. Not a defect — a design decision.

## Notes
- The MCP is a pure API client: no browser, no clicking (refactor 01980e5). Session login/
  refresh is external (session_daemon.py keeps /tmp/li_cookies.json fresh).
- Read-only mode (`LINKEDIN_READ_ONLY`) is an operating mode of `mcp/server.py`, not a library
  guarantee: `tools/*.py` and tests importing `LinkedInClient` directly are not covered by it.
  Documented as such in `26-READ-ONLY-MODE.md` §7 — do not restate it more strongly elsewhere.
