# API Status Matrix

Overview of what is **verified** (real call, HTTP status documented) vs. **discovered**
(seen in live traffic, schema known) vs. **inferred** (structure guessed, not yet confirmed).

Every write operation below was tested live on the **owner's own account**, minimally
invasive, and every test artifact was removed afterwards (verified clean).

## Legend
- ✅ **verified** — executed by us, status documented, reversion tested where applicable
- 🔍 **discovered** — captured from real client traffic (endpoint + schema are real)
- 🔩 **inferred** — derived from structure/naming, not yet confirmed
- **[O] open item** — the MCP tool is known **not to work today** and the cause or the missing
  artifact is open. Not a status of the endpoint: it says "do not rely on this tool". Every `[O]`
  has an entry in `BACKLOG.md` with the ranked candidates and the exact next capture.

## Read operations (GET)

| Operation | Endpoint | Status |
|---|---|---|
| Own profile (basic) | `voyager/api/me` | ✅ 200 |
| Full profile | `identity/dash/profiles/{urn}` | ✅ 200 |
| Profile (GraphQL) | `graphql voyagerIdentityDashProfiles` | ✅ 200 |
| Own posts | `graphql voyagerFeedDashProfileUpdates` | ✅ 200 |
| Comments on a post | `feed/comments?q=comments&updateId={urn}` | ✅ 200 |
| Reactions on a post | `voyagerSocialDashReactions?threadUrn={urn}&q=reactionType` | ✅ 200 |
| Feed | `graphql voyagerFeedDashMainFeed` | 🔍 |
| Messages (conversations) | `graphql messengerConversations` | 🔍 |
| Messages (content) | `graphql messengerMessages` | 🔍 |
| Network (connections) | `relationships/connectionsSummary` | ✅ 200 |
| Invitations | `relationships/invitationViews` | 🔍 |
| Notifications | `voyagerIdentityDashNotificationCards?q=filterVanityName` | ✅ 200 |
| Any profile by vanityName | `identity/dash/profiles?q=memberIdentity` | ✅ 200 |
| Search | `graphql voyagerSearchDashClusters` | 🔍 |
| Jobs (recommendations) | `graphql voyagerJobsDashJobsFeed` | 🔍 |
| Company page | `graphql voyagerOrganizationDashCompanies` | 🔍 |
| Events | `graphql voyagerEventsDashEventsCardGroupResource` | 🔍 |
| Premium analytics | `graphql voyagerPremiumDashAnalyticsView` | 🔍 |

## Write operations

All of the following were captured by driving the **real client** (click-and-record) and
verified live. See `04-WRITE-OPERATIONS.md` for full request/body schemas.

> Every write below is reachable through the MCP server only while read-only mode is **off**.
> With `LINKEDIN_READ_ONLY` set, all writing tools raise instead of calling — see
> `26-READ-ONLY-MODE.md` (offline-proven, not yet live-tested). The status column describes the
> **endpoint**, not the operating mode.
>
> **False-success note (2026-07-31).** A ✅ in this table means the *endpoint* was executed — it says
> nothing about whether the client would have *noticed* a failure. Two GraphQL writes reported
> success purely from the HTTP status: `create_poll` and `delete_repost`. Both now check
> `data.errors` through the shared `_gql_errors()` chokepoint like `create_post` and `edit_post`
> (`mcp/lib/client.py:367`), so a 200-with-`ValidationError` reads as `ok: False` — see
> `04-WRITE-OPERATIONS.md` for the check and its honest limits. Offline-proven against fixtures,
> **not yet live-tested**; the ✅ marks in this table are unchanged, and nothing new became ✅.

| Operation | World | Endpoint | Status |
|---|---|---|---|
| **Set like / reaction** | Voyager | `voyagerSocialDashReactions` POST | ✅ 201 (browserless) |
| **Unlike / remove reaction** | SDUI | `com.linkedin.sdui.reactions.delete` | ✅ verified (browserless — captured-body template + minimal headers) |
| **Create post** | Voyager | `graphql voyagerContentcreationDashShares` | ✅ verified (browserless) |
| **Edit post** | Voyager | `graphql voyagerContentcreationDashShares` + `resourceKey`/`updateUrn` | ✅ verified (browserless, docs/24) |
| **Delete post** | SDUI | `com.linkedin.sdui.update.deletePost` | 🔍 schema captured (browser); browserless **not proven** ³ |
| **Poll** | Voyager | `PollsPollSummary` → `Shares` `media.mediaUrn` (URN_REFERENCE) | ✅ verified (browserless, docs/24) |
| **Post media (image/video)** | Voyager | `MediaUploadMetadata?action=upload` → PUT → `Shares` asset | ✅ captured (docs/24) |
| **@mention in post** | Voyager | `commentary.attributesV2.profileMention` | ✅ verified (docs/24) |
| **Link preview** | Voyager | `graphql voyagerContentcreationDashUpdateUrlPreview` | ✅ verified (browserless, GET) |
| **Save / unsave post** | SDUI | `com.linkedin.sdui.update.saveState` (`isSaved` toggle) | ✅ verified (browserless) |
| **Repost / delete repost** | SDUI / Voyager | `createInstantRepost` / `graphql voyagerFeedDashReposts.<hash>` | repost: ✅ verified (browser only) · delete repost: 🔍 **[O]** endpoint captured, MCP tool **not operational** ⁴ |
| **Create comment** | SDUI | `com.linkedin.sdui.comments.createComment` | ✅ verified |
| **Delete comment** | Voyager | `DELETE feed/comments/{url-enc urn:li:comment:(activity,<id>)}` | ✅ verified (browserless, 204) |
| **React to comment** | SDUI | `reactions.create` (commentThreadUrn) | 🟡 captured (browser) |
| **Send DM / recall** | Voyager | `voyagerMessagingDashMessengerMessages?action=createMessage` / `?action=recall` | ✅ verified (browserless) ² |
| **React to a message** | Voyager REST | `voyagerMessagingDashMessengerMessages?action=reactWithEmoji` | 🔩 **[O]** implemented; first live observation = **HTTP 500**, cause open ² |
| **Follow / unfollow company** | Voyager | `feed/dash/followingStates/{urn}` PARTIAL_UPDATE | ✅ 201/200 (browserless) |
| **Follow person** | SDUI | `addaUpdateFollowState` | ✅ verified |
| **Connect (with note)** | Voyager | `voyagerRelationshipsDashMemberRelationships?action=verifyQuotaAndCreateV2` + `customMessage` | ✅ verified (docs/25) |
| **Endorse skill** | SDUI | `com.linkedin.sdui.requests.profile.endorseSkill` | ✅ verified (browserless 200) |
| **Remove connection** | SDUI | `com.linkedin.sdui.mynetwork.RemoveConnectionVanityName` | ✅ verified (docs/25) |
| **Open-to-work enable** | Voyager | `voyagerJobsDashOpenToWorkPreferencesFormElementInput` POST | ✅ verified |
| **Open-to-work disable** | Voyager | `…OpenToWorkPreferencesFormElementInput?formType=OPEN_TO_WORK` DELETE | ✅ verified |
| **Contact-info save** | SDUI | `com.linkedin.sdui.requests.profile.saveProfileContactInfoForm` | ✅ captured (docs/25) |
| **Profile — 16 sections documented** (persisted captures: 5 full, 3 add-only, 1 delete-only) | SDUI | `saveProfile<X>Form` / `deleteProfile<X>` | ✅ pattern ¹ |
| **Featured add/edit** | SDUI | `profile.featured.link` / `.media.edit` / `.media.delete` | 🔩 pattern (no persisted artifact) |

¹ Persisted capture artifacts back a **subset** of the 16 documented sections:
**full add+edit+delete for 5** (Certifications, Courses, Organizations, Projects, Volunteer),
**add-only for 3** (Experience, Publications, Honors), **delete-only for Test-scores**. The rest
(Skills, Languages, Education, Patents, Featured, Intro) are documented from the pattern without a
persisted artifact. **Browserless CREATE is demonstrated for captured forms** — SDUI forms
carry values twice: as `MemoryNamespace` state-refs AND as real literals in a top-level `states[]`
array, so a create can be replayed from pure `requests` (HTTP 200). See `BROWSERLESS-REPLAY.md`.

² Messaging note: reads use the dedicated `voyagerMessagingGraphQL/graphql` path
(`get_conversations`), sends use `voyagerMessagingDashMessengerMessages?action=createMessage` —
the body needs `trackingId` (16 RAW bytes as a latin-1 string, **not** base64) plus
`dedupeByClientGeneratedToken:false`. `recall_message` returns 204.
**`react_to_message` — updated 2026-07-30:** it was listed here as "implemented (schema known) but
not yet live-tested". It has now been run once by the owner and returned **HTTP 500** — that is the
**first live observation of this route at all**, so it does not contradict the earlier wording, it
fills it in. Two things follow. (a) The route is **Voyager REST**, not SDUI:
`mcp/lib/client.py:596-603` builds
`{BASE}/voyagerMessagingDashMessengerMessages?action=reactWithEmoji` and posts
`{"messageUrn", "emoji"}` through `self._vg()`; `06-MESSAGING.md:5` says all messaging runs over
Voyager REST.li. There is **no captured SDUI body** for message reactions
(`data/endpoints_sdui.json` has none; `mcp/lib/templates/` holds exactly three templates — unlike,
react_comment, create_comment — and no messaging template). The otherwise-good "captured SDUI
template + minimal headers" recipe therefore **does not apply here**, and minimal headers would be
a regression on a Voyager route (every verified Voyager write runs with vgreq's headers: `like`
201, `send_dm` 200, `recall_message` 204). (b) The **cause is open**. Candidates, ranked by
evidence strength, in `BACKLOG.md`.
Also note the docstring `mcp/lib/client.py:597` still says "VERIFIED" for this method — a doc
defect tracked in `BACKLOG.md`, not fixed here (doc-only ticket).
**Updated 2026-07-31 — deliberately NOT built.** The owner decided against a fix attempt: the
correction above (Voyager REST, no SDUI capture, so the "captured SDUI template + minimal headers"
recipe cannot apply) was accepted, and the tool is carried as an **[O] open item** instead. Nothing
in `react_to_message` was changed. The cause stays open and the ranked candidates stay in
`BACKLOG.md`; the shortest path to closing it is the one capture described there — set **and
immediately un-set** a reaction in the real client, which yields body *and* headers at once.
The `client.py:597` docstring is still uncorrected — same reason: this ticket changed no code in
that method.

³ **Delete post — corrected 2026-07-30.** `ENDPOINTS.md` said `✅ (browser-capture)` while
`COVERAGE-MAP.md` said `✅ MCP delete_post (browserless)`; both cannot hold. Resolved against the
evidence: `data/endpoints_sdui.json` carries the `update.deletePost` family with `url_sample: ""`
and `postData: null` — no captured body, no `trackingId` sample — and no browserless run with a
documented HTTP status exists. All three files now say **schema captured, browserless not proven**.

⁴ **Delete repost — corrected 2026-07-30.** Endpoint real (browser capture), MCP tool not runnable:
`_REPOST_DEL_QID = "voyagerFeedDashReposts"` has **no hash** (`mcp/lib/client.py:766`), and no read
in this repo maps a repost to `(urn:li:share:<shareId>,<repostId>)`. Details in `BACKLOG.md`.
**Updated 2026-07-31 — it now fails honestly.** The hash was **not** invented (it exists in no
capture in this repo). Instead the tool detects the missing `.<hash>` suffix before building the
URL and returns `{"ok": False, "status": "not_configured", "retryable": False, note: …}` with the
re-capture path (`tools/capture_write_action.py`) — **without sending the delete request**
(`mcp/lib/client.py:776-784`). Mind the layer: the *client method* sends nothing at all, held by a
test that counts calls on a fake `vgreq` and requires zero get/post/delete
(`mcp/tests/test_client.py:544`); the *tool* still emits the `ensure_session()` GET on `/me` first
(`mcp/server.py:312`, in `delete_repost`), so the claim is "no mutating call", not "an empty wire"
(`10-POST-INTERACTIONS.md`). Offline-proven, **not yet live-tested**; the tool stays **[O]** until a
captured hash exists.

## Important corrections (paths that do NOT work)

These were guessed early and **tested to fail** — do not use them:

| Guessed path | Result | Correct path |
|---|---|---|
| `contentcreation/dash/normShares` (create post) | ❌ 404 | `graphql voyagerContentcreationDashShares` |
| `identity/dash/profiles/{urn}` PARTIAL_UPDATE (edit) | ❌ 400 | SDUI `saveProfileIntroForm` |
| `voyagerSocialDashComments` POST (comment) | ❌ 400 | SDUI `comments.createComment` |
| Voyager `DELETE voyagerSocialDashReactions` (unlike) | ❌ 400 | SDUI `reactions.delete` |

## Key lesson

**Don't guess — click and record.** Every ✅ above was found by performing the action in
the real (logged-in) client and capturing the exact endpoint + body from the network log.
Guessing produced only 400/404s. This method works for any profile section (experience,
skills, education, etc.).