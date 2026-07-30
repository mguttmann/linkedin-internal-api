# 07 — Comments (verified)

Comment surface captured live on the owner's own post (test comment created and deleted; profile
left clean). Comments are a **mixed world**: reading is Voyager, writing is **SDUI**.
Read, create (top-level) and delete are verified; **reply is not** — see the reply section below.

Post URN used in examples: `urn:li:activity:<postId>`. Comment URN form:
`urn:li:fsd_comment:(<commentId>,urn:li:activity:<postId>)`.

---

## Read

| What | Endpoint | Notes |
|---|---|---|
| Read comments on a post | `GET /voyager/api/feed/comments?q=comments&updateId=<url-enc activity-urn>` | ✅ 200 |

---

## ✅ Create a comment (top-level)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.comments.createComment
Body: {
  "requestId": "com.linkedin.sdui.comments.createComment",
  "serverRequest": { ...
    "payload": {
      "optimisticKey": "<uuid>",
      "collection": {
        "updateKey": { "feedType": 3, "items": [{
          "feedUpdateUrn": { "updateUrnActivityUrn": { "activityUrn": { "activityId": "<postId>" }}},
          "trackingId": "<tracking>"
        }]},
        "threadUrn": { "threadUrnActivityThreadUrn": { "activityUrn": { "activityId": "<postId>" }}}
      },
      "commentary": { ...text... }
    }
  }
}
```
**Verified.** ✅

---

## 🔍/🔩 Reply to a comment (nested) — NOT implemented, NOT verified

**Downgraded 2026-07-30.** This section used to carry a `✅` and "Verified: reply appeared nested
under the parent". Per the repo's own rule (`05-VERIFICATION.md`), a `✅` requires an HTTP status
**and** a path (browser / browserless); neither was ever recorded here. What actually holds:

- 🔍 **Captured / observed in the UI:** a reply *was* posted manually and appeared nested. That is
  a UI observation of a manual session, not a replayed request.
- 🔩 **Inferred:** that the same endpoint `com.linkedin.sdui.comments.createComment` is used and
  that the payload carries a parent-comment reference — the reply targeting the parent comment's
  thread instead of the post's activity thread. The `component?componentId=…comments…` call that
  fetches the reply-box state was seen alongside it.
- ⚠️ **The field name is unknown.** `BACKLOG.md` names a `parentComment` binding, but **no capture
  covers that name** — the same backlog entry states the existing capture contains "no
  parent-comment reference at all". Treat `parentComment` as a **guessed name**, not a schema fact,
  and do not send it.
- ❌ **Not implemented:** there is no `reply_to_comment` MCP tool, no client method and no test. The
  usable request body does not exist in this repo (`data/endpoints_sdui.json` knows only
  `comments.createComment` and `comments.deleteComment`, both with an empty `url_sample` and
  `postData: null`).
- Consistent with this, `BROWSERLESS-REPLAY.md` marks "Comment create/reply/edit/delete" as
  🔬 replay-untested.

**Next step:** the concrete capture recipe (which script, which UI action, what to diff against,
and the cleanup order) lives in `BACKLOG.md` → "reply_to_comment".

> **Inferred key difference (not a verified schema):** top-level comment →
> `threadUrnActivityThreadUrn` (post). A reply is expected to point at the parent comment thread in
> `collection/threadUrn`. The shape `threadUrnCommentThreadUrn` *does* exist as a live-200 template
> — but for `reactions.create`, not for `createComment`
> (`mcp/lib/templates/react_comment_sdui.json.tpl`, `mcp/lib/client.py:425-436`). Reusing it for
> replies is a guess until a capture shows it.

---

## 🔩 Edit a comment (endpoint observed; not in the canonical SDUI inventory)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.comments.updateComment
Body: {
  "requestId": "com.linkedin.sdui.comments.updateComment",
  "serverRequest": { ...
    "payload": {
      "commentUrn": { "commentId": "<id>", "thread": "urn:li:activity:<postId>" },
      "commentBoxStateId": "urn:li:comment:(urn:li:activity:<postId>,<id>)",
      ...new text...
    }
  }
}
```
- UI button label: **"Änderungen speichern"** (not "Speichern").
- **Status:** endpoint shape observed during a manual session; **not in `data/endpoints_sdui.json`
  or ENDPOINTS.md**. Treat as inferred until re-captured.

---

## ✅ Delete a comment — VOYAGER REST (browserless, verified 204)

```
DELETE /voyager/api/feed/comments/<url-enc urn:li:comment:(activity:<postId>,<commentId>)>   → 204
```
- **This is the working browserless path.** Keyed by the comment's canonical `urn` form
  (activity FIRST, then comment id) — the same value the feed/comments read returns as `urn`.
- The other two URN forms are **rejected**: `urn:li:fs_objectComment:(<id>,activity:<post>)`
  (entityUrn) → 400, `urn:li:fsd_comment:(<id>,urn:li:activity:<post>)` (dashEntityUrn) → 400,
  wrong-order `urn:li:comment:(<post>,<id>)` → 500. A garbage key → 400. So the 204 is a real
  parse+delete, not a catch-all.
- **Note:** deleting a top-level comment does NOT delete its replies — replies survive as
  orphans and must be deleted separately.

### ⚠️ SDUI `comments.deleteComment` (POST) — does NOT work browserless

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.comments.deleteComment
```
Returns **500** on a pure-requests replay: the body needs the browser's
`requestMetadata.currentActor` binding (`identitySwitcherActorContext-<urn>` + `stringBinding`),
which only the live SDUI client sets — same limitation as unlike/repost. Superseded by the
Voyager REST DELETE above. (Capture: `api-docs/_writes/comment_delete.json`.)

---

## ✅ Like / react to a comment

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.reactions.create
Body: {
  "requestId": "com.linkedin.sdui.reactions.create",
  "serverRequest": { ...
    "payload": {
      "threadUrn": { "threadUrnCommentThreadUrn": {
        "commentUrn": { "commentId": "<id>", "thread": "urn:li:activity:<postId>" }
      }},
      "reactionType": "LIKE"   // LIKE | PRAISE | EMPATHY | INTEREST | APPRECIATION | ENTERTAINMENT
    }
  }
}
```
- **Verified:** 👍 reaction appeared on the comment. ✅
- **This is the general SDUI reaction-create** (`reactions.create`) — contrast with
  post-likes which use Voyager `voyagerSocialDashReactions`. For **comments**, reactions go
  through SDUI `reactions.create` with a `threadUrnCommentThreadUrn`.
- **Remove reaction:** SDUI `com.linkedin.sdui.reactions.delete` with the comment thread urn
  (same delete action used for unlike on posts).

---

## Still to capture (comments)
- Comment with **@mention** — same `attributesV2.profileMention` shape as posts (docs/24); the
  `commentary` field carries it. Verified for posts; comment reuse is the same commentary schema. ✅ pattern
- Comment with **image / GIF** ⏳
- **Report** a comment ⏳

> **World summary:** read = Voyager (`feed/comments`); create/reply/edit/delete/react = SDUI.
> `reactions.create` / `reactions.delete` are the generic comment-reaction endpoints.