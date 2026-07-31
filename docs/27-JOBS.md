# Jobs reads — `get_job` and `get_job_recommendations`

Two **read** tools for the jobs domain: one job posting by id, and LinkedIn's own
recommendation feed for the owner. Browserless (pure `requests` through `vgreq`), no confirm
gate — reads never get one — and registered on the READ side of the read-only split
(`mcp/tests/test_readonly.py`).

**Status of this document (updated 2026-07-30 by the owner's live run against commit `5a251da` —
provenance and its scope: `STATUS-MATRIX.md`, legend entry "(owner-run)").** The picture is no longer
uniform, so read the three lines separately:

- **`get_job` is ✅ live-verified**, on two paths: **HTTP 200** for a real job id with the flat
  projection holding up on real data, and **HTTP 404** for an invented one with an honest error that
  keeps the requested `job_id`. That is the 404 path only — the id-**mismatch** abort was *not*
  exercised and stays fixture-proven.
- **`get_job_recommendations` is ✅ only for its honesty**: on a live 200 without a findable container
  it reported `state: "unknown"`, not `empty`. The **endpoint** is a different matter — it answered but
  yielded no usable jobs, so it is **not verified usable** and stays open pending a capture of the raw
  body.
- **Everything else below is still offline evidence**: the identity table, the state table beyond
  `unknown`, the container-selection rules, the description cut with its `description_truncated` flag
  and every `company`-join case — the reference join and the sole-company fallback alike — are proven
  against **synthetic fixtures** only.

The offline suite is green; what that green covers is listed under "What is proven, and how", what the
live run added is in its own subsection there, and what neither covers is under "Open, not accepted".
Do not read this file as a release note.

---

## 1. The two routes

### 1.1 One job posting — legacy REST, not dash, not GraphQL

```
GET /voyager/api/jobs/jobPostings/<jobId>
    ?decorationId=com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65
```

Evidence: **executed live by the owner on 2026-07-30, HTTP 200** — through this very tool, not merely
captured from traffic. That makes the route **✅ verified** for the read path. The decoration id and the
path live in `mcp/lib/client.py` (`LinkedInClient._JOB_POSTING_DECO`, used in
`LinkedInClient.get_job`). A non-existent id on the same route answered **HTTP 404** and produced the
tool's honest error branch.

Three different resources exist for job postings and they are easy to confuse. This tool uses the
**first** one:

| Route | Used here |
|---|---|
| `voyager/api/jobs/jobPostings/<id>` (legacy Rest.li) | **yes** — the measured one |
| `voyagerJobsDashJobPostings` (dash resource) | no |
| `/voyager/api/graphql` (…job posting queries) | no |

Fields the capture delivered: `title`, `formattedLocation`, `formattedEmploymentStatus`,
`employmentStatus`, `workRemoteAllowed`, `applies`, `views`, `listedAt`, `description`
(Attributed Text, **not** a string), `salaryInsights`. The **employer name is not in `data`** —
it sits in `included[]` at the entry whose `$type` ends in `Company`.

### 1.2 The recommendation feed — GraphQL

```
GET /voyager/api/graphql?includeWebMetadata=true&variables=(count:<n>,start:0)
    &queryId=voyagerJobsDashJobsFeed.<hash>
GET /voyager/api/graphql?includeWebMetadata=true&variables=(paginationToken:<urlencoded>)
    &queryId=voyagerJobsDashJobsFeed.<hash>          # cursor variant
```

Both variants are in the endpoint catalogue (`data/endpoints_voyager.json`, section
`voyagerJobsDashJobsFeed`) with a captured response of ~110 KB. The hashes are held as
`LinkedInClient._JOBS_FEED_QID` and `_JOBS_FEED_PAGE_QID`.

**Live status (owner's run, 2026-07-30): this route answered HTTP 200 — and delivered nothing this
repo could read.** The tool reported `state: "unknown"` (see §4, "What the live run added"). So the
route is executed but **not verified usable**, and the next step is a capture of the **raw** body, not
a parser change.

**Not this route, and not to be confused with it:** the owner separately probed a REST-like form,
`voyagerJobsDashJobsFeed?decorationId=com.linkedin.voyager.dash.deco.jobs.JobsFeed-2&count=5&q=jobsFeed&start=0`,
and measured **HTTP 400** with a 14-byte body. Useful to know about *that* form; it says nothing about
the GraphQL route above, which the tool exclusively uses (`mcp/lib/client.py`,
`get_job_recommendations` — the URL is built from `_JOBS_FEED_QID` / `_JOBS_FEED_PAGE_QID` and no
`decorationId`/`q=jobsFeed` variant is ever sent) and which answered 200 in the same run.

**Re-capture path:** `queryId` and `decorationId` hashes rotate with LinkedIn deployments. When a
call answers 4xx, re-grab the request with `tools/crawl_recursive.py` and update the two constants
in `mcp/lib/client.py`; the error `note` of both tools says so at runtime.

---

## 2. What the tools return

### `get_job(job_id, description_chars=4000)`

`job_id` accepts an int, a numeric string, `urn:li:fsd_jobPosting:<id>`,
`urn:li:jobPosting:<id>` and a full `linkedin.com/jobs/view/…-<id>/` URL
(`jobs_parse.normalize_job_id`). Unusable input returns an honest error dict
**without any HTTP call** and without a traceback. A URL that names **two different** job ids at
identifying positions (`/jobs/view/<a>/?currentJobId=<b>`) is **refused**, not resolved by
precedence: the hard abort has to hold on the input side too, where the body-id guard can no longer
see the divergence — the body would agree with the wrongly chosen id.

Success shape (flat): `status`, `ok`, `job_id`, `url`, `title`, `company`, `location`,
`employment_status`, `remote_allowed`, `listed_at`, `applies`, `views`, `salary`,
`salary_present`, `reposted`, `description_text`, `description_truncated`.

Rules that the projection follows (`jobs_parse.project_posting_fields`):

- **`url` is always built from the requested, normalized id** — `…/jobs/view/<job_id>/`
  (`jobs_parse.job_url`). Never from an id found in the response body.
- **Unknown is not false.** `remote_allowed`, `applies`, `views`, `salary` and `reposted` are
  `null` when they were not read.
- **`salary_present`** separates "salary exists but is not projectable" from "no salary". The
  shape of `salaryInsights` is not captured, so `salary` may stay `null` while `salary_present`
  is true.
- **`reposted`** is parsed defensively: the capture shows the string `"True"`/`"False"`, not a
  JSON boolean, so `if value:` would be true for `"False"`. `jobs_parse.tri_bool` yields a real
  boolean or `null`.
- **Attributed Text is extracted, never `str()`-ed** (`jobs_parse.attributed_text`): strings,
  dicts, `None` and nested forms are tolerated with a depth limit, and a Python repr can never
  reach the caller. `description_text` is cut to `description_chars` with
  `description_truncated` telling you so; the budget is clamped to a ceiling and the clamp is
  reported in `note` (`jobs_parse.effective_description_chars`).
- `listed_at` is passed through **unchanged**. The unit (epoch milliseconds) is inferred, not
  captured — do not treat it as documented.

**The identity check (the point of this tool).** `jobs_parse.read_job_posting` compares the job id
carried by the read entity with the requested one. The id is read only at *identifying* positions,
and the key test is **exact**, not a suffix or substring test — the exact names are
`entityUrn`, `objectUrn`, `jobPostingUrn`, `trackingUrn`, `jobPostingId`, `jobId`
(`jobs_parse._ID_URN_KEYS` / `_ID_NUMERIC_KEYS`). That boundary matters in both directions: a
reference to *another* job (`similarJobPostingUrn`, `relatedJobPostingUrn` — one ends in
`jobpostingurn`, the other contains `jobposting`) must not abort a correct read, and a reference
carrying the *requested* id must not mask a diverging real `entityUrn`.

**Every** identifying position is collected, never the first one found
(`jobs_parse.identifying_job_ids`), so no verdict depends on the order in which LinkedIn
serialised its keys:

| `identity` | meaning | result |
|---|---|---|
| `match` | all identifying positions name exactly the requested id, and content was read | `ok=True` |
| `mismatch` | a **different** id, or two identifying ids that disagree with each other | `ok=False`, no fields, **no `url` at all** |
| `absent` | no identifying id anywhere | `ok=False` — nothing proves this body is that job |
| `ambiguous` | several `included[]` entities claim the requested id **and** carry content | `ok=False` — which one is the posting is not decidable |
| `match`, but nothing readable | the body identifies the job and not one content field could be read | `ok=False`, `read_fields=[]` — "could not read" is not "a posting without details" |

A mismatch is a **hard abort by instruction of the repo owner**: not corrected, not warned about,
and no field of the foreign job leaves the function. The reason: a corrected id would hand a
caller a link to a different job than the one it just judged. A body that contradicts *itself*
counts as a mismatch, because resolving it would mean guessing.

### `get_job_recommendations(count=20, pagination_token="")`

Returns `status`, `ok`, `state`, `count`, `results`, `read_entries`, `discarded`, plus
`paging_total` and `pagination_token` for the next page. Each card is flat: `job_id`, `url`,
`title`, `company`, `location`, `remote_allowed`, `listed_at`, `reposted`, `salary`,
`salary_present`. Duplicate ids are collapsed. A non-positive / non-numeric `count` is refused
**without any call**.

`state` exists so that an agent can tell an **answer** from a **failure**:

| `state` | meaning | `ok` |
|---|---|---|
| `hits` | the read container held entries and at least one projected | `True` |
| `empty` | the read container **itself** held no entries, and no candidate's `paging.total` contradicts that | `True` |
| `unknown` | no container was found — we could not read. **Not** "no jobs" | `False` |
| `ambiguous` | more than one candidate container holds entries; which one is the jobs collection is not decidable, so **none** is read | `False` |
| `drift` | the container (or a candidate's `paging.total`) says there are jobs, but not one entry was projectable | `False` |

Every non-`hits`/`empty` state carries a `reason` naming the re-capture path.

**`read_entries` / `discarded` are the balance against the raw list.** `read_entries` is the raw
length of the container's `elements`; `discarded` counts those that could not be projected. The
verdict *and* the balance are computed on the raw list, never on the projectable subset — filtering
first is what once let a container of three URN strings report "an empty page". A partial loss keeps
`ok=True` (the read did happen) but always names itself in `reason` / the tool's `note`, so a
genuine one-card page stays distinguishable from a three-card page that mostly failed to parse.

---

## 3. Why the reading code is shaped this way

An earlier attempt at these same two tools was handed back for two **reproduced false
successes**. Both classes are what the design above exists to prevent:

1. **The witness was not bound to what was read.** A helper counted every `elements` list
   anywhere in the body and took that as proof "the body was a job collection", while the reader
   read at a different root. A canonical Rest.li collection with three real cards therefore came
   out as `ok=True, count=0` with the note "a genuinely empty page" — and a test pinned that wrong
   rule. Consequence for this version: `jobs_parse.read_job_collection` reads **one** container
   node and takes hits, `paging.total` (`jobs_parse.paging_total`) and the cursor
   (`jobs_parse.find_pagination_token`, which does **not** descend into `elements` — a token
   hanging off a card is that card's tracking payload) out of **that same node** — one traversal,
   not two. `paging.count` is deliberately not read: it echoes the page size *we* sent and proves
   nothing about the server's answer. `included[]` is skipped as a container candidate — it is the
   entity pool, not the result list.
2. **`get_job` had only a quantitative witness** (how many fields carried content) and never an
   identifying one, and a divergent body id silently overwrote the caller's, `url` included. Hence
   the identity table above.

A third rule was added after the first fix round, because rules 1 and 2 do not bite without it:
**every derived value is a function of the complete node, and ambiguity or loss has a state.** A
verdict computed on a *reduction* of what was read — a filtered list, the first matching key, the
first of several candidates — is the same unbound claim one level deeper, and each of those three
reductions had produced its own false success. So container candidates
(`jobs_parse.find_collections`, all of them), identifying ids, company references and pagination
tokens are each collected over **all** candidate positions of the node and then passed through one
chokepoint (`jobs_parse._distinct`): exactly one distinct value is an answer, two are
`ambiguous`/`mismatch`, zero is `absent`/`unknown`. There is no "first one wins" and no verdict may
depend on JSON key order — LinkedIn's serialisation order is not a fact this repo controls.

Container **selection** follows from that rule and lives in exactly one place,
`jobs_parse._select_collection` — used by `read_job_collection` and by the standalone
`jobs_parse.find_collection`, so the two can never disagree about one body (the rule used to be
written twice, which is how two verdicts on the same body drift apart). The rule: the sole candidate
that actually holds entries is the read container; if none holds any, the shallowest is read (there
is nothing anywhere to confuse); more than one filled candidate is `ambiguous` and **none** is read.

What the candidate *search* may hide is part of that rule, and the asymmetry is load-bearing
(`jobs_parse.find_collections`): a candidate whose `elements` list **holds entries** is not
descended into, because a nested `elements` list is then that container's own card content (a card's
insight list) — but a candidate whose `elements` list is **empty** is kept as a candidate *and*
searched further, only the empty `elements` value itself is never entered. An empty container hides
nothing, so the reason for stopping ("it would be card content") has no content to protect. Without
that asymmetry an outer node carrying `elements: []` swallowed a filled container nested beneath it
and `state="empty"` was claimed over readable cards — the handed-back false-success class in
parent/child form.

Additional invariants: "empty" may only be claimed because it was **read** (a missing container is
`unknown`, never `empty`), and a `paging.total > 0` next to an empty hit list is an error, not an
empty list. The company name is a **join** on a reference the read entity itself carries, at any
depth, not a pick from the entity pool (see the next section).

---

## 4. What is proven, and how

### 4.0 What the live run added (owner-run, 2026-07-30 against `5a251da`)

This is the **only** live evidence in this document. It covers three things and not a millimetre more.

**(a) `get_job` end to end — HTTP 200.** The legacy Rest.li route answered 200 and the projection held
on a real body. What the values prove, quoted only where the value carries the proof (a public advert
of a real employer; no further detail, no personal data):

- `company` came back **filled** (`Dräger`) — the employer name was resolved out of `included[]` on a
  real body. **Which of the two branches produced it is not decidable from this run:** the reference
  join, or the sole-company fallback that applies when the entity references nothing resolvable and
  the pool holds exactly one company (`jobs_parse._company_name`). The returned value carries no
  marker of its branch, and the owner reported only the name. So the *reference path* against a real
  body stays **unproven**; both branches remain fixture-proven only.
- `description_text` was **Attributed Text, cleanly extracted, with no `str()`/repr artefact**. Its
  length equalled the character budget of that run. That alone does **not** show the cut applied: a
  text exactly as long as the budget comes back whole with `description_truncated=False`
  (`jobs_parse.job_fields`). The owner reported `description_truncated` as *present*, without its
  value, so **truncation itself is not live-evidenced** — it stays fixture-proven.
- `employment_status` and `location` were filled with plain strings — no stringified enum object.
- `remote_allowed: false`, `applies: 0`, `views: 0` were **read**, not left `null`; `salary: null`
  arrived next to the separate `salary_present` key, which is exactly the two-way split §2 describes.
- the `reposted` key was **present** in the answer — the reposting warning signal the owner wanted.
- `listed_at` came back as a 13-digit integer, consistent with epoch milliseconds. The **unit remains
  inferred**: a plausible magnitude is not documentation.
- `endpoint` (`voyager.jobs.jobPostings.get`) travels in the answer, so a caller can record which route
  verified a job.

**(b) The 404 path of `get_job` — HTTP 404.** An invented id produced `ok: false` with an honest error,
and the **requested** `job_id` stood unchanged in the answer: no silent failure, no empty success, no
id overwritten by the response. **This is the 404 path, not the id-mismatch path.** A body carrying a
*different* id than the requested one cannot be provoked without a prepared response, so the hard
mismatch abort remains proven by fixture only — the owner states that limit himself.

**(c) The honesty of `get_job_recommendations` — and only that.** The GraphQL feed route answered
**HTTP 200**, but no collection container was findable under `data`, and the tool reported
`state: "unknown"`, `count: 0`, `read_entries: 0`, `paging_total: null`, `ok: false` with the
re-capture note. It did **not** report `empty`. That is the direct counter-proof to the false success
which caused the first hand-back: the earlier version would have answered
`ok=True, count=0, "a genuinely empty page"` on this very body. **What this does not prove:** that the
endpoint is usable. It answered and delivered no readable jobs, and the **raw body was not kept** —
without it, "the response shape drifted (another container key)", "the feed was empty or not entitled"
and "an in-band error arrived with a 200" are all still open. The tool is verified honest; the endpoint
is not verified usable (`BACKLOG.md`).

### 4.1 Proven offline

**Proven offline, by passing tests** — `mcp/tests/test_jobs_parse.py` (pure parsers) and
`mcp/tests/test_client.py` (route, URL, argument pass-through against a fake transport):

- the request URL of both routes, including the decoration id and both feed `queryId`s, and that
  the cursor variant is used exactly when a `pagination_token` is passed;
- every documented `job_id` input form; that unusable input and a useless `count` send nothing at
  all; and that a URL naming two different job ids is refused instead of resolved by precedence;
- the hard abort on an id mismatch: requested id kept, no `jobs/view` link anywhere in the
  result, no field of the foreign job in the result; and the `absent` case reported as such;
- **order-invariance of the identity verdict**: two conflicting identifying ids are a mismatch in
  every key permutation, and a reference key (`similarJobPostingUrn`, `relatedJobPostingUrn`) is
  never an identity — in neither direction (it does not fake a mismatch, and it does not mask one);
- a posting entity living in `included[]` is read, not reported as contentless; an identified body
  without a single readable field is `ok=False`; two `included[]` entities claiming the requested
  job are `ambiguous`, not a pick;
- a body without an identifying id, a non-200, a 200 carrying an error envelope
  (`jobs_parse.inband_error`) and a non-JSON body are all honest failures;
- Attributed Text extraction incl. depth limit and "never a Python repr";
- `"False"` as a string is not truthy after `tri_bool`;
- unknown flags/counters stay `null`; `salary_present` distinguishes the two salary cases;
  an enum-ish `employmentStatus` object is never stringified;
- description truncation, the flag, and the clamp sentence;
- container selection by **shape and evidence** (an aliased GraphQL container is found; `elements`
  inside `included[]` is not the read container; the shallowest candidate is read only when no
  candidate holds entries; two filled candidates are `ambiguous`, not a choice);
- **an empty container cannot make a filled page look empty** — neither as a sibling
  (`test_an_empty_sibling_container_cannot_make_a_filled_page_look_empty`) nor as the **parent** of
  the filled one (`test_an_empty_outer_container_cannot_hide_a_filled_one_nested_below_it`, over
  both key orders, and `test_an_empty_outer_container_without_paging_still_finds_the_nested_cards`),
  while a **filled** container's own `elements` value is still never entered
  (`test_a_filled_elements_list_is_still_not_descended_into`, an insight list inside a card);
- the hard abort also holds at the **discarded wrapper level**: a diverging id on the outer `data`
  node aborts even though the read content sits on the inner one
  (`test_a_diverging_id_on_a_discarded_wrapper_still_aborts_hard`), and a wrapper carrying **no** id
  does not abort a correct nested read
  (`test_a_wrapper_without_an_id_does_not_break_a_correct_nested_read`);
- `empty` only for a container that was read empty (with and without `paging`), `unknown` when
  there is no container, `drift` when the entries carry no identifying id — including a container
  of URN strings, which is **never** an empty page — or when `paging_total > 0` yields no hits;
- partial loss is named: `read_entries` / `discarded` balance against the raw container and the
  `reason` says how many entries were dropped;
- `paging_total` is read from the chosen container only, and a `paginationToken` hanging off a card
  is not returned as the page cursor (two different container tokens yield no cursor at all);
- the company name is **joined on the reference the body itself carries**, nested reference
  included; a card reports no company it cannot join; an unjoinable posting next to several
  companies and two conflicting company references both report no employer;
- duplicates collapsed, limit applied.

**Registration:** `mcp/tests/test_server.py` asserts both tools exist, and
`mcp/tests/test_readonly.py` asserts they are on the READ side — unaffected by
`LINKEDIN_READ_ONLY=1` and ungated.

**Not proven, and it matters:**

- **Live evidence covers exactly the three items in §4.0 and nothing else.** Every other statement in
  this document is "the request we would send" and "how we parse a body of that shape". In particular:
  the **id-mismatch abort**, the `ambiguous` / `drift` / `absent` states, every container-selection rule
  and every negative `company`-join case were **not** exercised live.
- **The fixtures under `mcp/tests/fixtures/` are synthetic and PII-free.** They prove the parser
  logic only — they are **not** evidence of LinkedIn's response form. Where a real body differs,
  the honest failure states (`unknown`, `drift`, `absent`) are what the tools will produce, and
  the fix is a re-capture, not a parser guess.
- `listed_at`'s unit and the `salaryInsights` shape are **unconfirmed** (the live 200 showed a 13-digit
  integer and a `null` salary — neither documents a unit or a shape). The **container path of the feed
  body is more open than before, not less**: the live 200 offered no findable container at all, so
  nothing about where the real container sits was learned.
- The **employer name for a single posting** is joined on the company URN the posting entity itself
  references (`jobs_parse._company_name`, `_referenced_company_names`), and the fixture exercises
  that join through a nested `companyDetails.company` reference. Two different referenced employers
  (a staffing agency plus the hiring company) leave the field `null` rather than naming a plausible
  one. The pool is accepted as the witness only for a **single posting** body **and only when it
  holds exactly one company** — Manuel's capture note says *where* the name sits, not that there is
  ever only one entry, so anything beyond that would be an unbound claim. **What the live run adds
  here is less than it looks:** `company` came back filled on one real body (§4.0 (a)), so *some*
  branch resolved a name out of `included[]` — but the answer carries no marker of which one, so the
  **reference path itself remains unproven against a real body**, exactly as before. Both branches and
  every negative case (unreachable reference, two conflicting employers) stay fixture-only. `null` is
  the honest outcome there, never a plausible-looking wrong employer.

---

## 5. `search_jobs` is missing — on purpose

There is **no** `search_jobs` tool. The keyword/filter search is a separate route with its own
filter grammar, and no capture of it exists in this repo. Building it would mean inventing filter
keys, which is the one thing this repo's history says never to do ("don't guess — click and
record"). It waits for a capture of a real job search from the client, and only then a tool.

**Update 2026-07-30 — a capture exists, but not here.** The owner reports having produced one. It lives
on **his** host and is **not present in this clone** (searched for, not found). A capture that the repo
does not have is not evidence the repo may build on: the route, the query string and every filter key
stay unknown here, and the status of this section is unchanged. The next step is therefore not code —
it is getting the capture file into the repo (`BACKLOG.md`).

---

## 6. Open, not accepted

These are known, currently **unresolved** defects of the code described above. They are listed
because the doc must not claim more than the code holds, and the list is re-derived from the code
after **every** fix round — a written-down defect is only evidence while the code that produced it
still stands.

Closed since the first version of this section, each now pinned by a named test in the previous
section: URN-string entries read as an empty page, silent partial loss, an order-dependent identity
verdict, a positional container choice with an empty decoy **sibling**, a card token returned as the
page cursor, `ok=True` on an empty projection, `currentJobId` winning over `/jobs/view/<id>/`, an
empty **parent** container hiding a filled one nested beneath it, and a diverging id on the discarded
`data` wrapper passing as `match`. This section keeps no state of its own beyond what those test
names hold; what remains open is below.

1. **The candidate search has a depth and a width limit, and hitting it still reads as `empty`.**
   `find_collections` descends only to `_MAX_DEPTH` and walks only the first `_MAX_WIDTH` entries of
   a list (`mcp/lib/jobs_parse.py`, `find_collections`). If the real container sits deeper (or wider)
   than that **and** a shallow candidate with an empty `elements` list exists, that shallow one is
   read, comes back empty, and its own `paging.total: 0` is the evidence — the deeper `paging.total`
   is never seen, because the contradiction check in the empty branch of `read_job_collection` runs
   over the candidates that were *found*. Result: `ok=True, state="empty"` with cards unread in the
   same body. Measured against the current code. Strictly by the rules this is not a broken promise —
   the container that was read was read, was empty, and carried `total: 0` itself — but it is the
   handed-back damage picture, so it is listed here and not glossed over. Note that a truncated
   search is *not* the same as "no candidate": a body with **no** candidate at all is `unknown`, and
   only a body that also offers a shallow empty candidate produces the false `empty`. No test pins
   the limit, and the depth of the real container path is unconfirmed (see the previous section).
2. **The response root is not on the identity path.** `read_job_posting` reduces the body to its
   `data` node first and collects the identifying ids over that node and the inner one, never over
   the root itself (`mcp/lib/jobs_parse.py`, `read_job_posting`). A job id sitting at an identifying
   key of the **root envelope** is therefore never compared with the requested one: a root naming a
   different job, with the requested job on the inner node, comes back `identity="match"`. Measured
   against the current code. The content and the `url` still come from the node carrying the
   requested id, so the owner's damage picture (a foreign job under the requested link) does not
   occur — but the hard abort does not hold at that position. Two caveats keep this from being a
   simple patch: the root of the measured body is an HTTP envelope (`data` plus `included[]`) with no
   entity identity on it, so the failing shape is **not** backed by any capture, and the doubly
   nested `data.data` form the second unwrap serves is not captured either. This is the same class
   one reduction step further out, three rounds running, so the fix belongs in the chain that
   collects the ids (root, outer, inner in one expression) plus a test that an envelope **without**
   an id does not abort a correct read — not in another single-position patch.
3. **The read container is recognised by *shape*, not by evidence that it is the jobs feed.** Any
   dict holding an `elements` list qualifies (`mcp/lib/jobs_parse.py`, `find_collections`), and
   `_select_collection` takes the one that holds entries. Two consequences, both measured:
   a **filled** foreign container (a promo or similar-jobs rail with its own job ids) is not
   descended into and therefore shadows the real feed nested below it, without `ambiguous`; and a
   filled candidate wins even when a neighbouring candidate reads `paging.total: 0` — that
   contradiction is only checked in the empty branch. The origin of the read node never appears in
   the result either (no `reason` on `hits`), so a caller cannot tell a rail from the feed. What is
   *not* at risk: every card returned really stood in the body and its link is built from its **own**
   id, so no card points at a job other than the one it describes. A foreign container carrying no
   job ids at all falls to `drift`, not to a wrong answer. Closing this properly means descending
   into a filled candidate's non-`elements` keys as well (only the `elements` value stays off
   limits) so the existing `ambiguous` logic can bite — which deliberately changes what
   `test_the_shallowest_container_wins_and_is_the_one_read_from` pins today, and that is an owner
   decision, not a silent correction.
4. **The `read_entries` / `discarded` / `count` balance does not close** when entries drop out for a
   reason other than unreadability: collapsed duplicates and the cut at `count` are counted in
   neither `discarded` nor the `reason`. Neither falsifies a statement about *jobs* — a duplicate is
   the same posting, and the cut was requested by the caller — but a caller checking
   `read_entries - discarded == count` sees an unexplained gap.
5. **Only `description_text` is length-capped** (`MAX_DESCRIPTION_CHARS`). `title`, `location`,
   `employment_status`, `salary`, `company` and `listed_at` are passed through unbounded, and
   `count` has no upper bound either. The source is LinkedIn's own response, so this is robustness
   against a drifted body, not a leak — but the module's own reasoning for the cap ("an unbounded
   field would blow the agent's context window") applies to those fields too.
6. **`normalize_job_id` does not canonicalise on every branch.** The URN and the `/jobs/view/`
   path branch hand back the matched digit run unchanged, so non-ASCII digits and leading zeros
   survive (Python's `\d` matches Unicode digits). Both failure directions are safe — the route
   answers 404, or the body-id comparison reports a mismatch — but the returned `url` can be an
   unresolvable link, and a correct read can be aborted.

How to read the state table given items 1 and 3: `empty` now means the container that was read was
read empty, no candidate found anywhere in the body held entries, and no candidate's `paging.total`
contradicted it — that much is pinned by tests. The remaining reservation is narrow but real: it
covers only what the candidate *search* did not reach (item 1) or picked by shape alone (item 3).
`unknown`, `ambiguous` and `drift` mean exactly what the table says. `hits` names cards that really
stood in the body, each with a link built from its own id — the open question there is whether the
container they stood in is the feed. `company` on `get_job` is evidence-joined (see the previous
section); the live run showed the field filled on one real body, but not which branch filled it, so
the reference *path* is still unproven against a real body (§4.0 (a)).

**Items 1 and 3 were expected to be settled by a live feed call. They were not.** The owner's live run
did execute the feed route, but the 200 it returned offered **no findable container at all** (§4.0 (c)),
so neither the depth of the real container path nor the presence of a second, filled rail next to it was
observed. Both items stay open exactly as written, and what they now additionally wait on is the **raw
body** of that 200 — which is the same artifact the endpoint itself waits on.

---

## 7. The live call — executed, and what it left open

**This section is no longer a proposal for `get_job`.** The owner ran both tools on 2026-07-30 against
`5a251da`; the results are in §4.0, the provenance rule in `STATUS-MATRIX.md`. Outcome in one line:
`get_job` is verified on the 200 and the 404 path, the feed route answered 200 but read as
`state: "unknown"`, so the recommendations **endpoint** and open items 1 and 3 are **not** settled.

What is still needed, and it is no longer a plain live call:

- **What:** re-run `get_job_recommendations(3)` and **keep the raw response body** of the 200 (the tool
  deliberately never returns bodies, so this has to come from a capture — `tools/crawl_recursive.py`)
  or capture the jobs feed request from the real client again.
- **What it would prove:** which container key the real body carries (or that it carries none, or that a
  200 arrived with an in-band error, or that the feed is empty / not entitled) — the one fact that
  decides whether the endpoint is usable and that settles open items 1 and 3 for a real body.
- **Risk:** a GET on the owner's own account — nothing is created, changed or deleted. Residual risk is
  the usual one of any authenticated read (rate limiting / session wear), plus the handling rule that a
  captured body must be treated as private data and must never be committed.
- **Cost:** one request.

**Not part of this and still unexecuted: the SDUI header question** (minimal headers vs. vgreq's Voyager
headers). It is a **write**, so it needs the owner's explicit go; the one-variable call is written out in
`COVERAGE-MAP.md` ("The one-variable test that would settle it") and stands ready — only the approval is
missing.
