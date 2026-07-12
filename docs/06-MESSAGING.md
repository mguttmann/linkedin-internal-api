# 06 — Messaging / DMs (verified)

Complete direct-messaging surface, captured live via click-and-record and verified on the
owner's own account (test messages sent to the top conversation and immediately recalled).
**All messaging runs over Voyager REST.li** (not SDUI).

Base resource: `/voyager/api/voyagerMessagingDash…`. The two central URNs:
- **conversationUrn**: `urn:li:msg_conversation:(urn:li:fsd_profile:<ME>,<threadId>)`
- **messageUrn**: `urn:li:msg_message:(urn:li:fsd_profile:<ME>,<msgId>)`
- **mailboxUrn**: `urn:li:fsd_profile:<ME>` (your own profile URN)

---

## Read

| What | Endpoint | Notes |
|---|---|---|
| List conversations | `GET graphql messengerConversations` | 🔍 inbox list |
| Read a thread's messages | `GET graphql messengerMessages` | 🔍 by conversation |
| Mailbox unread counts | `GET messengerMailboxCounts` | 🔍 |

---

## ✅ Send a message

```
POST /voyager/api/voyagerMessagingDashMessengerMessages?action=createMessage
Content-Type: application/json
Body:
{
  "message": {
    "body": { "attributes": [], "text": "<your text>" },
    "renderContentUnions": [],
    "conversationUrn": "urn:li:msg_conversation:(urn:li:fsd_profile:<ME>,<threadId>)",
    "originToken": "<client-generated uuid>"    // idempotency key
  },
  "mailboxUrn": "urn:li:fsd_profile:<ME>",
  "trackingId": "<tracking>"
}
```
- `originToken` is a client UUID — reuse-safe idempotency key (prevents double-send).
- `trackingId` = **16 RAW bytes** (latin-1 string, NOT base64) + `dedupeByClientGeneratedToken:false`
  are REQUIRED — without them the call returns **HTTP 400**. (Found by click-and-record.)
- `body.attributes` carries **@mentions** and formatting (see `24-POST-ADVANCED.md` for the
  `attributesV2.profileMention` shape).
- **Verified:** ✅ browserless — sent + recalled live (send 200, recall 204). List conversations
  via the **`voyagerMessagingGraphQL/graphql`** path (its own graphql endpoint, NOT generic `/graphql`).

**Side calls the client also fires (optional, not required for the send to work):**
- `POST voyagerMessagingDashMessengerConversations?action=typing` — typing indicator,
  body `{"conversationUrn":"…"}`. Fire-and-forget; skip it for pure automation.
- `POST voyagerMessagingDashMessengerMessageDeliveryAcknowledgements?action=sendDeliveryAck`
  — read/delivery ack; not needed when sending.

---

## 🔩 Edit a sent message (endpoint observed; not in the canonical inventory)

```
POST /voyager/api/voyagerMessagingDashMessengerMessages/<url-encoded messageUrn>
Body: { "patch": { "$set": { "body": { "text": "<new text>", "attributes": [] } } } }
```
- REST.li PARTIAL_UPDATE (POST with a `patch.$set`). URN goes in the path (URL-encoded).
- **Status:** endpoint shape observed during a manual session; **not reproduced browserless and
  not present in the canonical endpoint inventory** (ENDPOINTS.md / STATUS-MATRIX / data JSON).
  Treat as inferred until re-captured.

---

## ✅ Delete (recall) a message

```
POST /voyager/api/voyagerMessagingDashMessengerMessages?action=recall
Body: { "messageUrn": "urn:li:msg_message:(urn:li:fsd_profile:<ME>,<msgId>)" }
```
- LinkedIn calls delete **"recall"**. Removes it for everyone.
- **Verified:** test message disappeared from the thread. ✅

---

## 🔩 React to a message with an emoji (implemented, not live-tested)

```
POST /voyager/api/voyagerMessagingDashMessengerMessages?action=reactWithEmoji
Body: { "messageUrn": "…", "emoji": "👏" }
```
- **Status:** implemented (schema known, `reactWithEmoji`), **not yet live-tested** — consistent
  with STATUS-MATRIX. The emoji-appeared observation was from an earlier manual session, not a
  reproduced browserless replay.
- **Remove reaction:** same endpoint toggles (re-send the same emoji removes it) —
  action name observed as `reactWithEmoji`; toggling off fires the same call.

---

## ✅ Mark conversation as read

```
POST /voyager/api/voyagerMessagingDashMessengerConversations?ids=List(<url-encoded convUrn>)
Body: { "entities": { "<convUrn>": { "patch": { "$set": { "read": true } } } } }
```
- REST.li batch PARTIAL_UPDATE. Set `"read": false` to mark unread.
- **Verified:** fired automatically when opening/reacting in a thread. ✅ (schema confirmed)

---

## Still to capture (messaging)
- **Reply** to a specific message (quote) — button "Diese Nachricht beantworten" exists;
  likely `createMessage` with a `renderContentUnions`/reply-reference. ⏳
- **Forward** a message ("Weiterleiten") ⏳
- **Start a NEW conversation** (compose to a new recipient) ⏳
- **Attachment / image / GIF** send ⏳
- **Archive / delete a whole conversation** ⏳
- **InMail** (premium) send ⏳

> **Automation note:** to send purely via `requests`, you only need `createMessage` with a
> valid `conversationUrn` + `originToken`. The typing and delivery-ack calls are cosmetic.
> Get the `conversationUrn` from `messengerConversations` (read).