# 20 — Contact info "Kontaktinformationen" (flow + field-map + save endpoint, all captured)

The contact-info editor (profile URL, email, phone, address, birthday, websites, IM). Reached
via the profile's **"Kontaktinformationen"** link → overlay → **"Kontaktinformationen
bearbeiten"** button. The flow, the **exact edit-modal field map**, AND the **save endpoint** are
all captured live on the stealth session (2026-07-12).

---

## Read — contact info overlay
The **"Kontaktinformationen"** link under the headline opens an overlay listing: profile URL,
website(s) (with labels like Blog/Portfolio), email, birthday. Alex's real values:
`linkedin.com/in/alex-rivera`, `github.com` (Portfolio), `example-user.github.io` (Blog),
`alex.rivera@example.com`, birthday (redacted).

> ⚠️ The legacy Voyager read-back `identity/profiles/{vanity}/profileContactInfo` is **gone**
> (verified `HTTP 410` this run); the dash `identity/dash/profiles?q=memberIdentity…` variants
> returned `400`/`500`. There is no known clean browserless GET for contact info right now — the
> authoritative current values come from the **edit-modal field state** (mapped below).

## ✅ Edit form — live field map (captured this run)
Open path (both survive the SDUI portal; use `contains=True`):
```python
s.click_label("Kontaktinformationen", contains=True)          # overlay
s.click_label("Kontaktinformationen bearbeiten", contains=True)  # edit modal
```
The modal's inputs render a beat AFTER the dialog appears — **poll** for `input[type=text]`
before reading (a same-tick query returns zero inputs; that was a false "field not found").

Modal fields **in DOM order** (ids are React `useId` `«rNN»` — **per-render, NOT stable**; locate
by order/label, never by id):

| # | element | role | value seen (Alex) | notes |
|---|---|---|---|---|
| 1 | `input[type=text]` | **Telefonnummer** | **`""` (empty)** | ← the safe test target |
| 2 | `select` | **Art der Telefonnummer** | (unset) | mobile / work / home |
| 3 | `textarea` | **Adresse** | `""` (empty) | 0/220 |
| 4 | `select aria="Monat"` | Geburtstag – month | `<MM>` | → (month, redacted) |
| 5 | `select aria="Tag"` | Geburtstag – day | `<DD>` | → (day, redacted) |
| 6 | `input[type=text]` | Website #1 URL | `https://github.com/example-user` | **REAL — do not touch** |
| 7 | `select` | Website #1 type | `WebsiteCategoryType_PORTFOLIO` | |
| 8 | `input[type=text]` | Website #2 URL | `https://example-user.github.io/` | **REAL — do not touch** |
| 9 | `select` | Website #2 type | `WebsiteCategoryType_BLOG` | |

Buttons: **Zurück** / **Speichern**.

**Capture-method note:** the phone `<input>` has **no `aria-label`** (its label is a separate
`<label for>` element), so an aria-based finder fails. Locate the phone field as the **first
`input[type=text]` in the dialog** — the one immediately preceding the phone-type `<select>`.
Alex has **no phone number**, so this field is empty and safe to write a test value into.

## ✅ Save endpoint — CAPTURED (2026-07-12, live click-and-record)

Captured in the click-and-record session (Alex drove: empty phone → test value → Speichern →
clear → Speichern; real fields untouched, phone confirmed empty after):

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileContactInfoForm
```
Screen: `com.linkedin.sdui.flagshipnav.profile.ProfileContactInfoAddForm`.
Payload fields (all **`MemoryNamespace` state-refs**, NOT literals):
`profileUrl`, `email`, `phoneNumber`, `phoneType`, `address`, `birthdayDay`, `birthdayMonth`
(and the website slots). Full schema in `docs/25-NETWORK-PROFILE-ACTIONS.md`.

> **Browserless-replayability:** because the values are `MemoryNamespace` refs (not literals),
> a pure-`requests` replay needs the form state seeded first (see `BROWSERLESS-REPLAY.md`); the
> **browser path is reliable today**. Same shape as the other profile forms (cf. docs/21 About).

**Verified safe:** tested with a throwaway phone number, then cleared — Alex's real contact info
(email, github/blog URLs, birthday (redacted)) never touched; phone confirmed empty after (browserless
`identity/dash/profiles` read shows no `phoneNumber` field).

## Reproduce (browser path)
```python
import sys, time; sys.path.insert(0, 'tools')
from capture_session import CaptureSession, browser_lock
with browser_lock():
    s = CaptureSession(new_tab=True)
    s.nav("https://www.linkedin.com/in/alex-rivera/", wait=12); time.sleep(2)
    s.click_label("Kontaktinformationen", contains=True); time.sleep(4)
    s.click_label("Kontaktinformationen bearbeiten", contains=True)
    # edit the FIRST input[type=text] (phone, empty), then click_label("Speichern", contains=False)
    s.close()
```
Never touch the website slots (#6–9) — those are Alex's real GitHub/blog URLs.

## Related, still open
- **Vanity/public URL** edit (`/public-profile/settings`) — separate flow, `identity/dash/profiles`
  seen on read; write not captured.
- **Manage email** / **add email** — separate sub-flow.
