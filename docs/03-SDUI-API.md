# 03 — SDUI API (Server-Driven UI / `rsc-action`)

LinkedIn is migrating parts of the web app to **SDUI** (Server-Driven UI). Instead of
classic REST endpoints, the client sends **action requests** to a generic handler that
addresses the concrete server action via an `sduiid`. **Important:** several operations run
**exclusively** over SDUI — e.g. removing a reaction (unlike), deleting a post, comment
create/delete, and profile save.

## Base endpoints

| Endpoint | Purpose |
|---|---|
| `POST /flagship-web/rsc-action/actions/server-request?sduiid=<ID>` | Single action (most writes) |
| `POST /flagship-web/rsc-action/actions/component?componentId=<ID>` | Component data (e.g. comment box state) |
| `POST /flagship-web/rsc-action/actions/pagination?sduiid=<ID>` | Pager (feed, lists) |
| `GET  /flagship-web/rsc-action/actions/server-stream-request?sduiid=<ID>&payload=<url-enc>` | Streaming response (SSE) |
| `POST /flagship-web/rsc-action/actions/app-config` | Client config (body `{}`) |

The `sduiid` is a **reverse-domain action identifier**, e.g.:
- `com.linkedin.sdui.reactions.delete` — remove a reaction (unlike)
- `com.linkedin.sdui.update.deletePost` — delete a post
- `com.linkedin.sdui.comments.createComment` / `...deleteComment` — comment create/delete
- `com.linkedin.sdui.requests.profile.saveProfileIntroForm` — save profile intro form

## Request structure (protobuf-JSON)

SDUI bodies are JSON representations of protobuf messages. Skeleton of a `server-request` POST:

```json
{
  "requestId": "com.linkedin.sdui.<ACTION>",
  "serverRequest": {
    "requestId": "com.linkedin.sdui.<ACTION>",
    "requestedArguments": {
      "$type": "proto.sdui.actions.requests.RequestedArguments",
      "payload": { /* action-specific data */ },
      "requestedStateKeys": [],
      "requestMetadata": { "$type": "proto.sdui.common.RequestMetadata" }
    },
    "isApfcEnabled": false,
    "isStreaming": false,
    "rumPageKey": ""
  }
}
```

The `payload` holds the actual data. For state references, SDUI uses
`{"key": "...", "namespace": "MemoryNamespace"}` instead of literal values (client-state
bindings — this matters for profile edits, see `04-WRITE-OPERATIONS.md`).

## Required headers (SDUI — differs from Voyager!)

```
csrf-token:                    ajax:<JSESSIONID>
content-type:                  application/json
x-li-rsc-stream:               true
x-li-application-version:      0.2.xxxx           # SDUI app version (changes!)
x-li-page-instance:            urn:li:page:d_flagship3_detail_base;<trackingId>
x-li-page-instance-tracking-id:<base64 tracking id>
x-li-anchor-page-key:          d_flagship3_detail_base
x-li-pageforestid:             <trace id>
x-li-application-instance:     <base64 instance id>
x-li-track:                    {"clientVersion":"0.2.xxxx", ... "mpName":"web", ...}
```

> **Note:** SDUI `x-li-track.mpName` is `"web"` (Voyager uses `"voyager-web"`), and
> `clientVersion` is the SDUI app version (`0.2.xxxx`), NOT the Voyager version
> (`1.13.xxxxx`). These headers are set on page load and must be carried along.

## Challenge for pure `requests` usage

SDUI requests need **ephemeral, page-bound headers** (`x-li-page-instance`,
`x-li-pageforestid`, `x-li-application-instance`) that are generated when the relevant page
loads. For stable automation, two options:
1. Grab these headers once per page context from a real page load and carry them along.
2. Run the call in the page context via CDP `Runtime.evaluate(fetch(...))`.

In practice the most reliable way to perform an SDUI write is to drive the **real (visible)
client** and let it fire the request (see `04-WRITE-OPERATIONS.md`). Voyager is far more
requests-friendly — SDUI is the price for the newer UI areas.

---

## SDUI action catalog

### Verified write actions (captured live + tested)
| `sduiid` | Operation | Status |
|---|---|---|
| `com.linkedin.sdui.reactions.delete` | Unlike / remove reaction | ✅ verified |
| `com.linkedin.sdui.update.deletePost` | Delete post | ✅ verified |
| `com.linkedin.sdui.comments.createComment` | Create comment | ✅ verified |
| `com.linkedin.sdui.comments.deleteComment` | Delete comment | ✅ verified |
| `com.linkedin.sdui.requests.profile.saveProfileIntroForm` | Save profile intro | ✅ schema verified |
| `com.linkedin.sdui.action.sharing.closed-sharebox.server-action` | Post-create follow-up (returns post URN) | ✅ verified |

### Discovered actions (seen in live traffic)
**Profile (server-driven profile cards):**
- `com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity`
- `com.linkedin.sdui.generated.profile.dsl.impl.profileCardsActivity`
- `com.linkedin.sdui.requests.profile.fetchProfileDiscoveryDrawer`
- `com.linkedin.sdui.requests.profile.profilePolicyNotice`

**MyNetwork (contains mutations):**
- `com.linkedin.sdui.requests.mynetwork.addaClearUnseenInvitationsMutation` ← mutation
- `com.linkedin.sdui.requests.mynetwork.addaMarkNotificationsSeen` ← mutation
- `com.linkedin.sdui.requests.mynetwork.mojoTabsBadge`

**Feed / Jobs (pagers):**
- `com.linkedin.sdui.pagers.feed.mainFeed`
- `com.linkedin.sdui.pagers.jobseeker.jobsHomeFeedModuleList`

**Search (contains mutation):**
- `com.linkedin.sdui.search.requests.searchHomeRequestAction`
- `com.linkedin.sdui.search.requests.updateSearchHistoryRequest` ← mutation

**Analytics / system:**
- `com.linkedin.sdui.requests.creatoranalytics.caSlowMetrics`
- `WvmpAnalytics`, `WvmpEntityList` (who-viewed-my-profile)
- `com.linkedin.sdui.impl.homenav.requests.getThirdPartyTrackingPixels`
- `com.linkedin.sdui.realtimeDefaultHandler` (realtime heartbeat, streaming)

> **Naming pattern:** `com.linkedin.sdui.<area>.<requests|pagers|generated>.<name>`.
> Mutations often end in `Mutation` or are named `mark…`/`clear…`/`update…`/`delete`.
> Full machine-readable catalog: `data/endpoints_sdui.json`.