# 13 — Volunteer experience / "Ehrenamt" (add / edit / delete) — VERIFIED

The **Volunteer Experience** profile section (`/in/<vanity>/details/volunteering-experiences/`),
captured live end-to-end via click-and-record on the owner's own profile and verified with
read-back proof. A test entry `APITEST Volunteer <ts>` was **added → edited → deleted**; the
section started empty and was left empty (verified: `Noch keine Informationen verfügbar`).
Nothing pre-existing was touched (the section had no real entries to begin with).

> **Status: ✅ add / edit / delete all verified live.** Capture artifacts:
> `<local capture, not shipped>`, `volunteer_edit.json`, `volunteer_delete.json`
> (full request bodies + decoded response bodies).

---

## ⚠️ Two naming deviations from the "universal profile-form" pattern

Unlike Projects/Certifications/Skills (which live under
`com.linkedin.sdui.requests.profile.saveProfile<Section>Form`), the Volunteer endpoints break
the naming convention in **two** ways — captured live, not guessed:

1. **Namespace is `…impl.profile.`, not `…requests.profile.`**
   (`com.linkedin.sdui.impl.profile.saveVolunteerExperienceForm`).
2. **No `Profile` infix in the name** — it is `saveVolunteerExperienceForm`, *not*
   `saveProfileVolunteerExperienceForm`. The delete is `deleteVolunteerExperience` — no
   `Form` suffix and no `Profile` infix (the same "delete drops the suffix" quirk seen with
   `deleteProfileCertification`, but here the whole namespace/prefix differs too).

| Op | sduiid |
|---|---|
| Add / Edit | `com.linkedin.sdui.impl.profile.saveVolunteerExperienceForm` |
| Delete | `com.linkedin.sdui.impl.profile.deleteVolunteerExperience` |
| Read-back | `com.linkedin.sdui.requests.profile.fetchVolunteerExperienceSections` |

So do **not** assume `saveProfileVolunteerExperienceForm` — that endpoint does not exist.

---

## The form (from the live "Ehrenamtliche Erfahrung hinzufügen" modal)

Fields:
- **Organisation*** — company **typeahead** (placeholder `Beispiel: a resolved company`). Picking a
  suggestion binds a real numeric org id.
- **Rolle*** — free text (placeholder `Beispiel: Betriebsrat`).
- **Guter Zweck** — cause `<select>` (enum `VolunteerCauseType_*`: `ANIMAL_WELFARE`,
  `ARTS_AND_CULTURE`, `CHILDREN`, `EDUCATION`, `ENVIRONMENT`, `HEALTH`, `HUMAN_RIGHTS`,
  `POVERTY_ALLEVIATION`, `SCIENCE_AND_TECHNOLOGY`, `SOCIAL_SERVICES`, … — the value serialises
  as e.g. `VolunteerCauseType_EDUCATION`).
- a **"currently volunteering"** checkbox.
- start / end **Monat** + **Jahr** selects.
- **Beschreibung** — textarea (≤ 2 000 chars).
- media (`Mediendatei hinzufügen`).

There is **no "Netzwerk informieren" / share toggle** on this form (nothing is broadcast to
the network on save), so it is safe to test.

---

## ✅ Add a volunteer experience

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.impl.profile.saveVolunteerExperienceForm
Content-Type: application/json
```
`serverRequest.requestedArguments.payload` holds the field **state-refs**
(`organizationId`, `organizationName`, `role`, `cause`, `startDate`, `endDate`, `description`
→ `{"key":"auto-binding-<uuid>ProfileVolunteerExperienceForm<field>","namespace":"MemoryNamespace"}`)
plus **literals** `profileId`, `vanityName`, and `mediaItems: []`. **Add has NO `volunteeringId`.**

> **Browserless-relevant property (same as Projects/Certs):** the request ALSO carries a
> top-level `states[]` array (mirrored at `serverRequest.states` and
> `serverRequest.requestedArguments.states`) with the **real literal values**:
> ```json
> [
>   {"key":"…FormvolunterOrganizationId","namespace":"MemoryNamespace","value":COMPANY_ID,"originalProtoCase":"intValue"},
>   {"key":"…FormvolunteerExperienceFormOrganization","namespace":"MemoryNamespace","value":"a resolved company","originalProtoCase":"stringValue"},
>   {"key":"…FormvolunteerExperienceFormRole","namespace":"MemoryNamespace","value":"APITEST Volunteer …","originalProtoCase":"stringValue"},
>   {"key":"…FormvolunteerExperienceFormCause","namespace":"MemoryNamespace","value":"VolunteerCauseType_EDUCATION","originalProtoCase":"stringValue"},
>   {"key":"ProfileVolunteerExperienceFormstartDate","value":{"day":0,"month":0,"year":0},"originalProtoCase":"dateValue"},
>   {"key":"ProfileVolunteerExperienceFormendDate","value":{"day":0,"month":0,"year":0},"originalProtoCase":"dateValue"},
>   {"key":"…FormvolunteerExperienceDescriptionBinding","value":"","originalProtoCase":"stringValue"}
> ]
> ```
> Note the **`volunterOrganizationId`** key (LinkedIn's own typo, "volunter") carries the
> resolved company id (`COMPANY_ID` = *a resolved company*) as an `intValue`. Empty dates are
> `{"day":0,"month":0,"year":0}` (`dateValue`); empty description is `""`. So the real values
> are present in the request body, not only in hidden client-state. **Not yet proven via pure
> `requests`** (would need the state-ref keys + `states[]` reproduced).

- **Org typeahead:** typing in `Organisation` returns real suggestions
  (`a resolved company`, `Bayerisches a resolved company (BRK)`, `Schweizerisches a resolved company`, …);
  picking one binds its numeric org id into `volunterOrganizationId`.
- The add flow also fires media-prep calls even with **no media attached**:
  `com.linkedin.sdui.requests.profile.profileMediaCheckUpload`,
  `com.linkedin.sdui.requests.profile.profileMediaRegister`,
  `com.linkedin.sdui.impl.profile.components.forms.uploadVolunteerMedia`.
- `screenId`: `com.linkedin.sdui.flagshipnav.profile.ProfileVolunteerExperienceDetailsAddForm`.
- UI: profile → Ehrenamt → **"Ehrenamt hinzufügen"** → fill `Organisation` (pick suggestion) +
  `Rolle` → **"Speichern"**.
- **Verified:** test entry `APITEST Volunteer 1783789311 · a resolved company · Bildung`
  appeared in the section on read-back. ✅

---

## ✅ Edit a volunteer experience

Same endpoint (`saveVolunteerExperienceForm`). The ONLY structural difference vs. add is that
the payload additionally carries **`volunteeringId: "<id>"`** (real literal — the numeric
volunteer-experience id, e.g. `SECTION_ITEM_ID`). State-ref keys use a fresh `auto-binding-<uuid>`
per form open; the literal new values again ride in the top-level `states[]` array.
- The edit flow's `uploadVolunteerMedia` call also references the same id as
  `entityId: "SECTION_ITEM_ID"`.
- `screenId`: `com.linkedin.sdui.flagshipnav.profile.ProfileVolunteerExperienceDetailsEditForm`.
- UI: **"Ehrenamt „<role>" bearbeiten"** (an `<a>` pencil link) → change a field → **"Speichern"**.
- **Verified:** added a `Beschreibung` (`APIEDIT edited 1783789467`) to the test entry; the
  change persisted and showed on read-back. ✅

---

## ✅ Delete a volunteer experience

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.impl.profile.deleteVolunteerExperience
Content-Type: application/json
```
The payload keeps the full form shape, but the target-identifying fields are **real literals**
(the descriptive fields stay as state-refs and are ignored for the delete):
```json
{
  "profileId":      "OWNER_PROFILE_ID",
  "volunteeringId": "SECTION_ITEM_ID",
  "vanityName":     "alex-rivera",
  "organizationId":     { "key": "auto-binding-…ProfileVolunteerExperienceFormvolunterOrganizationId", "namespace": "MemoryNamespace" },
  "role":               { "key": "auto-binding-…FormvolunteerExperienceFormRole",  "namespace": "MemoryNamespace" },
  "hasChanges":         { "key": "isActiveProfileFormHasChangesProfileEditForm",    "namespace": "MemoryNamespace" },
  "progressIndicator":  { "key": "isActiveProfileFormLoadingProfileEditForm",       "namespace": "MemoryNamespace" }
}
```
- UI: open the entry's edit modal → **"Ehrenamtliche Tätigkeit löschen"** → the modal asks to
  confirm (buttons **"Nein, danke"** / **"Löschen"**) → **"Löschen"**.
- **Verified:** test entry removed; section returned to the empty state
  (`Noch keine Informationen verfügbar`, no edit links) on read-back. ✅
- **Browserless-replayable: yes** — the delete carries the real `volunteeringId` as a literal
  (same category as language / project / certification delete). Only `profileId` +
  `volunteeringId` + `vanityName` are needed to identify the target.

---

## Read-back

After each write the client refetches the section via
`com.linkedin.sdui.requests.profile.fetchVolunteerExperienceSections`
(`cardType: "VolunteerExperienceTopLevel"` and `"VolunteerExperienceDetails"`, `vanityName`,
`profileId`), followed by the `volunteer_experience` pager
(`com.linkedin.sdui.pagers.profile.details.volunteer_experience`, `start:0, count:10`). Use
this — or a Voyager profile GET — to confirm the current list and to grab a `volunteeringId`
for edit/delete.

> **How the target id is obtained:** the numeric `volunteeringId` (e.g. `SECTION_ITEM_ID`) is read
> from the section on the detail page; the edit flow's `uploadVolunteerMedia` (`entityId`) and
> the `saveVolunteerExperienceForm` (edit) / `deleteVolunteerExperience` payloads all reference
> it.

---

## Cleanup proof

| Step | Marker | Result |
|---|---|---|
| Start state | — | section empty (`Noch keine Informationen verfügbar`) |
| After add | `APITEST Volunteer 1783789311` | entry visible on profile ✅ |
| After edit | `APIEDIT edited 1783789467` (Beschreibung) | change visible on profile ✅ |
| After delete | — | section empty again, no edit links, `APITEST` absent ✅ |

The profile was returned to its exact original (empty) state. No real data existed in this
section and none was touched.
