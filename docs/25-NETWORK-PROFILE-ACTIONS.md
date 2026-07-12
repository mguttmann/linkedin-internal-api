# 25 — Network & profile actions (endorse, connect, disconnect, contact-info, comment reactions)

Captured live via click-and-record on 2026-07-12 (Alex drove the clicks). Mix of SDUI
(`rsc-action`) and Voyager (`/voyager/api`) writes. Payload literals are shown; SDUI form values
that come as `MemoryNamespace` refs are noted.

---

## ✅ Endorse a skill

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.endorseSkill
payload: { "vanityName": "<their-vanity>", "profileId": "<their fsd_profile id>", "skillId": "48" }
```
- All real literals → browserless-replayable. `skillId` is the position/id of the skill on their profile.

---

## ✅ Connect with a note

```
POST /voyager/api/voyagerRelationshipsDashMemberRelationships?action=verifyQuotaAndCreateV2
{ "invitee": { "inviteeUnion": { "memberProfile": "urn:li:fsd_profile:<their urn>" } },
  "customMessage": "<the note text>" }
```
- Pure Voyager write, real literals → browserless. Omit `customMessage` for a note-less invite.
- **People-facing** — gate behind confirm in any tool; withdrawing is a separate invite-action.

---

## ✅ Remove a connection

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.mynetwork.RemoveConnectionVanityName
payload: { "disconnectVanityName": "<their-vanity>", "disconnectFirstName": "<name>", ... }
```
- Keyed by vanity name (+ display name for the confirm UI). Destructive → confirm.

---

## ✅ React to a comment (like a comment)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.reactions.create
payload: { "threadUrn": { "threadUrnCommentThreadUrn": { "commentUrn": { "commentUrn": {...} } } } }
```
- Same `reactions.create` action as post-likes, but the thread is a **CommentThreadUrn** (not an
  activity). Removal is `reactions.delete` (SDUI, browser-only like post-unlike — currentActor).

---

## ✅ Create a comment

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.comments.createComment
payload: { "optimisticKey": "...", "collection": { "updateKey": {...} }, commentary with attributesV2 }
```
- Same commentary/`attributesV2` shape as posts → supports **@mention in comments** (see docs/24).

---

## ✅ Contact info — save

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileContactInfoForm
payload (all MemoryNamespace form refs):
  profileUrl, email, phoneNumber, phoneType, address, birthdayDay, birthdayMonth, (twitter, im, …)
```
- Screen: `com.linkedin.sdui.flagshipnav.profile.ProfileContactInfoAddForm`.
- Values are **client-state refs** (`{key, namespace:"MemoryNamespace"}`), not literals — same as
  the other profile forms. To replay browserless you must seed the form state first (see the
  `states[]` note in BROWSERLESS-REPLAY.md); the browser path is reliable today.
- **Verified safe:** tested with a throwaway phone number, then cleared — Alex's real contact
  info (email, github/blog URLs, birthday) never touched; phone confirmed empty after.

---

## Status

| Action | Endpoint | Browserless? |
|---|---|---|
| Endorse skill | SDUI `endorseSkill` | ✅ literals |
| Connect + note | Voyager `MemberRelationships?verifyQuotaAndCreateV2` | ✅ literals |
| Remove connection | SDUI `RemoveConnectionVanityName` | ✅ literals |
| React to comment | SDUI `reactions.create` (commentThreadUrn) | 🟡 like post-like (currentActor for create ok, delete browser) |
| Create comment | SDUI `comments.createComment` | 🟡 currentActor |
| Contact-info save | SDUI `saveProfileContactInfoForm` | 🟡 MemoryNamespace form (browser reliable) |
