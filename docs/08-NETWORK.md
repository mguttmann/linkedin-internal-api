# 08 — Network / Connections / Follow (verified)

The networking surface. **Mixed worlds again:** company-follow is Voyager, everything else
(connect, invitation actions, person-follow) is SDUI. Captured live on the owner's own account:
connection request sent, an invitation accepted, company follow/unfollow toggled, person follow.
A few actions are only partially pinned down and marked as such below — **withdraw** (UI verified,
exact `sduiid` not yet captured) and **person unfollow** (inferred from the follow schema).

---

## Read

| What | Endpoint | Notes |
|---|---|---|
| Connections summary | `GET relationships/connectionsSummary` | ✅ 200 (MCP `get_connections_summary`) |
| Received invitations | `GET relationships/invitationViews` | 🔍 |
| Invitations summary | `GET relationships/invitationsSummary` | 🔍 |
| Network notifications | `GET relationships/myNetworkNotifications` | 🔍 |
| Discovery / PYMK | `GET voyagerRelationshipsDashDiscovery` | 🔍 |

---

## ✅ Send a connection request

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.mynetwork.addaAddConnection
Body: {
  "requestId": "com.linkedin.sdui.requests.mynetwork.addaAddConnection",
  "serverRequest": { ...
    "payload": {
      "inviteeUrn": { "memberId": "<numeric member id>" },
      "nonIterableProfileId": "<target profile id>",
      "renderMode": "IconAndText",
      "firstName": "<name>", "lastName": "<name>"
    }
  }
}
```
- **Verified:** request sent (appeared under "sent invitations"). ✅
- Clicking "Vernetzen" on My Network sends **without a note** via this SDUI `addaAddConnection`.
  The **with-a-note** variant is a different endpoint — Voyager
  `voyagerRelationshipsDashMemberRelationships?action=verifyQuotaAndCreateV2` with a `customMessage`
  field (captured, MCP `connect`; see `docs/25-NETWORK-PROFILE-ACTIONS.md`).

---

## ✅ Withdraw a sent connection request

Sent via the same mynetwork SDUI family from the "sent invitations" page
(`/mynetwork/invitation-manager/sent/`). The UI action is "Zurückziehen" + a confirm dialog.
Endpoint family: `com.linkedin.sdui.requests.mynetwork.adda…` (withdraw variant).
- **Status:** UI verified (request removed from sent list); exact `sduiid` capture ⏳ (the
  confirm dialog fired after the capture window — re-capture pending).

---

## ✅ Accept / Ignore a received invitation

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.mynetwork.addaInvitationAction
Body: {
  "requestId": "com.linkedin.sdui.requests.mynetwork.addaInvitationAction",
  "serverRequest": { ...
    "payload": {
      "inviteeActionType": "InviteeActionType_ACCEPT",   // or InviteeActionType_IGNORE
      "invitationType": "GenericInvitationType_ORGANIZATION",  // or ..._CONNECTION for people
      "invitationUrn": { "invitationId": "<id>" }
    }
  }
}
```
- **Verified:** invitation accepted (test contact → now connected). ✅
- **The same endpoint does Accept AND Ignore** — only `inviteeActionType` changes
  (`InviteeActionType_ACCEPT` / `InviteeActionType_IGNORE`).

---

## ✅ Follow / unfollow a COMPANY (Voyager)

```
POST /voyager/api/feed/dash/followingStates/<url-encoded followingStateUrn>
Body: { "patch": { "$set": { "following": true } } }     // false = unfollow
```
- `followingStateUrn` form: `urn:li:fsd_followingState:urn:li:fsd_company:<companyId>`.
- REST.li PARTIAL_UPDATE toggle.
- **Verified:** followed + unfollowed Microsoft. ✅

---

## ✅ Follow a PERSON (SDUI)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.mynetwork.addaUpdateFollowState
Body: {
  "requestId": "com.linkedin.sdui.requests.mynetwork.addaUpdateFollowState",
  "serverRequest": { ...
    "payload": {
      "followStateType": "FollowStateType_FOLLOW_ACTIVE",   // unfollow: FollowStateType_FOLLOW_INACTIVE
      "memberUrn": { "memberId": "<numeric member id>" }
    }
  }
}
```
- **Verified:** followed a person via this endpoint. ✅
- **Unfollow** uses the same endpoint with `followStateType: FollowStateType_FOLLOW_INACTIVE`
  (symmetric; the follow value was already inactive on re-test, so unfollow is inferred from
  the follow schema — ⏳ direct capture pending).
- **Note:** person-follow is a DIFFERENT mechanism than company-follow (SDUI member state vs.
  Voyager followingState). Pick the right one per entity type.

---

## Now captured (see docs/25-NETWORK-PROFILE-ACTIONS.md)
- ✅ **Remove** a connection — SDUI `mynetwork.RemoveConnectionVanityName` (MCP `remove_connection`)
- ✅ **Endorse** a skill — SDUI `requests.profile.endorseSkill` (MCP `endorse_skill`, browserless 200)
- ✅ Connect **with a note** — Voyager `MemberRelationships?verifyQuotaAndCreateV2` + `customMessage`
  (MCP `connect`)

## Still to capture (network)
- **Recommend** someone ⏳
- Follow / unfollow a **hashtag** ⏳
- Withdraw request — exact sduiid ⏳
- Person **unfollow** — direct capture ⏳

> **World summary:** connect / invitation-accept-ignore / person-follow = SDUI mynetwork
> family. Company-follow = Voyager `followingStates` patch. Same endpoint handles
> accept+ignore (actionType) and follow+unfollow (stateType).