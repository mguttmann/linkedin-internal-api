# 11 — Experience / Positions "Berufserfahrung" (verified add + form mapped)

The **Experience/positions** section (`/in/<vanity>/details/experience/`, add form
`/edit/forms/position/new/`). The **add was captured live** (`saveProfilePositionForm`);
the add/edit form was fully mapped. Add/edit follow the universal `saveProfilePositionForm`
pattern (same as skills/education).

> **Capture artifact:** `<local capture, not shipped>`
> (test entry `APITEST Position <ts>` · company `APITEST Firma`). The mutation recorded is
> `com.linkedin.sdui.requests.profile.saveProfilePositionForm` (an **add** — no `positionId`
> literal). **No delete capture exists in the repo** (`deleteProfilePositionForm` was not
> recorded); the delete endpoint below is **inferred** from the universal pattern, not captured.

---

## Form fields (from the live "Position hinzufügen" modal)
`Überschrift*` (title, required) · `Beschäftigungsverhältnis` (employment-type select) ·
`Unternehmen*` (company **typeahead**, required) · `Standorttyp` · `Standort` ·
start `Monat` + **`Jahr*`** (required) · end month/year (or "Ich arbeite aktuell hier") ·
description · skills sub-list · media. Plus the **"Netzwerk informieren"** share toggle —
**turn OFF** before saving to avoid notifying the network.

> **React-controlled `<select>` gotcha:** setting `.value` directly does NOT register. Use the
> native prototype setter + dispatch `input`+`change` events (a `setSelectByLabel` helper).

---

## ✅ Add a position

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfilePositionForm
```
- **Captured live** in `experience_add.json`. The save is discriminated as an *add* by the
  **absence** of a `positionId` literal (same discriminator as education/projects — add omits
  the id, edit adds it).
- The add flow also fires media-prep calls even with no media attached:
  `profileMediaCheckUpload`, `profileMediaRegister`,
  `com.linkedin.sdui.impl.profile.components.forms.uploadPositionMedia`.
- Like every profile form: `payload` fields are **state-refs**; real values are expected in
  the top-level **`states[]`** array, PLUS a resolved **company id** from the `Unternehmen`
  typeahead.
- **Verified:** the test position was captured on save. (Its later removal was intended via the
  delete below, but the delete request itself was **not** recorded — see the note.)

---

## Edit a position (schema — not separately captured)

- **Endpoint:** `com.linkedin.sdui.requests.profile.saveProfilePositionForm` (same as add;
  **edit** adds a real `positionId` literal — same discriminator as education/projects).
- **Status: 🔬 not captured** — a clean edit capture is still pending (would need a company
  typeahead pick).

## Delete a position (⏳ NOT captured — inferred endpoint)

- **Expected endpoint:** `com.linkedin.sdui.requests.profile.deleteProfilePositionForm` with a
  real `positionId` literal (by analogy to `deleteProfileProjectForm`). **This has NOT been
  captured** — no `deleteProfilePositionForm` request exists in any local capture. Treat
  the name and payload as **inferred**, not verified.

## Read-back
`fetchExperienceSections` (`cardType: ExperienceTopLevelSection` / `ExperienceDetailsSection`).

## Still to capture (experience)
- Clean **edit** capture with the `positionId` discriminator + full `states[]` body ⏳
- **Delete** capture (`deleteProfilePositionForm` + real `positionId`) ⏳
- **Career break** ("Berufliche Auszeit") variant of the same form ⏳
