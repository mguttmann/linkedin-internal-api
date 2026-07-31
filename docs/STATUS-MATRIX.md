# API Status Matrix

Overview of what is **verified** (real call, HTTP status documented) vs. **discovered**
(seen in live traffic, schema known) vs. **inferred** (structure guessed, not yet confirmed).

Every write operation below was tested live on the **owner's own account** and minimally invasive;
test artifacts were removed afterwards (verified clean) **except where a note says otherwise** — for
the image post of 2026-07-18 (note ⁵) the owner's report records that the post went live, not that it
was deleted again, so treat that artifact as possibly still standing.

## Legend
- ✅ **verified** — executed by us, status documented, reversion tested where applicable
- 🔍 **discovered** — captured from real client traffic (endpoint + schema are real)
- 🔩 **inferred** — derived from structure/naming, not yet confirmed
- **[O] open item** — the MCP tool is known **not to work today** and the cause or the missing
  artifact is open. Not a status of the endpoint: it says "do not rely on this tool". Every `[O]`
  has an entry in `BACKLOG.md` with the ranked candidates and the exact next capture.
- **(owner-run)** — provenance marker, defined here **once** and only referred to elsewhere: the call
  was executed by the repo owner in his own live session and reported with its HTTP status. The
  sessions that wrote the code had no session of their own, so wherever this marker stands, the
  measurement is the owner's — and it covers **exactly** the paths he ran, never a neighbouring one.
  **Every use names its own run**, because a marker pinned to a single date and commit would claim a
  wrong date the moment it is reused. The runs recorded so far:
  - **2026-07-30, against commit `5a251da`** — the jobs reads (`get_job`,
    `get_job_recommendations`); see the jobs live-run note below.
  - **2026-07-18, against code that was not committed at the time** — the image post
    (`create_post_with_image`); the code reached the repo later and untouched in that respect, see
    note ⁵. What the run proves: the upload + share path executed and the post went live
    (asset URN `D4E22AQGKhtES62GYIw`).

  A ✅ without the marker is an earlier live run of this repo.

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
| Jobs (recommendations) | `graphql voyagerJobsDashJobsFeed` | 🔍 endpoint — **not** verified usable. The **tool's honesty behaviour is ✅ (owner-run)**: on a live HTTP 200 whose body held no collection container under `data`, `get_job_recommendations` reported `state: "unknown"`, `count: 0`, `ok: false` with the re-capture note — **not** `empty`. The endpoint itself answered but yielded no readable jobs, so it stays open and needs a capture of the **raw** body (`BACKLOG.md`). Parsing offline-proven against synthetic fixtures; remaining open items (the candidate search has a depth/width limit, and the container is picked by shape rather than by evidence that it is the feed) in `27-JOBS.md` §6 |
| Job posting (detail) | `jobs/jobPostings/{id}?decorationId=…WebFullJobPosting-65` (legacy Rest.li, **not** the dash resource, **not** GraphQL) | ✅ 200 (owner-run) — MCP `get_job`, flat projection confirmed against real data; **plus** ✅ 404 (owner-run) for a non-existent id: honest error, requested `job_id` unchanged. That is the **404 path only** — the id-**mismatch** abort remains fixture-proven and was explicitly *not* exercised. Details and the field-level evidence in the live-run note below and `27-JOBS.md` |
| Company page | `graphql voyagerOrganizationDashCompanies` | 🔍 |
| Events | `graphql voyagerEventsDashEventsCardGroupResource` | 🔍 |
| Premium analytics | `graphql voyagerPremiumDashAnalyticsView` | 🔍 |

> **Session-diagnosis note (2026-07-31).** The `voyager/api/me` row above is also the MCP session
> probe, and the MCP tool `session_status` now reports *which kind* of failure that probe hit
> instead of one undifferentiated `logged_in: false`. It gained `session_suspect`, `error_code` and
> `retryable`; `error_code`'s remediation is returned as `hint`. **`session_suspect` is `True` for
> exactly one class** — a redirect to the login page, the only session death this repo evidences
> (`SESSION-AND-ERRORS-DESIGN.md`, section 2.1). A **403 is `csrf_missing`, not a dead session**
> (same document, section 2.2), an absent cookie file is `session_file_missing` — a setup problem —
> and a timeout is `transport_unavailable`. So a caller no longer reads "session dead" into every
> failure. The classification carries no response body: status, endpoint name, body length and the
> class, nothing else. Offline-proven against a faked transport, **not yet live-tested**; no row of
> this table changed status **through that change**, and it made nothing ✅ (the two jobs rows became
> ✅/partly ✅ later, through the owner's live run — see the jobs note below). `logged_in` is now the classification
> itself, so a 200 that the classification rejects — an HTML interstitial, a truncated body — reports
> `logged_in: false` **with** its `error_code` and `hint`, never a healthy session with no signal; the
> flip side is that the probe demands a readable JSON body where it previously demanded only HTTP 200,
> which no live call has exercised. What is held by a test, and the known limits — among them that an
> empty-bodied success is filed as a non-JSON read — are listed in
> `SESSION-AND-ERRORS-DESIGN.md`, section 2.7.
> The cookie inventory that the same document sketches in section 1 was **declined** and is a
> non-goal, not a backlog item.
> **Still not live-evidenced (as of the owner's report of 2026-07-30):** `session_suspect` exists and
> is offline-proven, but it has **never fired in operation** — no live failure has classified through
> it yet.

> **Jobs live-run note — the first ✅ in this repo that came from the owner's session (owner-run,
> see the legend).** Two paths of `get_job` were executed and one behaviour of
> `get_job_recommendations` was observed. What follows is the whole of it; nothing beyond it changed
> status.
>
> **1. `get_job`, real id → HTTP 200.** The legacy Rest.li route with
> `decorationId=…WebFullJobPosting-65` answered 200 and the flat projection held up on real data.
> Field-level evidence, kept to what carries the proof (a public job advert of a real employer; no
> further detail and no personal data is recorded here): `company` came back **filled** (`Dräger`), so a
> name was resolved out of `included[]` on a real body — but **not** which branch resolved it (the
> reference join or the sole-company fallback), so the reference path stays fixture-proven only.
> `description_text` was Attributed Text extracted **cleanly, with no `str()` artefact**; its length
> equalled the run's budget, which does **not** show a cut (an exactly budget-long text comes back
> whole), and the flag's value was not reported — truncation stays fixture-proven.
> `employment_status` and `location` were filled and
> not stringified objects. `remote_allowed: false`, `applies: 0`, `views: 0` were **read** rather than
> left `null`, and `salary: null` alongside the separate `salary_present` key. The `reposted` key was
> **present** — the reposting warning signal the owner asked for. `listed_at` came back as a 13-digit
> integer; that is consistent with epoch milliseconds but the unit is still **inferred**, not
> documented. `endpoint` (`voyager.jobs.jobPostings.get`) rides in the response so a caller can log
> which route verified a job.
>
> **2. `get_job`, invented id → HTTP 404.** The tool returned an honest error with `ok: false`, and
> the **requested** `job_id` stood unchanged in the answer — no silent failure, no empty success, no
> overwritten id. **This is the 404 path, not the id-mismatch path.** A body carrying a *different* id
> than the one requested cannot be provoked without a prepared response, so the hard mismatch abort
> stays **fixture-proven only**; the owner names that limit himself.
>
> **3. `get_job_recommendations` — the false success is structurally dead (✅ for the tool, not for the
> endpoint).** The route the tool actually sends is the captured **GraphQL** one —
> `graphql?includeWebMetadata=true&variables=(count:<n>,start:0)&queryId=voyagerJobsDashJobsFeed.<hash>`
> (`mcp/lib/client.py`, `get_job_recommendations`, with `_JOBS_FEED_QID` / `_JOBS_FEED_PAGE_QID`). It
> answered **HTTP 200**, but no collection container was findable under `data`, so the tool reported
> `state: "unknown"`, `count: 0`, `read_entries: 0`, `paging_total: null`, `ok: false` plus the
> re-capture note — and explicitly **not** `empty`. The previous version would have claimed
> `ok=True, count=0, "a genuinely empty page"` here; that is the false success which caused the first
> hand-back, and it is now provably gone. **What is missing is the raw response body:** without it,
> nobody can decide whether the response shape drifted (a different container key), whether the feed
> was empty or not entitled, or whether an in-band error arrived with a 200. So the **endpoint stays
> open** (`BACKLOG.md`), while the tool's honesty is verified.
>
> **Separately — a different, REST-like form measured 400.** The owner also tried
> `voyagerJobsDashJobsFeed?decorationId=com.linkedin.voyager.dash.deco.jobs.JobsFeed-2&count=5&q=jobsFeed&start=0`
> and got **HTTP 400** (14-byte body). That is a useful finding **about that form** and is recorded as
> such. It is **not** a statement about the route the tool uses: the tool never sends it, and the
> owner's own 200 above proves it did not — a 400 from the tool would have produced the
> `HTTP {status} for the jobs feed` branch with the queryId-rotation hint, not the container note. Do
> not merge the two.

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
| **Post with an image** (MCP `create_post_with_image`) | Voyager | `voyagerVideoDashMediaUploadMetadata?action=upload` → single PUT → `Shares` with `media.category=IMAGE` | ✅ verified (owner-run 2026-07-18, browserless) — the **hardenings** added when the code landed are offline-proven only ⁵ |
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

⁵ **Post with an image — added 2026-07-31, and the two halves have different provenance.**
The *route* is owner-run: on **2026-07-18** the owner ran the browserless single-part upload plus the
share in his own session, the asset URN `D4E22AQGKhtES62GYIw` came back and the post went live. That
is the ✅ — a metadata POST that answers with a `singleUploadUrl`, one raw PUT of the file bytes to
that URL, then the same `Shares` mutation as `create_post` with `media.category=IMAGE` and the
`feedshare-image` recipe. Images need no processing wait (unlike video). The URN stays recorded in the
docstrings of `upload_image()` and `create_post_with_image()` in `mcp/lib/client.py` as the
verification receipt.
The *hardenings* applied while bringing the code onto `main` are **offline-proven against fixtures and
not live-tested** — nobody re-ran the live call for them: (a) a path-free pre-flight
(`inspect_image()` in `mcp/lib/client.py`) classifies the file once, locally, from its own first
bytes, and every other step reads that result: an unreadable, empty or non-image file is refused at
**zero** outgoing calls, counted by a test rather than assumed; (b) uploads are restricted to
PNG/JPEG/GIF/WEBP **by file signature, not by extension**, and to **10 MiB** (`MAX_IMAGE_BYTES` in
`mcp/server.py`) — both are **our own** choices, not measured LinkedIn limits, and the refusal is a
guardrail in the server layer per `MCP-DESIGN.md` §5; (c) the confirmation payload names the **file
name, type and size**, never a path, because a tool response lands in the MCP transcript
(`create_post_with_image` in `mcp/server.py`); (d) the file-read path is wrapped in
`except (OSError, ValueError)` — the `ValueError` covers a path with an embedded NUL byte, which would
otherwise leave the tool as a raw traceback; (e) the share answer runs through the shared
`_gql_errors()` chokepoint, so a 200-with-`ValidationError` reads as `ok: False`; (f) the return
carries only status, endpoint name, byte length, asset URN and the client's own classification — no
response body, no header, no path.
Known honest limits, all read off the code and none of them live-measured: cap and type check bind the
**pre-flight snapshot, not the bytes that leave** (three separate reads of the file, the payload read
itself unbounded), and the signature check reads a **prefix** — so a valid image header with arbitrary
data appended passes, and any genuine image the process can read still goes out; the file is read
**wholly into memory** with no chunking; **transport exceptions are not caught** on the PUT or the
share POST, so a timeout or DNS failure still leaves the tool as a raw traceback carrying the target
URL (pre-existing for every write tool here, worst on this one because the target comes from the
response); the upload target URL and its headers come from the metadata **response**, unchecked and
with library-default redirect following; and the `urns` field of the success return is a **scrape of
the share response text** — `04-WRITE-OPERATIONS.md`, section "Create post", documents that the post
URN comes from the follow-up closed-sharebox SDUI call instead, so treat `urns` as unverified and
confirm a post through the independent read (`get_my_posts`). Details and the open owner decisions in
`04-WRITE-OPERATIONS.md`, section "Post with an image".

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