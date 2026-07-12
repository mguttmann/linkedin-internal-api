# 09 — Profile editing (all sections)

The full profile edit surface. **Everything runs over SDUI** with a very consistent pattern
per section. Captured live and verified on the owner's own profile (test skill added +
deleted; profile left clean).

## Complete profile section inventory (from the "Abschnitt hinzufügen" dialog)

This is the FULL list of profile sections LinkedIn offers, read directly from the live
"Add profile section" dialog (three categories). Each maps to a `saveProfile<Section>Form` /
`deleteProfile<Section>Form` SDUI endpoint and a `/in/<vanity>/details/<slug>/` detail page.

**Legend:** ✅ captured = a real request was recorded during click-and-record (raw captures kept local, not shipped); 🔩 pattern-only =
endpoint documented from the universal pattern, no persisted artifact (reference).

**Core (Wichtige Angaben):**
| Section (DE) | Section (EN) | Detail slug | Form endpoint (pattern) | Status |
|---|---|---|---|---|
| Ausbildung | Education | `education` | `saveProfileEducationForm` | 🔩 pattern-only |
| Position | Experience | `experience` | `saveProfilePositionForm` | ✅ add captured; delete inferred — docs/11 |
| Serviceleistungen | Services provided | `services` | — | N/A (not offered on this account) |
| Berufliche Auszeit | Career break | `experience` | `saveProfilePositionForm` (break variant) | 🔩 pattern-only |
| Kenntnisse | Skills | `skills` | `saveProfileSkillForm` | 🔩 pattern-only |

**Recommended (Empfohlen):**
| Section (DE) | Section (EN) | Detail slug | Status |
|---|---|---|---|
| Auswahl | Featured | `featured` | 🔩 pattern-only (no persisted artifact) — docs/12 |
| Verbundene App | Connected app / media service | — | ⏳ |
| Bescheinigungen und Zertifikate | Licenses & certifications | `certifications` | ✅ add+edit+delete captured |
| Projekte | Projects | `projects` | ✅ add+edit+delete captured |
| Kurse | Courses | `courses` | ✅ add+edit+delete captured — docs/15 |
| Empfehlungen | Recommendations | `recommendations` | ⏳ |

**More (Weitere):**
| Section (DE) | Section (EN) | Detail slug | Status |
|---|---|---|---|
| Ehrenamtliche Erfahrung | Volunteer experience | `volunteering-experiences` | ✅ add+edit+delete captured — docs/13 |
| Publikationen | Publications | `publications` | ✅ add captured; delete inferred — docs/14 |
| Patente | Patents | `patents` | 🔩 pattern-only (no persisted artifact) — docs/17 |
| Auszeichnungen/Preise | Honors & awards | `honors` | ✅ add captured; delete not captured — docs/16 |
| Prüfungsergebnisse | Test scores | `test-scores` | ✅ delete captured; add inferred — docs/19 |
| Sprachen | Languages | `languages` | 🔩 pattern-only |
| Organisationen | Organizations | `organizations` | ✅ add+edit+delete captured — docs/18 |
| Gute Zwecke | Causes / volunteer causes | `volunteering-causes` | N/A (checkbox field, not a list type) |

**Top-level intro edits (pencil icons on the profile header):**
| Edit (DE) | What | Endpoint | Status |
|---|---|---|---|
| Profil bearbeiten | Name/headline/location/industry | `saveProfileIntroForm` | ✅ |
| Info bearbeiten | About / summary | `saveProfileAboutForm` | ✅ — docs/21 |
| Kontaktinformationen | Contact info (email/phone/web/social) | `saveProfileContactInfoForm` | ✅ captured — docs/20 |
| Hintergrundbild bearbeiten | Cover/background photo (upload) | media upload flow | ⏳ |
| (Profilfoto) | Profile photo (upload/frame/visibility) | media upload flow | ⏳ |
| Öffentliches Profil und URL | Custom vanity URL | `saveProfileVanityName` (expected) | ⏳ |
| Profilsprache bearbeiten | Profile language / secondary locale | profile-language save | ⏳ |
| Standardaktivität bearbeiten | Default activity | — | ⏳ |
| Offen für | Open-to-work / hiring / services badge | `voyagerJobsDashOpenToWorkPreferencesFormElementInput` | ✅ enable+disable — docs/22 |

> This inventory is the checklist for 100% profile coverage. Each ⏳ row is captured the same
> way: open the detail page or pencil, drive the form, capture `saveProfile<X>Form`.

## The universal profile-form pattern

Every profile section (skills, experience, education, about, …) uses the same SDUI shape:

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfile<Section>Form
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfile<Section>Form
```

Field values are carried as **client-state references**, NOT literals:
```json
"payload": {
  "<field>": { "key": "<stateKey-uuid>", "namespace": "MemoryNamespace" },
  ...
}
```
The real value lives in the SDUI client state (filled by the form UI). This is why profile
edits are hard to do with pure `requests` — you must set the state, or drive the real client
(coordinate/keyboard input in the open modal). **The endpoint + field names are documented
here; the values come from the form.**

Confirmed sections/screens (from `screenId` and `sduiid` observed):
`ProfileSkillAddForm`, `ProfileIntroForm`, plus `fetchSkillsCollection` (read-back).

---

## ✅ Intro (name / headline / location / industry)

```
sduiid=com.linkedin.sdui.requests.profile.saveProfileIntroForm
payload: { firstName, lastName, headline, initialHeadline, ... } (all state refs)
```
- Button: **"Profil bearbeiten"** → **"Speichern"**.
- **Verified** (endpoint + schema). See also 04-WRITE-OPERATIONS.

---

## ✅ Skills / "Kenntnisse" (the "things you're good at")

**Add a skill:**
```
sduiid=com.linkedin.sdui.requests.profile.saveProfileSkillForm
payload: {
  "skillName": { "key": "addSkillsTypeaheadSkillName<uuid>", "namespace": "MemoryNamespace" },
  "skillId":   { "key": "addSkillsTypeahead<...>",           "namespace": "MemoryNamespace" }
}
```
- UI: profile → Skills section → **"Kenntnis hinzufügen"** → type skill → pick from
  typeahead → **"Speichern"**.
- Read-back: `com.linkedin.sdui.requests.profile.fetchSkillsCollection`
  (`cardType: "Skills"` / `"SkillDetails"`).
- **Verified:** added "Kubernetes", it appeared, then removed it. ✅

**Delete a skill:**
```
sduiid=com.linkedin.sdui.requests.profile.deleteProfileSkillForm
payload: { "skillName": {state ref}, "skillId": {state ref} }
```
- UI: edit the skill → **"Kenntnis löschen"** → confirm.
- **Verified:** skill removed from profile. ✅

---

## ✅ Projects / "Projekte" (Recommended section) — VERIFIED add / edit / delete

Detail page: `/in/<vanity>/details/projects/`. Captured live end-to-end on the owner's own
profile (test project `APITEST Project <ts>` added → renamed → deleted; the owner's real
the owner's real project was never touched; profile verified clean afterwards).

**The add/edit form fields** (from the live "Neues Projekt hinzufügen" modal):
`Projektname*` (only required field), `Beschreibung` (≤2000 chars), a "currently working"
checkbox, start/end `Monat`+`Jahr` selects, `Verbunden mit` (associate a position), a skills
sub-list, contributors, media, and `Sprache auswählen`.

### Add a project
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileProjectForm
Content-Type: application/json
```
Body: `requestId` = the sduiid, `serverRequest.requestedArguments.payload` holds the field
**state-refs** (`title`, `description`, `associateId`, `startDate`, `endDate`, `skills`,
`currentlyWorking`, `contributors`, `legacyProjectUrl` → `{"key":"…ProjectForm<field>","namespace":"MemoryNamespace"}`)
plus **literals** `profileId` / `profileIdForm` / `vanityName`. **Add has NO `projectIdForm`.**

> **Important (differs from the intro-form note):** this request ALSO carries a top-level
> `states[]` array with the **real literal values**, e.g.
> `{"key":"…ProjectFormname","namespace":"MemoryNamespace","value":"APITEST Project …","originalProtoCase":"stringValue"}`.
> So the values ARE present in the request body (not only in hidden client-state) — the
> client serialises the referenced state alongside the ref. Empty dates are sent as
> `{"day":0,"month":0,"year":0}` (`dateValue`); the checkbox as `"Unchecked"` (`stringValue`).
> This means a browserless replay is more plausible here than for the intro form, provided
> the state-ref keys + `states[]` are reproduced. **Not yet proven via pure `requests`.**

- UI: profile → Projects section → **"Ein neues Projekt hinzufügen"** → fill `Projektname`
  → **"Speichern"**.
- **Verified:** test project appeared in the Projects section. ✅

### Edit a project
Same endpoint (`saveProfileProjectForm`). The ONLY structural difference vs. add is that the
payload additionally carries **`projectIdForm: "<projectId>"`** (real literal — the numeric
project id, e.g. `SECTION_ITEM_ID`). State-ref keys use a fresh `auto-binding-<uuid>` per form
open. The literal new values again ride in the top-level `states[]` array.
- UI: **"Projekt „<name>“ bearbeiten"** → change a field → **"Speichern"**.
- **Verified:** renamed the test project (name appended " EDITED"); change showed on profile. ✅

### Delete a project
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfileProjectForm
Content-Type: application/json
```
Body payload (all **real literals** — no typeahead / no state-ref for the target):
```json
{
  "profileId":  "OWNER_PROFILE_ID",
  "projectId":  "SECTION_ITEM_ID",
  "vanityName": "alex-rivera",
  "hasChanges":        { "key": "isActiveProfileFormHasChangesProfileEditForm", "namespace": "MemoryNamespace" },
  "progressIndicator": { "key": "isActiveProfileFormLoadingProfileEditForm",  "namespace": "MemoryNamespace" }
}
```
- UI: open the project's edit modal → **"Projekt löschen"** → confirm.
- **Verified:** test project removed; gone from the profile on read-back. ✅
- **Browserless-replayable: yes** — the delete carries the real `projectId` as a literal
  (same category as language delete). Only `profileId` + `projectId` + `vanityName` are needed.

### Read-back
After each write the client refetches the section via
`com.linkedin.sdui.requests.profile.fetchProjectsSections`
(`cardType: "Projects"` and `"ProjectsDetails"`, `vanityName`, `profileId`). Use this — or a
Voyager profile GET — to confirm the current project list and to grab a `projectId` for
edit/delete.

> **How the target project id is obtained:** the numeric `projectId` (e.g. `SECTION_ITEM_ID`) is
> read from the section on the detail page; the edit flow's `uploadProjectMedia` and the
> `saveProfileProjectForm` (edit) / `deleteProfileProjectForm` payloads all reference it.

---

## ✅ Licenses & Certifications / "Bescheinigungen und Zertifikate" (Recommended section) — VERIFIED add / edit / delete

Detail page: `/in/<vanity>/details/certifications/`. Captured live end-to-end on the owner's
own profile (test cert `APITEST Certification <ts>` added → credential-ID edited → deleted;
the owner's real certifications were never touched; profile
verified clean afterwards: `APITEST`/`APIEDIT` both absent, all real certs still present).

**The add/edit form fields** (from the live "Ein Zertifikat hinzufügen" modal):
`Name*` (required — the certification name), `Ausgestellt von*` (required — the issuing
organization, a **company typeahead**), issue-date `Monat`+`Jahr` selects, expiration-date
`Monat`+`Jahr` selects, `Zertifikats-ID` (credential id, free text), `URL des Nachweises`
(credential URL, free text), a skills sub-list (`Kenntnis hinzufügen`), and media
(`Mediendatei hinzufügen`). **No "Netzwerk informieren" toggle** on this form.

### Add a certification
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileCertificationForm
Content-Type: application/json
```
Body: `requestId` = the sduiid; `serverRequest.requestedArguments.payload` holds the field
**state-refs** (`name`, `issuingOrganization`, `issuingOrganizationId`, `issueDate`,
`expirationDate`, `credentialId`, `credentialUrl`, `skills` →
`{"key":"…ProfileCertificationForm<field>","namespace":"MemoryNamespace"}`) plus **literals**
`profileId`, `vanityName`, and `mediaItems: []`. **Add has NO `certificationId`.**

> **Same browserless-relevant property as Projects:** the request ALSO carries a top-level
> `states[]` array with the **real literal values**, e.g.
> `{"key":"…ProfileCertificationFormname","namespace":"MemoryNamespace","value":"APITEST Certification …","originalProtoCase":"stringValue"}`,
> `issuingOrganization → "Coursera"`, and `issuingOrganizationId → -1`. So the values are
> present in the request body (not only in hidden client-state). Empty dates are sent as
> `{"$type":"proto.sdui.common.Date","day":0,"month":0,"year":0}` (`dateValue`); empty
> credential id/url as `""`; skills as `[]`. **Not yet proven via pure `requests`.**

- **Issuer typeahead:** typing in `Ausgestellt von*` fires
  `sduiid=PROFILE_COMPANY_TYPEAHEAD_REQUEST` (payload: `keywordsField` state-ref +
  `resultsComponentRef`/`idField`/`textInputComponentRef`). Picking a suggestion is meant to
  bind a real company id into `issuingOrganizationId`; in our capture the value serialised as
  **`-1`** (free-text / unresolved-entity sentinel), which the server still accepted. A
  resolved company would carry its numeric org id here.
- The add flow also fires media-prep calls even with no media attached:
  `profileMediaCheckUpload`, `profileMediaRegister`,
  `com.linkedin.sdui.impl.profile.components.forms.uploadCertificationMedia`.
- UI: profile → Licenses & certifications → **"Ein Zertifikat hinzufügen"** → fill `Name` +
  `Ausgestellt von` → **"Speichern"**.
- `screenId`: `com.linkedin.sdui.flagshipnav.profile.ProfileCertificationDetailsAddForm`.
- **Verified:** test cert appeared in the section on read-back. ✅

### Edit a certification
Same endpoint (`saveProfileCertificationForm`). The ONLY structural difference vs. add is
that the payload additionally carries **`certificationId: "<id>"`** (real literal — the
numeric certification id, e.g. `SECTION_ITEM_ID`). State-ref keys use a fresh `auto-binding-<uuid>`
per form open; the literal new values again ride in the top-level `states[]` array (in our
capture `credentialId → "APIEDIT-<ts>"`).
- The edit flow's `uploadCertificationMedia` call also references the same id as
  `entityId: "SECTION_ITEM_ID"`.
- UI: **"Bescheinigung oder Zertifikat „<name>“ bearbeiten"** (an `<a>` link, not a `<button>`)
  → change a field → **"Speichern"**.
- `screenId`: `com.linkedin.sdui.flagshipnav.profile.ProfileCertificationDetailsEditForm`.
- **Verified:** set the test cert's `Zertifikats-ID` to `APIEDIT-<ts>`; change persisted and
  showed on read-back. ✅

### Delete a certification
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfileCertification
Content-Type: application/json
```
> **⚠️ Naming exception:** the delete endpoint is `deleteProfileCertification` — **NOT**
> `deleteProfileCertificationForm`. It breaks the otherwise-predictable
> `deleteProfile<Section>Form` pattern (contrast `deleteProfileProjectForm`,
> `deleteProfileSkillForm`). Captured live, not guessed.

The payload keeps the full form shape, but the target-identifying fields are **real literals**:
```json
{
  "profileId":        "OWNER_PROFILE_ID",
  "certificationId":  "SECTION_ITEM_ID",
  "vanityName":       "alex-rivera",
  "name":             { "key": "…ProfileCertificationFormname", "namespace": "MemoryNamespace" },
  "hasChanges":       { "key": "isActiveProfileFormHasChangesProfileEditForm", "namespace": "MemoryNamespace" },
  "progressIndicator":{ "key": "isActiveProfileFormLoadingProfileEditForm",   "namespace": "MemoryNamespace" }
}
```
- UI: open the cert's edit modal → **"Bescheinigung oder Zertifikat löschen"** → the modal
  asks to confirm (buttons **"Nein, danke"** / **"Löschen"**) → **"Löschen"**.
- **Verified:** test cert removed; gone from the profile on read-back (`APITEST` absent). ✅
- **Browserless-replayable: yes** — the delete carries the real `certificationId` as a literal
  (same category as language delete and project delete). Only `profileId` + `certificationId`
  + `vanityName` are needed to identify the target.

### Read-back
After each write the client refetches the section via
`com.linkedin.sdui.requests.profile.fetchCertificationsSections`
(`cardType: "CertificationTopLevel"` and `"CertificationDetailsLevel"`, `vanityName`,
`profileId`). Use this — or a Voyager profile GET — to confirm the current cert list and to
grab a `certificationId` for edit/delete.

> **How the target cert id is obtained:** the numeric `certificationId` (e.g. `SECTION_ITEM_ID`)
> is read from the section on the detail page; the edit flow's `uploadCertificationMedia`
> (`entityId`) and the `saveProfileCertificationForm` (edit) / `deleteProfileCertification`
> payloads all reference it.

---

## Capture status by section (see per-section docs)
**Full add+edit+delete captured (5):** Certifications, Projects, Courses (docs/15), Volunteer
(docs/13), Organizations (docs/18).
**Add captured, delete inferred (3):** Experience/position (docs/11), Publications (docs/14),
Honors (delete not captured — docs/16).
**Delete captured, add inferred (1):** Test scores (docs/19).
**Pattern-only, no persisted artifact:** Skills, Languages, Education, Patents (docs/17), Featured
(docs/12), Intro, About/Summary (docs/21). Contact-info save is captured (docs/20).
**16 sections total documented** — the universal `saveProfile<X>Form` / `deleteProfile<X>` pattern
is consistent across all of them, but only the sections above marked ✅ are backed by a recorded
request. The rest are documented from the pattern and should be confirmed by a fresh capture.

## Sections still to capture (same pattern expected)
Each is reachable via `/in/<vanity>/details/<section>/` + "Hinzufügen" / edit → save:
- **Experience** (position) add/edit — delete ✅, but the add/edit `saveProfilePositionForm`
  capture is still pending (requires a real company typeahead pick; skipped to avoid a network
  notification / junk position). See docs/11.
- **Career break** (`saveProfilePositionForm` break variant) ⏳
- **Connected app / media service** ⏳
- **Recommendations** (give/request) ⏳
- **Profile photo** upload/change ⏳
- **Background/cover photo** ⏳
- **Custom public URL** (button "Öffentliches Profil und URL bearbeiten") ⏳
- **Profile language** (button "Profilsprache bearbeiten") ⏳

> **Detail pages** to drive each section:
> `/in/<vanity>/details/experience/`, `/education/`, `/certifications/`, `/projects/`,
> `/volunteering-experiences/`, `/languages/`, `/courses/`, `/honors/`, `/publications/`,
> `/patents/`, `/featured/`, `/skills/`.

> **Automation note:** the endpoint names are 100% predictable
> (`saveProfile<Section>Form` / `deleteProfile<Section>Form`). The hard part is the
> client-state field values — for real edits, drive the modal; for read, use the
> `fetchXCollection` / Voyager profile GETs.