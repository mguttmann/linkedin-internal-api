# 23 — Read discovery: verified queryId hashes + per-surface map (2026-07-12)

Passive capture (no writes, no cache-bust, stealth session) across the major surfaces — Jobs,
Notifications, Analytics, My Network, Company admin, Settings. **Result: the read side was
already complete** (the earlier 74-endpoint sweep covered every base endpoint seen here). The new
value is (a) the concrete **queryId hashes** you need for live GraphQL calls, and (b) a
**per-surface map** of which endpoints actually fire where. Honest negatives noted.

---

## Verified GraphQL queryId hashes (needed for live calls)
These are the exact hashes captured live — GraphQL calls fail without the right hash.

| Base | queryId hash | What it loads |
|---|---|---|
| `voyagerOrganizationDashCompanies` | `2fce873504d824e22294f312f718b4c7` | Company entity (admin/page) |
| `voyagerFeedDashMainFeed` | `5c6157cdad2a34970e85f40c8f93ca2b` | Home main feed |
| `voyagerFeedDashProfileUpdates` | `20c70fe0314184158516a7ec004c0408` | **Own posts (full text)** — the Composio gap |
| `voyagerDashMySettings` | `8fdc6cac2e41f88f83e8d17dc78ac26c` | Settings values |
| `voyagerMessagingDashMessagingSettings` | `a555e413ad439d1d3f58ceef31ff0728` | Messaging settings |
| `voyagerJobsDashJobSeekerPreferences` | `53d4a0b454b82ce339abf8afc2c65190` | Open-to-work / job prefs |
| `voyagerPremiumDashFeatureAccess` | `c87b20dac35795f9920f2a8072fd7af5` | Premium gating flags |
| `voyagerIdentityDashProfiles` | `b5c27c04968c409fc0ed3546575b9b7a` | Profile (top-card variant) |
| `voyagerIdentityDashProfiles` | `da93c92bffce3da586a992376e42a305` | Profile (variant) |
| `voyagerIdentityDashProfiles` | `e9b0809465a07db1f02e70a82d455e10` | Profile (variant) |
| `voyagerFeedDashIdentityModule` | `803fe19f843a4d461478049f70d7babd` | Right-rail identity module |
| `messengerConversations` | `0d5e6781bbee71c3e51c8843c6519f48` | Inbox conversations |
| `messengerMailboxCounts` | `fc528a5a81a76dff212a4a3d2d48e84b` | Unread counts |

## Per-surface REST reads (non-GraphQL)
- **Notifications** (`/notifications/`): `relationships/myNetworkNotifications`,
  `relationships/invitationsSummary`, `relationships/invitationViews`,
  `relationships/connectionsSummary`, `growth/socialproofs`,
  `publishing/editorFirstPartyArticles`, `voyagerLaunchpadDashLaunchpadViews`.
- **Every authenticated surface** (chrome, ignore as noise): `voyagerGlobalAlerts`,
  `voyagerIdentityDashNotificationCards`, `voyagerMessagingDashConversationNudges`,
  `voyagerMessagingDashSecondaryInbox`, `voyagerOrganizationDashPageMailbox`,
  `voyagerSegmentsDashChameleonConfig`, `premium/featureAccess`, `me`.

## Honest negatives
- **Settings** (`/mypreferences/d/categories/{account,privacy,visibility}`): **0 API calls
  captured** — these are a server-rendered / SPA shell that doesn't fetch its data via the
  voyager REST/GraphQL layer we can see. Confirms the earlier finding: settings are not
  scriptable through this API surface. (`voyagerDashMySettings` above is read by *other* pages,
  not the settings UI itself.)
- **Modern surfaces are GraphQL-first:** Jobs/Network/Analytics pages fetch almost everything
  through `graphql?queryId=…`; there are few page-specific REST endpoints left. The hash IS the
  API — capture is the only way to get it.

## Bottom line
Read coverage is complete for automation purposes. For any GraphQL read, use the hash table
above; for lists/counts use the `relationships/*` REST endpoints. Settings remain out of reach
via this API.