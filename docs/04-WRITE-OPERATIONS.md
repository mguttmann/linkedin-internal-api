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

> **How the MCP client applies that lesson (updated 2026-07-31).** The body check is no longer
> copy-pasted per method: `LinkedInClient._gql_errors()` (`mcp/lib/client.py:367`) is the single
> place that extracts `data.errors`, and **every** GraphQL write in the file calls it and computes
> `ok = 2xx AND not errors` — today `create_post` (`mcp/lib/client.py:491`), `edit_post` (`:522`),
> `create_poll` (`:538`) and `delete_repost` (`:790`). `create_poll` and `delete_repost` did **not**
> check it before and reported a false success on a 200-with-`ValidationError`; `create_poll`
> additionally no longer returns a `poll_urn` when the body carries errors. A regression guard
> parses `client.py` and fails on a method that POSTs an `action=execute` mutation, reports `ok` and
> skips `_gql_errors` (`mcp/tests/test_client.py:556`).
>
> **What that guard does and does not catch — it is a literal-text heuristic, not a semantic
> analysis.** It walks the `ast.FunctionDef` nodes directly in the `LinkedInClient` class body and
> flags a method whose source text contains `action=execute`, `.post(` and `"ok"` but not
> `_gql_errors`. So it does **not** see a future write that builds the URL from a constant or a
> helper (no literal `action=execute` in the method), returns `dict(ok=…)` or uses `'ok'` in single
> quotes, is declared `async def`, or lives outside that class body. Treat it as a tripwire against
> the copy-paste recurrence that actually happened here, not as a proof that no false-success write
> can ever be added again.
>
> **Honest limits of the check itself** (offline-proven against fixtures, **not yet live-tested** —
> there was no session):
> - It reads `data.errors` only, because that is the shape this repo has actually captured
>   (the warning above). A **top-level** `errors` next to a `null` `data` would not be seen.
> - A 200 whose body is not parsable JSON (e.g. a login interstitial) yields "no errors" and
>   therefore `ok: True`. Both residues are tracked in `BACKLOG.md`.
> - The error text is passed through from the server response verbatim and uncapped
>   (`errors[0]["message"]`) — also tracked in `BACKLOG.md`.
> - The three GraphQL **reads** (`get_my_posts`, `get_conversations`, `get_link_preview`) were
>   deliberately left alone: they return the parsed JSON and claim no `ok`, so they cannot report a
>   false success. The caller sees `data.errors` itself.
> - Nothing about the **sent** request changed. URL and body of `create_poll` and `delete_repost`
>   are frozen by a test (`mcp/tests/test_client.py:578`).
- **The created post URN** is NOT in the GraphQL response, but in the immediately following
  SDUI call `com.linkedin.sdui.action.sharing.closed-sharebox.server-action`, field `postUrl`
  (`urn:li:share:...`) and `feedDashUpdateEntityUrnString` (`urn:li:activity:...`). Remember
  this URN to delete the post later.

**Verification:** ✅ Created live (post appeared in the feed) and then deleted again.

> **queryId hash:** `voyagerContentcreationDashShares.<hash>` — the hash changes on LinkedIn
> deployments. Re-grab the current hash via `tools/capture_write_action.py`.

---

## ✅ Post with an image — VERIFIED live by the OWNER (Voyager, browserless, single PUT)

Two calls plus the ordinary share. No browser, no multipart finalize step, and — unlike video — no
wait for processing.

**1. Register the upload.**

```
POST /voyager/api/voyagerVideoDashMediaUploadMetadata?action=upload
Body: { "mediaUploadType": "IMAGE_SHARING", "fileSize": <bytes>, "filename": "<file name>" }
→ data.value.urn               = urn:li:digitalmediaAsset:<id>
  data.value.singleUploadUrl   = the URL the bytes go to
  data.value.singleUploadHeaders = headers to replay on the PUT
```

**2. PUT the raw bytes** to `singleUploadUrl`, with those headers. A 200/201/204 means the asset
holds the image.

**3. Share it** — the same `Shares` mutation as *Create post* above, with media added:

```
"media": { "category": "IMAGE",
           "mediaUrn": "urn:li:digitalmediaAsset:<id>",
           "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"] }
```

**Verification:** ✅ the owner ran this in his own live session on **2026-07-18** — asset URN
`D4E22AQGKhtES62GYIw` came back and the post went live. That is the whole of the live evidence: the
happy path, once. Provenance and its limits: `STATUS-MATRIX.md`, legend entry "(owner-run)" and note 5.
The URN stays in the docstrings of `upload_image()` and `create_post_with_image()` in
`mcp/lib/client.py` as the receipt.

> **What was hardened when the code landed on `main` — offline-proven against fixtures, NOT
> live-tested.** Nobody re-ran the live call for any of the following; each is held by a test that
> counts transport calls rather than trusting the code to be quiet.
> - **The payload is classified before a single byte goes out.** `inspect_image()` in
>   `mcp/lib/client.py` stats the file and reads its first 12 bytes — locally, no outgoing call,
>   never raising — and answers `{ok, name, kind, size, status}`, with no directory component
>   anywhere in it. Confirmation, refusal and upload all read that one result instead of each
>   looking at the file for themselves. The rule behind it: *readable* is not *valid*. An empty file
>   used to register with `fileSize: 0`, PUT zero bytes and be reported as a success on a post with
>   a blank image; it is now `status: "empty_file"` at zero calls.
> - **Content, not the extension, decides what may be uploaded.** A signature allowlist — PNG,
>   JPEG, GIF, and WEBP via `RIFF….WEBP` — because renaming a file must not decide which bytes we
>   hand to LinkedIn. Anything else is `unsupported_type` with zero calls. The type set is **our
>   own** choice, matching what a feed share accepts in practice; no upload of a rejected type was
>   ever attempted live, so the mapping itself is unverified against LinkedIn.
> - **A size cap of 10 MiB** (`MAX_IMAGE_BYTES` in `mcp/server.py`), deliberately **not** presented
>   as a LinkedIn limit: nothing above it has ever been uploaded from here, so we refuse instead of
>   guessing. The refusal is a guardrail and therefore lives in the server layer
>   (`MCP-DESIGN.md` §5); byte access stays in the client. The number may be stated here because a
>   test holds it (`test_an_image_over_the_cap_is_refused_without_a_single_outgoing_call` in
>   `mcp/tests/test_readonly.py`).
> - **The confirmation names the file, its type and its size — never the path.** The
>   `needs_confirmation` payload carries `image_name` (base name only; `(no file name)` when a
>   trailing slash leaves the base name empty), `image_kind`, `image_bytes` and `image_status`
>   (`create_post_with_image` in `mcp/server.py`). A tool response ends up in the MCP transcript,
>   where a full path would publish the user name and the directory layout while adding nothing to
>   the one judgement the caller has to make: *what* is about to become a public post. Type and size
>   answer that; the path does not. The gate returns **before** `ensure_session()` — no session and
>   no outgoing call. It is not free of local reads: the pre-flight stat and 12-byte read happen
>   ahead of the gate on purpose, so that the question can carry type and size at all, and
>   `inspect_image()` never raises so that this read cannot turn a question into an error.
> - **An unreadable, missing or unparsable path costs zero calls.** The pre-flight sits in
>   `try/except (OSError, ValueError)` — `ValueError` as well, because an embedded NUL byte in the
>   path makes `open()` raise it and that would otherwise cross the tool boundary as a raw
>   traceback. The failure is a flat dict — `ok: False`, `step: "read"`, `status:
>   "unreadable_file"` — whose message names the file, never the path. This covers the **file-read**
>   path; transport exceptions are a separate, still-open case, see the limits below.
> - **The share runs through the `_gql_errors()` chokepoint** (see *Create post* above), so a
>   200 carrying a `ValidationError` reads as `ok: False` and no URN is handed back. It is not an
>   inline copy of the check: the existing AST regression guard picked the new method up on its own.
> - **The return carries no response body and no header** — only status, the endpoint name, the byte
>   length, the asset URN, the visibility, the phase and the client's own classification.
>
> **Honest limits, read off the code and none of them live-measured.** They are named here because
> the caller's blast radius depends on them:
> - **The cap and the type check bind the pre-flight snapshot, not the bytes that leave.** The file
>   is opened three times on one successful call — once by the gate, once by the pre-flight inside
>   `upload_image()`, and once for the payload read, which is itself unbounded (the client does not
>   know `MAX_IMAGE_BYTES`). A file that changes between those reads is uploaded unchecked and
>   unbounded. Exploiting that needs a second local writer racing us, so the practical risk is low —
>   but the control is a property of a moment, not of the payload, and should be read that way.
> - **The signature check reads a prefix.** A file that starts with a valid PNG header and carries
>   arbitrary data behind it passes and is uploaded whole. And the check limits the *type*, never the
>   *intent*: any genuine image the process can read still goes out — a private photo, a screenshot
>   showing credentials. In an MCP setting `confirm` is typically set by the model, so the type,
>   size and file name in the confirmation are the whole of the human-readable evidence.
>   A location restriction (an allowed directory) is an **open owner decision**, not implemented, and
>   not yet a `BACKLOG.md` entry — the ticket that wrote this section could not touch that file.
> - The file is read **wholly into memory** — no chunking. The cap bounds the measured size, the
>   process RAM bounds the rest. Streaming (`data=fh`) was deliberately not introduced: it changes
>   `Content-Length` / transfer encoding on the one PUT the owner actually proved.
> - **A transport exception is not caught.** Neither the PUT nor the share POST sits in a
>   `try/except`, so a timeout, a DNS failure, or a non-HTTP scheme in the response-supplied target
>   propagates out of the tool as a raw exception — against the rule that no traceback crosses the
>   tool boundary. Two consequences: the `requests` message carries the target host or URL, i.e. the
>   short-lived signed upload URL, into the transcript, and after a successful PUT the `asset_urn` is
>   lost with it. This is pre-existing for every write tool in this repo (the transport layer wraps
>   nothing), and worst here because the target comes from a response instead of being hard-coded.
>   Not fixed in this ticket.
> - The upload **target URL and its headers come from the metadata response** — the only place in
>   this client where an outgoing target is not hard-coded — with no scheme or host check, and the
>   PUT uses the library default for redirects (`lib/vgreq.py` sets `allow_redirects=False`
>   throughout; this call does not), so a 3xx would carry method and body onward to the new location.
>   The PUT goes out through bare `requests` **without** the session, so no cookies travel with it.
>   Forcing `https`, `allow_redirects=False` and a host allowlist are **open owner decisions**: no
>   capture in this repo records the upload host, so we would be guessing at the shape.
> - `urns` in the success return is a **regex scrape of the share response text** and is therefore
>   unverified: *Create post* above documents that the post URN comes from the follow-up
>   closed-sharebox SDUI call, not from this response. The field may be absent, and with more than
>   one match it is not proven that the first is ours. Confirm a post through the independent read
>   (`get_my_posts`), which is what the `note` in the return says.
> - **Multi-step write, partial state.** If the upload succeeds and the share fails, the asset is
>   already in the media store; the failure return says so only implicitly, through `asset_urn` and
>   `phase: "post"` — there is no `note` on that branch, at exactly the point where an outgoing side
>   effect has already happened. A retry uploads again and leaves another orphan. Nothing cleans
>   this up today.
> - Video hangs off the same metadata route but is **not** implemented as a tool and not proven.

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
| **Post with an image** | Voyager | `voyagerVideoDashMediaUploadMetadata?action=upload` → single PUT → `Shares` `media.category=IMAGE` | ✅ verified browserless, **owner-run 2026-07-18** — MCP `create_post_with_image`; hardenings and limits offline-proven only, see the section above |
| **Save/unsave post** | SDUI | `com.linkedin.sdui.update.saveState` | ✅ verified browserless |
| **Repost / delete repost** | SDUI / Voyager | `createInstantRepost` / `voyagerFeedDashReposts` | repost: ✅ verified (browser only) · delete repost: 🔍 endpoint captured, MCP tool **not operational** — see `STATUS-MATRIX.md` note 4 |
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