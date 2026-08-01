# Coverage Map — LinkedIn feature surface vs. what we have

> Working document for the enterprise audit. Goal: map EVERY user-facing LinkedIn function
> to an endpoint, mark its status honestly (✅ verified / 🔍 discovered-read / ❌ missing),
> and drive the capture work until coverage is real. **This file is the source of truth for
> "who does what" and for the honest coverage answer.**
>
> Legend: ✅ verified (executed live) · 🔍 discovered (seen in traffic, read-only) ·
> 🟡 partial (some captured) · ❌ missing (not captured yet)

## Current state (live)

**130 distinct endpoints** (141 raw captures) mapped. The write surface is now broad and, for the everyday actions,
**verified live**. Shipped as an **MCP server** — see `../mcp/`. Reads and writes run **browserless**
through pure `requests`; SDUI writes replay a **captured full body**. Header note: `unlike` and
`react_to_comment` go through `_sdui_min_headers()`, while `create_comment` posts the same kind of
SDUI route through vgreq's Voyager headers (`mcp/lib/client.py:242`) and is live 200 — so
"minimal headers" is not a proven requirement of the SDUI route (see "Key finding" below).

**MCP tools:**
- *Reads (browserless):* `get_me`, `get_my_posts`, `get_profile`, `get_notifications`,
  `get_conversations`, `get_connections_summary`, `get_post_comments`, `get_link_preview`,
  `get_job`, `get_job_recommendations` (both ungated reads, and **both live-verified** by the owner's
  runs: `get_job` on 2026-07-30 against `5a251da` — 200 on a real id, 404 on an invented one; and
  `get_job_recommendations` on 2026-07-31 against `75afead` — 200 with `state: "hits"` and three job
  cards read out of five modules, so the recommendations **endpoint is verified usable**. Only the
  `hits` path is covered by that ✅; the failure branches stay fixture-proven. Provenance and scope:
  `STATUS-MATRIX.md`, legend entry "(owner-run)" and the jobs live-run note; remaining open items in
  `27-JOBS.md` §6)
- *Posts:* `create_post` (+poll_urn), `create_post_with_image` (browserless single-part upload;
  live-verified by the **owner's** run of 2026-07-18 — provenance and the exact scope in
  `STATUS-MATRIX.md`, legend entry "(owner-run)" and note 5 — while the hardenings that came with the
  code are offline-proven only), `edit_post`, `delete_post`, `create_poll`, `save_post`,
  `repost`, `delete_repost` (repost create browserless 200; repost delete captured via browser
  only — the `delete_repost` tool is **not operational** and now **refuses up front, without ever
  sending the delete request**, see §1)
- *Engagement:* `like` (browserless 201), `unlike` (browserless 200), `create_comment`,
  `delete_comment` (all browserless)
- *Messaging:* `send_dm` (browserless live), `recall_message` (browserless 204 live),
  `react_to_message` (implemented; first live observation was a 500 — not working today)
- *Network:* `follow_company`, `connect`, `endorse_skill` (browserless 200), `remove_connection`
- *Session:* `session_status` (also reports `read_only`), `refresh_session`

**Guardrails on the write surface:** **every** writing tool requires `confirm=True` — since
2026-07-31 the last seven (`like`, `unlike`, `follow_company`, `endorse_skill`, `save_post`,
`create_poll`, `react_to_message`) are gated as well, so no write fires on the first call — and
`LINKEDIN_READ_ONLY=1` blocks **every** writing tool of the MCP server outright (reads unaffected)
— the recommended default for cron / unattended agents. The two locks are independent and their
order is fixed: the read-only gate answers **first**, so `confirm=True` never buys a write while the
flag is set. Offline-proven per tool with the transport counted, not yet live-tested; scope
and honest limit in `26-READ-ONLY-MODE.md`.
The split itself is asserted, not claimed: one test pins the registry at **12 reads and 20 gated
writes** (`test_tool_registry_splits_into_reads_and_gated_writes` in `mcp/tests/test_readonly.py`) and
compares the exposed tool names against the two tables it drives, so a future writing tool that is
added without a gate fails there instead of shipping. Counting note: the 12 include `session_status`
and `refresh_session`, which the tool list above names separately under *Session*. Adding a tool
changes that line on purpose — it is the only place in this repo where a tool count is held by a test,
which is why it is the only count these docs state.

**Path leaks in tool responses (added 2026-07-31):** a tool response is transcript content, so an
absolute filesystem path in one leaks the user name and the directory layout. The guard used to be a
blacklist of one known string (`/tmp/`), which an ordinary home-directory path walked straight past.
It now tests the **class**: every gated tool is called without `confirm`, every path-shaped argument is
poisoned with a `$HOME` path first, and the whole nested return value is walked recursively for
cookie markers and for anything that looks like an absolute or `~`-rooted path
(`test_no_gated_tool_leaks_a_cookie_or_a_filesystem_path` in `mcp/tests/test_readonly.py`). A second
test, `test_the_path_leak_probe_is_not_vacuous`, keeps the predicate from failing open in either
direction — a set of leak shapes must be caught, including the old `/tmp/` instance, and legitimate
payload values such as URNs, a bare file name or `https://…` must not. Offline-proven; the class-guard
idea, not the list, is the point.

**Honesty of the write results (added 2026-07-31):** a GraphQL write can answer HTTP 200 and still
carry a `ValidationError` in the body. `create_poll` and `delete_repost` used to report `ok` purely
from the status code and therefore reported false successes; every GraphQL write now runs the body
through the shared `_gql_errors()` extractor (`mcp/lib/client.py:367`) and computes
`ok = 2xx AND not errors`. `delete_repost` additionally refuses to send at all while its `queryId`
hash is missing. Both are **offline-proven, not yet live-tested**, and the known residues of the
false-success class are listed in `BACKLOG.md` — details and limits in `04-WRITE-OPERATIONS.md`.

**Key finding:** SDUI writes are browserless-replayable — the earlier `currentActor` "needs a
browser" story was a red herring (that field is empty in the real browser request too; see
`mcp/lib/client.py:433-434`).

**What is actually proven, and what is not** (corrected 2026-07-30 — the previous wording claimed
more than the evidence carries):

- **Proven factor — the body.** Replay the **full captured body** verbatim; hand-built partial
  bodies 500. Evidence: `mcp/lib/client.py:417-418` and the `unlike` fix note `:433-436`.
- **Unproven factor — the headers.** The claim "vgreq's Voyager `accept`/`x-restli` headers make
  the SDUI route 500" is **not verified** and is **contradicted for `comments.createComment`** by
  this repo's own code: `create_comment_browserless` posts the SDUI route
  (`_SDUI_COMMENT_URL`, `mcp/lib/client.py:161-162`, used at `:215`) through
  `self._vg().post(url, body, is_json=False)` (`mcp/lib/client.py:242`) — i.e. **with** the
  Voyager headers, **not** via `_sdui_min_headers()` — and that path is documented as live 200
  (`mcp/lib/client.py:159-160`, `:191`). So vgreq headers on an SDUI route do not by themselves
  produce a 500.
- **Why the old claim looked proven:** the `unlike` fix changed **body and headers at the same
  time** (`mcp/lib/client.py:433-436` names both (a) and (b)). That is a confounded A+B fix; only
  the body factor is isolated. The same unproven causality is still asserted in the
  `_sdui_min_headers` docstring (`mcp/lib/client.py:401-405`) — see `BACKLOG.md`.
- **The one-variable test that would settle it** (nothing else will): fire the *same* existing
  `unlike_sdui.json.tpl` body twice against the *same own* post — run A through
  `_post_sdui_template()` (minimal headers, `mcp/lib/client.py:414-428`), run B through
  `self._vg().post(url, body, is_json=False)` — and record both HTTP statuses. Reversible
  (like/unlike only), own account only. Until then the header contribution is **unknown**, and
  `03-SDUI-API.md:51-64` (ten "required" SDUI headers) vs. the three that `_sdui_min_headers()`
  sends (`mcp/lib/client.py:411-412`) also stays unresolved.
- **Status of that test as of 2026-07-30: still not executed, and the reason is not technical.** The
  owner's live run settled the jobs reads (see `STATUS-MATRIX.md`, jobs live-run note) but deliberately
  left this one alone: it is a **write**, and his operating rule requires the owner's explicit go for a
  write. The call stands ready as described above — only the approval is missing. The header question
  therefore remains **open**, unchanged.

---

## 1. Feed & Posts
| Function | Endpoint | Status |
|---|---|---|
| Read own/others posts | `graphql voyagerFeedDashProfileUpdates` | 🔍 |
| Read main feed | `graphql voyagerFeedDashMainFeed` / SDUI `pagers.feed.mainFeed` | 🔍 |
| Create post (text) | `graphql voyagerContentcreationDashShares` | ✅ MCP `create_post` (browserless live) |
| Delete post | SDUI `com.linkedin.sdui.update.deletePost` | 🔍 schema captured (browser-capture); **browserless not proven** — see `ENDPOINTS.md` + `BACKLOG.md` |
| Post with **image/video/document** | Voyager `MediaUploadMetadata`→PUT→`Shares` asset | ✅ captured (docs/24) |
| Post with an **image** (end to end) | `voyagerVideoDashMediaUploadMetadata?action=upload`→single PUT→`Shares` `media.category=IMAGE` | ✅ MCP `create_post_with_image` (browserless, **owner-run 2026-07-18**, asset URN returned and the post went live). Only the image path is covered — video hangs off the same metadata route but is **not** implemented as a tool and not proven. The hardenings shipped with the code (a path-free pre-flight that classifies the file by its own first bytes, a signature allowlist for PNG/JPEG/GIF/WEBP and a 10 MiB cap as **our own** guardrails in the server layer, file name + type + size instead of the path in the confirmation, honest error with zero calls on an unreadable/empty/non-image file, `_gql_errors()` on the share, body-free returns) are **offline-proven, not live-tested**, and the honest limits — cap and type check bind the pre-flight snapshot rather than the bytes that leave, signature checked as a prefix, whole file in memory, transport exceptions uncaught, upload target taken from the response, `urns` an unverified scrape — are in `STATUS-MATRIX.md` note 5 and `04-WRITE-OPERATIONS.md`, section "Post with an image" |
| Post with **@mention** of a person | `commentary.attributesV2.profileMention` | ✅ verified (docs/24) |
| Post with **link preview** | `voyagerContentcreationDashUpdateUrlPreview` | ✅ MCP `get_link_preview` (browserless 200) |
| Post **poll** | `PollsPollSummary`→`Shares` URN_REFERENCE | ✅ MCP `create_poll` + `create_post(poll_urn)` (browserless live) |
| Edit an existing post | `Shares` + `resourceKey`/`updateUrn` | ✅ MCP `edit_post` (browserless live) |
| **Repost** (instant) | SDUI `feed.requests.createInstantRepost` | ✅ MCP `repost` (browser-only, 500 headless) |
| Delete repost | Voyager `graphql voyagerFeedDashReposts` (delete-by-key) | 🔍 endpoint captured **via browser**; MCP `delete_repost` is **not operational** (queryId carries no hash — `mcp/lib/client.py:766`) + no read maps repost→share. Since 2026-07-31 it **fails honestly without sending the delete request** (`status: "not_configured"`, `retryable: False`, re-capture path in the note — `mcp/lib/client.py:776-784`). The client method sends nothing at all — zero get/post/delete (`mcp/tests/test_client.py:544`); at **tool** level the `ensure_session()` GET on `/me` still runs (`mcp/server.py:312`), so the claim is "no mutating call", not "an empty wire" — `10-POST-INTERACTIONS.md`. `BACKLOG.md` |
| Quote repost (with thoughts) | `voyagerContentcreationDashShares` + reshare ref | ⏳ |
| **Save / unsave** post | SDUI `update.saveState` `{isSaved}` | ✅ MCP `save_post` (browserless live) |
| Report post | ? (blocklisted in crawler) | ❌ |
| Set post **visibility** after publish | ? | ❌ |
| Who reacted (list) | `voyagerSocialDashReactions?q=reactionType` | ✅ read |

## 2. Reactions
| Function | Endpoint | Status |
|---|---|---|
| Like a post | `voyagerSocialDashReactions` POST `{reactionType:LIKE}` | ✅ |
| Other reactions (PRAISE/EMPATHY/INTEREST/APPRECIATION/ENTERTAINMENT) | same, other enum | 🟡 enum known, not each verified |
| Unlike | SDUI `reactions.delete` | ✅ |
| **React to a comment** | SDUI `reactions.create` (commentThreadUrn) | 🟡 captured (browser) |
| **Change** reaction type | ? (re-POST?) | ❌ |

## 3. Comments  ← verified (see docs/07-COMMENTS.md)
| Function | Endpoint | Status |
|---|---|---|
| Read comments | `feed/comments?q=comments&updateId=` | ✅ read |
| Create comment | SDUI `comments.createComment` | ✅ |
| Delete comment | SDUI `comments.deleteComment` | ✅ |
| **Edit** comment | SDUI `comments.updateComment` | ✅ |
| **Reply** to a comment (nested) | SDUI `comments.createComment` (parent ref — **field name unknown**) | 🔍 captured in the UI / 🔩 inferred — **not implemented, not verified**; no `reply_to_comment` tool exists. `BACKLOG.md` + `07-COMMENTS.md` |
| **Like/react** to a comment | SDUI `reactions.create` (commentThreadUrn) | ✅ |
| **Unreact** to a comment | SDUI `reactions.delete` | ✅ |
| Comment with **@mention** | `commentary.attributesV2.profileMention` (same as posts) | ✅ pattern (docs/24) |
| Comment with **image/GIF** | ? | ❌ |
| Report comment | ? | ❌ |

## 4. Messaging / DMs  ← core verified (see docs/06-MESSAGING.md)
| Function | Endpoint | Status |
|---|---|---|
| Read conversations list | `voyagerMessagingGraphQL/graphql messengerConversations` | ✅ MCP `get_conversations` (browserless, own path) |
| Read messages in a thread | `voyagerMessagingGraphQL/graphql messengerMessages` | 🔍 |
| **Send** a message | `messengerMessages?action=createMessage` | ✅ MCP `send_dm` (browserless live; needs raw-bytes trackingId) |
| **Edit** a sent message | `messengerMessages/<urn>` patch body | ✅ |
| **Delete** a message | `messengerMessages?action=recall` | ✅ MCP `recall_message` (browserless 204 live) |
| **React** to a message (emoji) | Voyager REST `messengerMessages?action=reactWithEmoji` | 🔩 MCP `react_to_message` implemented, **first live observation = HTTP 500** (2026-07-30, owner-reported); cause open, **owner decision 2026-07-31: no fix attempt** — carried as `[O]` in `STATUS-MATRIX.md`, candidates in `06-MESSAGING.md` + `BACKLOG.md` |
| Mark conversation read/unread | `messengerConversations` patch read | ✅ |
| **Typing** indicator | `messengerConversations?action=typing` | ✅ |
| **Reply** to a message (quote) | button exists, schema pending | ⏳ |
| Start **new** conversation | ? | ❌ |
| Send **attachment / image / GIF** | ? | ❌ |
| **Forward** a message | ? | ❌ |
| Archive / delete conversation | ? | ❌ |
| Send **InMail** (premium) | ? | ❌ |

## 5. Network / Connections  ← core verified (see docs/08-NETWORK.md)
| Function | Endpoint | Status |
|---|---|---|
| Read connections | `relationships/connectionsSummary` | 🔍 |
| Read invitations | `relationships/invitationViews` | 🔍 |
| **Send** connection request | SDUI `mynetwork.addaAddConnection` | ✅ |
| **Accept** invitation | SDUI `addaInvitationAction` (ACCEPT) | ✅ |
| **Ignore/reject** invitation | SDUI `addaInvitationAction` (IGNORE) | ✅ schema |
| **Withdraw** sent invitation | SDUI mynetwork (withdraw) | 🟡 UI verified |
| **Follow** a person | SDUI `addaUpdateFollowState` (ACTIVE) | ✅ |
| **Unfollow** a person | SDUI `addaUpdateFollowState` (INACTIVE) | 🟡 inferred |
| **Follow / unfollow** a company | Voyager `followingStates` patch | ✅ |
| **Remove** a connection | SDUI `mynetwork.RemoveConnectionVanityName` | ✅ MCP `remove_connection` (docs/25) |
| Connect **with a note** | Voyager `MemberRelationships?verifyQuotaAndCreateV2` + `customMessage` | ✅ MCP `connect` (docs/25) |
| Follow / unfollow a **hashtag** | ? | ❌ |
| Endorse a skill | SDUI `requests.profile.endorseSkill` | ✅ MCP `endorse_skill` (browserless 200) |
| Give a recommendation | ? | ❌ |

## 6. Profile editing  ← 16 sections documented; persisted captures: 5 full add/edit/delete, 3 add-only, 1 delete-only (see docs/09–21)
| Function | Endpoint | Status |
|---|---|---|
| Edit intro (name/headline/location/industry) | SDUI `saveProfileIntroForm` | 🔩 pattern-only |
| **Skills** | SDUI `saveProfileSkillForm` / `deleteProfileSkillForm` | 🔩 pattern-only (no artifact) |
| **Languages** | SDUI `saveProfileLanguageForm` / `deleteProfileLanguageForm` | 🔩 pattern-only |
| **Education** | SDUI `saveProfileEducationForm` / `deleteProfileEducationForm` | 🔩 pattern-only |
| **Licenses/Certifications** | SDUI `saveProfileCertificationForm` / `deleteProfileCertification` (⚠️ no `Form` on delete) | ✅ add+edit+delete captured |
| **Projects** | SDUI `saveProfileProjectForm` / `deleteProfileProjectForm` | ✅ add+edit+delete captured |
| **Volunteer** | SDUI `saveVolunteerExperienceForm` / `deleteVolunteerExperience` (⚠️ `impl.profile`, no `Profile` infix) | ✅ add+edit+delete captured — docs/13 |
| **Experience** (position) | SDUI `saveProfilePositionForm` / `deleteProfilePositionForm` | ✅ add captured; delete inferred — docs/11 |
| **Featured** (add link/media, edit, delete) | SDUI `profile.featured.link` / `.media.edit` / `.media.delete` | 🔩 pattern-only (no artifact) — docs/12 |
| Edit **About/Summary** (+ top skills) | SDUI `saveProfileAboutForm` (no `isEdit`/id; identity = profile) | 🔩 pattern-only — docs/21 |
| **Courses** | SDUI `saveProfileCourseForm` / `deleteProfileCourse` (⚠️ no `Form` on delete) | ✅ add+edit+delete captured — docs/15 |
| **Publications** | SDUI `saveProfilePublicationForm` / `deleteProfilePublication` (⚠️ no `Form`) | ✅ add captured; delete inferred — docs/14 |
| **Honors** | SDUI `saveProfileHonorForm` / `deleteProfileHonor` (⚠️ no `Form`) | ✅ add captured; delete not captured — docs/16 |
| **Patents** | SDUI `saveProfilePatentForm` / `deleteProfilePatent` (⚠️ no `Form`) | 🔩 pattern-only (no artifact) — docs/17 |
| **Organizations** | SDUI `saveProfileOrganizationForm` / `deleteProfileOrganization` (⚠️ no `Form`) | ✅ add+edit+delete captured — docs/18 |
| **Test-scores** | SDUI `saveProfileTestScoreForm` / `deleteProfileTestScore` (⚠️ no `Form`) | ✅ delete captured; add inferred — docs/19 |
| **Services** (Serviceleistungen) | — | ⛔ N/A: NOT offered in this account's "Abschnitt hinzufügen" dialog (LinkedIn gates it to freelancer/provider accounts). No section = no endpoint to capture. |
| **Causes** (Gute Zwecke) | part of Volunteering | ⛔ not a list-type section: it's a checkbox category picker under volunteering, no add/edit/delete list items. Detail page empty (131 chars). |
| **Profile photo** upload/change | media upload flow | ❌ |
| **Background/cover photo** | media upload flow | ❌ |
| **Contact info** (email/phone/website/social) | ? | ❌ |
| Custom public **URL** | `identity/dash/profiles` seen | ❌ write |
| Open-to-work / hiring badges | ? | ❌ |
| Profile **language** | `voyagerDashLanguageSelection` seen | ❌ write |

## 7. Notifications
| Function | Endpoint | Status |
|---|---|---|
| Read notifications | `voyagerIdentityDashNotificationCards` | 🔍 |
| Mark seen (network) | SDUI `addaMarkNotificationsSeen` | 🔍 |
| Mark badge | `voyagerNotificationsDashBadge` | 🔍 |
| Delete / mute a notification | ? | ❌ |
| Notification settings | ? | ❌ |

## 8. Search
| Function | Endpoint | Status |
|---|---|---|
| Search (people/posts/jobs/companies) | `graphql voyagerSearchDashClusters` | 🔍 |
| Update search history | SDUI `updateSearchHistoryRequest` | 🔍 |
| **Save a search** / alert | ? | ❌ |
| Typeahead / suggestions | seen | 🔍 |

## 9. Jobs
| Function | Endpoint | Status |
|---|---|---|
| Read job recommendations/cards | `graphql voyagerJobsDashJobsFeed` (count + cursor variant) | ✅ 200 (owner-run 2026-07-31 against `75afead`) — MCP `get_job_recommendations`, **verified usable**: `ok: true`, `state: "hits"`, `count: 3`, `read_entries: 5`, `discarded: 0`, `paging_total: 9`, three job cards read out of five modules on a real body, with the count cross-checked against the raw body by the owner. The employer/location split and the chain feed → `get_job` held on real data too (`27-JOBS.md` §4.0). **The ✅ covers the `hits` path only:** the read-error path (`discarded: 0`, never triggered), the partial-loss path and every other state stay fixture-proven, and the **raw** body is still worth capturing for the open items in `27-JOBS.md` §6 (`BACKLOG.md`). History: on 2026-07-30 the same route answered a container-less 200 and `get_job_recommendations` reported `state: "unknown"`, `count: 0`, `ok: false` with the re-capture note, **not** `empty` — the false success that caused the first hand-back is dead. Otherwise unchanged: flat cards; ambiguous candidates and partial loss have their own state/`reason`; `read_entries`/`discarded` balance `count` against the raw container; a candidate nested under an empty container IS found (pinned by test); parsing offline-proven against synthetic fixtures; remaining open items (candidate-search depth/width limit, container picked by shape rather than by evidence that it is the feed) in `27-JOBS.md` §6 |
| Read job posting detail | `jobs/jobPostings/{id}?decorationId=…WebFullJobPosting-65` (legacy Rest.li) | ✅ 200 (owner-run 2026-07-30) MCP `get_job` — the flat projection held on real data: `company` resolved out of `included[]` and came back filled, Attributed Text extracted with no `str()` artefact, `reposted` present, read counters read rather than `null`. **✅ 404 (owner-run)** for an invented id: honest error with the **requested** `job_id` unchanged — that is the 404 path, **not** the id-mismatch path, which stays fixture-proven. Still offline evidence only: identity checking at exact identifying keys and independently of key order (a divergent or self-contradictory body id is a hard abort with **no** `url`, never a correction), the `company` join being `null` when ambiguous, and the description cut plus its `description_truncated` flag. The **reference *path*** for `company` also stays unproven against a real body: the filled value does not say whether the reference join or the sole-company fallback produced it — `27-JOBS.md` |
| Read job posting detail (dash / detail sections) | `voyagerJobsDashJobPostingDetailSections` | 🔍 catalogued, not used by any tool |
| **Search** jobs (keyword + filters) | ? | ❌ **not built.** The route and its filter grammar have no capture **in this repo**. Update 2026-07-30: the owner reports he produced a capture, but it lives on **his** host and is **not present in this clone** (searched for, not found) — so it is not evidence here and nothing may be derived from it. Until the file is in the repo, building it would mean inventing filter keys (`27-JOBS.md` §5, `BACKLOG.md`) |
| **Save / unsave** a job | ? | ❌ |
| **Apply** to a job (Easy Apply) | `voyagerJobsDashOnsiteApplyApplication` seen | ❌ write |
| Set job **alerts / preferences** | `voyagerJobsDashJobSeekerPreferences` | 🔍 read verified; **write not buildable on current evidence** — open items [O-1]…[O-4] in `22-OPEN-TO-WORK.md` (the only documented write path switches the recruiter signal ON; `minimumPay` is ABSENT repo-wide) |
| Post a job | `voyagerJobsDashJobPostings` POST seen | ❌ verify |

## 10. Companies / Organizations
| Function | Endpoint | Status |
|---|---|---|
| Read company page | `graphql voyagerOrganizationDashCompanies` | 🔍 |
| Follow / unfollow company | Voyager `feed/dash/followingStates` patch | ✅ MCP `follow_company` (browserless; see §5) |
| Company admin: post as company | ? | ❌ |
| Company analytics | `voyagerOrganizationDashViewWrapper` etc. | 🔍 |

## 11. Other domains (barely touched)
| Domain | Status |
|---|---|
| Events (create/RSVP) | 🔍 read only |
| Groups (join/post/leave) | 🔍 1 read endpoint |
| Newsletters / Articles (publish) | `publishing/editorFirstPartyArticles` seen | ❌ write |
| Premium features | 🔍 read |
| Learning | not captured |
| Settings & Privacy (all toggles) | ❌ |
| Who viewed my profile | ✅ read (WvmpAnalytics) |

---

## Honest coverage estimate (start of audit)
- **Reads:** broad coverage of the main domains (🔍), but many sub-pages unvisited.
- **Writes:** ~7 verified of ~80+ meaningful write actions → **roughly 10-15% of the write surface.**
- **"Who does what" documentation:** essentially absent (catalog only). ← main enterprise gap.

## Plan to close the gap (capture priority — highest value first)
1. Messaging: send / edit / delete / react / mark-read  ← user asked explicitly
2. Comments: edit / reply / like  ← user asked
3. Mentions in post + comment  ← user asked
4. Profile: all sections (experience, education, skills, about, photo, contact, featured…)  ← user asked "100% profile"
5. Connections/follow: send/accept/withdraw/remove/follow/unfollow
6. Post interactions: repost, save, edit, media upload
7. Reactions: each type + comment reactions
8. Then: deep re-crawl for remaining read sub-pages.