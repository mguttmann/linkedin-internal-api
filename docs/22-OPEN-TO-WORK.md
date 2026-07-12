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
  Both verified live (see above).