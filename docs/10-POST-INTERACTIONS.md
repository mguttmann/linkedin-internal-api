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
- **Verified:** repost removed. ✅
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