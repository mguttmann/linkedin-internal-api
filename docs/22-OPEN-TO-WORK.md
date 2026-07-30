# 22 — Open to work / Job Seeker Preferences (read + write verified)

The "Für neue Möglichkeiten offen" / open-to-work feature. Alex does **not** want a visible
`#OpenToWork` search signal — so the correct state is **OFF** (recruiters-only at most, never
the public green banner). Both the read endpoint and the enable/disable **write** are fully
verified live (see below); the profile was verified to stay OFF throughout, no signal left on.

---

## ✅ Read — `voyagerJobsDashJobSeekerPreferences`

```
GET /voyager/api/voyagerJobsDashJobSeekerPreferences  → 200
```
Returns the full job-seeker preference object. Alex's current (correct, OFF) state:
```json
{
  "sharedWithRecruiters": false,          // ← recruiter signal OFF
  "openCandidateVisibility": null,        // ← not visible as candidate
  "profileSharedWithJobPoster": false,
  "seekingRemote": false,
  "preferredRolesUrns": [],
  "geoUrns": [],
  "jobRecommendationsEmailEnabled": false,
  "openToWorkReachabilityEmailEnabled": false,
  "openToWorkReachabilityNotificationEnabled": false,
  "entityUrn": "urn:li:fsd_jobSeekerPreference:urn:li:fsd_profile:<profileId>",
  "$type": "com.linkedin.voyager.dash.jobs.JobSeekerPreference"
}
```
- **The key fields for "is open-to-work on?":** `sharedWithRecruiters` (recruiters-only signal),
  `openCandidateVisibility` (public banner — `null`/`false` = off), `profileSharedWithJobPoster`.
- **Verification of OFF state:** all three are false/null → no open-to-work signal on the profile.
  ✅ Confirmed via this pure-`requests` read (browserless).

## ✅ Write — enable + disable BOTH captured (live)

### Enable
```
POST /voyager/api/voyagerJobsDashOpenToWorkPreferencesFormElementInput
     ?action=submitFormAndGenerateView
     &decorationId=com.linkedin.voyager.dash.deco.jobs.OpenToWorkNextActionsView-23
```
Body = `formElementInputs[]`, each `{formElementUrn, formElementInputValues[]}` with **real URN
literals** (browserless-replayable, no state-refs):
- `…FormElement:JOB_TITLES` → `entityInputValue{inputEntityUrn: urn:li:fsd_standardizedTitle:TITLE_ID}`
- `…FormElement:WORKPLACES` → `urn:li:fsd_workplaceType:1` (Vor Ort), `:3` (Hybrid)
- `…FormElement:JOB_LOCATIONS` → `urn:li:fsd_geo:GEO_ID` ((location))
- `…FormElement:JOB_TYPES` → `FULL_TIME`
- `…FormElement:VISIBILITY` → `RECRUITERS` (private — no public #OpenToWork banner)
- `origin: PROFILE_TOP_CARD`

Post-enable read confirmed `openCandidateVisibility:"RECRUITERS", sharedWithRecruiters:true`.

### Disable (turn OFF completely) — the clean one-shot
```
DELETE /voyager/api/voyagerJobsDashOpenToWorkPreferencesFormElementInput?formType=OPEN_TO_WORK
```
A single Voyager DELETE with `formType=OPEN_TO_WORK` — no body needed. **Verified live:** after
the DELETE the read returns `sharedWithRecruiters:false, openCandidateVisibility:null` → OFF.
✅ browserless-replayable (plain DELETE).

**UI trigger:** the reliable entry point is the dedicated URL
`https://www.linkedin.com/jobs/opportunities/job-opportunities/onboarding/` which opens the
"Jobeinstellungen bearbeiten" modal directly; its bottom-left **"Löschen"** → confirm fires the
DELETE above. (The profile-top-card pencil is flaky — it kept opening the notifications panel.)

## Browserless status
- **Read:** ✅ browserless (pure requests, 200).
- **Write:** ✅ browserless — enable is a Voyager POST (`submitFormAndGenerateView`) with real URN
  literals (no state-refs); disable is a plain Voyager `DELETE ?formType=OPEN_TO_WORK` (no body).
  Both verified live (see above). **Scope:** "write" here means *the whole open-to-work form*
  (on / off). Writing **individual job-seeker preferences** without touching the open-to-work
  signal is a different thing and is **not covered** — see the next section.

---

# Writing individual job-seeker preferences — open items [O]

Researched 2026-07-30 against this repo, **no live call made** (no session in that run). Everything
below is either evidence from this repo or explicitly marked ABSENT/unknown. The trigger was a
request for a `set_job_preferences(seeking_remote, minimum_pay, preferred_roles, geo, confirm)`
tool. **Conclusion: on this evidence base that tool is not buildable** — and the reason is a hazard,
not a missing detail.

## [O-1] ⚠️ HAZARD — the only documented write path turns the recruiter signal ON

Read this before designing any preferences write.

- The **only** write path for job-seeker preferences documented in this repo is the open-to-work
  form POST above. Its captured body contains `…FormElement:VISIBILITY → RECRUITERS`, and the
  post-enable read confirmed `openCandidateVisibility:"RECRUITERS"`, `sharedWithRecruiters:true`.
  That is exactly the signal this document opens by declaring **not wanted**.
- A preferences write route **decoupled** from that form is **ABSENT**: in both endpoint catalogs
  (`data/endpoints_voyager.json`, `data/endpoints_sdui.json`) `JobSeekerPreferences` appears
  **only as GET** — the GraphQL read and the REST read with
  `decorationId=…FullJobSeekerPreference-8`. There is **no POST / PUT / PATCH** on it.
- There is **no captured `VISIBILITY` value meaning "off"**. The only documented way back to OFF is
  the `DELETE …?formType=OPEN_TO_WORK` above, which deletes the **whole form**, not one field.
- **Therefore:** building `set_job_preferences` today would require **guessing** a `VISIBILITY`
  value (or omitting the element and hoping the server keeps the old one). Both are guesses on the
  one field that flips a publicly consequential signal. Do not guess it — the repo rule is
  "don't guess, click and record".
- **Unknown on top of that:** whether a `WORKPLACES` write even changes the read field
  `seekingRemote`. `seekingRemote` does not appear literally in the captured write body, and there
  is no before/after capture. ABSENT.

**The one capture that unblocks this:** in "Jobeinstellungen" change **only** remote / pay, **without**
activating open-to-work (entry point: the onboarding URL above). Record (a) route + body,
(b) a before/after read of `sharedWithRecruiters` and `openCandidateVisibility`, (c) whether a pay
element appears in the form at all, (d) which `workplaceType` URN "Remote" sends. Until that exists,
the honest answer to "set my preferences browserless" is: only via the full form, which switches the
recruiter signal on.

## [O-2] `minimumPay` — does not exist anywhere in this repo

- `minimumPay` and **every** pay-related field are **ABSENT**: a grep for
  `minimumPay|minimum_pay|salary|compensation|expectedPay|payRange` over the repo returns **0
  hits**. Not in the read response, not as a form element, not in prose.
- Consequence for the question *"can `minimumPay` be set without Premium?"* — **this repo cannot
  answer it.** That is why it is listed here as **[O]**, and not shipped as a parameter that would
  fail silently.
- The read that would answer it: the verified **Voyager-REST** read above (`GET
  /voyager/api/voyagerJobsDashJobSeekerPreferences → 200`, this file's Read section) returns
  **9 documented fields**, none pay-related. The same REST family **with**
  `decorationId=…FullJobSeekerPreference-8` (`data/endpoints_voyager.json:706-707`) **and** the
  GraphQL variant `voyagerJobsDashJobSeekerPreferences.53d4a0b454b82ce339abf8afc2c65190`
  (`data/endpoints_voyager.json:86-87`) are **both** catalogued with `response_len: 0` — whether
  either returns more fields is **unknown**. Note the layer distinction: the verified read is
  Voyager REST; the decorated REST URL and the GraphQL queryId are two *separate* catalogued
  routes, neither of which has ever been executed here.
  **Cheapest next step:** capture the decorated REST read **with its body** once. It answers "does
  pay exist in the read at all" with zero write risk.

## [O-3] `workplaceType` URNs — `:2` is ABSENT

- Documented and captured: `urn:li:fsd_workplaceType:1` (Vor Ort / on-site) and `:3` (Hybrid) — see
  the enable body above. Note the precise status: what the live POST proves is that the request with
  these URNs succeeded; the **label mapping** ("1 = on-site", "3 = Hybrid") is a documentation
  annotation, not something a read confirmed.
- `urn:li:fsd_workplaceType:2` does **not occur anywhere in this repo** — ABSENT. It would be
  *plausible* that `:2` is Remote, but that is an **explicitly unproven guess**, stated here only so
  nobody mistakes it for a fact. Do not send `:2` until a capture shows it (capture [O-1] would).

## [O-4] URN → plain-text resolver (`fsd_standardizedTitle`, `fsd_geo`) — ABSENT

The read returns `preferredRolesUrns` as bare ids (e.g. `urn:li:fsd_standardizedTitle:<id>`) and
`geoUrns` likewise, so a caller cannot see which roles/locations are stored. A resolver would be
useful — but:

- **No resolver exists in this repo.** Nothing maps a `fsd_standardizedTitle` or `fsd_geo` URN back
  to a label.
- The two candidates in the catalog point the **wrong way** and are empty:
  `voyagerJobsDashLocationSuggestions.<hash>` and
  `voyagerJobsDashJobSearchSuggestionComponents.<hash>` are both catalogued with `variables=()` and
  `response_len: 0`. By name they are **typeahead** endpoints, i.e. free text → URN, which is the
  opposite direction. Their suitability is 🔩 inferred from the name only.
- Related repo rule that confirms only the forward direction is understood:
  `BROWSERLESS-REPLAY.md` — "typeahead fields send an **id** resolved from a typeahead call; for a
  browserless write you must first resolve that id (a typeahead GET)". A real typeahead capture
  exists only for **companies** (`sduiid=PROFILE_COMPANY_TYPEAHEAD_REQUEST`,
  `09-PROFILE-EDITING.md`), plus a jobs typeahead SDUI screen with captured `postData`
  (`data/endpoints_sdui.json`). For titles and geos: **ABSENT**.
- **Capture that would close it:** open the job-preferences form with roles/locations already
  stored and record the **read** that renders their labels (the form must resolve them to display
  them) — that response carries the URN→label pairs. A second, independent option: record one
  title/location typeahead request+response and check whether it can be queried by id.

> Caveat on catalog citations: `url_sample` and `postData` in `data/endpoints_voyager.json` are
> truncated at 200 characters (`tools/build_docs.py`), so a `variables=()` in the catalog may have
> carried parameters that are simply not visible there. None of the statements above depends on a
> complete URL. See `BACKLOG.md`.