# 02 — Voyager API — Endpoint Catalog

> Auto-generated from live captures. **112 unique Voyager endpoints** (REST + GraphQL, incl. hash variants), **29 SDUI actions** (see 03-SDUI-API.md).

Every GraphQL `queryId` has the form `<queryName>.<hash>`. The hash changes on LinkedIn deployments — the queryName stays stable.

## Identity/Profile

*11 endpoints*

### `voyagerIdentityDashGameEntryPoints.4666a73a66c1a9663577e1c37f1ac13a`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 6918 B

### `voyagerIdentityDashGameEntryPoints.67a406e3f9e3a8305fa432f77157bead`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 8368 B

### `voyagerIdentityDashProfileCards.aec4c2601fac8c5f615c7630b8db1ab3`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerIdentityDashProfileComponents.86824295e1093fb0f5acdd8d57213aaa`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerIdentityDashProfiles.4be600f2992df8cd036dba7aef973bab`
- **Method:** `GET` · **Type:** GQL

### `voyagerIdentityDashProfiles.b5c27c04968c409fc0ed3546575b9b7a`
- **Method:** `GET` · **Type:** GQL

### `voyagerIdentityDashProfiles.da93c92bffce3da586a992376e42a305`
- **Method:** `GET` · **Type:** GQL

### `voyagerIdentityDashProfiles.e9b0809465a07db1f02e70a82d455e10`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 36647 B

### `identity/dash/profiles/urn:li:fsd_profile:OWNER_PROFILE_ID`
- **Method:** `GET` · **Type:** REST

### `me`
- **Method:** `GET` · **Type:** REST

### `voyagerIdentityDashNotificationCards`
- **Method:** `GET` · **Type:** REST


## Feed/Posts

*17 endpoints*

### `inSessionRelevanceVoyagerFeedDashClientSignal.d14b45e21b8bec350407b606edf9cba0`
- **Method:** `POST` · **Type:** GQL
- **Body sample:** `{"variables":{"backendUpdateUrn":"urn:li:activity:ACTIVITY_ID","duration":"<ms>","durationStartTime":"<epoch_ms>"},"queryId":"inSessionRelevanceVoyagerFeedDashClientSignal.d14b45e21b8bec3`

### `voyagerContentcreationDashSharebox.6065bbd24f145384527c50bfc0c387ed`
- **Method:** `POST` · **Type:** GQL
- **Response size (sample):** 48189 B
- **Body sample:** `{"variables":{"origin":"FEED"},"queryId":"voyagerContentcreationDashSharebox.6065bbd24f145384527c50bfc0c387ed","includeWebMetadata":true}`

### `voyagerContentcreationDashShares.<hash>`
- **Method:** `POST` · **Type:** GQL
- **✅ Verified write:** Create post — verified (GraphQL)

### `voyagerContentcreationDashUpdateUrlPreview.b092c1aea4b6c087ec0d09614b3b3320`
- **Method:** `GET` · **Type:** GQL

### `voyagerFeedDashGlobalNavs.5e79c576bb420351fa8ff438d86b2c31`
- **Method:** `GET` · **Type:** GQL

### `voyagerFeedDashIdentityModule.803fe19f843a4d461478049f70d7babd`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 12539 B

### `voyagerFeedDashMainFeed.5c6157cdad2a34970e85f40c8f93ca2b`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerFeedDashOrganizationalPageUpdates.9e7a905afe23cba60c62b452066bf7d7`
- **Method:** `GET` · **Type:** GQL

### `voyagerFeedDashPackageRecommendations.a17e2926893fd3ff632c189cd61176d1`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 13964 B

### `voyagerFeedDashProfileUpdates.20c70fe0314184158516a7ec004c0408`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerFeedDashProfileUpdates.81bef031b9f0920ede4b0c9983e3744c`
- **Method:** `GET` · **Type:** GQL

### `voyagerFeedDashProfileUpdates.d6bd2ffe955d1ba0d19440ec139f0666`
- **Method:** `GET` · **Type:** GQL

### `voyagerFeedDashThirdPartyIdSyncs.e9d3044f7ad311ff359561b405629210`
- **Method:** `GET` · **Type:** GQL

### `voyagerFeedDashTopics.9075cab8b59e14d62b497b48f77d5e12`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 23072 B

### `voyagerContentcreationDashClosedSharebox`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 7359 B

### `voyagerContentcreationDashGuiderPrompts`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 7033 B

### `voyagerSocialDashReactions`
- **Method:** `POST` · **Type:** REST
- **✅ Verified write:** Set like — HTTP 201


## Messaging

*19 endpoints*

### `messengerConversations.0d5e6781bbee71c3e51c8843c6519f48`
- **Method:** `GET` · **Type:** GQL

### `messengerMailboxCounts.fc528a5a81a76dff212a4a3d2d48e84b`
- **Method:** `GET` · **Type:** GQL

### `messengerMailboxRealtimeSubscriptionAuthorizationTokens.1a3b0efc0a0a2c24c23367b5f8a25e62`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 3672 B

### `messengerMessages.5846eeb71c981f11e0134cb6626cc314`
- **Method:** `GET` · **Type:** GQL

### `messengerMessages.d8ea76885a52fd5dc5c317078ab7c977`
- **Method:** `GET` · **Type:** GQL

### `messengerQuickReplies.4338d226319203b5b08920ab7621fa45`
- **Method:** `GET` · **Type:** GQL

### `messengerSeenReceipts.dc29d9bcecad524b9dd264acbbde3b5c`
- **Method:** `GET` · **Type:** GQL

### `voyagerLegoDashPageContents.6e5607181411f5835938e105d18564e2`
- **Method:** `GET` · **Type:** GQL

### `voyagerMessagingDashAffiliatedMailboxes.da7e8047e61ae87c4b97ee31fed7d934`
- **Method:** `GET` · **Type:** GQL

### `voyagerMessagingDashAwayStatusV2.ee0ba3add6f8a58c35df3e08daa87b11`
- **Method:** `GET` · **Type:** GQL

### `voyagerMessagingDashComposeViewContexts.e15a66a8288033ed20e84acb49714a78`
- **Method:** `GET` · **Type:** GQL

### `voyagerMessagingDashMessagingSettings.a555e413ad439d1d3f58ceef31ff0728`
- **Method:** `GET` · **Type:** GQL

### `voyagerMessagingDashRecipientSuggestions.0623e89a6faf64755e04151fc3d5dced`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 20332 B

### `voyagerPremiumDashUpsellSlotContent.cb21d2bd460f3c55ceed3c190756a060`
- **Method:** `GET` · **Type:** GQL

### `messaging/dash/presenceStatuses`
- **Method:** `POST` · **Type:** REST
- **Body sample:** `ids=List(urn%3Ali%3Afsd_profile%3AOWNER_PROFILE_ID)`

### `voyagerMessagingDashConversationNudges`
- **Method:** `GET` · **Type:** REST

### `voyagerMessagingDashMessagingBadge`
- **Method:** `POST` · **Type:** REST
- **Body sample:** `{"until":1783720782358}`

### `voyagerMessagingDashMessengerMessageDeliveryAcknowledgements`
- **Method:** `POST` · **Type:** REST
- **Body sample:** `{"messageUrns":["urn:li:msg_message:(urn:li:fsd_profile:OWNER_PROFILE_ID,2-<message-id-redacted>)"],"clientId"`

### `voyagerMessagingDashSecondaryInbox`
- **Method:** `GET` · **Type:** REST


## Network

*5 endpoints*

### `relationships/connectionsSummary`
- **Method:** `GET` · **Type:** REST

### `relationships/invitationViews`
- **Method:** `GET` · **Type:** REST

### `relationships/invitationsSummary`
- **Method:** `GET` · **Type:** REST

### `relationships/myNetworkNotifications`
- **Method:** `GET` · **Type:** REST

### `voyagerRelationshipsDashDiscovery`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 88302 B


## Notifications

*4 endpoints*

### `voyagerOrganizationDashNotificationCounts.a6ef8bce390030a050e51c825d1e1eef`
- **Method:** `GET` · **Type:** GQL

### `notifications/dash/edgesetting/urn:li:fsd_edgeSetting:urn:li:fsd_company:COMPANY_ID`
- **Method:** `GET` · **Type:** REST

### `voyagerNotificationsDashBadge`
- **Method:** `POST` · **Type:** REST
- **Body sample:** `{"notificationFilterUrn":"urn:li:fsd_notificationFilter:ALL","until":1783720797188}`

### `voyagerNotificationsDashBadgingItemCounts`
- **Method:** `GET` · **Type:** REST


## Search

*9 endpoints*

### `voyagerJobsDashJobCards.9c135b2568ee44623733b4a578d25279`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashJobSearchHistories.220d01e7d55ec8363130acffb73298ff`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashJobSearchSuggestionComponents.04e260716e8739f78bad924422f85f2f`
- **Method:** `GET` · **Type:** GQL

### `voyagerSearchDashClusters.a7a0567fa66c52d645b5ff2f960b92aa`
- **Method:** `GET` · **Type:** GQL

### `voyagerSearchDashLazyLoadedActions.3a131e1ec0f98666d762cda12366ccea`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 87045 B

### `growth/pageContent/job_search`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 7469 B

### `voyagerJobsDashJobCards`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerJobsDashJobSearchHistories`
- **Method:** `POST` · **Type:** REST
- **Body sample:** `{"query":{"origin":"JOBS_HOME_JYMBII","locationUnion":{"geoUrn":"urn:li:fsd_geo:GEO_ID"},"spellCorrectionEnabled":true},"referenceId":"$Mzö\u0015òÿ¹À39Ùp","jobSearchType":"CLASSIC"}`

### `voyagerJobsDashSearchFilterClustersResource`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 88460 B


## Jobs

*14 endpoints*

### `voyagerJobsDashJobCards.e5b6b761ede078dabe8ad857aa42c220`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerJobsDashJobPostingDetailSections.77cb64956921ef397a36de4f7f8bce47`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashJobPostings.891aed7916d7453a37e4bbf5f1f60de4`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashJobSeekerPreferences.53d4a0b454b82ce339abf8afc2c65190`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashJobSeekerUpdates.b2ecb69b3e0f6f22f4a0d8d32c070c83`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashJobsFeed.711cec89dd87dcf89df6a9d6e7ab5682`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashJobsFeed.8b4a94e0e9d8395f1e7482987dd2f815`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerJobsDashLocationSuggestions.c5a03455b489e62d92bbf5bb089f619e`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashNavigationPanel.00e17eebd503c82434a0717b64fd0a4b`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 26524 B

### `voyagerJobsDashNavigationPanel.0d3dbfde78d0547cb1d03d910d14f602`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashNavigationPanel.e161df0f6116399fa0059aaf1bf736bc`
- **Method:** `GET` · **Type:** GQL

### `voyagerJobsDashOnsiteApplyApplication.96a2a30d12bccaec2b5ba9acbcbbf97c`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerJobsDashJobPostings`
- **Method:** `POST` · **Type:** REST
- **Response size (sample):** 1222 B
- **Body sample:** `{"jobPosting":{"title":"","companyDetails":{"jobCompanyUnion":{"company":"urn:li:fsd_company:COMPANY_ID"}},"locationUrn":"urn:li:fsd_geo:GEO_ID"}}`

### `voyagerJobsDashJobSeekerPreferences`
- **Method:** `GET` · **Type:** REST


## Organization

*12 endpoints*

### `voyagerOrganizationDashCompanies.148b1aebfadd0a455f32806df656c3c1`
- **Method:** `GET` · **Type:** GQL

### `voyagerOrganizationDashCompanies.2fce873504d824e22294f312f718b4c7`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 13083 B

### `voyagerOrganizationDashDiscoverCardGroups.faf15c48adb2a3a65e8dd984b743394e`
- **Method:** `GET` · **Type:** GQL

### `voyagerOrganizationDashViewWrapper.8d20f7b47ae1c746f3198561c595895e`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerPremiumDashAnalyticsView.677f8e447e2d15652410d574abfe1d1e`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 87816 B

### `voyagerPremiumDashPremiumChooserFlow.e9f6f9ca895fa4a332189cfc6eb281a8`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 48530 B

### `voyagerPremiumDashUpsellSlotContent.59114115a17b6a93502faec8f3fadf6b`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 8198 B

### `voyagerTalentbrandDashCandidateInterestAdmin.7ce96d008cea14b03263ce4bffb00096`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 9297 B

### `voyagerTalentbrandDashCandidateInterestMember.d831bf85b9873ef0228a2bab19781290`
- **Method:** `GET` · **Type:** GQL

### `voyagerTalentbrandDashOrganizationLifePageTrafficStatistics.6342711231e2205554d6740d552f8426`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 7791 B

### `voyagerOrganizationDashInformationCallout`
- **Method:** `GET` · **Type:** REST

### `voyagerOrganizationDashPageMailbox/`
- **Method:** `GET` · **Type:** REST


## Events

*3 endpoints*

### `voyagerEventsDashEventsCardGroupResource.76207ae0cd3b83dc7ea5b00903bc9ed3`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** SECTION_ITEM_ID B

### `voyagerLegoDashWidgetActionEvents`
- **Method:** `POST` · **Type:** REST
- **Body sample:** `{"trackingToken":"0NfmlWqldVomNMsSBA9z0Kc3RBsCZzkTsCfn9xk6NBkDsCfmhLjmNBkDsCcjRApnhPpnlNpl9JtmUCjAZ9l4BjjR0Zuk9OpmhOjThBpShFtOpQpmtAqntvsClFpCBQrClAqlZQrSNPnStKqmhOomZyrCZvgjcBu7lFpBZ1cOlCqmoZp4BQpmtA`

### `voyagerLegoDashWidgetImpressionEvents`
- **Method:** `POST` · **Type:** REST
- **Body sample:** `{"trackingToken":"cjRBuCBjum5Is7dFp2oMbz0Zpn9LoRdT9zROol1Ipl9T9zRArQRIpl9T9zAVejAVfmhBt7dBtn5BkCRRrypejQBkildfk3RVgD9Bp79ft6lDp6BT9CNBoC5InTtBrBZPoCZGnSVFrmhxnQ4P9ndBpS5MnQ4P9mpFpzRAinhBpShFtOoMfmVLqn`


## Groups

*1 endpoints*

### `voyagerGroupsDashGroups/urn:li:fsd_group:GROUP_ID`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 78419 B


## Premium

*2 endpoints*

### `voyagerPremiumDashFeatureAccess.c87b20dac35795f9920f2a8072fd7af5`
- **Method:** `GET` · **Type:** GQL

### `premium/featureAccess`
- **Method:** `GET` · **Type:** REST


## Talentbrand

*1 endpoints*

### `voyagerTalentbrandDashTargetedContents.1662b25622fa5eaba012696316461035`
- **Method:** `GET` · **Type:** GQL


## Settings/Other

*4 endpoints*

### `voyagerDashMySettings.8fdc6cac2e41f88f83e8d17dc78ac26c`
- **Method:** `GET` · **Type:** GQL

### `voyagerGlobalAlerts`
- **Method:** `GET` · **Type:** REST

### `voyagerLaunchpadDashLaunchpadViews`
- **Method:** `GET` · **Type:** REST

### `voyagerSegmentsDashChameleonConfig`
- **Method:** `GET` · **Type:** REST


## Misc

*10 endpoints*

### `voyagerDashGeo.8909acb4ad554861d9693b15249caf61`
- **Method:** `GET` · **Type:** GQL

### `voyagerHiringDashJobPostingFlowEligibilities.23b8178f769be71e0f473a72de4ccbee`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 1532 B

### `voyagerMarketplacesDashSimilarServiceProvidersView.ebe089e3081272020de3b4d2d32d5ec5`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 66516 B

### `voyagerNewsDashStorylines.c042ce89aeaa19a94ba27cf715164f46`
- **Method:** `GET` · **Type:** GQL
- **Response size (sample):** 19612 B

### `growth/socialproofs`
- **Method:** `GET` · **Type:** REST

### `identity/normalizedProfiles/OWNER_PROFILE_ID`
- **Method:** `GET` · **Type:** REST

### `publishing/editorFirstPartyArticles`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 231 B

### `voyagerDashLanguageSelection`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 4403 B

### `voyagerHiringDashJobHiringSocialHirersCards`
- **Method:** `GET` · **Type:** REST
- **Response size (sample):** 27361 B

### `voyagerOnboardingDashMemberHandles`
- **Method:** `GET` · **Type:** REST

