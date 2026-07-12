# 18 — Organizations "Organisationen" (add + edit + delete all verified live)

The **Organizations** profile section (`/in/<vanity>/details/organizations/`). All three write
operations were captured end-to-end via click-and-record on Alex's live profile and
**verified by browser render**: ADD persisted, EDIT persisted (name changed to `…EDITED…`),
DELETE removed it, and the final render carries **no `APITEST` marker**. Profile confirmed
clean ("Noch keine Informationen verfügbar").

Add/Edit share the standard `saveProfileOrganizationForm` endpoint (discriminated by
`isEdit` + `organizationId`); the **delete deviates** (`deleteProfileOrganization`, no `Form`
suffix) — same quirk as Honor/Course/Certification/Publication/Patent.

> **One required field:** `Name der Organisation*` (payload state `title`). Per budget
> discipline only this field was filled; the save persisted reliably with just the name.

---

## ✅ Add an organization — `saveProfileOrganizationForm` (standard naming, `isEdit:false`)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileOrganizationForm
```
- **Standard `saveProfile<X>Form` naming** — no deviation on the add.
- Full-page form (`screenId: com.linkedin.sdui.flagshipnav.profile.ProfileOrganizationDetailsAddForm`,
  URL `/details/organizations/edit/forms/new/`). Opened by the **"Organisationen hinzufügen"** button.
- **Discriminator:** payload `isEdit: false`, **no** `organizationId` key → this is a create.
- **Form fields** (from the live modal):
  - `Name der Organisation*` (payload state `title`) — **required**.
  - `Aktuelle Position` (payload state `position`) — free text.
  - `Beschreibung` (payload state `description`) — textarea.
  - `associatedWith` (typeahead linking to a position/education — payload `associatedId`).
  - `ongoing` (boolean), `startDate` / `endDate` (`proto.sdui.common.Date`).
- No "Netzwerk informieren"/share toggle exists for an empty section.
- **Payload = state-refs; body-level `states[]` = real literal values** (the browserless-relevant
  part). The `payload` object carries only refs like
  `{"key":"auto-binding-<uuid>ProfileOrganizationFormtitle","namespace":"MemoryNamespace"}`;
  the top-level `states[]` array resolves each ref to its real value:

```
payload (identifying literals):
{
  "name":         {"key":"auto-binding-<uuid>ProfileOrganizationFormtitle","namespace":"MemoryNamespace"},
  "position":     {"key":"...ProfileOrganizationFormposition","namespace":"MemoryNamespace"},
  "associatedId": {"key":"...ProfileOrganizationFormassociatedWith","namespace":"MemoryNamespace"},
  "description":  {"key":"...ProfileOrganizationFormdescription","namespace":"MemoryNamespace"},
  "isOngoing":    {"key":"...ProfileOrganizationFormongoing","namespace":"MemoryNamespace"},
  "startDate":    {"key":"...ProfileOrganizationFormstartDate","namespace":"MemoryNamespace"},
  "endDate":      {"key":"...ProfileOrganizationFormendDate","namespace":"MemoryNamespace"},
  "isEdit": false,                                             ← create discriminator
  "profileId": "OWNER_PROFILE_ID",
  "vanityName": "alex-rivera",
  "hasChanges":        {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "progressIndicator": {"key":"isActiveProfileFormLoadingProfileEditForm","namespace":"MemoryNamespace"}
}

states[] (real values — browserless-relevant), each {key, namespace, value, originalProtoCase}:
  ...Formtitle          → "APITEST Org <ts>"                         (stringValue)   ← the one required value
  ...Formposition       → ""                                        (stringValue)
  ...FormassociatedWith → ""                                        (stringValue)
  ...Formdescription    → ""                                        (stringValue)
  ...Formongoing        → false                                     (booleanValue)
  ...FormstartDate      → {"$type":"proto.sdui.common.Date","day":0,"month":0,"year":0} (dateValue)
  ...FormendDate        → {"$type":"proto.sdui.common.Date","day":0,"month":0,"year":0} (dateValue)
```
- **Verified:** after save, `APITEST Org <ts>` rendered live on the organizations detail page. ✅

---

## ✅ Edit an organization — `saveProfileOrganizationForm` (same endpoint, `isEdit:true` + `organizationId`)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileOrganizationForm
```
- **Same endpoint as add**, discriminated by the payload:
  - `isEdit: true`
  - `organizationId: "SECTION_ITEM_ID"` ← real numeric id, plain literal (the entry being edited)
  - `profileId: "OWNER_PROFILE_ID"`, `vanityName: "alex-rivera"`
- `screenId: com.linkedin.sdui.flagshipnav.profile.ProfileOrganizationDetailsEditForm`
  (edit URL `/details/organizations/edit/forms/<organizationId>/`). Opened by the entry's
  **"… bearbeiten"** (aria-label) pencil.
- Same state-ref payload + body-level `states[]` real-values structure as add. Captured `states[]`:
  - `title` → `"APITEST Org EDITED <ts>"` (changed value) ✅
  - other fields unchanged (empty strings / `false` / zero dates).
- **Verified:** after save, the profile rendered the new `EDITED` name (old name gone). ✅

---

## ✅ Delete an organization — ⚠️ deviating name `deleteProfileOrganization` (no `Form`)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfileOrganization
Body (serverRequest.requestedArguments.payload — the identifying literals):
{
  "isEdit": true,
  "organizationId": "SECTION_ITEM_ID",                 ← real id, plain literal
  "profileId": "OWNER_PROFILE_ID",
  "vanityName": "alex-rivera",
  "name":         {"key":"auto-binding-<uuid>ProfileOrganizationFormtitle","namespace":"MemoryNamespace"},
  "position":     {"key":"...ProfileOrganizationFormposition","namespace":"MemoryNamespace"},
  "description":  {"key":"...ProfileOrganizationFormdescription","namespace":"MemoryNamespace"},
  ... (all other form fields carried as state-refs, same shape as save) ...
  "hasChanges":        {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "progressIndicator": {"key":"isActiveProfileFormLoadingProfileEditForm","namespace":"MemoryNamespace"}
}
```
- **Naming deviation (captured, not guessed):** `deleteProfileOrganization` — **no `Form`
  suffix** (same quirk as `deleteProfileHonor`, `deleteProfilePatent`, `deleteProfileCourse`,
  `deleteProfileCertification`, `deleteProfilePublication`).
- Carries the **real `organizationId` as a plain literal** in the payload (easy for replay — the
  id is not buried in a state-key), alongside `profileId` and `vanityName`. The `organizationId`
  is also visible in the edit-form URL (`/details/organizations/edit/forms/<organizationId>/`).
- The delete payload re-sends the full form shape (all fields as state-refs + body-level
  `states[]`), but the operative identifier is `organizationId`.
- **UI/capture note:** the in-modal delete button is section-specific: **"Organisation löschen"**
  (bottom of the edit modal, next to "Speichern"). `click_label("Organisation löschen", contains=False)`
  matched directly. The confirm dialog's button is the plain **"Löschen"**
  (`click_label("Löschen", index=-1, contains=False)`).
- **Verified + cleaned up:** every `APITEST Org` test entry was removed; the organizations
  detail page re-rendered with **no `APITEST` marker** ("Noch keine Informationen verfügbar"). ✅

---

## Read-back — `fetchOrganizationsSections` + details pager
- Section fetch: `com.linkedin.sdui.requests.profile.fetchOrganizationsSections`
  with `cardType: "Organizations"` (top-level card) and `cardType: "OrganizationsDetails"`
  (detail list), keyed by `collection-content-profile_Organizations_alex-rivera`.
- Detail pager: `com.linkedin.sdui.pagers.profile.details.organizations`
  payload `{vanityName, start:0, count:10, profileId}` (`count:10`).
- Component sections rendered via `com.linkedin.sdui.generated.profile.dsl.impl.*` component
  actions (`screenId: …ProfileOrganizationDetailsAddForm` / `…EditForm`).
- **Verify cleanup via browser render, not Voyager read** (playbook rule 7): navigate
  `/in/<vanity>/details/organizations/?nc=<ts>` and check `document.body.innerText` for the marker.

## Browserless-replay status
| Op | Endpoint | Body carries | Browserless |
|---|---|---|---|
| Add | `saveProfileOrganizationForm` (`isEdit:false`) | state-refs + body `states[]` real values (`title` required; `position`/`description`/`ongoing`/dates optional) | 🔬 same family as `saveProfileLanguageForm` (create proven browserless); needs full `states[]` reconstruction |
| Edit | `saveProfileOrganizationForm` (`isEdit:true` + real `organizationId`) | state-refs + body `states[]` real values | 🔬 id in hand; same family/caveats as add |
| Delete | `deleteProfileOrganization` (⚠️ no `Form`) | **real `organizationId` literal** + `profileId`/`vanityName` | 🔬 id in hand, but SDUI profile delete via pure requests is a no-op today (see docs/BROWSERLESS-REPLAY.md); UI delete reliable |

## Capture provenance
- Live capture on `alex-rivera` via `tools/capture_session.py` (CDP click-and-record).
- Budget discipline followed: filled only the single required field (`Name der Organisation*`);
  delete-first safety applied (ADD → DELETE → verify before attempting EDIT).
- A mid-run script bug (`time.sleep=2` typo) crashed the edit cycle *after* the edit save but
  *before* its delete, leaving live test entries; a dedicated cleanup loop (`_org_cleanup.py`)
  deleted all leftover `APITEST` entries and the final independent render confirmed the section
  is clean. **No test entry left live.**

## Still to capture (organizations)
- `associatedWith` typeahead (`associatedId`) capture linking an org to a position/education ⏳
- Full `states[]` body with a real `startDate`/`endDate` and `ongoing:true` ⏳
