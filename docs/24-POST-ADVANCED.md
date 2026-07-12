# 24 — Post advanced features (edit, poll, media, @mention)

Captured live via click-and-record on 2026-07-12 (Alex drove the clicks, we recorded the
requests). All four are variations of the **same `voyagerContentcreationDashShares` create
mutation** — they differ only in what goes into `media` / `attributesV2` / the edit keys.

Base: `POST /voyager/api/graphql?action=execute&queryId=voyagerContentcreationDashShares.<hash>`

---

## ✅ Edit a post

Reuses the Shares mutation with two extra keys that target the existing post:

```json
{ "variables": {
    "entity": {
      "entity": { "commentary": { "text": "<new text>", "attributesV2": [] } },
      "resourceKey": "urn:li:share:<shareId>"
    },
    "updateUrn": "urn:li:fsd_update:(urn:li:activity:<activityId>,MEMBER_SHARES_PROFILE_ACTIVITY,EMPTY,DEFAULT,false)"
  },
  "queryId": "voyagerContentcreationDashShares.f2afb8a73071c94140f970bdb7e48fb3",
  "includeWebMetadata": true }
```
- The edit modal is opened via SDUI `com.linkedin.sdui.requests.sharing.LaunchSharebox` with
  `editingPostUpdateKey` (feedType 13). The **save** is the Shares call above.
- `resourceKey` = the share URN, `updateUrn` = the fsd_update URN of the post.

---

## ✅ Poll — two steps

**1. Create the poll** (returns a pollSummary URN):
```json
POST graphql?action=execute&queryId=voyagerFeedDashPollsPollSummary.f8ad99cf791d833d37dddb373d06fb3a
{ "variables": { "poll": {
    "question": "<question>",
    "duration": "ONE_WEEK",            // also: ONE_DAY / THREE_DAYS / TWO_WEEKS
    "options": ["Option 1", "Option 2", "Option 3"]   // 2–4 options
}}}
```
**2. Post it** — the Shares create with the poll URN as an URN-reference media:
```json
"media": { "mediaUrn": "urn:li:fsd_pollSummary:<id>", "category": "URN_REFERENCE" }
```

---

## ✅ Media (image / video / document) — three steps

**1. Register the upload** (returns an upload URL + a `digitalmediaAsset` URN):
```json
POST /voyager/api/voyagerVideoDashMediaUploadMetadata?action=upload
{ "mediaUploadType": "VIDEO_SHARING", "fileSize": SECTION_ITEM_ID, "filename": "clip.mp4" }
```
- `mediaUploadType`: `VIDEO_SHARING` for video, `IMAGE_SHARING` for images (analogous endpoint
  path may differ for images — capture once to confirm).
**2. PUT the raw file bytes** to the returned single-/multi-part upload URL.
**3. Post it** — Shares create with the asset URN as media:
```json
"media": { "category": "VIDEO",
           "mediaUrn": "urn:li:digitalmediaAsset:<id>",
           "recipes": ["urn:li:digitalmediaRecipe:feedshare-video-..."] }
```
- Upload progress is reported over SDUI `com.linkedin.sdui.action.web-interop.share-upload`
  (`status: Uploading/Processing`) — informational, not required for the post.

---

## ✅ @mention

A mention is just an entry in the post's `commentary.attributesV2`, pointing at the mentioned
member's profile URN and marking the character span:
```json
"commentary": {
  "text": "Jordan Doe baut …",
  "attributesV2": [
    { "detailDataUnion": { "profileMention": "urn:li:fsd_profile:<memberUrn>" },
      "start": 0, "length": 10 }
  ]
}
```
- `start`/`length` mark the mention text span (0-indexed, in the commentary text).
- The member URN comes from the mentions typeahead as you type `@Name`.
- Same pattern works for **@company** (`companyMention`) and in comments (`comments.createComment`).

---

## Status

| Feature | Endpoint | Browserless? |
|---|---|---|
| Edit post | Shares + `resourceKey`/`updateUrn` | ✅ replayable (all literals) |
| Poll | `PollsPollSummary` → Shares `URN_REFERENCE` | ✅ replayable |
| Media | `MediaUploadMetadata` → PUT → Shares asset | ✅ replayable (needs the file PUT) |
| @mention | `attributesV2.profileMention` | ✅ replayable |

All four carry real literals in the request body → they replay from pure `requests`. **`edit_post`
and poll are wired as MCP tools** (`edit_post`, `create_poll` + `create_post(poll_urn)`); **media
upload and @mention are not yet wired** (documented for manual use) — see COVERAGE-MAP.
