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

## Notes
- The MCP is a pure API client: no browser, no clicking (refactor 01980e5). Session login/
  refresh is external (session_daemon.py keeps /tmp/li_cookies.json fresh).
