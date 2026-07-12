# 19 — Test scores "Prüfungsergebnisse" (verified delete + add mapped)

The **Test scores** profile section (`/in/<vanity>/details/test-scores/`). The **delete was
captured live** (`deleteProfileTestScore`). The add form was mapped but its save request was
**not** recorded. Delete deviates from the naming convention (no `Form` suffix), consistent
with Honor/Course/Patent/Org.

> **Capture artifacts:** `<local capture, not shipped>` holds the real delete
> mutation (`deleteProfileTestScore`). `<local capture, not shipped>` exists but is
> **empty** (`[]`) — **no add request was captured**. So the add endpoint/discriminator below
> is **inferred** from the sibling `saveProfile<X>Form` family, not verified.

---

## Add a test score — ⏳ NOT captured (inferred `saveProfileTestScoreForm`)

> **⚠️ Not actually captured.** `test_score_add.json` is empty. The endpoint and field map
> below are **inferred** by analogy to the other sections; treat as unverified.

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileTestScoreForm   (INFERRED)
```
- **Expected two required fields** (like Patents — a title-only add would silently fail to persist):
  - `Überschrift*` — the test name → payload `title`, state key `…ProfileTestScoreFormtestScoreTitle`.
  - `Ergebnis*` — the score → payload `score`, state key `…ProfileTestScoreFormtestScore`.
- Optional: `associateId` (typeahead link to a position/education), `description`, `testDate`.
- Expected `payload` = **state-refs**; real values in the top-level **`states[]`** array.
- **Add discriminator (expected):** `isEdit:false` and **no `testScoreId`** in the payload.

## Edit a test score — ⏳ NOT captured (inferred)
- Expected same `saveProfileTestScoreForm`; discriminated by `isEdit:true` plus a real
  `testScoreId` literal in the payload (by analogy to Patents/Org; not captured). 🔬

## ✅ Delete a test score — `deleteProfileTestScore` (captured)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.deleteProfileTestScore
Body (serverRequest.requestedArguments.payload):
{
  "vanityName":"alex-rivera",
  "testScoreId":"SECTION_ITEM_ID",                    ← real id, plain literal
  "profileId":"OWNER_PROFILE_ID",
  "hasChanges":       {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "progressIndicator":{"key":"isActiveProfileFormLoadingProfileEditForm","namespace":"MemoryNamespace"}
}
```
- **Captured live** in `test_score_delete.json`.
- **Naming deviation:** `deleteProfileTestScore` — **no `Form` suffix** (same quirk as
  `deleteProfileCourse`/`deleteProfileHonor`/`deleteProfilePatent`/`deleteProfileOrganization`).
- Carries the **real `testScoreId` as a plain literal** — replay-friendly.
- **Verified + cleaned up:** the `APITEST Score` entry was removed; test-scores page re-rendered
  with no `APITEST` marker. ✅

---

## Read-back — `fetchTestScoresSections`
`cardType: TestScores` / `TestScoresDetails`; detail pager
`com.linkedin.sdui.pagers.profile.details.test-scores` (or `.testScores`) `count:10`.

## Browserless-replay status
| Op | Endpoint | Body carries | Browserless |
|---|---|---|---|
| Add | `saveProfileTestScoreForm` (⚠️ inferred) | — | ⏳ **not captured** (`test_score_add.json` empty) |
| Edit | `saveProfileTestScoreForm` + `isEdit:true` + `testScoreId` (inferred) | — | ⏳ not captured |
| Delete | `deleteProfileTestScore` (no `Form`) | **real `testScoreId` literal** | 🔬 id in hand; UI delete reliable, pure-requests SDUI delete is a no-op today (see docs/BROWSERLESS-REPLAY.md) |

## Still to capture (test scores)
- **Add** capture (`test_score_add.json` was empty — re-run to record `saveProfileTestScoreForm`) ⏳
- **Edit** capture with the `testScoreId` discriminator ⏳
