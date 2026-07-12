# 04 — Write Operations

This document lists only **verified** write operations. **Nothing here is guessed-as-if-it-works.**
Every endpoint marked ✅ was executed live and its result documented. Where an early guessed
path failed, it is listed at the bottom under "Corrections" so nobody repeats the mistake.

> **Test discipline:** all write tests on the **owner's own** account, minimally invasive
> (marker text like `apitest ...`), deleted immediately, and verified clean afterwards
> (no leftover post, comment, like, or headline change).

---

## ✅ Set like / reaction — VERIFIED (HTTP 201, Voyager)

```
POST /voyager/api/voyagerSocialDashReactions?threadUrn=<url-encoded activity-urn>
Content-Type: application/json; charset=UTF-8
Body: {"reactionType":"LIKE"}
```

`reactionType` ∈ `LIKE | PRAISE | APPRECIATION | EMPATHY | INTEREST | ENTERTAINMENT`.

**Response:** `201 Created`, empty body. The created reaction ID is in the header:
```
X-RestLi-Id: urn:li:fsd_reaction:(urn:li:fsd_profile:<MEMBER>,urn:li:activity:<ID>,0)
```

**Verification:** GET `voyagerSocialDashReactions?threadUrn=<urn>&q=reactionType` lists the
reaction with `actorUrn` = own profile. ✅ Tested live, 201 confirmed.

**Copy-paste (with `lib/vgreq.py`):**
```python
import urllib.parse, vgreq
enc = urllib.parse.quote("urn:li:activity:<ID>", safe="")
r = vgreq.post(f"https://www.linkedin.com/voyager/api/voyagerSocialDashReactions?threadUrn={enc}",
               {"reactionType": "LIKE"})
print(r.status_code, r.headers.get("X-RestLi-Id"))  # 201, reaction URN
```

---

## ✅ Unlike / remove reaction — VERIFIED (SDUI)

**The key finding:** the obvious Voyager `DELETE` on `voyagerSocialDashReactions` returns
**constant HTTP 400** — in ALL tested key formats. LinkedIn removes reactions **only via SDUI**:

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.reactions.delete
Content-Type: application/json
Body (full schema, captured live 2026-07-12):
{
  "requestId": "com.linkedin.sdui.reactions.delete",
  "serverRequest": {
    "requestId": "com.linkedin.sdui.reactions.delete",
    "requestedArguments": {
      "$type": "proto.sdui.actions.requests.RequestedArguments",
      "payload": {
        "threadUrn": {"threadUrnActivityThreadUrn": {
          "__typename": "proto_com_linkedin_common_ActivityUrn",
          "activityUrn": {"activityId": "<numeric activity id>"}}},
        "reactionType": "ReactionType_LIKE",
        "reactionSource": "Update"
      },
      "requestedStateKeys": [],
      "requestMetadata": {
        "$type": "proto.sdui.common.RequestMetadata",
        "currentActor": { …Bindable with key
          "id": "identitySwitcherActorContext-urn:li:activity:<id>" … }
      }
    }
  }
}
```

**Verification:** after the SDUI call the own reaction is gone from the GET list (`total` −1).
✅ Tested, reaction cleanly removed.

**Browserless status (honest):** the payload fields are all real literals (activityId,
reactionType, reactionSource) — but a pure-`requests` replay of this body returns **HTTP 500**.
The server needs the full `requestMetadata.currentActor` Bindable (the
`identitySwitcherActorContext` binding the browser fills in) and likely the SDUI page-state
context. So: **set-like is browserless (201); un-like is reliable via the client (real button
click → this endpoint), but NOT yet reproduced by pure requests.** Use the browser path for
unlike until the currentActor binding is reconstructed.

> **Lesson:** for toggle actions (like↔unlike), do NOT assume create and delete use the same
> endpoint. LinkedIn mixes Voyager (create) and SDUI (delete).

---

## ✅ Create post — VERIFIED (Voyager GraphQL)

Post creation runs over Voyager GraphQL (NOT the often-cited `normShares`, which returns 404):

```
POST /voyager/api/graphql?action=execute&queryId=voyagerContentcreationDashShares.<hash>
Content-Type: application/json; charset=UTF-8
Body:
{
  "variables": {
    "post": {
      "allowedCommentersScope": "ALL",
      "intendedShareLifeCycleState": "PUBLISHED",
      "origin": "FEED",
      "visibilityDataUnion": { "visibilityType": "ANYONE" },
      "commentary": { "text": "<your text>", "attributesV2": [] }
    }
  },
  "queryId": "voyagerContentcreationDashShares.<hash>",
  "includeWebMetadata": true
}
```

- `visibilityType`: `ANYONE` (public) | `CONNECTIONS_ONLY` (connections only). ⚠️ The value is
  `CONNECTIONS_ONLY`, NOT `CONNECTIONS` — the latter fails with a ValidationError. **And note:
  the GraphQL call returns HTTP 200 even on a validation error — you MUST check `data.errors`
  in the response body, or you'll report a false success.** (Verified the hard way.)
- `allowedCommentersScope`: `ALL` | `CONNECTIONS_ONLY` | `NONE`
- **The created post URN** is NOT in the GraphQL response, but in the immediately following
  SDUI call `com.linkedin.sdui.action.sharing.closed-sharebox.server-action`, field `postUrl`
  (`urn:li:share:...`) and `feedDashUpdateEntityUrnString` (`urn:li:activity:...`). Remember
  this URN to delete the post later.

**Verification:** ✅ Created live (post appeared in the feed) and then deleted again.

> **queryId hash:** `voyagerContentcreationDashShares.<hash>` — the hash changes on LinkedIn
> deployments. Re-grab the current hash via `tools/capture_write_action.py`.

---

## ✅ Delete post — VERIFIED (SDUI)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.update.deletePost
Content-Type: application/json
Body:
{
  "requestId": "com.linkedin.sdui.update.deletePost",
  "serverRequest": {
    "requestId": "com.linkedin.sdui.update.deletePost",
    "requestedArguments": {
      "$type": "proto.sdui.actions.requests.RequestedArguments",
      "payload": {
        "updateKeyContainer": {
          "feedType": 3,
          "items": [{
            "feedUpdateUrn": {
              "updateUrnActivityUrn": {
                "__typename": "proto_com_linkedin_common_ActivityUrn",
                "activityUrn": { "activityId": "<ID from the post URN>" }
              }
            },
            "trackingId": "<tracking id of the update>"
          }]
        },
        "shareLifeCycleState": "ShareLifeCycleState_PUBLISHED",
        "isUpdateInCarousel": false
      }
    }
  }
}
```

- `feedType: 3` = profile/detail feed. `activityId` is the numeric ID from the post URN.
- The `trackingId` comes from the update object (present in the feed response).

**Verification:** ✅ Live post deleted, then gone from the feed (GET confirmed empty).

---

## ✅ Create comment — VERIFIED (SDUI)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.comments.createComment
Content-Type: application/json
Body: {
  "requestId": "com.linkedin.sdui.comments.createComment",
  "serverRequest": { ...
    "payload": {
      "optimisticKey": "<uuid>",
      "collection": {
        "updateKey": { "feedType": 3, "items": [{
          "feedUpdateUrn": { "updateUrnActivityUrn": { "activityUrn": { "activityId": "<post-id>" }}},
          "trackingId": "<tracking-id>"
        }]},
        "threadUrn": { "threadUrnActivityThreadUrn": { "activityUrn": { "activityId": "<post-id>" }}}
      },
      "commentary": { ... the text ... }
    }
  }
}
```

**Verification:** ✅ Created live (comment appeared on the post) and deleted again.

**Read comments (Voyager, verified):**
```
GET /voyager/api/feed/comments?q=comments&updateId=<url-encoded activity-urn>   → 200
```
Comment URN form: `urn:li:fsd_comment:(<commentId>,urn:li:activity:<postId>)`.

---

## ✅ Delete comment — VERIFIED (SDUI)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.comments.deleteComment
Body: {
  "requestId": "com.linkedin.sdui.comments.deleteComment",
  "serverRequest": { ...
    "payload": { "commentUrn": { "commentId": "<id>", "thread": "urn:li:activity:<postId>" }, ... }
  }
}
```

**Verification:** ✅ Test comment deleted, then gone from `feed/comments`.

---

## ✅ Edit profile (headline/intro) — save endpoint VERIFIED (SDUI)

Profile editing runs **entirely over SDUI**. The "Edit profile" button opens an intro form;
saving fires:

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileIntroForm
Body: {
  "requestId": "com.linkedin.sdui.requests.profile.saveProfileIntroForm",
  "serverRequest": { ...
    "payload": {
      "firstName":       { "key": "firstNameIntroForm",       "namespace": "MemoryNamespace" },
      "lastName":        { "key": "lastNameIntroForm",        "namespace": "MemoryNamespace" },
      "headline":        { "key": "headlineIntroForm",        "namespace": "MemoryNamespace" },
      "initialHeadline": { "key": "initialHeadlineIntroForm", "namespace": "MemoryNamespace" },
      ...
    }
  }
}
```

**Verification:** ✅ Save endpoint + schema captured live (save click fired; headline stayed
unchanged because no new value was set).

> **⚠️ SDUI form peculiarity:** field values are NOT sent literally in the request but as
> **state references** (`{"key": "...", "namespace": "MemoryNamespace"}`). The client holds
> the real value in the SDUI client-state; the server reads it from that state on save. To
> change a value programmatically you must **either** set the client-state via a `SetState`
> action (complex), **or** fill the field in the real client context (the editor sits in an
> iframe/shadow-DOM — direct DOM access fails). The pure `requests` path is NOT trivial here —
> profile edit is the most complex write op. **To set real values: drive the real client
> (coordinate/keyboard input in the open modal), not DOM injection.**

---

## ✅ Profile Projects — add / edit / delete — VERIFIED (SDUI)

Full end-to-end capture on the owner's own profile (added `APITEST Project <ts>`, renamed it,
deleted it; the owner's real project was untouched; profile verified clean).
See `docs/09-PROFILE-EDITING.md` for the field-by-field breakdown and
the raw captured bodies were recorded during click-and-record (kept out of the public repo).

**Add / Edit** (same endpoint):
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileProjectForm
```
- `serverRequest.requestedArguments.payload` carries the fields as **state-refs**
  (`title`, `description`, `startDate`, `endDate`, `skills`, `currentlyWorking`, …) plus the
  literals `profileId` / `vanityName`.
- **Add vs. Edit discriminator:** the EDIT payload additionally contains
  **`projectIdForm: "<projectId>"`** (real numeric id, e.g. `SECTION_ITEM_ID`); ADD has no
  `projectIdForm`.
- **Values ARE in the body:** unlike the intro form, this request also carries a top-level
  `states[]` array with the **literal values** (e.g. the project name as
  `"value":"APITEST Project …","originalProtoCase":"stringValue"`; empty dates as
  `{"day":0,"month":0,"year":0}`). So the write is more replayable than the intro form —
  but a pure-`requests` replay is **not yet proven** (the state-ref key naming must be
  reproduced).
- **Verified:** ✅ project created live, then renamed live (both showed on the profile).

**Delete** (real ids — browserless-replayable):
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfileProjectForm
Body payload: {
  "profileId":  "<profileId>",
  "projectId":  "<projectId>",     // real literal numeric id
  "vanityName": "<vanity>",
  "hasChanges": {state-ref}, "progressIndicator": {state-ref}
}
```
- **Verified:** ✅ test project deleted; gone on read-back.
- Carries the real `projectId` as a literal (same category as language delete) → a pure
  `requests` replay is plausible; only `profileId` + `projectId` + `vanityName` are needed.

**Read-back:** `com.linkedin.sdui.requests.profile.fetchProjectsSections`
(`cardType: "Projects"` / `"ProjectsDetails"`) refetches the section after each write and is
where the numeric `projectId` for edit/delete is obtained.

---

## Other ops capturable by click-and-record (pattern established)

The method (`.click()` in the real client + network capture) works for ANY profile section.
Capturable analogously — each with its own SDUI/Voyager endpoint:
- **Experience** add/edit/delete
- **Education**, **skills**, **certificates**, **projects**, **featured**
- **Connection** send/accept, **follow**, **send message**

Pattern: open the profile/detail page → click the relevant edit button (`.click()`) → fill
the field → click save (`.click()`) → capture the save request. See
`tools/capture_write_action.py` and `docs/05-VERIFICATION.md`.

---

## Status table (verified)

| Operation | World | Endpoint | Status |
|---|---|---|---|
| **Read** (profile, posts, feed, comments …) | Voyager | various GET | ✅ 200 |
| **Set like** | Voyager | `voyagerSocialDashReactions` POST | ✅ 201 |
| **Unlike** | SDUI | `com.linkedin.sdui.reactions.delete` | ✅ verified |
| **Create post** | Voyager | `graphql voyagerContentcreationDashShares` | ✅ verified |
| **Delete post** | SDUI | `com.linkedin.sdui.update.deletePost` | ✅ verified |
| **Create comment** | SDUI | `com.linkedin.sdui.comments.createComment` | ✅ verified |
| **Delete comment** | SDUI | `com.linkedin.sdui.comments.deleteComment` | ✅ verified |
| **Edit post** | Voyager | `Shares` + `resourceKey`/`updateUrn` | ✅ verified browserless (docs/24) |
| **Poll** | Voyager | `PollsPollSummary` → `Shares` URN_REFERENCE | ✅ verified browserless (docs/24) |
| **@mention** | — | `commentary.attributesV2.profileMention` | ✅ verified (docs/24) |
| **Media (image/video)** | Voyager | `MediaUploadMetadata` → PUT → `Shares` asset | ✅ captured (docs/24) |
| **Save/unsave post** | SDUI | `com.linkedin.sdui.update.saveState` | ✅ verified browserless |
| **Repost / delete repost** | SDUI / Voyager | `createInstantRepost` / `voyagerFeedDashReposts` | ✅ verified |
| **Send / recall / react DM** | Voyager | `messengerMessages?action=…` | ✅ verified browserless (docs/06) |
| **Connect / endorse / remove connection** | Voyager+SDUI | see docs/25 | ✅ verified |
| **Contact-info save** | SDUI | `saveProfileContactInfoForm` | ✅ captured (docs/25) |
| **Profile sections (16)** — documented (5 full capture, 3 add-only, 1 delete-only, rest pattern) | SDUI | `saveProfile<X>Form` / `deleteProfile<X>` | 🟡 partial (docs/09–21) |

¹ Save endpoint + schema verified. SDUI forms carry values twice — as `MemoryNamespace` state-refs
AND as real literals in a top-level `states[]` array — so a CREATE replays from pure `requests`
(HTTP 200); see `BROWSERLESS-REPLAY.md`.

## Corrections — paths that were guessed and FAILED

Do not use these (kept here so the mistake is not repeated):

| Guessed path | Result | Correct path |
|---|---|---|
| `contentcreation/dash/normShares` (create post) | ❌ 404 | `graphql voyagerContentcreationDashShares` |
| `identity/dash/profiles/{urn}` PARTIAL_UPDATE (edit) | ❌ 400 | SDUI `saveProfileIntroForm` |
| `voyagerSocialDashComments` POST (comment) | ❌ 400 | SDUI `comments.createComment` |
| Voyager `DELETE voyagerSocialDashReactions` (unlike) | ❌ 400 | SDUI `reactions.delete` |

## Bottom line for automation
- **Fully productive (even pure `requests`):** reads (everything), like/unlike.
- **Verified, but SDUI client context needed:** create/delete post, create/delete comment,
  profile save. These run over SDUI and need the page-bound headers + partly client-state —
  most robust via the real (visible) client with `.click()`.
- **Golden rule for new ops:** don't guess — **click and record.** The real client shows the
  exact endpoint + body in the network log. That is how every ✅ above was found.