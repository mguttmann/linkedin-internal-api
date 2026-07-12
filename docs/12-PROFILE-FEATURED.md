# 12 — Featured / "Im Fokus" (add + edit + delete mapped; raw capture not persisted)

The **Featured** section (the showcase links/media on the profile,
`/in/<vanity>/details/featured/`). Driven live on the owner's own profile: a test link
(`en.wikipedia.org/...API`) was added → edited → deleted; profile reported clean afterwards
(`hasMark:false`). **Featured does NOT use the `saveProfile<Section>Form` pattern** — it has its
own `com.linkedin.sdui.profile.featured.*` family and a two-step add flow.

> **⚠️ Provenance:** there is **no capture artifact for Featured** in the local captures
> (no `featured*.json`; nothing referencing `profile.featured` in any persisted capture or in
> `data/endpoints_*.json`). This doc is written from endpoint/body details reported during a
> live run whose raw capture was **not persisted** (same situation as docs 19/20/21). Treat the
> endpoints below as **mapped from a live run, not artifact-verified** — re-capture to confirm.

---

## Add a featured LINK (two-step flow) — mapped (raw capture not persisted)

**Step 1 — URL preview / ingest.** Typing the URL + "Hinzufügen" fires a `component` call
that ingests the URL and returns an **`ingestedContentId`** plus auto-filled
title/description/thumbnail:
```
POST /flagship-web/rsc-action/actions/component?componentId=com.linkedin.sdui.generated.profile.dsl.impl.urlPreview&sduiid=…
Body: {"clientArguments":{"payload":{"componentData":{"inputUrl":{…"value":{"key":"linkFormUrl…","namespace":"MemoryNamespace"}}…}}}}
→ returns ingestedContentId (e.g. CONTENT_ID) + preview metadata
```

**Step 2 — Save.** "Speichern" POSTs the featured-link create:
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.profile.featured.link
Body: {
  "requestId":"com.linkedin.sdui.profile.featured.link",
  "serverRequest":{…"payload":{
     "profileId":"<ME>",
     "title":       {state-ref …-mediaTitle},
     "description":  {state-ref},
     "ingestedContentId":"CONTENT_ID",   ← real literal, from step 1
     "assetUrns":[…],
     "vanityName":"alex-rivera"
  }},
  "states":[ … real values e.g. {"value":"API - Wikipedia", …} … ]
}
```
- **Verified:** the featured link appeared on the profile. ✅
- **Browserless:** the real title/description ride in top-level `states[]`; the
  `ingestedContentId` is a real literal but must first be obtained from the step-1 preview
  call. So a browserless add = preview POST (to get the id) → link POST. 🔬 (two-step, id
  dependency — same states[] mechanism as other forms).

---

## Edit a featured item — mapped (raw capture not persisted)

Even a **link** is edited through the generic "featured **media**" edit form
(`screenId: ProfileEditFeaturedMediaForm`):
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.profile.featured.media.edit
Body: {…"payload":{
   "profileId":"<ME>",
   "mediaId":"MEDIA_ID",          ← real literal (distinguishes edit)
   "title":        {state-ref},
   "description":  {state-ref},
   "mediaAssetUrns":[…],
   "isLink":true,
   "vanityName":"alex-rivera"
}, "states":[ {"value":"API - Wikipedia EDITED", …} ]}
```
- **Verified:** the title changed live. ✅
- `mediaId` is the featured item's real id; `isLink:true` marks it as a link vs. uploaded media.

---

## Delete a featured item — mapped (raw capture not persisted)

Like edit, delete goes through the generic **featured media** family
(`com.linkedin.sdui.profile.featured.media.delete`). Driven live: a fresh test link was
added → deleted → profile reported clean (`hasMark:false`).
```
POST /flagship-web/rsc-action/actions/server-request?sduiid=com.linkedin.sdui.profile.featured.media.delete
Body: {
  "requestId":"com.linkedin.sdui.profile.featured.media.delete",
  "serverRequest":{…"requestedArguments":{"payload":{
     "profileId":"<ME>",                    ← real literal
     "mediaId":"MEDIA_ID",             ← real literal (the featured item's id)
     "vanityName":"alex-rivera",         ← real literal
     "isLoading":{"key":"featured-deleted<uuid>","namespace":"MemoryNamespace"},  ← UI loading state-ref (ignorable)
     "navigateBack":false
  }}},
  "states":[]                                ← empty (no form values needed)
}
```
- **HTTP:** `POST` (SDUI server-request; no `X-RestLi-Id` on the response).
- **UI trigger:** the item's **"Löschen"** button — `aria-label="<title> löschen"` (e.g.
  `"API - Wikipedia löschen"`), which sits at the bottom of the item's edit/overflow panel next
  to "Speichern". Clicking it fires the delete directly (**no separate confirm dialog** — the
  DELETE POST goes out on that single click). After it, the client refreshes the section via the
  `featuredTopLevelSection` / `featuredDetailsSection` `component` calls + the `…pagers.profile.details.featured`
  pagination read.
- **Verified:** the link disappeared from the profile; browser-render check `hasMark:false`. ✅
- **Browserless:** ✅ fully replayable. The payload carries **real literals** only
  (`profileId`, `mediaId`, `vanityName`); `states[]` is empty and `isLoading` is just a UI
  loading-flag state-ref that can be dropped. You only need the target item's `mediaId` first —
  fetch it from the read-back pager below (or it's the same `mediaId` used by the edit form).

---

## Read-back
`POST /flagship-web/rsc-action/actions/pagination?sduiid=com.linkedin.sdui.pagers.profile.details.featured`
(`{vanityName, start, count, profileId}`) — lists the featured items.

## Still to capture (featured)
- Add featured **post** (your own update) vs. link vs. **media upload** (image/doc) ⏳
- **Reorder** featured items ⏳