# Jobs reads — `get_job` and `get_job_recommendations`

Two **read** tools for the jobs domain: one job posting by id, and LinkedIn's own
recommendation feed for the owner. Browserless (pure `requests` through `vgreq`), no confirm
gate — reads never get one — and registered on the READ side of the read-only split
(`mcp/tests/test_readonly.py`).

**Status of this document (three owner runs; provenance and its scope: `STATUS-MATRIX.md`, legend entry
"(owner-run)").** The picture is not uniform, so read the five lines separately:

- **`get_job` is ✅ live-verified** (owner-run 2026-07-30 against `5a251da`), on two paths: **HTTP 200**
  for a real job id with the flat projection holding up on real data, and **HTTP 404** for an invented
  one with an honest error that keeps the requested `job_id`. That is the 404 path only — the
  id-**mismatch** abort was *not* exercised and stays fixture-proven.
- **`get_job_recommendations` was ✅ only for its honesty** on that run: on a live 200 without a findable
  container it reported `state: "unknown"`, not `empty`. That is history now — see the next two lines —
  but it is the reason the tool's output is taken at face value below.
- **The SHAPE of the feed body became known — 🔍, owner-run 2026-07-31 (the measured body).** The owner
  measured the response of the feed route himself (`count:5`,
  `queryId voyagerJobsDashJobsFeed.8b4a94e0e9d8395f1e7482987dd2f815`) and reported the container path,
  the module and card key sets, the union branch names and the values of one card. The chain has
  **three** hops, not two, and `*elements` points at **modules**, not at job cards (§1.3). This was the
  owner's measurement of a **body**, not a run of this parser.
- **`get_job_recommendations` is now ✅ live-verified as a READ — owner-run 2026-07-31 against
  `75afead`** (a second, separate run of that date: the tool executing, not a body being read). **HTTP
  200**, `ok: true`, `state: "hits"`, `count: 3`, `read_entries: 5`, `discarded: 0`, `paging_total: 9`.
  The three-hop projection produced correct cards on real data, and the count was checked against the
  **raw** body rather than against the tool's own output. The **endpoint is verified usable**. What that
  ✅ does not reach — the read-error path, the partial-loss path, the inlined-object chokepoint and every
  state other than `hits` — is named in §4.0.
- **Everything else below is offline evidence**: the identity table, the state table beyond `unknown`
  and `hits`, the container-selection rules, every failure branch of the feed projection (a card that
  does not resolve, a partial loss, a form that was not understood), the description cut with its
  `description_truncated` flag and every `company`-join case — the reference join and the sole-company
  fallback alike — are proven against **fixtures** only (the feed fixture reproduces the owner's
  measured form and says in its own `_provenance` which values are his and which are synthetic).

What the passing tests cover is listed under "What is proven, and how", what the live runs added is in
its own subsection there, and what neither covers is under "Open, not accepted". **The offline suite is
green** — which says only that the shapes the tests describe behave as described. The open defects in
`§6` are measured by **review probes against this very tree**, not by red tests: a green suite is not a
claim that nothing is open. Do not read this file as a release note.

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

**Live status: ✅ verified usable (owner-run 2026-07-31 against `75afead`, HTTP 200).** The tool read
three job cards out of five modules on a real body — the numbers and their independent witnesses are in
§4.0. **The earlier picture, kept because it is the reason the reader looks the way it does:** on
2026-07-30 the same route answered HTTP 200 and delivered nothing this repo could read; the tool
reported `state: "unknown"`, so the route was executed but **not** verified usable then.

**What the second owner run (2026-07-31, the measured body) changed about that:** the owner measured a body of this route
himself, and it *does* carry a container — under `data.data.jobsDashJobsFeedAll`, whose entry list is
called **`*elements`** (Rest.li's star: a list of URNs resolved through `included[]`). The reader of
2026-07-30 accepted only the unstarred `elements`, which is a mechanism that produces exactly the
observed `unknown` on exactly such a body. **That is the mechanism, not an identification of the two
bodies:** the raw body of the 07-30 run was never kept, so it cannot be shown that it was this shape —
only that a body of this shape reads as `unknown` under the old reader and is read under the new one
(offline, §4.2).

**Not this route, and not to be confused with it:** the owner separately probed a REST-like form,
`voyagerJobsDashJobsFeed?decorationId=com.linkedin.voyager.dash.deco.jobs.JobsFeed-2&count=5&q=jobsFeed&start=0`,
and measured **HTTP 400** with a 14-byte body. Useful to know about *that* form; it says nothing about
the GraphQL route above, which the tool exclusively uses (`mcp/lib/client.py`,
`get_job_recommendations` — the URL is built from `_JOBS_FEED_QID` / `_JOBS_FEED_PAGE_QID` and no
`decorationId`/`q=jobsFeed` variant is ever sent) and which answered 200 in the same run.

**Re-capture path:** `queryId` and `decorationId` hashes rotate with LinkedIn deployments. When a
call answers 4xx, re-grab the request with `tools/crawl_recursive.py` and update the two constants
in `mcp/lib/client.py`; the error `note` of both tools says so at runtime.

### 1.3 The feed body: three hops, and `*elements` points at MODULES (🔍 owner-run 2026-07-31)

The form below is the owner's own measurement of a live response. It is **not** ✅: this repo did not
execute the call, and that the parser reads this form is proven **offline** only.

```
data.data.jobsDashJobsFeedAll
  └─ *elements[i]                    "urn:li:fsd_jobsFeedCardModule:(JOBS_HOME_JYMBII,<uuid>)"
       │  hop A — a URN string, resolved through included[] by entityUrn
       ▼
     JobsFeedCardModule
       └─ entitiesResolutionResults[]  EMBEDDED list, not a reference
            └─ <union branch>          18 keys, exactly ONE filled; the filled NAME is the type
                 └─ jobPostingCardWrapper
                      └─ *jobPostingCard  "urn:li:fsd_jobPostingCard:(<id>,JOBS_HOME_JYMBII)"
                           │  hop B — a URN string, resolved through included[]
                           ▼
                         JobPostingCard   ← the payload
```

Three consequences, and each of them is why a type-led single hop had to guess:

- **The entry level does not point at job cards.** It points at modules, and a module may carry no job
  at all. Measured module keys — **not one `*` key** among them: `hide`, `moduleType`, `entityUrn`,
  `footer`, `header`, `$recipeTypes`, `entitiesResolutionResults`, `$type`. Also usable:
  `moduleType` ∈ {`VERTICAL_LIST`, `SINGLE`, `TABBED`} and `header.title`.
- **The union is self-describing.** 18 branch keys, exactly one filled, and the filled key's **name**
  is the type — nothing has to be inferred from the target. Measured names: `endOfResultsCard`,
  `jobPostingCardWrapper`, `jobSearchHistoryCard`, `jobSearchSuggestion`, `premiumUpsellSlot`,
  `seekerNextBestActionComponent`, `carouselEntityHighlightCard`, `feedbackCard`,
  `newCollectionHeaderCard`, `carouselCollectionCard`, `careerEnrichmentCard`, `tabbedCollection`,
  `noResultsCard`, `seeAllCard`, `*promotionalCard`, `refreshStateCard`, `jobPostingCard`,
  `jumpBackInCard`. `jobPostingCard` is a branch **of its own next to** `jobPostingCardWrapper`; it was
  null throughout the measured run and the parser reads both (`jobs_parse._JOB_BRANCH_KEYS`). The list
  is documentation, deliberately **not** an allowlist in the code: an unknown sibling branch must stay
  silently skippable instead of becoming an error at LinkedIn's next deployment.
- **The card carries its own display fields, so there is no hop after it.** Measured card keys:
  `preDashNormalizedJobPostingUrn`, `footerItems`, `*jobSeekerJobState`, `primaryActions`,
  `primaryDescription`, `debugInfo`, `jobInsightsV2ResolutionResults`, `title`, `$recipeTypes`,
  `relevanceInsight`, `$type`, `secondaryDescription`, `entityUrn`, `logo`, `tertiaryDescription`.
  Exactly **one** `*` key: `*jobSeekerJobState` (optional — saved/applied/viewed).

Two properties of the card that decide the projection:

1. **Employer and location sit in ONE string**, `primaryDescription.text`, separated by `' · '`. A feed
   body carries **no `Company` entity**, so unlike `get_job` there is nothing to join — waiting for
   `Company.name` here waits forever.
2. **The job id is in the card's own `entityUrn`**, as a tuple: `(<id>,<origin>)`. The `url` and the id
   for `get_job` are built from that, from nothing else.

The measured run, module by module (this table is the shape of `mcp/tests/fixtures/jobs_feed_modules.json`):

| # | `moduleType` | entries | filled union branch | `header.title` |
|---|---|---|---|---|
| 0 | `VERTICAL_LIST` | 3 | `jobPostingCardWrapper` ×3 | a title |
| 1 | `VERTICAL_LIST` | 0 | — | `null` |
| 2 | `SINGLE` | 1 | `*premiumUpsellSlot` | `null` |
| 3 | `SINGLE` | 1 | `*promotionalCard` | `null` |
| 4 | `TABBED` | 4 | `tabbedCollection` ×4 | a title |

So a feed of five entries answers with three jobs. That arithmetic is the reason for the
wrongly-transferred invariant in §3 — and the owner's executed run of 2026-07-31 produced exactly that
shape on a real body: five modules, three cards (§4.0).

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

Returns `status`, `ok`, `state`, `count`, `results`, `read_entries`, `discarded`, `skipped`, `lost`,
`unread`, `dropped`, plus `paging_total` and `pagination_token` for the next page. Duplicate ids are
collapsed — **without a counter**, which is the one subtrahend of the balance that still has no name
(§6 item 12). A non-positive / non-numeric `count` is refused **without any call**.

Each card is flat. On the **feed** path the values come out of the JobPostingCard itself
(`jobs_parse.project_feed_job_card`) — no second entity is consulted:

| field | source on the feed card | note |
|---|---|---|
| `job_id` | the card's own `entityUrn` tuple, and only that | a second identity on the card (`preDashNormalizedJobPostingUrn`) is read **solely to contradict it**: two disagreeing ids are a loss, never a choice |
| `url` | built from that `job_id` | `…/jobs/view/<id>/` |
| `title` | `title` (a string or Attributed Text) | |
| `company` | the part of `primaryDescription.text` **before** `' · '` | no `Company` join exists in a feed body |
| `location` | the part **after** the first `' · '` | without the separator the whole text is the employer and `location` is `null` — the missing half is never invented |
| `module_type`, `module_title` | the module the card stood in (`moduleType`, `header.title`) | says which rail delivered the card |
| `job_seeker_job_state_urn` | `*jobSeekerJobState`, **passed through unresolved** | optional; the state entity's shape is not measured, so it is not interpreted. Absent → `null`, not an error |
| `remote_allowed`, `listed_at`, `reposted`, `salary` | not carried by a feed card → `null` | **unknown is not `False`.** `location` may say "(Vor Ort)"; prose is not a measured flag |
| `salary_present` | `False` — no salary field exists on the card | |

`state` exists so that an agent can tell an **answer** from a **failure**:

| `state` | meaning | `ok` |
|---|---|---|
| `hits` | the read container held entries and at least one job card came out | `True` |
| `empty` | nothing to read: either the container **itself** held no entries (and no candidate's `paging.total` contradicts that), or every entry was read and understood and none of them carried a job — a pure promotion feed | `True` |
| `unknown` | no container was found — we could not read. **Not** "no jobs" | `False` |
| `ambiguous` | more than one candidate container holds entries; which one is the jobs collection is not decidable, so **none** is read | `False` |
| `card_lost` | a job branch **was** there and its card did not resolve in `included[]` (or resolved twice): at least one card is missing from `results` | `False` |
| `drift` | the container says there are entries but not one was projectable; a candidate reports `paging.total > 0` next to an **empty entry list**; an entry arrived in a form this parser does not understand (`unread > 0` — see the "unread" level below); or the balance guard did not add up | `False` |

Every non-`hits`/`empty` state carries a `reason` naming the re-capture path.

**The three levels — silent toward siblings, named toward a form we do not understand, fail-closed
toward a lost card.** The first and the last are not in conflict because they sit on different levels of
the chain (`jobs_parse._feed_module_cards`); the middle one exists because "not understood" was being
sold as the first, which is the false success this ticket rejected one level deeper:

- **Silent** (`skipped`): a module whose filled union branch is not a job branch (promotion, upsell,
  `TABBED` collections), a module with an **empty** entry list, and a module with `hide: true`. Those are
  **expectable siblings**, measured in the owner's own run — they produce neither a value nor an
  ambiguity. Silence toward an **unknown branch name** belongs here too and is deliberate (§1.3).
- **Unread** (`unread`, `state="drift"`, `ok=False`): a form this parser does not understand. Two of
  those forms sit **inside** a module — the measured container key `entitiesResolutionResults`
  **missing or not a list** (i.e. a rename of exactly that key,
  `module_entitiesResolutionResults_missing` / `_not_a_list`), a union item that is not an object
  (`union_item_is_not_an_object`), and a union item with **no** filled branch at all
  (`union_item_with_no_filled_branch`; measured is "exactly one filled"). Two more sit one level
  **above** them, at the entry itself, and they are the chokepoint of the whole chain
  (`jobs_parse.read_job_collection`): an entry that came out of the **starred** entry list `*elements`
  and that is not readable as a module (`referenced_entity_that_is_not_a_readable_feed_module`), and an
  **inlined** entity that carries a job branch without being a readable module
  (`entity_with_a_job_branch_that_is_not_a_readable_module`). Neither is projected as a card; the reason
  why is §6 item 10. None of these are job-free modules; they are entries we could not read, so `count`
  may be incomplete and the `reason` names which forms appeared. Silence toward a missing **container
  key** is what this level ended.
- **Fail-closed** (`lost`): a `jobPostingCardWrapper` (or a `jobPostingCard` branch) **is** present and
  its card cannot be resolved — including a union item with **both** job branches filled, where which
  card is *the* card is not decidable. Then a card is lost, which is `state="card_lost"`, `ok=False`,
  `lost=N`, with the count of lost against the count of named cards in `reason`. `results` still carries
  what *was* read — nothing is invented to fill the gap, and nothing is quietly shortened.

**`read_entries` / `discarded` / `skipped` / `lost` / `unread` / `dropped` are the balance against the
raw list.** `read_entries` is the raw length of the container's entry list — on the feed those entries
are **modules**; `discarded` counts entries that could not be projected at all, `skipped` the modules
that carried no job, `lost` the job branches whose card did not resolve, `unread` the forms that were not
understood, `dropped` the cards a caller's `limit` cut off (named in `reason`, and on the feed path the
client passes no `limit` at all — see §6 item 8). Verdict *and* balance are computed on the raw list,
never on the projectable subset — filtering first is what once let a container of three URN strings
report "an empty page". Behind all of them sits a **balance guard**: every card that was projected is
either returned, a collapsed duplicate, or a named cut; if that ever fails to add up, the read reports
`drift` instead of the short list (`jobs_parse.read_job_collection`). The one subtrahend the guard uses
but does not **publish** is the collapsed duplicate — §6 item 12, and it is why `count` is still not a
fully closed quantity on this path.

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

**The container has two possible entry keys.** `elements` (inlined entries) and `*elements` (the star is
Rest.li's marker that the values are URNs resolved through `included[]`) — `jobs_parse._ENTRY_KEYS`. The
starred spelling is admitted **only together with a collection witness in the same node**
(`jobs_parse.container_entry_keys`), because a starred list of URNs is by shape indistinguishable from
any other URN list in the body; without that condition a similar-jobs rail would qualify as the
container. The owner's feed sends the starred form (§1.3), which is why the earlier reader found nothing.

Additional invariant: "empty" may only be claimed because it was **read** — a missing container is
`unknown`, never `empty`. The company name for a **single posting** is a **join** on a reference the read
entity itself carries, at any depth, not a pick from the entity pool (see the next section); a **feed**
card has no company to join at all (§1.3).

### The wrongly transferred invariant — `paging.total` counts different things on the two routes

A rule of this repo said: *`paging.total > 0` next to zero results is an error.* That rule belongs to
the **search** route. It was **wrongly transferred from the search route, where `total` counts jobs, to
the feed, where it counts modules** — transferred without checking what the counter counts there. The
authorship belongs named, and it is not the owner's: the **main session** carried the rule over and set
it as binding across several tickets; the owner's measurement is what refuted it. It was never
"withdrawn" in the sense of a preference reconsidered — at this place it was simply **false**, and
recording it as a withdrawal would read in six months like a matter of taste.

**Why it is false for the feed:** `paging` sits on the same node as `*elements`, but `total`
counts **modules, not job cards**. A feed with five modules can mean three jobs and two advertising
slots (§1.3) — the owner's executed run measured exactly that, `paging_total: 9` next to `count: 3` and
five modules read (§4.0). So `paging_total > 0` next to `count: 0` is the **normal case** of a pure
promotion feed: `state="empty"`, `ok=True`, no `reason`, no error. Pinned by
`test_a_pure_promotion_feed_with_a_paging_total_is_empty_and_not_an_error` (parser) and
`test_a_pure_promotion_feed_is_not_an_error_at_the_client_boundary` (tool).

Two boundaries of that correction, and neither may be widened by accident:

- **The rule is false for the FEED route only.** On the **search** route (`voyagerJobsDashJobCards`)
  `paging.total` counts **jobs** (the owner measured 129 at `count:5`), so there the old rule stays
  plausible. That route is untouched here. Do not merge the two arithmetics again.
- **What survives even on the feed:** an entry list that is **empty** next to a candidate reporting
  `total > 0` still reads as `drift`, `ok=False` (`jobs_parse.read_job_collection`, the `not entries`
  branch), because zero modules contradict a module count of five just as much. Whether that half should
  also fall for the feed — a cursor page past the end of the feed looks exactly like this — is an **open
  owner decision**, not a settled rule: §6 item 9.

The reliable error edge of the feed is the other one: a job branch that is there and a card that does not
resolve (`state="card_lost"`).

---

## 4. What is proven, and how

### 4.0 What the live runs added (owner-run)

Three runs, and they prove different kinds of thing. **2026-07-31 (the measured body)** contributed a
body **shape** (the three-hop chain of §1.3) — a shape, not a verdict of this code, so on its own it
produced **no ✅**. Its content is written out in §1.3 and is not repeated here. **2026-07-30** and
**2026-07-31 against `75afead`** contributed executed **calls**, and that is what the rest of this
subsection is about. Keep the two runs of 2026-07-31 apart: one is a body the owner read, the other is
this code running.

#### 2026-07-30, against commit `5a251da`

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
and "an in-band error arrived with a 200" were all still open **at that date**. The tool was verified
honest; the endpoint was not verified usable. That second half is what the next run settled.

#### 2026-07-31, against commit `75afead` — the feed read, executed

**This is the run that makes `get_job_recommendations` a ✅ read**, and it is a different run from the
measured body of the same date: there the owner read a body, here he ran the tool. He cleared the
bytecode cache before the run, so what answered is that commit's code and not a stale artefact.

`get_job_recommendations(5)` returned `status 200`, `ok: true`, `state: "hits"` — `unknown` on
2026-07-30 — with `count: 3`, `read_entries: 5`, `discarded: 0`, `paging_total: 9` and
`endpoint voyager.graphql.jobsFeed`. The three cards, recorded with no more detail than the proof needs
(public job adverts; employer names and job titles are public listing data, and nothing beyond the job
ids identifies anything):

| `job_id` | title | employer | location |
|---|---|---|---|
| 4441501850 | Leitung IT/Systemadministration (w/m/d) | Universum Managementges. mbH | Bremen (on site) |
| 4438192247 | Leiter Support Operations (m/w/d) | Stellenwert GmbH & Co. KG | Oldenburg (hybrid) |
| 4446987819 | Teamleiter IT (m/w/d) | Robert Walters | Vechta (remote) |

**What carries the proof is not the output but the cross-checks the owner ran against it.** Four of
them, and each one closes a different way of being wrong:

- **The count was checked against the raw body.** He put the raw response next to the result and
  counted `jobPostingCardWrapper` himself: **three in five modules**, against the tool's `count: 3`,
  `read_entries: 5`, `discarded: 0`. That is an independent count of the body, not a reading of the
  tool's own report — so neither a silent loss nor a duplication is compatible with it. This is the
  cross-check §2 asks for when it calls `read_entries`/`discarded` "the balance against the raw list".
- **The silent route works on real data.** Advertising, upsell, a `TABBED` collection and the empty
  module were skipped **without an error** — the "expectable siblings" level of §2, until now measured
  only in a fixture of the owner's earlier body.
- **The `' · '` split works on real data.** `primaryDescription` = "Universum Managementges. mbH ·
  Bremen, Deutschland (Vor Ort)" separated into `company` and `location`, which is the one projection
  rule of §2 that has no second source to fall back on: a feed body carries no `Company` entity.
- **The chain feed → `get_job` holds on real ids.** With ids out of the feed he ran `get_job` and got
  the postings back ("Leiter Support Operations (m/w/d) | Stellenwert GmbH & Co. | Vollzeit |
  remote=False"; "Teamleiter IT (m/w/d) | Robert Walters | Vollzeit | remote=True"). The feed delivers
  the id, `get_job` the detail — so the `job_id` the feed mints out of the card's own `entityUrn` is a
  usable identity and not merely a well-formed string.

And the arithmetic that used to look like a defect stands there consistently: `paging_total: 9` next to
`count: 3`, five modules of nine on this page. That is §3 measured rather than argued.

**What this run does NOT make ✅.** Each of these stays fixture-proven, and none of them may be widened
on the strength of a green run:

- **The read-error path** — a `jobPostingCardWrapper` present whose card does not resolve. `discarded`
  was `0`, so it was never triggered.
- **The partial-loss path**, for the same reason.
- **The chokepoint for an object standing inlined in the starred list** — proven offline (§4.2), and it
  did not occur in this body.
- **Every state other than `hits`.** `empty`, `unknown`, `ambiguous`, `card_lost` and `drift` are what
  the tests hold, not what this run showed.
- **`search_jobs` / P1b does not exist** and nothing here changes that (§5).

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
  of URN strings, which is **never** an empty page — or when `paging_total > 0` stands next to an
  **empty entry list** (`test_paging_total_above_zero_with_no_hits_is_an_error_not_an_empty_list`, whose
  body carries no entry at all; that is the surviving half of the wrongly transferred invariant, §3);
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

### 4.2 The feed's three-hop chain — proven offline, and what the green does not reach

Everything here is **offline** evidence for the shape of §1.3: passing tests in
`mcp/tests/test_jobs_parse.py` (parser) and `mcp/tests/test_client.py` (the tool boundary) against
`mcp/tests/fixtures/jobs_feed_modules.json`. The fixture's own `_provenance` separates the owner's
measured values from the synthetic additions. A live run of this code now **does** exist (§4.0), and it
covers the `hits` path and nothing else — everything below that is not that path is offline evidence,
exactly as it was.

Held by passing tests:

- **the owner's whole five-module run reads exactly its three job cards**, with title and employer, and
  the advertising siblings silently skipped
  (`test_the_measured_five_module_feed_reads_exactly_its_three_job_cards`, and at the tool boundary
  `test_get_job_recommendations_reads_the_owner_measured_module_feed`) — this is the one item of this
  list that the executed run of 2026-07-31 also confirms **live**, with the same arithmetic (§4.0);
- **the corrected invariant stays corrected**: a promotion-only feed with a `paging.total` is `empty`,
  `ok=True`, without a `reason` — in the parser and at the tool boundary
  (`test_a_pure_promotion_feed_with_a_paging_total_is_empty_and_not_an_error`,
  `test_a_pure_promotion_feed_is_not_an_error_at_the_client_boundary`);
- **a lost card is an error, not a shorter list**: a wrapper whose `*jobPostingCard` is not in
  `included[]` is `card_lost`/`ok=False` with nothing invented, a **partial** loss names itself instead
  of reporting the survivors, and both reach the caller
  (`test_a_job_branch_whose_card_is_missing_is_a_read_error_not_an_absent_card`,
  `test_a_partial_card_loss_names_itself_instead_of_reporting_the_survivors`,
  `test_a_lost_job_card_reaches_the_caller_as_an_error_not_as_a_short_list`);
- **`jobPostingCard` as a branch of its own is read like the wrapper**
  (`test_the_bare_job_posting_card_branch_is_read_like_the_wrapper`);
- **an entity pool that contradicts itself resolves nothing**: two `included[]` entries with the same
  `entityUrn` are fail-closed, not "the first one"
  (`test_two_included_entries_with_the_same_entity_urn_are_fail_closed`);
- **no verdict depends on key order**, module, card and union item permuted — and the union item carries
  *filled* foreign branches next to the job branch, so "the first filled branch is the type" cannot pass
  (`test_the_feed_verdict_does_not_depend_on_key_order_in_any_permutation`); the job branch is found at
  **every position of the full measured 18-branch union**
  (`test_the_job_branch_is_found_at_every_position_of_the_full_eighteen_branch_union`);
- **the card's own identity is the only id**: a card whose `preDashNormalizedJobPostingUrn` disagrees
  with its `entityUrn` is lost, not guessed
  (`test_a_card_contradicting_itself_about_its_job_id_is_lost_not_guessed`);
- **`primaryDescription` without the separator is all employer**, location `null`
  (`test_a_primary_description_without_the_separator_is_all_employer`);
- **an empty module and a `hide: true` module are silently skipped**
  (`test_an_empty_module_and_a_hidden_module_are_silently_skipped`); a card without
  `*jobSeekerJobState` is no error and the field is `null`
  (`test_a_card_without_a_job_seeker_state_is_no_error`);
- **a module is recognised by its own URN even without a `$type`**
  (`test_a_module_is_recognised_without_a_type_by_its_own_urn`) — the `$type` **value** is not
  owner-measured, so it may not be the load-bearing witness;
- **the starred entry key needs a collection witness**: a `*elements` list in a node that does not prove
  it is a collection is not the container, and a node holding *both* entry keys with content is
  `ambiguous` (`test_a_starred_entry_list_without_a_collection_witness_is_not_a_container`,
  `test_a_node_holding_both_entry_keys_with_content_is_ambiguous`).

Held by passing tests, added when the losses above were closed:

- **a module wider than the traversal's width cap returns every resolvable card**, because the cap does
  not apply to it: `_MAX_WIDTH` bounds recursive **discovery** over an unknown body, while a module's
  `entitiesResolutionResults` is a flat walk over one already-parsed embedded list
  (`test_a_module_wider_than_the_width_cap_does_not_lose_cards_silently`,
  `test_a_module_wider_than_fifty_returns_every_resolvable_card`);
- **a `limit` never cuts cards with a module number**, and whatever it does cut is counted in `dropped`
  and named in `reason` (`test_the_limit_never_cuts_cards_read_out_of_modules_and_names_what_it_does_cut`,
  and at the tool boundary `test_the_requested_count_caps_the_request_and_never_silently_cuts_the_read_cards`
  — the client sends the count to LinkedIn and passes **no** `limit` into the read);
- **a form that was not understood is `drift`, never a promotion feed**: a drifted container key, a
  non-object union item and an item with no filled branch each reach `ok=False` with the forms named,
  and an unread form standing next to a readable card names **both**
  (`test_a_module_form_that_was_not_understood_is_drift_and_never_a_promotion_feed`,
  `test_an_unread_form_next_to_a_readable_card_still_names_both`);
- **a card identity must be the whole URN**: a card URN merely *nested inside* a longer foreign URN is
  not an identity (`test_a_card_urn_nested_inside_a_foreign_urn_is_not_an_identity`), and an entity that
  carries the measured container is treated as a **module** even when `$type` and URN prefix drift, so
  its `trackingUrn` cannot become a card's id
  (`test_a_feed_entity_never_gets_its_id_from_a_foreign_tracking_urn`,
  `test_a_feed_entity_whose_container_key_drifted_is_not_projected_by_the_search_route`);
- **an entry named by the starred list is a module or it is unread — never a card**: an entity resolved
  out of `*elements` that is not readable as a module never reaches the search projection, whether its
  job branch sits two levels down or whether it carries no job branch at all and only a `trackingUrn`;
  both shapes answer `ok=False`, `state="drift"`, `count=0`, and neither the foreign id nor the foreign
  title appears anywhere in the result
  (`test_a_referenced_entity_that_is_no_module_never_reaches_the_search_projection`, parametrized over
  the two shapes). The rule is positive — it asks where the entry **came from**, not what it contains —
  and the same test file pins that the search route, whose `elements` are inlined, passes the
  chokepoint untouched (`test_the_chokepoint_leaves_the_search_route_untouched`).

**What the green does not reach.** The chokepoint above closes the foreign-identity class for entries
that arrive as a **URN string** in the starred list, which is the measured feed shape; it does **not**
close the class as such. A second reach — an entry standing **inlined as an object inside the starred
`*elements` list** — was closed on 2026-08-01 by keying the decision on the starred **container key**
rather than on an entry's runtime type, and a test pins it. **One reach is still open:** a drifted
entity in a non-starred `elements` list whose job branch sits deeper than the one-level witness looks
still mints a card id from a foreign `trackingUrn` and reports `hits`/`ok=True` — §6 item 10 (b), which
is why this subsection does not claim the class is closed. That one is search-route behaviour and an
owner decision, not a feed defect. `count` on the feed path is
a closed quantity against every shape listed above, and **not** against a body carrying the same
`job_id` twice (§6 item 12).

**Not proven, and it matters:**

- **The feed's reading code has met LinkedIn exactly once, on the `hits` path** (owner-run 2026-07-31
  against `75afead`, §4.0). Every branch that run did not walk — a card that does not resolve, a
  partial loss, a form that was not understood, and every state other than `hits` — is proven against a
  fixture of the owner's measured body and nothing more.
- **Live evidence covers exactly the items in §4.0 and nothing else.** Every other statement in
  this document is "the request we would send" and "how we parse a body of that shape". In particular:
  the **id-mismatch abort**, the `ambiguous` / `drift` / `absent` / `card_lost` states, every
  container-selection rule and every negative `company`-join case were **not** exercised live.
- **The fixtures under `mcp/tests/fixtures/` are synthetic and PII-free.** They prove the parser
  logic only — they are **not** evidence of LinkedIn's response form. Where a real body differs,
  the honest failure states (`unknown`, `drift`, `absent`) are what the tools will produce, and
  the fix is a re-capture, not a parser guess.
- `listed_at`'s unit and the `salaryInsights` shape are **unconfirmed** (the live 200 showed a 13-digit
  integer and a `null` salary — neither documents a unit or a shape). The **container path of the feed
  body** is no longer open: the owner measured it on 2026-07-31 (§1.3). What the 07-30 run itself
  learned about it stays nothing — that body was never kept.
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

**Update 2026-07-31 — open, and explicitly not urgent (the owner's own priority).** The card
**projection** for the search route exists and carries; what is missing is the **request** path — the
route and its filter grammar. The owner states there is **no urgency for his operation**, because mail
plus the recommendation feed already give him the coverage he needs, and the feed is now a verified read
(§4.0). So this stays open rather than being pulled forward, and it is **not** a defect. His session
stands ready for captures whenever the request path is wanted; nothing here is blocked on anything but
that.

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
   the limit. **What the 2026-07-31 measurement changes here:** the real feed container sits at
   `data.data.jobsDashJobsFeedAll` (§1.3), which is inside the depth limit — so for that measured body
   the depth half of this item does not bite. It stays open because the limit itself is unchanged and
   nothing pins it, and because the **width** half now has a measured victim of its own (item 7).
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

Items 7 to 13 are **new with the feed's three-hop reader** and all of them belong to one class the two
earlier hand-backs already named: **a quantitative or qualitative reduction that does not name itself.**
They are listed separately because each sits at a different place in the chain. Items 7, 8 and 11 were
**closed** in a fix round and are kept here with what closed them, so the class stays visible; item 10
is **partly** closed — its measured shape is held by a chokepoint, two drifted shapes are not — and 12
and 13 are open. Everything called open here is measured by a review probe against this tree, and the
probe's answer is quoted with it.

7. **CLOSED — a module wider than the traversal's width cap lost resolvable cards silently.**
   `_feed_module_cards` walked `entitiesResolutionResults[:_MAX_WIDTH]`, so the surplus entries of a
   wider module were dropped with `ok=True`, `lost=0`, `reason=None`. **Closed by removing the cap from
   this walk** (`mcp/lib/jobs_parse.py:1122`, in `_feed_module_cards`, with the reason in its docstring
   at `:1109-1111`): `_MAX_WIDTH`
   (`mcp/lib/jobs_parse.py:126`) bounds the recursive **discovery** over an unknown body, not a flat walk
   over one already-parsed, measured list. Two tests hold it (§4.2). Kept here because the reasoning
   generalises: a bound written for a search is not a bound for a read.
8. **CLOSED — the `limit` cut on the feed path counted modules, not cards.**
   `read_job_collection(raw, limit=n)` was called with the same `n` the client sent to LinkedIn as the
   page size, and that `n` is a **module** count on this route (§1.3), while the cut applied it to
   **cards** — five modules of three cards returned five cards with a balance that looked closed over
   ten dropped ones, unreachable by cursor paging. **Closed on both sides**: the client no longer passes
   a `limit` into the read at all (`mcp/lib/client.py:541`, in `get_job_recommendations`), and the cut
   that remains for a caller who does pass one is bound to entries that are **not** modules and counts
   what it cuts in `dropped`, naming it in `reason` (`mcp/lib/jobs_parse.py:1308-1312`, in
   `read_job_collection`). Two tests hold it (§4.2).
9. **The surviving half of the wrongly transferred invariant is an owner decision, not a settled rule.** An empty
   entry list next to a candidate reporting `total > 0` still reads `drift`, `ok=False`
   (`mcp/lib/jobs_parse.py`, `read_job_collection`, the `not entries` branch), and two tests pin it
   (`test_paging_total_above_zero_with_no_hits_is_an_error_not_an_empty_list`, and at the tool boundary
   `test_get_job_recommendations_never_reports_a_silent_zero_for_a_full_page`). On the **feed** that
   shape has a plausible innocent cause: a cursor page **past the end** of the feed carries no module
   while `total` still counts the modules of the whole feed. The reading code's justification ("drift on
   either route") is written for two routes, but `read_job_collection` has exactly one caller today —
   the feed. **Decision needed:** drop this half for the feed as well (then it becomes `empty`), or
   keep it deliberately as a feed special case. Until then this document does not claim it is right; it
   claims only what the two tests hold, which is the current behaviour.
10. **PARTLY CLOSED, and still the sharpest item on this list — an entry that is not recognised as a
    module can be projected by the SEARCH projection into a card with a FOREIGN id.**
    `read_job_collection` hands a non-module dict to `project_job_card`
    (`mcp/lib/jobs_parse.py:1272`, in `read_job_collection`), which reads the job id at the search
    route's identifying positions (`_ID_URN_KEYS`, `mcp/lib/jobs_parse.py:112`, e.g. `trackingUrn`). The
    entity that *contains* the real cards is then itself projected into a card whose `job_id` and `url`
    come from a **different** position than a JobPostingCard's own `entityUrn`, reported as
    `hits`/`ok=True`, while the real cards inside it go unread.
    **What is closed, and closed at a chokepoint rather than by another witness:** an entry that arrived
    as a **URN string** in the starred entry list `*elements` is, by where it came from, a name for a
    module — so if it does not read as one it is `unread` and never projected
    (`mcp/lib/jobs_parse.py:1253-1264`, in `read_job_collection`, keyed on `from_reference` at `:1234`).
    The rule is positive and does not ask what the entity contains, so it cannot be out-drifted one
    level deeper. Review probes against this tree, both shapes: a drifted entity with
    `trackingUrn: urn:li:jobPosting:7777777` and a resolvable `jobPostingCardWrapper` **two** levels
    down, and the same entity with no job branch at all, each answer `ok=False`, `state="drift"`,
    `count=0`, `unread=1`, with neither the foreign id nor the foreign title anywhere in the result.
    A parametrized test pins both, and a second test pins that the search route — whose `elements` are
    inlined, never URN strings — is untouched by the rule (§4.2). Two earlier, instance-level defences
    still stand underneath it: the anchored `_CARD_URN_RE` (`mcp/lib/jobs_parse.py:153`) and
    `is_feed_card_module` recognising a module by the measured container key even when `$type` and URN
    prefix drift.
    **(a) CLOSED 2026-08-01, and it used to be the worse of the two.** An **object standing directly
    inside the starred `*elements` list** (instead of the measured URN string) answered `ok=True`,
    `state="hits"` with `job_id 7777777` and the foreign title; in a **mixed** list the foreign identity
    stood next to a correctly read card with nothing marking the difference, so a caller saw a plausible
    page. The fix is the rule expressed one step more positively: the signal is the **starred container
    key**, which the reader already computes (`container_entry_keys`), not an entry's runtime type. An
    entry from a starred list is a feed entry whether it arrived as a URN or inlined, so an inlined
    object there is `unread`, `state="drift"`, `ok=False`, whatever it contains. Pinned by
    `test_an_inlined_object_inside_the_starred_list_never_becomes_a_card`.
    **What is NOT closed** — one reach remains, measured by a review probe against this tree and not
    pinned by a test:
    (b) the same drifted entity in a **non-starred, inlined `elements` list**, with its job branch
    deeper than the one-level `carries_a_job_branch` witness looks (`mcp/lib/jobs_parse.py:974`,
    consulted at `:1266`): `ok=True`, `state="hits"`, `job_id 7777777`. This one is **not** new with this
    reader — the same body answers the same way on the baseline parser — and it is the search route's
    projection semantics, which this ticket's scope forbids touching. It is written down here so it is
    not rediscovered as a regression.
    Neither reach is triggered by the owner's measured body; both are what a drifted body would
    produce. Reach (b) is an owner decision about the **search** route and does not belong in a feed
    change — without a provenance signal, feed and search are not distinguishable in that shape, and a
    guessed fourth witness would be exactly the mistake this series closed.
11. **CLOSED — `skipped` counted shapes that were not understood as "understood and job-free".** Three
    of them reached `state="empty"`, `ok=True`, `reason=None`: a module whose owner-measured
    `entitiesResolutionResults` key is **missing or not a list**, a union item that is not an object,
    and a union item with **no** filled branch at all. **Closed by giving them their own level**: they
    are counted in `unread` and reported as `state="drift"`, `ok=False`, with the forms named in
    `reason` (`mcp/lib/jobs_parse.py:1118-1128`, in `_feed_module_cards`; the verdict in
    `read_job_collection`) — see §2, "the three levels". The boundary that was never in question stayed
    put: silence toward an **unknown branch name** is correct and deliberate (§1.3); it was silence
    toward a missing **container key** that this item was about.
12. **Collapsed duplicates have no counter on the feed either, and the `card_lost` arithmetic can
    disagree with itself.** The same `job_id` in two modules (plausible: a "top jobs" rail and a
    "jump back in" rail) is dropped without a counter and without a `reason`, so "duplicate collapsed"
    is not distinguishable from "card lost"; and when a loss and a collapse meet, the `reason`'s own
    numbers ("N of M job cards … so count=X is INCOMPLETE") do not add up to `count`. Measured by a
    **review probe; no test pins it** — two modules naming the same card answer `count: 1`,
    `read_entries: 2`, `skipped: 0`, `lost: 0`, `discarded: 0`, `reason: None`. This is item 4 of this
    list on the feed path — the same unexplained gap in `read_entries - discarded == count`. The
    balance **guard** added since (§2) does account for duplicates, which is why the shortening is at
    least not silent to the parser itself; what is missing is that the guard's subtrahend is not a
    published key, so it is not visible to the caller. Cheapest honest fix: return the count it already
    computes.
13. **OPEN — a failed hop A is not fail-closed, and its `reason` names the wrong cause.** The
    fail-closed rule was built for hop B (a `*jobPostingCard` that does not resolve). At hop A — the
    module URN out of `*elements` — the resolution **reason** is computed and then discarded
    (`mcp/lib/jobs_parse.py:1236`, in `read_job_collection`, where `_why` distinguishes "unresolved"
    from "ambiguous" and is dropped). Two review probes against this tree: a module URN that is not in
    `included[]`, standing next to a readable module, answers `ok: True`, `state: "hits"`,
    `discarded: 1` with the reason "no identifying job id at a readable position" — and behind that one
    lost entry can stand a whole module of job cards (module 0 of the owner's run carried three). Two
    `included[]` entries with the same **module** `entityUrn` answer the same way. So the ticket's
    fail-closed requirement for a duplicated `entityUrn` is met for the **card** URN (`card_lost`,
    `ok=False`, pinned by a test) and **not** for the module URN. Note this is not a wrong card — no
    foreign id is minted — it is a lost module reported as a projection failure. **Decision needed:**
    carry hop A's failure into `unread`/`lost` (then it is `ok=False`, consistent with §2), or leave it
    at `ok=True` and rewrite the `reason` to name the real cause. Either way the discarded `_why` is the
    fix's starting point.

How to read the state table given this list. `unknown` and `ambiguous` mean exactly what the table says.
`empty` means the container that was read was read empty (or every entry was read and carried no job),
and no candidate's `paging.total` contradicted it — pinned by tests, with two reservations that are
narrow but real: what the candidate *search* did not reach (item 1) or picked by shape alone (item 3).
The three not-understood module shapes no longer arrive here at all (item 11). `drift` means what the
table says and now covers the unread forms and the balance guard too (§2), with item 9 as an open
question about one of its triggers, not about the state. `card_lost` is the feed's reliable error edge
at hop **B** and is pinned by tests; at hop **A** there is no such edge (item 13). `hits` names cards
that really stood in the body, each with a link built from its **own** `entityUrn` — with the two
exceptions that keep item 10 open, an unrecognised entity minting an id from a foreign position when it
stands **inlined** in the starred list or in a non-starred one. An entry that the starred list names by
URN can no longer do this. `count`
is closed against every shape §4.2 lists and **not** against a body naming the same card twice
(item 12). `company` on `get_job` is evidence-joined (see §4.1); on a **feed** card it is the first half
of one measured string and there is nothing to join (§1.3).

**What the live calls did and did not settle.** Items 1 and 3 were expected to be settled by the
2026-07-30 call and were not — that 200 offered no findable container and its body was not kept (§4.0).
The owner's 2026-07-31 measurement settled the **shape** question they were waiting on (§1.3), and his
executed run of the same date answered the remaining one: **this reader** does produce on a real body
what it produces on the fixture, on the `hits` path. Neither call touches items 7 to 13 — they are
decisions and fixes in this repo, and none of them needs LinkedIn to be answered. What a **further**
call could still add is the raw body itself (item 3: whether a second, filled rail sits beside the feed
container), which the tool deliberately never returns.

---

## 7. The live calls — executed, and what they left open

**This section is a record, not a proposal.** The owner ran both tools on 2026-07-30 against `5a251da`
and the feed read again on 2026-07-31 against `75afead`; the results are in §4.0, the provenance rule in
`STATUS-MATRIX.md`. Outcome in two lines: `get_job` is verified on the 200 and the 404 path; the feed
route answered 200 and read as `state: "unknown"` on 07-30, and on 07-31 the three-hop reader produced
three correct cards out of five modules on a real body — so the recommendations **endpoint** is settled
as **usable** and the read is ✅.

**What that leaves.** The one call that was written here as a decision sheet has been made, and it
proved what it was expected to prove and no more: the `hits` path. It says nothing about what is still
open in §6 — the reach item 10 keeps, item 12 and item 13 — which are decisions in this repo and need
no call at all.

**Still worth having in a future session, and cheap:** **keep the raw response body** of such a 200 via
`tools/crawl_recursive.py` (the tool deliberately never returns bodies). It is the artifact that would
show whether the measured shape is stable and whether a second, filled rail sits beside the feed
container (§6 item 3). **Handling:** a captured feed body is private data — never commit it
(`.gitignore` already excludes `_captures*/`), and strip it before any of it reaches a doc.

**Not part of this and still unexecuted: the SDUI header question** (minimal headers vs. vgreq's Voyager
headers). It is a **write**, so it needs the owner's explicit go; the one-variable call is written out in
`COVERAGE-MAP.md` ("The one-variable test that would settle it") and stands ready — only the approval is
missing.
