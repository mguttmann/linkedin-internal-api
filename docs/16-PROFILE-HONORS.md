# 16 — Honors & Awards "Auszeichnungen/Preise" (verified add + delete mapped)

The **Honors & Awards** profile section (`/in/<vanity>/details/honors/`). The **add was
captured live** (`saveProfileHonorForm`); the add form and endpoint were mapped from that run.
Add follows the standard `saveProfile<X>Form` pattern; the **delete deviates** (no `Form`
suffix), like Course/Certification — but see the ⚠️ note: the delete request was **not**
actually recorded.

> **Capture artifacts:** `<local capture, not shipped>` holds the real add mutation
> (`saveProfileHonorForm`). `<local capture, not shipped>` exists but its `mutations`
> array is **empty** (`[]`) — the delete cleanup ran but **no delete request was captured**.
> So the delete endpoint/payload below is **inferred from the sibling sections**, not verified.

---

## ✅ Add an honor — `saveProfileHonorForm` (standard naming)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileHonorForm
```
- **Standard `saveProfile<X>Form` naming** — no deviation on the add. **Captured live** in
  `honor_add.json`.
- Full-page form (`screenId: ProfileHonorDetailsAddForm`, URL `/details/honors/edit/forms/new/`).
- **Form fields** (from the live modal):
  - `Überschrift*` (honorTitle) — required.
  - `Verbunden mit` (associateId) — a **typeahead** linking the honor to a position/education.
  - `Verliehen durch` (honorIssuer) — issuing organization (free text).
  - `Monat` / `Jahr` (issueDate).
  - `Beschreibung` (honorDescription).
- No "Netzwerk informieren"/share toggle exists for an empty section.
- Like every profile form: `payload` fields are **state-refs** + a top-level **`states[]`**
  array carrying the **real literal values** (browserless-relevant part).
- **Edit** discriminator (expected, by analogy to course/project): a real `honorIdForm`
  literal added to the payload; absent → add, present → edit. 🔬 (edit not separately captured —
  the agent hit the iteration cap right after the add).
- **Verified:** after save, `APITEST Honor <ts>` was captured live. ✅

---

## Delete an honor — ⏳ NOT captured (inferred, deviating name)

> **⚠️ Not actually captured.** `honor_delete.json` recorded **zero mutations** — the delete
> request was never recorded. The endpoint name and `honorId` below are **inferred** from the
> sibling delete quirk (`deleteProfileCourse` etc.), NOT observed. Do not treat as verified.

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfileHonor   (INFERRED)
Body (serverRequest.requestedArguments.payload — expected shape):
{
  "honorId":"<id>",                              ← expected: real id, plain literal
  "profileId":"OWNER_PROFILE_ID",
  "vanityName":"alex-rivera",
  "hasChanges":       {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "progressIndicator":{"key":"isActiveProfileFormLoadingProfileEditForm","namespace":"MemoryNamespace"}
}
```
- **Expected naming deviation:** `deleteProfileHonor` — **no `Form` suffix** (same quirk as
  `deleteProfileCourse`, `deleteProfileCertification`). Unconfirmed.
- **UI note:** in this section the in-modal delete button is plain **"Löschen"** (at the bottom
  of the edit modal).

---

## Read-back — `fetchHonorsSections`
`cardType: HonorsTopLevel` / `HonorsDetails`; detail pager
`com.linkedin.sdui.pagers.profile.details.honors` (`start`/`count`, `count:10`).

## Browserless-replay status
| Op | Endpoint | Body carries | Browserless |
|---|---|---|---|
| Add | `saveProfileHonorForm` | state-refs + `states[]` real values | 🔬 same family as the other `saveProfile<X>Form` creates; pure-requests replay not proven |
| Edit | `saveProfileHonorForm` + `honorIdForm` (expected) | — | 🔬 not captured |
| Delete | `deleteProfileHonor` (⚠️ inferred, no `Form`) | expected `honorId` literal | ⏳ **not captured** — endpoint/payload inferred, not observed |

## Still to capture (honors)
- **Delete** capture (`honor_delete.json` was empty — re-run to record the real request) ⏳
- Clean **edit** capture with the `honorIdForm` discriminator + full `states[]` body ⏳
