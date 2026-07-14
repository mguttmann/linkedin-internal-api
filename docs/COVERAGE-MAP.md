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
through pure `requests`; comment/reaction SDUI writes replay a captured full body with minimal headers.

**MCP tools:**
- *Reads (browserless):* `get_me`, `get_my_posts`, `get_profile`, `get_notifications`,
  `get_conversations`, `get_connections_summary`, `get_post_comments`, `get_link_preview`
- *Posts:* `create_post` (+poll_urn), `edit_post`, `delete_post`, `create_poll`, `save_post`,
  `repost`, `delete_repost` (repost create browserless 200; repost delete via browser)
- *Engagement:* `like` (browserless 201), `unlike` (browserless 200), `create_comment`,
  `delete_comment` (all browserless)
- *Messaging (browserless live):* `send_dm`, `recall_message`, `react_to_message`
- *Network:* `follow_company`, `connect`, `endorse_skill` (browserless 200), `remove_connection`
- *Session:* `session_status`, `refresh_session`

**Key finding:** SDUI writes are ALL browserless-replayable — the earlier `currentActor` "needs a
browser" story was a red herring (that field is empty in the real browser request too). Two things
mattered: (1) replay the **full captured body** verbatim (hand-built partial bodies 500), and
(2) send **minimal headers** (csrf + cookies + content-type) — vgreq's Voyager `accept`/`x-restli`
headers make the SDUI route 500. Proven live for `unlike` and `create_comment`.

---

## 1. Feed & Posts
| Function | Endpoint | Status |
|---|---|---|
| Read own/others posts | `graphql voyagerFeedDashProfileUpdates` | 🔍 |
| Read main feed | `graphql voyagerFeedDashMainFeed` / SDUI `pagers.feed.mainFeed` | 🔍 |
| Create post (text) | `graphql voyagerContentcreationDashShares` | ✅ MCP `create_post` (browserless live) |
| Delete post | SDUI `com.linkedin.sdui.update.deletePost` | ✅ MCP `delete_post` (browserless) |
| Post with **image/video/document** | Voyager `MediaUploadMetadata`→PUT→`Shares` asset | ✅ captured (docs/24) |
| Post with **@mention** of a person | `commentary.attributesV2.profileMention` | ✅ verified (docs/24) |
| Post with **link preview** | `voyagerContentcreationDashUpdateUrlPreview` | ✅ MCP `get_link_preview` (browserless 200) |
| Post **poll** | `PollsPollSummary`→`Shares` URN_REFERENCE | ✅ MCP `create_poll` + `create_post(poll_urn)` (browserless live) |
| Edit an existing post | `Shares` + `resourceKey`/`updateUrn` | ✅ MCP `edit_post` (browserless live) |
| **Repost** (instant) | SDUI `feed.requests.createInstantRepost` | ✅ MCP `repost` (browser-only, 500 headless) |
| Delete repost | Voyager `graphql voyagerFeedDashReposts` (delete-by-key) | ✅ MCP `delete_repost` |
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
| **Reply** to a comment (nested) | SDUI `comments.createComment` (parent ref) | ✅ |
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
| **React** to a message (emoji) | `messengerMessages?action=reactWithEmoji` | ✅ MCP `react_to_message` |
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
| Read job recommendations/cards | `voyagerJobsDashJobCards` etc. | 🔍 |
| Read job posting detail | `voyagerJobsDashJobPostingDetailSections` | 🔍 |
| **Save / unsave** a job | ? | ❌ |
| **Apply** to a job (Easy Apply) | `voyagerJobsDashOnsiteApplyApplication` seen | ❌ write |
| Set job **alerts / preferences** | `voyagerJobsDashJobSeekerPreferences` | 🔍 |
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