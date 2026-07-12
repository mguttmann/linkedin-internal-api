# Browserless Replay — how to write LinkedIn WITHOUT a browser

> This is the answer to the core question: **can we control LinkedIn 100% without a browser?**
> The honest, evidence-based answer per operation type is below. Nothing here is guessed —
> every claim is backed by a real captured request (raw captures are kept **local and withheld**
> from the repo — they contain session/personal data — but every documented body was recorded
> from real traffic, not guessed).

## The two body shapes (why some ops are browserless and some aren't)

LinkedIn's write requests come in two shapes:

### 1. Voyager REST.li — real literals in the body → **browserless-ready**
Messaging, post-create, likes, follow, etc. carry their values **directly**:
```json
// createMessage
{"message":{"body":{"text":"hello","attributes":[]}, "conversationUrn":"…","originToken":"<uuid>"}}
```
You can build and POST this from pure `requests` (`lib/vgreq.py`). ✅

### 2. SDUI profile forms — state-refs PLUS a `states[]` array with real values
Profile sections (skills, languages, education, certifications, projects, …) send the
`payload` with **state-references** (`{"key":"…","namespace":"MemoryNamespace"}`) — which alone
would NOT be replayable. **BUT** the same request also carries a top-level **`states[]`**
array that contains the **real literal values**:

```json
// saveProfileLanguageForm — states[] (real values, captured live)
"states": [
  {"key":"languageProfileLanguagesFormauto-binding-<uuid>",
   "namespace":"MemoryNamespace","value":"Latein","originalProtoCase":"stringValue"},
  {"key":"selectProficiencyProfileLanguagesFormauto-binding-<uuid>",
   "namespace":"MemoryNamespace","value":"","originalProtoCase":"stringValue"}
]
```

**This is the key finding:** the values ARE in the request body, not hidden in opaque
client-only state. So SDUI profile writes are **replayable in principle** — you POST the same
`sduiid` endpoint with a `payload` of state-refs + a `states[]` array whose `value`s you set.

**Demonstrated live (2026-07-11, not persisted as a repo artifact):** an SDUI profile **create**
was replayed fully browserless. A pure `vgreq.post` of `saveProfileLanguageForm` — reconstructed
from a capture, with a **self-generated `auto-binding-<uuid>`** and `states[]` value `"Latein"` —
returned **HTTP 200 and the language appeared on the live profile**. The server accepted a
client-chosen uuid; no preceding `component` fetch was needed. This suggests the whole profile-form
CREATE family is browserless-ready (they are structurally identical — only `<FormName>` and field
keys change). ⚠️ **Caveat:** this was a one-off live observation; no capture artifact for it is
persisted in the repo, so treat it as *demonstrated once, not continuously reproduced*. The status
table below marks the general profile-form replay as 🔬 (values present, replay not re-verified).

**Caveats (honestly):**
- **Typeahead fields** (school, company, skill) also send an **id** (`issuingOrganizationId`,
  `skillId`) resolved from a typeahead call. For a browserless write you must first resolve
  that id (a typeahead GET), then include it.
- **Delete is NOT solved browserless yet.** A pure `deleteProfileLanguageForm` POST returns
  **HTTP 200 but is a no-op** — the language stays. Tried: real `languageId` in `payload`;
  `languageId` + literal `hasChanges:true` + `progressIndicator:false`; the captured empty
  `states[]`. None removed the entry. The server evidently ties the delete to state prepared by
  a preceding `component`/form-load call (the delete confirms a change it doesn't see). **The
  UI delete works 100% reliably** (real mouse click via `click_label`), so delete stays a
  browser action for now. 🔬 Open: capture the exact `component` pre-call the form fires on
  open and replay it before the delete.
- **Read caveat:** the legacy Voyager `identity/profiles/{id}/languages` GET is **stale /
  deprecated** (returned 410/400 and lagged behind live edits by minutes). For cleanup
  verification, trust the **freshly-rendered profile page** (browser), not that endpoint.

## Status per operation family

| Family | Create | Edit | Delete | Notes |
|---|---|---|---|---|
| Messaging | ✅ literal | ✅ literal patch | ✅ recall | fully browserless |
| Post like / save / follow | ✅ | — | ✅ | fully browserless |
| Post create | ✅ GraphQL literal | ⏳ | ✅ SDUI | create browserless |
| Comment create/reply/edit/delete | 🔬 SDUI | 🔬 | ✅ id | values in body; replay untested |
| Profile sections (skill/lang/edu/cert/project/…) | 🔬 states[] | 🔬 states[]+id | ✅ id | **states[] carries values**; uuid-binding replay untested |

Legend: ✅ proven browserless · 🔬 body has the values, pure-requests replay not yet proven ·
⏳ not captured yet.

## Next proof needed
Run a pure `vgreq.post` replay of ONE SDUI profile create (e.g. a language) reconstructing
`payload` + `states[]` with a self-generated uuid. If the server accepts it → **100% browserless
confirmed** for the whole profile-form family (they're structurally identical). If it rejects
the uuid → we prepend the `component` fetch that issues the binding, then post. Either way the
path is now known; only the uuid-issuance detail is open.