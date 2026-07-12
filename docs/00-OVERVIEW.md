# 00 — Overview: LinkedIn's two API worlds

LinkedIn's web frontend talks to **two parallel backend architectures**. Anyone using the
internal API has to know both — many features live in only one of them.

```
┌─────────────────────────────────────────────────────────────┐
│                   Browser (logged in)                        │
│              Cookies: li_at + JSESSIONID                     │
└───────────────┬─────────────────────────┬───────────────────┘
                │                         │
      ┌─────────▼─────────┐     ┌─────────▼──────────────┐
      │   VOYAGER API     │     │   SDUI (rsc-action)    │
      │  /voyager/api/…   │     │ /flagship-web/rsc-     │
      │                   │     │   action/actions/…     │
      │ REST.li + GraphQL │     │ Server-Driven UI       │
      │ "normalized JSON" │     │ Protobuf-JSON          │
      └───────────────────┘     └────────────────────────┘
         established, broad         newer, growing
         read- & write-strong       some writes ONLY here
```

## Voyager — the established world

- **Path:** `/voyager/api/…`
- **Two styles:**
  - **REST.li**: classic resource paths, e.g. `/voyager/api/identity/dash/profiles/{urn}`
  - **GraphQL**: `/voyager/api/graphql?variables=(…)&queryId=<name>.<hash>`
- **Response:** "normalized JSON" — `data` (payload with URN references `*elements`),
  `included[]` (dereferenced entities), `meta.microSchema` (type info).
- **Auth:** `csrf-token` + `x-restli-protocol-version: 2.0.0` + normalized-accept.
- **requests-friendly:** works cleanly with pure Python `requests` (no browser).
- **Covers:** profile, feed, own posts, network, messages, search, jobs, organizations,
  notifications, premium, analytics — and **creating a post** + **setting a like**.

## SDUI — the new world

- **Path:** `/flagship-web/rsc-action/actions/…`
- **Principle:** the server drives the UI. The client sends **action requests** carrying an
  `sduiid` (e.g. `com.linkedin.sdui.reactions.delete`); the server replies with UI state.
- **Response:** protobuf-based (JSON-encoded), sometimes streaming (SSE via `server-stream-request`).
- **Auth:** like Voyager PLUS ephemeral page-bound headers (`x-li-page-instance`,
  `x-li-pageforestid`, `x-li-application-instance`, `x-li-application-version`).
- **less requests-friendly:** needs page-context headers → often easier via CDP in the page context.
- **Covers (and growing):** unlike, delete post, create/delete comment, profile save,
  home-nav, realtime, and other newer flows.

## Decision rule

> **If an operation is available over Voyager → use Voyager** (more stable, requests-friendly).
> **Only if Voyager fails (e.g. constant 400) → check SDUI.** Unlike is the textbook case:
> Voyager DELETE = 400, SDUI = works. Note the mixed pattern: **create post = Voyager,
> delete post = SDUI**; **set like = Voyager, unlike = SDUI**.

## How this was captured

Two complementary methods (details in `docs/05-VERIFICATION.md`):
1. A **self-discovering crawler** (`tools/crawl_recursive.py`) loads pages headless, records
   all API traffic (both worlds), extracts internal links and follows them recursively (BFS).
   This finds **read** endpoints automatically.
2. **Click-and-record** (`tools/capture_write_action.py`): drive a real action in the
   logged-in client and capture the exact request it fires. This is how every **write**
   endpoint was found — you cannot guess these.

## Consuming this: the MCP server

The reverse-engineered API is shipped as an **MCP server** (`../mcp/`, 26 tools) so any Claude can
read/write LinkedIn: reads (`get_me`, `get_my_posts`, `get_conversations`, …), posts
(`create_post`, `edit_post`, `delete_post`, `save_post`, `repost`, `create_poll`), engagement
(`like`, `unlike`), messaging (`send_dm`, `recall_message`, `react_to_message`), and network
(`connect`, `endorse_skill`, `remove_connection`, `follow_company`). Session persistence via a
patchright stealth browser; reads + most writes run browserless through pure `requests`.