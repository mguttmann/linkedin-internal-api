# 15 — Courses "Kurse" (add / edit / delete — all three verified live)

The **Courses** profile section (`/in/<vanity>/details/courses/`). All three write
operations were performed in the live client and the requests captured (click-and-record —
never guessed). A crashed earlier agent had left an `APITEST Course` live on the profile; it
was removed first (delete-first safety), then a fresh add → edit → delete cycle was recorded.
**Profile is clean afterwards — verified by browser render (no `APITEST` marker).**

Raw captures: `<local capture, not shipped>` (gitignored — may hold session data).

---

## ✅ Add a course — `saveProfileCourseForm`

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileCourseForm
Body (serverRequest.requestedArguments.payload):
{
  "name":        {"key":"auto-binding-<uuid>ProfileCourseFormcourseName",   "namespace":"MemoryNamespace"},
  "number":      {"key":"auto-binding-<uuid>ProfileCourseFormcourseNumber", "namespace":"MemoryNamespace"},
  "associateId": {"key":"auto-binding-<uuid>ProfileCourseFormassociateId",  "namespace":"MemoryNamespace"},
  "profileIdForm":"OWNER_PROFILE_ID",
  "vanityName":"alex-rivera",
  "hasChanges":       {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "progressIndicator":{"key":"isActiveProfileFormLoadingProfileEditForm",   "namespace":"MemoryNamespace"}
}
```
- **Standard `saveProfile<X>Form` naming** — no deviation here (unlike the delete, below).
- The `payload` fields are **state-refs**, but the same request also carries a **top-level
  `states[]` array with the real literal values** (the browserless-relevant part):
  ```json
  "states":[
    {"key":"auto-binding-<uuid>ProfileCourseFormcourseName",  "namespace":"MemoryNamespace","value":"APITEST Course 1783794409","originalProtoCase":"stringValue"},
    {"key":"auto-binding-<uuid>ProfileCourseFormcourseNumber","namespace":"MemoryNamespace","value":"APT-1783794409",           "originalProtoCase":"stringValue"}
  ]
  ```
- **NO `courseIdForm` in the payload** — its absence is what makes this an *add* rather than an edit.
- **Form fields** (from the live modal):
  - `Name` (courseName) — placeholder *"Beispiel: Weltgeschichte"* — required.
  - `Nummer` (courseNumber) — placeholder *"Beispiel: Grundlagen der Geschichte"* — optional.
  - `Verknüpft mit` (associateId) — a **typeahead** ("Suche") linking the course to a
    position/education entry. Empty in this capture; when picked it resolves to an id.
- UI trigger: courses detail page → **"Kurse hinzufügen"** (empty section) or **"Neuen Kurs
  hinzufügen"** → fill → **"Speichern"**.
- **Verified:** after save, `APITEST Course 1783794409` rendered live on the profile. ✅

## ✅ Edit a course — same `saveProfileCourseForm` + `courseIdForm` literal

```
POST …sduiid=com.linkedin.sdui.requests.profile.saveProfileCourseForm   (identical endpoint)
payload adds:  "courseIdForm":"SECTION_ITEM_ID"     ← real course id, plain literal
```
- **Edit reuses the exact add endpoint.** The **only** structural difference is a
  `courseIdForm` literal in the `payload` (the real course id, `SECTION_ITEM_ID`). Present → edit
  (update existing); absent → add (create new).
- Field values still travel as state-refs + a real-value `states[]` array, same as add. In this
  capture the `Nummer` field was changed to `APT-EDIT-1783794544`.
- UI trigger: the course's edit pencil — aria-label **"Kurs „<name>“ bearbeiten"** → change
  fields → **"Speichern"**.
- **Verified:** after save, the profile rendered the new number `APT-EDIT-1783794544`. ✅

## ✅ Delete a course — ⚠️ deviating name `deleteProfileCourse`

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfileCourse
Body (serverRequest.requestedArguments.payload):
{
  "vanityName":"alex-rivera",
  "courseId":"SECTION_ITEM_ID",                       ← real id, plain literal
  "profileId":"OWNER_PROFILE_ID",
  "hasChanges":       {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "progressIndicator":{"key":"isActiveProfileFormLoadingProfileEditForm",   "namespace":"MemoryNamespace"}
}
```
- **Naming deviation (captured, not guessed):** it is `deleteProfileCourse` — **no `Form`
  suffix** (same quirk as `deleteProfileCertification` and `deleteVolunteerExperience`).
- The delete carries the **real `courseId` as a plain literal** in the payload (not embedded in
  a state-key like publications). So the id is trivially available for replay.
- **Preceding `navigation` action** also carries the id — fired when the edit modal opens:
  ```
  POST …/actions/navigation?screenId=…ProfileCourseDetailsEditForm
  {"clientArguments":{"payload":{"vanityName":"alex-rivera","courseId":"SECTION_ITEM_ID"}, …}}
  ```
- UI trigger: open the course's edit modal → **"Kurs löschen"** (section-specific label at the
  **bottom** of the modal next to "Speichern", **not** plain "Löschen") → confirm dialog
  **"Löschen"**.
  - Capture recipe: `s.click_label("Kurs löschen", contains=False)` then
    `s.click_label("Löschen", index=-1, contains=False)`.
- **Verified + cleaned up:** the `APITEST Course` was removed; the courses detail page
  re-rendered to *"Noch keine Informationen verfügbar"* with no `APITEST` marker. ✅

---

## Read-back — `fetchCoursesSections`

After every write the client refetches the section (both card types):
```
POST …sduiid=com.linkedin.sdui.requests.profile.fetchCoursesSections
payload: {"vanityName":"alex-rivera","profileId":"<urn>",
          "cardType":"CourseTopLevelSection" | "CourseDetailsSection",
          "collectionIds":{"key":"collection-content-profile_<cardType>_alex-rivera","namespace":"MemoryNamespace"}}
```
- `CourseTopLevelSection` = the summary card on the main profile; `CourseDetailsSection` = the
  full list on the details page.
- Detail list paginator: `com.linkedin.sdui.pagers.profile.details.courses`
  (`start`/`count`, `count:10`).
- Section-render components:
  `impl.courseTopLevelSection` / `impl.courseDetailSection` (`/actions/component`).
- **Read-back caveat (playbook lesson):** the legacy Voyager `identity/profiles/{id}/courses`
  GET is stale/cached. To verify a write, trust the **freshly-rendered profile page**
  (`?nc=<ts>` cache-bust) — that is what confirmed cleanup here.

## Browserless-replay status

| Operation | Endpoint | Body carries | Browserless |
|---|---|---|---|
| Add    | `saveProfileCourseForm` | state-refs **+ `states[]` real values** | 🔬 replayable-in-principle (same family as `saveProfileLanguageForm`, whose create is **proven** browserless — self-gen uuid + `states[]` value → HTTP 200). Course create not individually replayed yet. |
| Edit   | `saveProfileCourseForm` + `courseIdForm` literal | state-refs + `states[]` + real `courseIdForm` | 🔬 same as add; add a real `courseIdForm`. |
| Delete | `deleteProfileCourse` (⚠️ no `Form`) | **real `courseId` literal** | ✅ id in hand, but per `docs/BROWSERLESS-REPLAY.md` a pure-requests SDUI profile delete is currently a **no-op** (server ties delete to state from a preceding `component`/form-load call). UI delete is 100% reliable. 🔬 |

See `docs/BROWSERLESS-REPLAY.md` for the general two-body-shape explanation and the proven
language-create replay. Courses are structurally identical to the rest of the
`saveProfile<X>Form` family — only `<FormName>` (`ProfileCourseForm`) and the field keys
(`courseName` / `courseNumber` / `associateId`) change.

## Field / id reference (this capture)

| Item | Value |
|---|---|
| vanityName | `alex-rivera` |
| profileId (urn) | `OWNER_PROFILE_ID` |
| test course id (add→edit→delete) | `SECTION_ITEM_ID` |
| add fields | name=`APITEST Course <ts>`, number=`APT-<ts>` |
| edit change | number → `APT-EDIT-<ts>` |
| add/edit endpoint | `com.linkedin.sdui.requests.profile.saveProfileCourseForm` |
| delete endpoint | `com.linkedin.sdui.requests.profile.deleteProfileCourse` |
| read-back | `com.linkedin.sdui.requests.profile.fetchCoursesSections` |
| detail pager | `com.linkedin.sdui.pagers.profile.details.courses` |
