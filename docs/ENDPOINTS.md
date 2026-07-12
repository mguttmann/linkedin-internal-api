# ENDPOINTS — full reference

Complete inventory of every LinkedIn internal endpoint captured for this project: **141 raw captured requests** (112 Voyager + 29 SDUI) which dedupe to **130 distinct endpoint families** (the same family often appears under several rotating GraphQL query-id hashes), plus the **verified write/action endpoints** below.

- **Voyager** = `/voyager/api/…` REST.li + GraphQL. Auth: cookies + csrf-token (see `01-AUTH-AND-COOKIES.md`).
- **SDUI** = `/flagship-web/rsc-action/…` server-driven UI actions (POST with a `requestId` body).
- GraphQL `queryId` hashes rotate on LinkedIn deploys — re-capture if a call starts 404-ing.

> Auto-generated from `data/endpoints_*.json` + the curated write table. Regenerate: `python3 tools/gen_endpoints_md.py`.

---
## ✅ Verified write / action endpoints (the money table)

These are captured live and verified on the owner's own account. Full bodies in `04-WRITE-OPERATIONS.md`
and the per-section docs. **Browserless** = works via pure `requests` (`vgreq`); **browser** = needs
the patchright session (SDUI currentActor binding).

### Engagement
| Action | Layer | Endpoint | Browserless | Doc |
|---|---|---|---|---|
| Like a post | Voyager | `POST voyagerSocialDashReactions?threadUrn={urn}` `{reactionType:LIKE}` | ✅ 201 | 04 |
| Unlike | SDUI | `com.linkedin.sdui.reactions.delete` | ⚠️ 500 (browser) | 04 |
| Create post | Voyager GQL | `graphql?action=execute&queryId=voyagerContentcreationDashShares.<hash>` | ✅ 200 | 04 |
| Edit post | Voyager GQL | `voyagerContentcreationDashShares.<hash>` + `resourceKey`/`updateUrn` | ✅ 200 | 24 |
| Delete post | SDUI | `com.linkedin.sdui.update.deletePost` (activityId + trackingId) | ✅ (browser-capture) | 04 |
| Poll | Voyager GQL | `voyagerFeedDashPollsPollSummary.<hash>` → `Shares` `media.mediaUrn` | ✅ 200 | 24 |
| Post media (image/video) | Voyager | `POST voyagerVideoDashMediaUploadMetadata?action=upload` → PUT → `Shares` | ✅ captured | 24 |
| @mention in post | Voyager | `commentary.attributesV2.profileMention` (+ start/length) | ✅ | 24 |
| Link preview | Voyager GQL | `GET voyagerContentcreationDashUpdateUrlPreview.<hash>` | ✅ 200 | 24 |
| Read own posts (full text) | Voyager GQL | `voyagerFeedDashProfileUpdates.<hash>` | ✅ 200 | 02 |
| Read post comments | Voyager | `GET feed/comments?q=comments&updateId={urn}` | ✅ 200 | 04 |
| Create comment | SDUI | `com.linkedin.sdui.comments.createComment` | ⚠️ (browser) | 04 |
| Delete comment | SDUI | `com.linkedin.sdui.comments.deleteComment` | ⚠️ (browser) | 04 |
| React to comment | SDUI | `com.linkedin.sdui.reactions.create` (commentThreadUrn) | ⚠️ (browser) | 25 |
| Repost / instant repost | SDUI | `com.linkedin.sdui.feed.requests.createInstantRepost` | ⚠️ 500 (browser) | 10 |
| Delete repost | Voyager GQL | `voyagerFeedDashReposts` (delete-by-key) | ✅ | 10 |
| Save / unsave post | SDUI | `com.linkedin.sdui.update.saveState` (`isSaved` toggle) | ✅ 200 | 10 |

### Messaging (Voyager; sends/recall/react are browserless-friendly)
| Action | Endpoint | Doc |
|---|---|---|
| Send message | `POST voyagerMessagingDashMessengerMessages?action=createMessage` (originToken idempotency; `trackingId` = 16 raw bytes latin-1, `dedupeByClientGeneratedToken:false`) | 06 |
| Recall (delete) message | `POST voyagerMessagingDashMessengerMessages?action=recall` (→ 204) | 06 |
| React with emoji | `POST voyagerMessagingDashMessengerMessages?action=reactWithEmoji` (implemented, not live-tested) | 06 |
| Mark conversation read | `POST voyagerMessagingDashMessengerConversations?ids=List(...)` `patch.$set.read` | 06 |
| List conversations | `GET voyagerMessagingGraphQL/graphql messengerConversations.<hash>?variables=(mailboxUrn:{ME})` | 06 |

### Network
| Action | Layer | Endpoint | Doc |
|---|---|---|---|
| Follow / unfollow company | Voyager | `POST feed/dash/followingStates/{urn}` `patch.$set.following` | 08 |
| Follow a person | SDUI | `com.linkedin.sdui.requests.mynetwork.addaUpdateFollowState` | 08 |
| Connect (with note) | Voyager | `POST voyagerRelationshipsDashMemberRelationships?action=verifyQuotaAndCreateV2` + `customMessage` | 25 |
| Accept / ignore invitation | SDUI | `mynetwork` invitation-action family | 08 |
| Endorse a skill | SDUI | `com.linkedin.sdui.requests.profile.endorseSkill` (vanityName+profileId+skillId) | 25 |
| Remove a connection | SDUI | `com.linkedin.sdui.mynetwork.RemoveConnectionVanityName` | 25 |
| Read connections summary | Voyager | `GET relationships/connectionsSummary` | 08 |

### Profile editing — `saveProfile<X>Form` / `deleteProfile<X>` (SDUI)
16 sections are **documented** from the universal `saveProfile<X>Form` / `deleteProfile<X>` pattern.
Persisted capture artifacts (the local captures (kept local, not shipped), gitignored) back a **subset**; the `Captured`
column below reflects what actually has a recorded request. The **`states[]` array carries real
values**, so a captured CREATE replays from pure `requests` (HTTP 200) — see `BROWSERLESS-REPLAY.md`.
Sections without a persisted artifact are reference-only (endpoint inferred from the pattern);
each per-section doc (09–21) states its exact captured-vs-inferred status.

| Section | Save form | Delete | Captured | Doc |
|---|---|---|---|---|
| Intro (name/headline/location) | `saveProfileIntroForm` | — | pattern-only | 09 |
| About / Summary | `saveProfileAboutForm` | — | pattern-only | 21 |
| Contact info | `saveProfileContactInfoForm` | — | ✅ save | 20 |
| Skills | `saveProfileSkillForm` | `deleteProfileSkillForm` | pattern-only | 09 |
| Languages | `saveProfileLanguageForm` | `deleteProfileLanguageForm` | pattern-only | 09 |
| Education | `saveProfileEducationForm` | `deleteProfileEducationForm` | pattern-only | 09 |
| Certifications | `saveProfileCertificationForm` | `deleteProfileCertification` | ✅ add+edit+delete | 09 |
| Projects | `saveProfileProjectForm` | `deleteProfileProjectForm` | ✅ add+edit+delete | 09 |
| Experience (position) | `saveProfilePositionForm` | `deleteProfilePositionForm` (inferred) | ✅ add only | 11 |
| Featured | `profile.featured.link` / `.media.edit` | `.media.delete` | pattern-only | 12 |
| Volunteer | `saveVolunteerExperienceForm` | `deleteVolunteerExperience` | ✅ add+edit+delete | 13 |
| Publications | `saveProfilePublicationForm` | `deleteProfilePublication` (inferred) | ✅ add only | 14 |
| Courses | `saveProfileCourseForm` | `deleteProfileCourse` | ✅ add+edit+delete | 15 |
| Honors | `saveProfileHonorForm` | `deleteProfileHonor` (inferred) | ✅ add only | 16 |
| Patents | `saveProfilePatentForm` (2 required fields) | `deleteProfilePatent` | pattern-only | 17 |
| Organizations | `saveProfileOrganizationForm` | `deleteProfileOrganization` | ✅ add+edit+delete | 18 |
| Test scores | `saveProfileTestScoreForm` | `deleteProfileTestScore` | ✅ delete only | 19 |

### Jobs / Open-to-work
| Action | Endpoint | Doc |
|---|---|---|
| Read job-seeker prefs | `GET voyagerJobsDashJobSeekerPreferences` | 22 |
| Enable open-to-work | `POST voyagerJobsDashOpenToWorkPreferencesFormElementInput?action=submitFormAndGenerateView` | 22 |
| Disable open-to-work | `DELETE voyagerJobsDashOpenToWorkPreferencesFormElementInput?formType=OPEN_TO_WORK` | 22 |

---

## All discovered READ endpoints

## Voyager (101 distinct / 112 raw)

### Messaging (18)

| Method | Type | Endpoint |
|---|---|---|
| POST | REST | `messaging/dash/presenceStatuses` |
| GET | GQL | `messengerConversations .<hash>` |
| GET | GQL | `messengerMailboxCounts .<hash>` |
| GET | GQL | `messengerMailboxRealtimeSubscriptionAuthorizationTokens .<hash>` |
| GET | GQL | `messengerMessages .<hash>` |
| GET | GQL | `messengerQuickReplies .<hash>` |
| GET | GQL | `messengerSeenReceipts .<hash>` |
| GET | GQL | `voyagerLegoDashPageContents .<hash>` |
| GET | GQL | `voyagerMessagingDashAffiliatedMailboxes .<hash>` |
| GET | GQL | `voyagerMessagingDashAwayStatusV2 .<hash>` |
| GET | GQL | `voyagerMessagingDashComposeViewContexts .<hash>` |
| GET | REST | `voyagerMessagingDashConversationNudges` |
| POST | REST | `voyagerMessagingDashMessagingBadge` |
| GET | GQL | `voyagerMessagingDashMessagingSettings .<hash>` |
| POST | REST | `voyagerMessagingDashMessengerMessageDeliveryAcknowledgements` |
| GET | GQL | `voyagerMessagingDashRecipientSuggestions .<hash>` |
| GET | REST | `voyagerMessagingDashSecondaryInbox` |
| GET | GQL | `voyagerPremiumDashUpsellSlotContent .<hash>` |

### Feed/Posts (15)

| Method | Type | Endpoint |
|---|---|---|
| POST | GQL | `inSessionRelevanceVoyagerFeedDashClientSignal .<hash>` |
| GET | REST | `voyagerContentcreationDashClosedSharebox` |
| GET | REST | `voyagerContentcreationDashGuiderPrompts` |
| POST | GQL | `voyagerContentcreationDashSharebox .<hash>` |
| POST | GQL | `voyagerContentcreationDashShares.<hash>` |
| GET | GQL | `voyagerContentcreationDashUpdateUrlPreview .<hash>` |
| GET | GQL | `voyagerFeedDashGlobalNavs .<hash>` |
| GET | GQL | `voyagerFeedDashIdentityModule .<hash>` |
| GET | GQL | `voyagerFeedDashMainFeed .<hash>` |
| GET | GQL | `voyagerFeedDashOrganizationalPageUpdates .<hash>` |
| GET | GQL | `voyagerFeedDashPackageRecommendations .<hash>` |
| GET | GQL | `voyagerFeedDashProfileUpdates .<hash>` |
| GET | GQL | `voyagerFeedDashThirdPartyIdSyncs .<hash>` |
| GET | GQL | `voyagerFeedDashTopics .<hash>` |
| POST | REST | `voyagerSocialDashReactions` |

### Jobs (11)

| Method | Type | Endpoint |
|---|---|---|
| GET | GQL | `voyagerJobsDashJobCards .<hash>` |
| GET | GQL | `voyagerJobsDashJobPostingDetailSections .<hash>` |
| POST | REST | `voyagerJobsDashJobPostings` |
| GET | GQL | `voyagerJobsDashJobPostings .<hash>` |
| GET | REST | `voyagerJobsDashJobSeekerPreferences` |
| GET | GQL | `voyagerJobsDashJobSeekerPreferences .<hash>` |
| GET | GQL | `voyagerJobsDashJobSeekerUpdates .<hash>` |
| GET | GQL | `voyagerJobsDashJobsFeed .<hash>` |
| GET | GQL | `voyagerJobsDashLocationSuggestions .<hash>` |
| GET | GQL | `voyagerJobsDashNavigationPanel .<hash>` |
| GET | GQL | `voyagerJobsDashOnsiteApplyApplication .<hash>` |

### Organization (11)

| Method | Type | Endpoint |
|---|---|---|
| GET | GQL | `voyagerOrganizationDashCompanies .<hash>` |
| GET | GQL | `voyagerOrganizationDashDiscoverCardGroups .<hash>` |
| GET | REST | `voyagerOrganizationDashInformationCallout` |
| GET | REST | `voyagerOrganizationDashPageMailbox/` |
| GET | GQL | `voyagerOrganizationDashViewWrapper .<hash>` |
| GET | GQL | `voyagerPremiumDashAnalyticsView .<hash>` |
| GET | GQL | `voyagerPremiumDashPremiumChooserFlow .<hash>` |
| GET | GQL | `voyagerPremiumDashUpsellSlotContent .<hash>` |
| GET | GQL | `voyagerTalentbrandDashCandidateInterestAdmin .<hash>` |
| GET | GQL | `voyagerTalentbrandDashCandidateInterestMember .<hash>` |
| GET | GQL | `voyagerTalentbrandDashOrganizationLifePageTrafficStatistics .<hash>` |

### Identity/Profile (7)

| Method | Type | Endpoint |
|---|---|---|
| GET | REST | `identity/dash/profiles/urn:li:fsd_profile:OWNER_PROFILE_ID` |
| GET | REST | `me` |
| GET | GQL | `voyagerIdentityDashGameEntryPoints .<hash>` |
| GET | REST | `voyagerIdentityDashNotificationCards` |
| GET | GQL | `voyagerIdentityDashProfileCards .<hash>` |
| GET | GQL | `voyagerIdentityDashProfileComponents .<hash>` |
| GET | GQL | `voyagerIdentityDashProfiles .<hash>` |

### Misc (10)

| Method | Type | Endpoint |
|---|---|---|
| GET | REST | `growth/socialproofs` |
| GET | REST | `identity/normalizedProfiles/OWNER_PROFILE_ID` |
| GET | REST | `publishing/editorFirstPartyArticles` |
| GET | GQL | `voyagerDashGeo .<hash>` |
| GET | REST | `voyagerDashLanguageSelection` |
| GET | REST | `voyagerHiringDashJobHiringSocialHirersCards` |
| GET | GQL | `voyagerHiringDashJobPostingFlowEligibilities .<hash>` |
| GET | GQL | `voyagerMarketplacesDashSimilarServiceProvidersView .<hash>` |
| GET | GQL | `voyagerNewsDashStorylines .<hash>` |
| GET | REST | `voyagerOnboardingDashMemberHandles` |

### Search (9)

| Method | Type | Endpoint |
|---|---|---|
| GET | REST | `growth/pageContent/job_search` |
| GET | REST | `voyagerJobsDashJobCards` |
| GET | GQL | `voyagerJobsDashJobCards .<hash>` |
| POST | REST | `voyagerJobsDashJobSearchHistories` |
| GET | GQL | `voyagerJobsDashJobSearchHistories .<hash>` |
| GET | GQL | `voyagerJobsDashJobSearchSuggestionComponents .<hash>` |
| GET | REST | `voyagerJobsDashSearchFilterClustersResource` |
| GET | GQL | `voyagerSearchDashClusters .<hash>` |
| GET | GQL | `voyagerSearchDashLazyLoadedActions .<hash>` |

### Network (5)

| Method | Type | Endpoint |
|---|---|---|
| GET | REST | `relationships/connectionsSummary` |
| GET | REST | `relationships/invitationViews` |
| GET | REST | `relationships/invitationsSummary` |
| GET | REST | `relationships/myNetworkNotifications` |
| GET | REST | `voyagerRelationshipsDashDiscovery` |

### Notifications (4)

| Method | Type | Endpoint |
|---|---|---|
| GET | REST | `notifications/dash/edgesetting/urn:li:fsd_edgeSetting:urn:li:fsd_company:COMPANY_ID` |
| POST | REST | `voyagerNotificationsDashBadge` |
| GET | REST | `voyagerNotificationsDashBadgingItemCounts` |
| GET | GQL | `voyagerOrganizationDashNotificationCounts .<hash>` |

### Settings/Other (4)

| Method | Type | Endpoint |
|---|---|---|
| GET | GQL | `voyagerDashMySettings .<hash>` |
| GET | REST | `voyagerGlobalAlerts` |
| GET | REST | `voyagerLaunchpadDashLaunchpadViews` |
| GET | REST | `voyagerSegmentsDashChameleonConfig` |

### Events (3)

| Method | Type | Endpoint |
|---|---|---|
| GET | GQL | `voyagerEventsDashEventsCardGroupResource .<hash>` |
| POST | REST | `voyagerLegoDashWidgetActionEvents` |
| POST | REST | `voyagerLegoDashWidgetImpressionEvents` |

### Premium (2)

| Method | Type | Endpoint |
|---|---|---|
| GET | REST | `premium/featureAccess` |
| GET | GQL | `voyagerPremiumDashFeatureAccess .<hash>` |

### Groups (1)

| Method | Type | Endpoint |
|---|---|---|
| GET | REST | `voyagerGroupsDashGroups/urn:li:fsd_group:GROUP_ID` |

### Talentbrand (1)

| Method | Type | Endpoint |
|---|---|---|
| GET | GQL | `voyagerTalentbrandDashTargetedContents .<hash>` |

## SDUI (29 distinct / 29 raw)

### Misc (12)

| Method | Type | Endpoint |
|---|---|---|
| POST | SDUI | `WvmpEntityList` |
| POST | SDUI | `com.linkedin.sdui.generated.profile.dsl.impl.browsemapRecommendedEntitySection` |
| POST | SDUI | `com.linkedin.sdui.generated.profile.dsl.impl.productRecommendedEntitySection` |
| POST | SDUI | `com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity` |
| POST | SDUI | `com.linkedin.sdui.generated.profile.dsl.impl.profileCardsActivity` |
| POST | SDUI | `com.linkedin.sdui.generated.profile.dsl.impl.pymkRecommendedEntitySection` |
| POST | SDUI | `com.linkedin.sdui.impl.homenav.requests.getThirdPartyTrackingPixels` |
| POST | SDUI | `com.linkedin.sdui.infra.register.cooloff.activity` |
| GET | SDUI | `com.linkedin.sdui.realtimeDefaultHandler` |
| POST | SDUI | `com.linkedin.sdui.requests.profile.fetchProfileDiscoveryDrawer` |
| POST | SDUI | `com.linkedin.sdui.requests.profile.profilePolicyNotice` |
| POST | SDUI | `rsc-action` |

### Feed/Posts (6)

| Method | Type | Endpoint |
|---|---|---|
| POST | SDUI | `com.linkedin.sdui.action.sharing.closed-sharebox.server-action` |
| POST | SDUI | `com.linkedin.sdui.comments.createComment` |
| POST | SDUI | `com.linkedin.sdui.comments.deleteComment` |
| POST | SDUI | `com.linkedin.sdui.pagers.feed.mainFeed` |
| POST | SDUI | `com.linkedin.sdui.reactions.delete` |
| POST | SDUI | `com.linkedin.sdui.update.deletePost` |

### Network (4)

| Method | Type | Endpoint |
|---|---|---|
| POST | SDUI | `com.linkedin.sdui.requests.mynetwork.addaClearUnseenInvitationsMutation` |
| POST | SDUI | `com.linkedin.sdui.requests.mynetwork.addaMarkAllNetworkHighlightsAsSeen` |
| POST | SDUI | `com.linkedin.sdui.requests.mynetwork.addaMarkNotificationsSeen` |
| POST | SDUI | `com.linkedin.sdui.requests.mynetwork.mojoTabsBadge` |

### Search (3)

| Method | Type | Endpoint |
|---|---|---|
| POST | SDUI | `com.linkedin.sdui.generated.jobseeker.dsl.impl.jobSearchBox` |
| POST | SDUI | `com.linkedin.sdui.search.requests.searchHomeRequestAction` |
| POST | SDUI | `com.linkedin.sdui.search.requests.updateSearchHistoryRequest` |

### Analytics (2)

| Method | Type | Endpoint |
|---|---|---|
| POST | SDUI | `WvmpAnalytics` |
| POST | SDUI | `com.linkedin.sdui.requests.creatoranalytics.caSlowMetrics` |

### Identity/Profile (1)

| Method | Type | Endpoint |
|---|---|---|
| POST | SDUI | `com.linkedin.sdui.requests.profile.saveProfileIntroForm` |

### Jobs (1)

| Method | Type | Endpoint |
|---|---|---|
| POST | SDUI | `com.linkedin.sdui.pagers.jobseeker.jobsHomeFeedModuleList` |