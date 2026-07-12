# 21 — About / Summary "Info" (verified edit)

The profile **About/Summary** section (LinkedIn "Info"; the free-text blurb under the intro card,
plus its attached **top-skills** list). Captured live on the **stealth session** via
click-and-record, using a **minimal reversible change**: append one trailing space to Alex's
existing text, save, capture the endpoint, and confirm the stored text is unchanged. Alex's
About text was left **byte-identical** to its pre-edit state (SHA256 verified, see below).

> No `_writes/` artifact committed (gitignored); this doc is written from the captured request
> body reported live during the run. Raw capture kept locally at `/tmp/about_edit_capture.json`.

---

## Reach it

Profile page → **"Info bearbeiten"** (`aria-label="Info bearbeiten"`) pencil on the About card.
Opens a modal (SDUI screen `com.linkedin.sdui.flagshipnav.profile.ProfileAboutForm`) whose text
field is a **`contenteditable` div** (NOT a `<textarea>`) plus a re-orderable **top-skills** picker.
Buttons: **Verwerfen** / **Speichern**.

- Real click helper: `s.click_label("Info bearbeiten", contains=False)`.
- Caret-to-end + one keystroke to dirty the form:
  ```js
  const ce=document.querySelector('[contenteditable=true]');
  ce.focus();
  const r=document.createRange(); r.selectNodeContents(ce); r.collapse(false);
  const sel=getSelection(); sel.removeAllRanges(); sel.addRange(r);
  ```
  then `Input.insertText " "` → **Speichern** enables (`disabled:false`).

**No network-share toggle** exists on this form — editing About does **not** post to the feed
(unlike some section adds). The `Beiträge/Kommentare/Bilder` checkboxes seen on the page are the
Featured-activity filter in the background, not part of this modal. Nothing to turn off.

---

## ✅ Save About — `saveProfileAboutForm` (standard naming)

```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.requests.profile.saveProfileAboutForm
```

Request body (`serverRequest.requestedArguments.payload`) — all field values are **state-refs**;
the real values ride in the **top-level `states[]`** array (the browserless-replay pattern):

```jsonc
payload: {
  "about":         {"key":"about<AUTO>AboutForm","namespace":"MemoryNamespace"},          // → states[] real text
  "skills":        {"key":"<AUTO>AboutForm…skillIdsBinding","namespace":"MemoryNamespace"},// → states[] real skill ids
  "initialAbout":  {"key":"initialAbout<AUTO>AboutForm","namespace":"MemoryNamespace"},    // → states[] pre-edit text
  "initialSkills": {"key":"initialSkills<AUTO>AboutForm","namespace":"MemoryNamespace"},   // → states[] pre-edit skill ids
  "progressIndicator":{"key":"isActiveProfileFormLoadingProfileEditForm","namespace":"MemoryNamespace"},
  "hasChanges":       {"key":"isActiveProfileFormHasChangesProfileEditForm","namespace":"MemoryNamespace"},
  "profileId":  "OWNER_PROFILE_ID",   // ← real literal
  "vanityName": "alex-rivera",                            // ← real literal
  "premiumUpsellEligible": true,
  "hasAtLeastOneTopSkillLackingAssociations": true
}
```

**Top-level `states[]`** (4 entries — the replay-friendly literals):

| state key (suffix) | value | proto case |
|---|---|---|
| `about…AboutForm`        | **the About text** (real string, `\n\n` paragraph breaks) | expression |
| `…skillIdsBinding`       | `["ProfileSkill:ID1","ProfileSkill:ID2","ProfileSkill:ID3","ProfileSkill:ID4","ProfileSkill:ID5"]` | expression |
| `initialAbout…AboutForm` | pre-edit About text (for change diffing) | — |
| `initialSkills…AboutForm`| pre-edit skill id list | stringListValue |

- `about` and `skills` are the **new** values; `initialAbout`/`initialSkills` are the pre-edit
  values the form carries so the server can diff. The `<AUTO>` segment is a per-open uuid
  (`auto-binding-<uuid>`), so it must be read from the live form, not hard-coded.
- `requestedStateKeys` lists those same four keys (`$case:"id"`).
- **No `x-restli-id`** on the response; the two follow-up
  `actions/component?componentId=…aboutTopLevelSection` / `…skillsTopLevelSection` POSTs just
  re-render the profile card after the save.
- Modal closes on success (no confirm dialog).

### Edit vs. add
About is **not a list section** — every profile has exactly one About. So there is no
add/delete; `saveProfileAboutForm` is always an **edit/replace** of the single blurb (+ its top
skills). There is **no `isEdit` discriminator and no `aboutId`** — identity is the profile itself
(`profileId` + `vanityName`).

---

## ⚠️ Trailing-whitespace is trimmed on serialize (capture-method note)

The reversible change here was **append one trailing space → save**. Observed: the value the form
**sent** in `states[]` was **byte-identical to `initialAbout`** — no trailing space — i.e. the
About form **strips trailing whitespace when it serializes the `contenteditable`**. So the single
save persisted Alex's text unchanged; the planned *"remove the space and save again"* second
pass was **unnecessary** (there was nothing to undo — the space never left the browser).

Implication for a real edit: send the exact final text you want; do not rely on trailing spaces
surviving. Leading/interior whitespace and the `\n\n` paragraph breaks **are** preserved.

---

## Verification — byte-identical, triple-checked

Alex's About = *"<the owner's real About/summary text>"* (redacted — real profile content)

| check | value |
|---|---|
| Voyager `summary` **before** edit | <N> chars · SHA256 `<hash>` |
| `about` value **sent** on save (states[]) | byte-identical to `initialAbout` · SHA256 `<hash>`¹ |
| Voyager `summary` **after** edit | <N> chars · SHA256 `<hash>` — **identical to before** ✅ |
| tail | `…nicht in Tickets.` — no trailing whitespace ✅ |

¹ The `29bddf63` (Voyager read) and `6a02a68d` (form state) hashes differ **only** because the
legacy Voyager `summary` GET **collapses the `\n\n` paragraph breaks** into nothing, while the
SDUI form state preserves them (1804 chars w/ breaks vs 1798 without). Both are internally stable
and unchanged across the edit. The form-state value is the authoritative on-wire representation.

**Cleanup:** nothing to clean — the mutation was a no-op by construction. Confirmed by an
independent post-run Voyager read (SHA matches the pre-run read exactly) and by re-opening the
form (`Verwerfen` closed with no unsaved-changes confirm, i.e. the field was not dirty).

---

## Read-back
- **Voyager (browserless):** `identity/dash/profiles?q=memberIdentity&memberIdentity=<vanity>`
  `&decorationId=…FullProfileWithEntities-101` → `summary` field (HTTP 200). ⚠️ collapses `\n\n`.
- **SDUI (authoritative text, with paragraph breaks):** the `saveProfileAboutForm` / the form's
  seeding `component` call carry `initialAbout` in `states[]`.

## Browserless-replay status
| Op | Endpoint | Body carries | Browserless |
|---|---|---|---|
| Edit About (+top skills) | `saveProfileAboutForm` | **real About text + skill-id literals in `states[]`** (auto-binding uuid key), real `profileId`/`vanityName` | 🔬 same family as `saveProfileLanguageForm` (create proven browserless in docs/BROWSERLESS-REPLAY.md). Replayable if you (a) mint the `auto-binding-<uuid>` key set and (b) send both `about` and `initialAbout` — not separately re-verified here. |

The single friction for a pure-`requests` replay is the per-open `auto-binding-<uuid>` in every
state key; capture it from one live form open, or reuse the form's seeding `component` response.
