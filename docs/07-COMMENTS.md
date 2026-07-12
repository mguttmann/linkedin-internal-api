# 07 — Comments (verified)

Complete comment surface, captured live and verified on the owner's own post
(test comment/reply created and deleted; profile left clean). Comments are a **mixed world**:
reading is Voyager, writing is **SDUI**.

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

## ✅ Reply to a comment (nested)

Same endpoint `com.linkedin.sdui.comments.createComment`, **but the payload carries a
parent-comment reference** (the reply targets the parent comment's thread instead of the
post's activity thread). Preceded by a `component?componentId=…comments…` call that fetches
the reply box state.
**Verified:** reply appeared nested under the parent. ✅

> **Key difference:** top-level comment → `threadUrnActivityThreadUrn` (post). Reply →
> parent comment thread in the collection/threadUrn. Both use `createComment`.

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

## ✅ Delete a comment

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.comments.deleteComment
Body: {
  "requestId": "com.linkedin.sdui.comments.deleteComment",
  "serverRequest": { ...
    "payload": {
      "commentUrn": { "commentId": "<id>", "thread": "urn:li:activity:<postId>" },
      "containerThreadUrn": { "threadUrnActivityThreadUrn": { "activityUrn": { "activityId": "<postId>" }}}
    }
  }
}
```
- **Verified.** ✅
- **Note:** deleting a top-level comment does NOT delete its replies — replies survive as
  orphans and must be deleted separately.

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