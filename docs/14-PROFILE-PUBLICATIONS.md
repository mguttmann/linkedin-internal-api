# 14 — Publications "Publikationen" (verified add + form mapped)

The **Publications** profile section (`/in/<vanity>/details/publications/`). The **add was
captured live** (`saveProfilePublicationForm`); add/edit follow the profile-form pattern. The
delete endpoint is documented below by analogy but is **not captured** in the repo.

> **Capture artifact:** `<local capture, not shipped>` — the recorded mutation is
> `com.linkedin.sdui.requests.profile.saveProfilePublicationForm` (an **add**). There is **no
> publication delete capture** in the local captures (no `deleteProfilePublication` request was
> recorded); the delete section below is **inferred**, not verified.

---

## ✅ Add a publication — `saveProfilePublicationForm`

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfilePublicationForm
```
- **Standard `saveProfile<X>Form` naming.** Captured live in `publication_add.json`.
- Form fields (from the live modal): `Titel*` (title), `Publikation/Herausgeber`
  (publisherTitle), publication date, `URL der Publikation`, description, `Autor:in hinzufügen`
  (co-authors sub-list).
- Like every profile form: `payload` fields are **state-refs**; real values ride in the
  top-level **`states[]`** array. **Add discriminator:** no `publicationId` in the payload.
- **Browserless:** expected to carry real values in `states[]` like every other profile form.
  Status: 🔬 (pure-`requests` replay not proven).

---

## Delete a publication — ⏳ NOT captured (inferred, deviating name)

> **Not captured in this repo.** The delete endpoint and payload shape below are **inferred**
> from the sibling sections' "delete drops the `Form` suffix" quirk (cf. `deleteProfileCourse`,
> `deleteProfileCertification`). No `deleteProfilePublication` request was recorded — do not
> treat this as verified.

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfilePublication   (INFERRED)
```
- **Expected naming deviation:** `deleteProfilePublication` — **no `Form` suffix** (same quirk
  as `deleteProfileCertification`).
- **Expected id shape (by analogy):** unlike course/patent deletes that carry a plain
  `publicationId` literal, the publication form is expected to key fields by
  `ProfilePublicationForm-<publicationId>` (the id embedded in the state key). **Unconfirmed.**
- UI: edit the publication → **"Publikation löschen"** (not plain "Löschen") → confirm.

## Read-back
`fetchPublicationsSections` (`cardType: PublicationTopLevelSection` /
`PublicationDetailsSection`) + `pagers.profile.details.publications`.

## Still to capture (publications)
- Clean **edit** capture with full `states[]` body ⏳
- **Delete** capture (`deleteProfilePublication`) to confirm endpoint name + id shape ⏳
