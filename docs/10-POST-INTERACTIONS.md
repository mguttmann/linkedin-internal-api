# 10 — Post interactions (verified)

Beyond create/delete (04) and reactions (04/07), these are the everyday post actions on
someone else's (or your own) post. Captured live and cleaned up (test save + repost undone).

Post URN: `urn:li:activity:<id>`. Feed control-menu actions run over SDUI; some deletes go
back to Voyager GraphQL.

---

## ✅ Save a post ("Für später speichern")

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.update.saveState
Body: {
  "requestId": "com.linkedin.sdui.update.saveState",
  "serverRequest": { ...
    "payload": {
      "isSaved": true,
      "saveObjectUrn": { "saveEntityUrnFeedUpdateUrn": {
        "feedUpdateUrn": { "updateUrnActivityUrn": { "activityUrn": { "activityId": "<id>" }}}
      }}
    }
  }
}
```
- UI: post "…" menu → **"Speichern"**.
- **Verified:** post saved (appeared in /my-items/saved-posts/). ✅

## ✅ Unsave a post

Same endpoint, `"isSaved": false`.
- UI: "…" menu shows **"Nicht mehr speichern"** once saved.
- **Verified:** post unsaved. ✅

> The control menu also fires a `feedUpdateControlMenuRequest` (fetches the menu items) —
> that's a read, not the mutation. The mutation is `saveState`.

---

## ✅ Repost instantly ("Sofort teilen")

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.feed.requests.createInstantRepost
Body: {
  "requestId": "com.linkedin.sdui.feed.requests.createInstantRepost",
  "serverRequest": { ...
    "payload": {
      "threadUrn": { "threadUrnActivityThreadUrn": { "activityUrn": { "activityId": "<original postId>" }}}
    }
  }
}
```
- UI: post repost button → **"Sofort teilen"** (vs. "Mit Kommentar teilen" = quote repost).
- **Verified:** repost created (appeared in my recent activity). ✅
- **Quote repost** ("Mit Kommentar teilen") opens the sharebox with the original attached —
  same `voyagerContentcreationDashShares` create as a normal post, plus a reshare reference ⏳.

---

## ✅ Delete a repost ("Repost löschen")

```
POST /voyager/api/graphql?action=execute&queryId=voyagerFeedDashReposts.<hash>
Body: {
  "variables": {
    "resourceKey": "urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:<shareId>,<repostId>)"
  },
  "queryId": "voyagerFeedDashReposts.<hash>",
  "includeWebMetadata": true
}
```
- This is a GraphQL **DELETE-by-key** (the `resourceKey` is the repost URN).
- UI: your repost → "…" → **"Repost löschen"** → confirm.
- **Verified:** repost removed. ✅ — but note this was verified **in the browser**. The MCP tool
  `delete_repost` is **not operational**: its `queryId` carries no `.<hash>`
  (`_REPOST_DEL_QID`, `mcp/lib/client.py:766`), and no captured read maps a repost to its share. See
  `STATUS-MATRIX.md` note 4 and `BACKLOG.md`.
- **Since 2026-07-31 the tool fails honestly instead of firing a doomed request.** `delete_repost`
  checks `_qid_has_hash()` (`mcp/lib/client.py:381`) **before** building the URL and returns
  `{"ok": False, "status": "not_configured", "retryable": False, note: …}` — the note names
  `tools/capture_write_action.py` as the way to re-capture the hash
  (`mcp/lib/client.py:776-784`). `status` is deliberately a **string**, not an HTTP code, and
  `retryable` is explicit, so a caller that retries on 5xx does not read this as "try again".
  A test counts the transport calls on a fake `vgreq` and requires **zero** `post`/`get`/`delete`
  in this state (`mcp/tests/test_client.py:544`). Offline-proven, **not yet live-tested**.
  The still-open half — which hash, and which read maps repost→share — stays in `BACKLOG.md`.
- **Which layer sends nothing — read this before quoting the zero-call result.** *Zero calls* is a
  statement about `LinkedInClient.delete_repost()`. The MCP **tool** `server.delete_repost()` still
  runs `li.ensure_session()` first, which is a **GET** on `/voyager/api/me`
  (`mcp/server.py:312`, in `delete_repost`), and only then does the client method refuse. So: no request to the delete
  endpoint, no mutating call at all — but not literally an empty wire at tool level. The read-only
  suite therefore asserts `not _mutating(transport)` for this one tool
  (`mcp/tests/test_readonly.py:343`), and the file itself warns that "a GET is NOT proof of a write"
  (`:114-117`).
- **Mixed world:** create repost = SDUI (`createInstantRepost`), delete repost = Voyager
  GraphQL (`voyagerFeedDashReposts`).

---

## Still to capture (post interactions)
- **Quote repost** with commentary (reshare reference schema) ⏳
- **Edit** an existing post ⏳
- **Report** a post ⏳
- Post with **image / video / document** (media upload flow) ⏳
- Post with **poll** ⏳
- **Turn off / on comments** on your post ⏳
- Change **who can see** / **who can comment** after publish ⏳
- "**Nicht interessiert**" / hide / unfollow-author from a feed post ⏳