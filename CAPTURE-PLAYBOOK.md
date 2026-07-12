# Capture Playbook — how to record a LinkedIn write endpoint

This is the exact, proven procedure to capture ONE write operation end-to-end and document
it so it can later be replayed. Read it fully. **Never guess an endpoint — perform the real
action in the live client and record what it sends.**

## Environment
- A visible Chrome runs with CDP on `http://127.0.0.1:9222`, logged in as the owner account.
- A Python venv with the repo's dependencies (`fastmcp patchright requests websocket-client`).
- Capture helper: `tools/capture_session.py` (class `CaptureSession`).
- Cookies for browserless replay test: a local cookies JSON (+ `lib/vgreq.py`).
- Profile identity comes from env (`LI_OWNER_URN` / `LI_OWNER_VANITY`); placeholders
  `OWNER_PROFILE_ID` / `OWNER_PLAIN_ID` stand in for real values in this doc.

## CRITICAL RULES

### ⏱️ PACING — go slow, look human (rule zero, prevents force-logout)
Rapid, evenly-spaced, cache-busted requests are the #1 signal that force-logs-out the session.
**Slow down and randomize:**
1. **NO cache-bust params.** Never append `?nc=<timestamp>` / `?fresh=…` to re-load a page.
   Navigate to the real URL once; `nav()` now warns if you don't. For a post-write freshness
   check, prefer a `vgreq` read over re-navigating in the browser.
2. **Pause between every page load / major action:** the tooling now calls `human_pause("page")`
   (randomized 6–14s) inside `nav()` and micro-pauses inside `click_xy`/`type_text`
   automatically. Do NOT bypass them; do NOT loop-navigate.
3. **One thing at a time.** Do NOT render 6 sections in 90s. Handle ONE section, pause, done.
   Reads that only *check* state should go through `vgreq` (requests), not the browser.
4. **Type like a human:** `type_text()` now inserts char-by-char with jitter — leave it on.
5. If you must disable pacing for an offline/dry run, set `capture_session.PACING = False`
   explicitly — never for live LinkedIn work.

1. **You may do anything on the owner's profile EXCEPT delete real/existing data.** Add TEST
   data, capture, then remove ONLY the test data you added. Never remove pre-existing items.
2. **Use a fresh tab per capture run:** `CaptureSession(new_tab=True)` — so concurrent runs don't
   fight over the page. Call `.close()` at the end (it closes the tab).
3. **Turn OFF "Netzwerk informieren" / "Share with network"** toggles before saving profile
   changes, so the capture doesn't spam the owner's network.
4. **Mark test data clearly**: text `APITEST <unix-ts>`. For typeahead fields (skills,
   companies, schools) you must pick a real suggestion — use an obviously-removable real value
   and delete it right after.
5. **Clean up and VERIFY** the profile is back to original (`... in document.body.innerText`
   check). Report if anything is left behind.

## HARD-WON LESSONS (waves 1–2) — follow these or you WILL leave junk on the profile
6. **DELETE-FIRST SAFETY:** the moment a test entry is created, capture the DELETE **before**
   doing the EDIT. Order: ADD → capture → **DELETE → capture → verify gone** → (only if time
   permits) re-ADD → EDIT → capture → DELETE again. Reason: a run can be interrupted
   mid-way; if delete is last, a test entry stays LIVE on the owner's profile. Never end a run
   with an un-deleted test entry.
   **Efficiency:** the ADD is expensive (form fill, typeahead, save). To reliably reach the
   DELETE: (a) fill ONLY the single required field (e.g. title) — skip typeahead/date/description;
   (b) don't pretty-print or over-inspect the captured ADD body before deleting — dump it to
   a file and move straight to the delete; (c) the delete is the #1 obligation. If a run is
   running long and the entry still exists, abort everything else and delete now.
7. **VERIFY CLEANUP VIA BROWSER RENDER, NOT VOYAGER READ.** The legacy Voyager
   `identity/profiles/{id}/<section>` GET is stale/cached (lags minutes, returns 410/400).
   To confirm cleanup: `s.nav(<detail page>+"?nc="+str(int(time.time())))`, wait, then check
   `s.ev("document.body.innerText")` for the `APITEST` marker. That fresh render is truth.
8. **ONE SECTION PER FILE.** Each section's findings go in its own `docs/NN-...md`. Avoid editing
   the shared summary files (`09-PROFILE-EDITING.md`, `COVERAGE-MAP.md`, `STATUS-MATRIX.md`)
   during capture — reconcile them in a separate pass so parallel edits don't collide in git.
9. **Delete button label:** in most profile modals the delete button is just **"Löschen"**
   (plain text, not "X löschen"). Use `s.click_label("Löschen", contains=False)` then the
   confirm dialog's `s.click_label("Löschen", index=-1, contains=False)`.
   BUT some sections use a section-specific label, e.g. **"Publikation löschen"**,
   **"Position löschen"**. If plain "Löschen" returns not-found, dump the modal's visible
   buttons and use `s.click_label("löschen", contains=True)` (lowercase substring) for the
   in-modal delete, then `s.click_label("Löschen", index=-1, contains=False)` for the confirm.
   The delete button sits at the BOTTOM of the edit modal (next to "Speichern").
10. **Don't assume the endpoint name.** Some sections deviate: Volunteer is
    `impl.profile.saveVolunteerExperienceForm` (no `Profile` infix), Certification delete is
    `deleteProfileCertification` (no `Form`), Featured is `profile.featured.link`/`.media.edit`.
    Capture what the client ACTUALLY sends; document any deviation explicitly.

## The capture pattern (copy this)
```python
import sys; sys.path.insert(0,'tools')
from capture_session import CaptureSession
import time, json
s = CaptureSession(new_tab=True)
s.nav("<detail page or edit URL>", wait=12); time.sleep(3)

# open the form (real mouse click, survives SDUI portals):
s.click_label("Kenntnis hinzufügen")        # or the button's aria-label/text
time.sleep(3)

# fill fields: focus via JS, then type via CDP (real keystrokes)
s.ev('''(()=>{const i=document.querySelector('input[aria-label*="..."]');i.focus();i.click();return 1;})()''')
s.type_text("APITEST 123")
time.sleep(2)
# pick a typeahead option if present:
s.ev('''(()=>{const o=document.querySelector('[role=option]');if(o)o.click();return 1;})()''')

# capture the SAVE request:
s.clear()
s.click_label("Speichern", contains=False)
s.pump(5)
muts = s.dump("SECTION ADD")               # prints endpoints + bodies
json.dump(muts, open('../local-captures/<section>_add.json','w'), ensure_ascii=False, indent=2)

# then EDIT and DELETE the same way, capturing each. Clean up. Verify.
s.close()
```

## What to record for each operation (the deliverable)
For **create / edit / delete** (and any sub-actions) of the section:
- Full URL (with `sduiid=` or `queryId=`).
- Exact request **body** with field names. **Flag whether field values are real literals or
  SDUI state-refs** (`{"key":"...","namespace":"MemoryNamespace"}`). This determines whether
  the op is browserless-replayable.
- HTTP method + any `x-restli-id` response header.
- The read-back endpoint (`fetchXCollection` / Voyager GET) so values can be pre-fetched.
- Which UI button (aria-label) triggers it.

## Browserless-replay note (the end goal)
The end goal is controlling LinkedIn WITHOUT a browser. An op is browserless-replayable only
if its body carries **real values** (like `languageId`, `body.text`), not `MemoryNamespace`
state-refs. Deletes usually carry real ids (✅). Creates via SDUI often use state-refs (need
the form). When you capture, **explicitly note** which category each op falls in. If a Voyager
equivalent exists (e.g. `identity/dash/profile<Section>`), test a raw `vgreq.post` and record
the status + required schema.

## Output
Write a markdown section per operation into the matching `docs/NN-*.md` and update
`docs/COVERAGE-MAP.md`. Commit + push with a clear message. Report exactly which endpoints
you verified, their browserless-replay status, and confirm cleanup.