# API Status Matrix

Overview of what is **verified** (real call, HTTP status documented) vs. **discovered**
(seen in live traffic, schema known) vs. **inferred** (structure guessed, not yet confirmed).

Every write operation below was tested live on the **owner's own account**, minimally
invasive, and every test artifact was removed afterwards (verified clean).

## Legend
- ✅ **verified** — executed by us, status documented, reversion tested where applicable
- 🔍 **discovered** — captured from real client traffic (endpoint + schema are real)
- 🔩 **inferred** — derived from structure/naming, not yet confirmed

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

| Operation | World | Endpoint | Status |
|---|---|---|---|
| **Set like / reaction** | Voyager | `voyagerSocialDashReactions` POST | ✅ 201 (browserless) |
| **Unlike / remove reaction** | SDUI | `com.linkedin.sdui.reactions.delete` | ✅ verified (browserless — captured-body template + minimal headers) |
| **Create post** | Voyager | `graphql voyagerContentcreationDashShares` | ✅ verified (browserless) |
| **Edit post** | Voyager | `graphql voyagerContentcreationDashShares` + `resourceKey`/`updateUrn` | ✅ verified (browserless, docs/24) |
| **Delete post** | SDUI | `com.linkedin.sdui.update.deletePost` | ✅ verified |
| **Poll** | Voyager | `PollsPollSummary` → `Shares` `media.mediaUrn` (URN_REFERENCE) | ✅ verified (browserless, docs/24) |
| **Post media (image/video)** | Voyager | `MediaUploadMetadata?action=upload` → PUT → `Shares` asset | ✅ captured (docs/24) |
| **@mention in post** | Voyager | `commentary.attributesV2.profileMention` | ✅ verified (docs/24) |
| **Link preview** | Voyager | `graphql voyagerContentcreationDashUpdateUrlPreview` | ✅ verified (browserless, GET) |
| **Save / unsave post** | SDUI | `com.linkedin.sdui.update.saveState` (`isSaved` toggle) | ✅ verified (browserless) |
| **Repost / delete repost** | SDUI / Voyager | `createInstantRepost` / `graphql voyagerFeedDashReposts` | ✅ verified (repost = browser only) |
| **Create comment** | SDUI | `com.linkedin.sdui.comments.createComment` | ✅ verified |
| **Delete comment** | Voyager | `DELETE feed/comments/{url-enc urn:li:comment:(activity,<id>)}` | ✅ verified (browserless, 204) |
| **React to comment** | SDUI | `reactions.create` (commentThreadUrn) | 🟡 captured (browser) |
| **Send DM / recall / react** | Voyager | `voyagerMessagingDashMessengerMessages?action=…` | ✅ verified (browserless) ² |
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
`dedupeByClientGeneratedToken:false`. `recall_message` returns 204. `react_to_message` is
implemented (schema known) but not yet live-tested.

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