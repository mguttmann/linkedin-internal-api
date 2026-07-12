# 17 — Patents "Patente" (documented from the pattern; no persisted capture artifact)

The **Patents** profile section (`/in/<vanity>/details/patents/`). The endpoints below are
documented from the universal profile-form pattern. ⚠️ **No capture artifact for Patents is
persisted in this repo** (the local captures (kept local, not shipped) has no `patent_*.json`), so — unlike Certifications /
Courses / Organizations / Projects / Volunteer — the Patents add/edit/delete are **reference-only /
inferred**, not backed by a recorded request. Treat the exact bodies below as the expected shape
by analogy, to be confirmed by a fresh capture.

Add/Edit share the standard `saveProfile<X>Form` endpoint (discriminated by `isEdit`+`patentId`);
the **delete deviates** (`deleteProfilePatent`, no `Form` suffix) — same quirk as
Honor/Course/Certification/Publication.

> ⚠️ **Two required fields** (unlike most sections which have one): `Patentbezeichnung*`
> (title) **and** `Patent- oder Antragsnummer*` (patent/application number). A save with only
> the title silently fails to persist. Fill both to make the entry stick.

---

## Add a patent (inferred) — `saveProfilePatentForm` (standard naming, `isEdit:false`)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfilePatentForm
```
- **Standard `saveProfile<X>Form` naming** — no deviation on add.
- Full-page form (`screenId: com.linkedin.sdui.flagshipnav.profile.ProfilePatentDetailsAddForm`,
  URL `/details/patents/edit/forms/new/`). Opened by the **"Neues Patent hinzufügen"** button.
- **Discriminator:** payload `isEdit: false`, **no** `patentId` key → this is a create.
- **Form fields** (from the live modal):
  - `Patentbezeichnung*` (payload `title`) — **required**.
  - `Patent- oder Antragsnummer*` (payload `referenceNumber`) — **required**.
  - `Ausgestellt am` — month/year (payload `issueDate`, a `proto.sdui.common.Date`).
  - `Patent-URL` (payload `url`).
  - `Beschreibung` (payload `description`).
  - `Erfinder:in hinzufügen` (payload `inventorContributors`) — typeahead contributor list.
  - Hidden default: `patentState` = `"Issued"` (Ausgestellt) vs `"Pending"` (Beantragt),
    driven by the `reason` radio group; `filingDate` for pending patents.
- No "Netzwerk informieren"/share toggle exists for an empty section.
- Like every profile form: `payload` fields are **state-refs**
  (`{"key":"auto-binding-<uuid>ProfilePatentForm<field>","namespace":"MemoryNamespace"}`)
  and a top-level **`states[]`** array carries the **real literal values** — the
  browserless-relevant part. Example `states[]` entries captured:
  - `...ProfilePatentFormtitle` → `"APITEST Patent <ts>"` (`stringValue`)
  - `...ProfilePatentFormpatentNumber` → `"APITEST-<ts>"` (`stringValue`)
  - `...ProfilePatentFormpatentState` → `"Issued"` (`stringValue`)
  - `...ProfilePatentFormissueDate` / `filingDate` → `{day,month,year}` (`dateValue`)
  - `...ProfilePatentFormpatentInventors` → `[]` (`stringListValue`)
- **Expected:** after save, the entry would render on the patents detail page (inferred; not captured in this repo).

---

## Edit a patent (inferred) — `saveProfilePatentForm` (same endpoint, `isEdit:true` + `patentId`)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfilePatentForm
```
- **Same endpoint as add**, discriminated by the payload:
  - `isEdit: true`
  - `patentId: "SECTION_ITEM_ID"` ← real numeric id, plain literal (the entry being edited)
  - `profileId: "OWNER_PROFILE_ID"`, `vanityName: "alex-rivera"`
- `screenId: com.linkedin.sdui.flagshipnav.profile.ProfilePatentDetailsEditForm`
  (edit URL `/details/patents/edit/forms/<patentId>/`). Opened by the **"Patent bearbeiten"**
  (aria-label) pencil on the entry.
- Same state-ref payload + `states[]` real-values structure as add. Captured `states[]`:
  - `title` → `"…EDITED…"` (changed value)
  - `patentNumber` → `"APITEST-<ts>"`, `patentState` → `"Issued"`
- **Expected:** edit would replace the title (inferred; not captured).

---

## Delete a patent (inferred) — ⚠️ deviating name `deleteProfilePatent` (no `Form`)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfilePatent
Body (serverRequest.requestedArguments.payload — the identifying literals):
{
  "isEdit": true,
  "patentId": "SECTION_ITEM_ID",                       ← real id, plain literal
  "profileId": "OWNER_PROFILE_ID",
  "vanityName": "alex-rivera",
  "title":       {"key":"auto-binding-<uuid>ProfilePatentFormtitle","namespace":"MemoryNamespace"},
  "referenceNumber": {"key":"...ProfilePatentFormpatentNumber","namespace":"MemoryNamespace"},
  ... (all other form fields carried as state-refs, same as save) ...
  "hasChanges":       {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "progressIndicator":{"key":"isActiveProfileFormLoadingProfileEditForm","namespace":"MemoryNamespace"}
}
```
- **Naming deviation (captured, not guessed):** `deleteProfilePatent` — **no `Form` suffix**
  (same quirk as `deleteProfileHonor`, `deleteProfileCourse`, `deleteProfileCertification`,
  `deleteProfilePublication`).
- Carries the **real `patentId` as a plain literal** in the payload (easy for replay — the id
  is not buried in a state-key), alongside `profileId` and `vanityName`.
- The delete payload re-sends the full form shape (all fields as state-refs + `states[]`), but
  the operative identifier is `patentId`.
- **UI/capture note:** the in-modal delete button is section-specific: **"Patent löschen"**
  (bottom of the edit modal, next to "Speichern"). `click_label("Patent löschen", contains=False)`
  matched directly. The confirm dialog's button is the plain **"Löschen"**
  (`click_label("Löschen", index=-1, contains=False)`).
- **Expected:** delete would remove the entry (inferred; not captured — no `patent_delete.json` artifact).

---

## Read-back — `fetchPatentsSections` + details pager
- Section fetch: `com.linkedin.sdui.requests.profile.fetchPatentsSections`
  with `cardType: "Patents"` (top-level card) and `cardType: "PatentsDetails"` (detail list),
  keyed by `collection-content-profile_Patents_alex-rivera`.
- Detail pager: `com.linkedin.sdui.pagers.profile.details.patents`
  payload `{vanityName, start:0, count:10, profileId}` (`count:10`).
- Component sections: `...dsl.impl.patentTopLevelSection` / `...patentDetailSection`.
- **Verify cleanup via browser render, not Voyager read** (playbook rule 7): navigate
  `/in/<vanity>/details/patents/?nc=<ts>` and check `document.body.innerText` for the marker.

## Browserless-replay status
| Op | Endpoint | Body carries | Browserless |
|---|---|---|---|
| Add | `saveProfilePatentForm` (`isEdit:false`) | state-refs + `states[]` real values (`title`, `patentNumber`, `patentState`, dates) | 🔬 same family as `saveProfileLanguageForm` (create proven browserless); needs full `states[]` reconstruction |
| Edit | `saveProfilePatentForm` (`isEdit:true` + real `patentId`) | state-refs + `states[]` real values | 🔬 id in hand; same family/caveats as add |
| Delete | `deleteProfilePatent` (⚠️ no `Form`) | **real `patentId` literal** + `profileId`/`vanityName` | 🔬 id in hand, but SDUI profile delete via pure requests is a no-op today (see docs/BROWSERLESS-REPLAY.md); UI delete reliable |

## Capture provenance
- Live capture on `alex-rivera` via `tools/capture_session.py` (CDP click-and-record).
- Budget discipline followed: filled only the two required fields; delete-first safety applied;
  no test entry left live. Two full ADD→…→DELETE cycles run, final render clean.
- One early ADD (title only, no number) **silently failed to persist** — the reason the section
  needs both required fields; documented above so future agents don't chase a "vanishing" entry.

## Still to capture (patents)
- Full `states[]` body for a *pending* patent (`patentState: "Pending"` + `filingDate`) ⏳
- Inventor/contributor typeahead (`inventorContributors`) capture with a real suggestion ⏳
