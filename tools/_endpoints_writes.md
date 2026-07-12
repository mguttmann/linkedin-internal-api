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
