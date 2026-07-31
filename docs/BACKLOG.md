# Backlog — linkedin-internal-api MCP

Open items, honestly scoped. Verified facts only (✅ done / 🔍 diagnosed / ⏳ todo).

## ⏳ reply_to_comment (nested replies)

**Status:** diagnosed, not implemented (2026-07-16).

`create_comment` posts **top-level comments only** (browserless SDUI createComment, verified).
Replying *to a comment* (nested, e.g. under a specific person) needs a `parentComment` binding
that top-level create does not carry.

**Why it's not built yet:** the existing capture `api-docs/_writes/comment_reply.json` is
**unusable** — it contains no parent-comment reference at all. Its two requests
(`submitCommentButton` + `createComment`) are byte-for-byte identical to the top-level
`comment_create.json` except for the random `trackingId` and the `commentBoxText` token (which
is also identical). The only "parent" strings are `parentSpanId` in the URL, which is a UI span
tracking value, NOT a comment reference. Both captures carry only the post activity id
(`7469679647589412864`) — so the "reply" capture was almost certainly a mislabeled top-level
comment, or the parent binding lives somewhere the capture didn't record.

**⚠️ `parentComment` is a GUESSED name.** No capture in this repo covers it — the paragraph above
says the capture contains "no parent-comment reference at all". It is written here as the *thing to
look for*, not as a schema fact. Never send it.

**Also correct the docs, not just the code:** `07-COMMENTS.md` and `COVERAGE-MAP.md` used to mark
reply with `✅`. Downgraded 2026-07-30 to captured/inferred-and-not-implemented, pointing here.

### Concrete capture recipe (executable as written, needs a live session)

**Blocked offline.** This needs a logged-in browser session; there is no session in an offline run.
And nothing can be diffed offline either: the old capture `api-docs/_writes/comment_reply.json`
**is not present in this clone and never was in git** (`.gitignore` excludes `_writes/`), so its
"unusable" verdict above is a repo statement that cannot be re-checked here.

1. **Script:** `tools/capture_session.py` with `CaptureSession(new_tab=True)` and human pacing (see
   `CAPTURE-PLAYBOOK.md`). **Not** `tools/capture_write_action.py` — that one runs a single JS
   action per run, grabs `page_target()[0]` and does no pacing, which loses the multi-step reply
   flow.
2. **Set `s.capture_reads = True`.** The default records only POST/PUT/DELETE, and the reply-box
   `component?componentId=…comments…` pre-call must be captured too.
3. **Target post — hard rule:** an **own** post with **no third-party comments on it**. Never work
   on a post that carries other people's comments.
4. **UI action:** create the parent test comment **browserless** first via `create_comment`
   (that path is verified), then in the UI click "Antworten" on it → type → send.
5. **Diff against:** a `dry_run=True` body from `create_comment_browserless`
   (`mcp/lib/client.py` `dry_run` branch), normalised on `TOKEN`, `trackingId` and `optimisticKey`
   (those differ per call by design). Questions the diff must answer:
   (a) same `sduiid`? (b) is `payload.collection.threadUrn` the activity thread or a comment thread?
   (c) any new `payload` keys? (d) does the state-key suffix change (`…FeedType_FEED_DETAIL`)?
   (e) is the `component` pre-call required for the submit to be accepted?
   (f) **both copies** of `requestedArguments` changed identically — the captured body carries that
   block twice (under `serverRequest.requestedArguments` and as a sibling on `serverRequest`
   level), so a reply template must patch both.
6. **Cleanup, in this order:** delete the **reply first, then the parent** — deleting a top-level
   comment does **not** delete its replies, they survive as orphans (`07-COMMENTS.md`). Delete the
   test comment immediately after the capture, same session.
7. **Then, and only then:** add `reply_to_comment`, confirm-gated, plus a URL/body-shape test.
   Which header path it must use (minimal headers like `unlike`, or vgreq like `create_comment`) is
   itself unsettled — see code-defect 3 below and "What is actually proven" in `COVERAGE-MAP.md`.

Until then, replies must be posted manually — the agent correctly declines to guess.

## 🔍 delete_post — browserless unproven, and the `trackingId` question is second

**Status:** diagnosed 2026-07-30, nothing implemented or changed.

`delete_post(activity_id, tracking_id)` (`mcp/lib/client.py:605`) puts the tracking id in
`serverRequest.requestedArguments.payload.updateKeyContainer.items[0].trackingId`, next to the
activity id (`:620-624`).

**Verdict:** the *first* missing proof is not the tracking id — it is that `delete_post` works
browserless **at all**. Evidence: the SDUI catalog entry for `com.linkedin.sdui.update.deletePost`
has `url_sample: ""` and `postData: null` (`data/endpoints_sdui.json`) — no captured body, therefore
**no `trackingId` sample in the repo** — while claiming `"verified"`. `ENDPOINTS.md` and
`COVERAGE-MAP.md` contradicted each other on this row until 2026-07-30; both now say *schema
captured, browserless not proven*.

**Is the value client-minted or server-bound? Undecided — and this repo contains precedent for
both readings, so it must not be assumed:** client-minted tokens of exactly this kind are verified
elsewhere — the `commentBoxText` token is a self-mintable protobuf of `{timestamp varint + 16 random
bytes}` (`mcp/lib/client.py:164-184`), `send_dm`'s `trackingId` is 16 **raw** bytes as a latin-1
string (`:562-575`), and `create_comment` fills the *same* `updateKey.items[].trackingId` structure
with a **random** 16-byte base64 value and is live 200 (`:223-232`, `:159-160`). Whether
`deletePost` also accepts an arbitrary value — its `activityId` already identifies the post — or
whether the value must match a server-side one, is **untested and undocumented**. The claim in
`04-WRITE-OPERATIONS.md` that "the trackingId comes from the update object (present in the feed
response)" is an **assumption**: no response body of `voyagerFeedDashProfileUpdates` is stored in
this repo, so no read is *proven* to yield a per-update tracking id.

**Cheapest experiment that decides it, in order:**
1. Free, read-only: run `get_my_posts()` live once and grep the raw JSON for `trackingId`; record
   the JSON path. Answers "is a real tracking id obtainable at all".
2. One throwaway own post, delete it browserless with the tracking id from step 1 → establishes the
   browserless path.
3. **Owner decision, irreversible, costs exactly one own post:** delete a second throwaway post
   with a **fabricated** tracking id. 2xx + post gone ⇒ client-minted, browserless cleanup needs no
   read. 4xx ⇒ a read is required.

## 🔍 delete_repost — two gaps, and the tool is not operational

**Status:** diagnosed 2026-07-30. **Updated 2026-07-31: the tool now fails honestly instead of
sending a doomed request — but it is still not operational, and both gaps below are still open.**
What changed: `delete_repost` checks the `.<hash>` suffix first (`_qid_has_hash`,
`mcp/lib/client.py:381`, call site `:776`) and returns
`{"ok": False, "status": "not_configured", "retryable": False, note: …}` naming
`tools/capture_write_action.py`, **without sending the delete request**. Scope of that claim, by
layer: the **client method** makes no transport call at all — proven offline by a test that counts
`post`/`get`/`delete` on a fake `vgreq` and requires all three empty
(`mcp/tests/test_client.py:544`); the **tool** `server.delete_repost()` still emits the
`ensure_session()` GET on `/me` before the refusal (`mcp/server.py:298`), so what holds end-to-end is
"no mutating call", not "an empty wire". No hash was invented. Not live-tested (there is no session).
**What is still missing is exactly the two items below** — one capture run closes both.

1. **The intermediate read repost→share is ABSENT.** The required key is doubly nested:
   `urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:<shareId>,<repostId>)`
   (`mcp/lib/client.py:774`, `10-POST-INTERACTIONS.md`) — both parts are needed. No read in this
   repo maps a repost to those two values: neither endpoint catalog contains any
   `repost`/`instantRepost`/`reshare` entry, and the `createInstantRepost` response is not
   documented to return the URN. Precedent points the other way: on post-create the URN arrives not
   in the mutation response but in a follow-up `…closed-sharebox.server-action` call
   (`04-WRITE-OPERATIONS.md`) — an analogous follow-up for reposts was never captured.
2. **`_REPOST_DEL_QID` still has no hash** (`mcp/lib/client.py:766`) — the real value is in no
   capture in this repo and must not be guessed. Even a perfect URN would fail, which is why the
   tool now refuses up front rather than reporting the failure as a transport problem.

**One capture run closes both** (the UI produces both values in the same flow): throwaway repost on
an **own** post ("Sofort teilen") → set `s.capture_reads = True` → (A) record the page-load GET
`…queryId=voyagerFeedDashProfileUpdates.<hash>` and grep its response for
`fsd_repost`/`instantRepost`, (B) click "…" on the repost (`feedUpdateControlMenuRequest`), (C)
"Repost löschen" → confirm: that POST yields the **live `voyagerFeedDashReposts.<hash>`** and a real
`resourceKey` URN in one go. Also dump the `createInstantRepost` response itself.
**Note for planning:** whether `repost()` works browserless is itself contradictory in this repo
(`COVERAGE-MAP.md` says "repost create browserless 200" in one place and "browser-only, 500
headless" in another; `ENDPOINTS.md` says "⚠️ 500 (browser)") — so assume the throwaway repost has
to be created through the UI. Afterwards: set `_REPOST_DEL_QID` to `<family>.<hash>` and add a
URL-shape test like the existing `test_get_my_posts_uses_exact_captured_url_shape`.
**When the hash arrives:** setting `_REPOST_DEL_QID` to the captured `<family>.<hash>` re-enables the
call automatically — the guard is a suffix check, not a feature flag. Two existing tests then still
apply: the frozen URL+body (`mcp/tests/test_client.py:578`) and the `data.errors` check on the
response (`:535`). The `NOT_OPERATIONAL` set in `mcp/tests/test_readonly.py:332` must be emptied in
the same change, otherwise the flag-off test keeps expecting the tool to send **no mutating call**
(`assert not _mutating(transport)`, `:343`) instead of requiring the write to arrive. Note the layer
while reading that assert: it does **not** claim "nothing sent" — at tool level the
`ensure_session()` GET on `/me` still goes out (`mcp/server.py:298`). "Nothing at all" is a claim
about the client method only and is held one layer down (`mcp/tests/test_client.py:544`).

## 🔩 react_to_message — HTTP 500, cause open (and it is NOT an SDUI route)

**Status:** first live observation 2026-07-30 (owner-reported 500). Diagnosed, nothing changed.
**Owner decision 2026-07-31 — do not build a fix.** The correction below (Voyager REST, no captured
SDUI body) was accepted, and the owner does not need the tool; it is carried as an **[O]** open item
in `STATUS-MATRIX.md` with the cause open and the candidates ranked by evidence strength. No code was
touched. Re-opening it means running the capture named under "Next step", not writing code first.

**Correction of a plausible-sounding fix path:** the suggested remedy "full captured SDUI body as a
template plus minimal headers, like `unlike`" **cannot apply here.** `react_to_message` is
**Voyager REST**, not SDUI: `mcp/lib/client.py:596-603` posts
`{BASE}/voyagerMessagingDashMessengerMessages?action=reactWithEmoji` with `{messageUrn, emoji}`
through `self._vg()`, and `06-MESSAGING.md` states all messaging runs over Voyager REST.li. There is
**no captured SDUI body** for message reactions anywhere (`data/endpoints_sdui.json` has none;
`mcp/lib/templates/` holds exactly three templates — unlike, react_comment, create_comment). On a
Voyager route minimal headers would be a **regression**: every verified Voyager write runs *with*
vgreq's headers.

**Status-code calibration from this repo:** this Voyager messaging family answers structurally
incomplete bodies with **400** (`createMessage` without raw-bytes `trackingId` +
`dedupeByClientGeneratedToken:false` → 400, `06-MESSAGING.md`). A **500** is documented exactly once
— for a URN that passes envelope validation but resolves wrongly server-side (wrong-order
`urn:li:comment:(<post>,<id>)` → 500, garbage key → 400, `07-COMMENTS.md`). So a 500 points more at
**semantically wrong content of an accepted field** than at a structurally broken request.

**Candidates, ranked by evidence strength:**
1. **Wrong `messageUrn` form** — inferred, strongest repo analogy (the 500-vs-400 calibration
   above). Expected form: `urn:li:msg_message:(urn:li:fsd_profile:<ME>,<msgId>)`
   (`06-MESSAGING.md`, `mcp/lib/client.py:589`). What was actually passed is not knowable from this
   repo — the exact input is needed. **Free cross-check:** the same URN string must be able to feed
   `recall_message` (`mcp/lib/client.py:587-594`, same route family, documented 204).
2. **Hand-built partial body, at least one mandatory field missing** — inferred, as a *class*:
   `createMessage` needs `mailboxUrn`, `trackingId`, `dedupeByClientGeneratedToken`, while the docs
   believe the reaction body is two fields — **without a persisted capture**. Most concrete suspect
   inside the class: a missing **`mailboxUrn`**. Further fields are ABSENT and must not be guessed.
3. **Session / permission problem** — no evidence either way, but the cheapest check and it costs
   zero captures: a 500 only counts as endpoint-specific if another Voyager write was green in the
   same session window (`like` → 201).
4. **Emoji encoding** — code fact, causality unproven: `lib/vgreq.py:45-46` serialises with
   `json.dumps` (so `👏` goes over the wire ASCII-escaped) and `:48` sets
   `content-type: application/json; charset=UTF-8`. That is **valid** JSON, and nothing in this repo
   shows LinkedIn 500s on it. Keep it as a cheap test, not as a suspicion with evidence.
5. **Wrong/stale action name `reactWithEmoji`** — inferred, low: the name was noted from real client
   traffic at least once (`06-MESSAGING.md`).
6. **Headers** — no evidence at all, and see candidate ordering above: all verified Voyager writes
   use exactly these headers.

**Remaining doc drift for `react_to_message`, outside this ticket's file scope** (each still reads
as "verified", none corrected here): the docstring `mcp/lib/client.py:597`; in `README.md` the
**Messaging** row of the tool table under "The MCP server" and the **Messaging** bullet under
"Coverage" ("send, recall, react … all browserless"); in `mcp/README.md` the **Messaging** line
under "Tools"; `04-WRITE-OPERATIONS.md` ("Send / recall / react DM … ✅ verified browserless");
and in `BROWSERLESS-REPLAY.md` the Messaging row under "Status per operation family" (summarised
as "fully browserless"). `STATUS-MATRIX.md`,
`ENDPOINTS.md` and `COVERAGE-MAP.md` were corrected on 2026-07-30.

**Next step — zero calls first:** get the exact `message_urn` that produced the 500, and check
whether another Voyager write was green in the same window (decides 1 and 3). **Then one capture**
of the real web client setting **and immediately un-setting** a 👏 reaction — it decides 1, 2, 4 and
5 at once because it yields body *and* headers. **Owner decision:** a reaction notifies the other
person in the thread, so the thread has to be chosen deliberately; whether a self/notes thread
exists is ABSENT.

## ⏳ Code defects found while researching the above — deliberately NOT fixed here

**Status:** all diagnosed 2026-07-30 in a **doc-only** ticket; every item below is a code or test
change and therefore out of scope by rule. Each has file + symptom + basis.

1. **`_REPOST_DEL_QID` has no hash → `delete_repost` cannot work.** — **the missing hash is still
   open, the silent-failure half is fixed (2026-07-31).**
   `mcp/lib/client.py:766` sets the bare family name `"voyagerFeedDashReposts"`, used in the URL
   (`:785`) and in the body (`:787`), while every other `queryId` in the file carries a
   `<family>.<hash>` — and `02-VOYAGER-API.md` states the hash *is* the API. The real hash exists
   nowhere in this repo (all occurrences are `<hash>` placeholders) and was **not** invented.
   The method no longer sends that request at all: it detects the missing suffix (`:776`) and
   returns a distinguishable non-retryable error with the re-capture path. Tracked above in
   "delete_repost — two gaps".
2. ~~**No `data.errors` check in `create_poll` and `delete_repost`**~~ — **FIXED 2026-07-31,
   offline-proven, not live-tested.** `04-WRITE-OPERATIONS.md` warns that a GraphQL **200 can carry
   a ValidationError** and that `data.errors` MUST be checked ("Verified the hard way"). Every
   GraphQL write in the file now does, through one shared extractor `_gql_errors()`
   (`mcp/lib/client.py:367`): `create_post` (`:491`), `edit_post` (`:522`), `create_poll` (`:538`),
   `delete_repost` (`:790`). `create_poll` additionally no longer returns a `poll_urn` when the body
   carries errors. A regression guard parses `client.py` and fails on a method that POSTs an
   `action=execute` mutation, reports `ok` and skips `_gql_errors`
   (`mcp/tests/test_client.py:556`). **The guard's reach is narrower than "any future method"** — see
   the residue entry below, item 5: it is a literal-text match over the sync `ast.FunctionDef` nodes
   of `LinkedInClient`. **Residues of the same class are tracked as their own entry
   below ("False-success residues").**
3. **Unproven header causality asserted in a docstring.** `_sdui_min_headers`
   (`mcp/lib/client.py:401-405`) states as fact that vgreq's Voyager headers "make the SDUI endpoint
   500". That is not verified and is contradicted for `comments.createComment` by `:242` (SDUI route
   + vgreq headers, documented live 200). See "SDUI header causality" in `COVERAGE-MAP.md` for the
   one-variable test. **Do not delete the docstring line before that test has run** — mark it, then
   settle it.
4. **`tools/build_docs.py` truncates `url_sample` AND `postData` at 200 characters**
   (`tools/build_docs.py:102`, `:105`). Because of that the complete query strings of the jobs
   search route and the `SearchFilterClusters` route are lost from the catalog.
   **⚠️ Fixing the truncation alone is not enough and would be actively misleading:** the existing
   values in `data/endpoints_voyager.json` were produced *by the old rule*, and the raw captures are
   **not in this repo**. So either re-derive the catalog in the same change that changes the rule, or
   leave both alone — a longer limit applied to old rows yields old, still-truncated values that now
   *look* complete.
5. **Stale tool counts ("26 tools")** — already tracked as its own entry above. Not corrected in this
   ticket either: no test holds those numbers in the affected files.
6. **Seven writing tools without a confirm gate** — already tracked as its own entry above; it is an
   **owner decision** (`endorse_skill` writes on a third party's profile), not something to change
   unilaterally.
7. **The standalone runner of `mcp/tests/test_client.py` is broken.**
   `python mcp/tests/test_client.py` raises
   `TypeError: test_delete_comment_force_bypasses_guard() missing 1 required positional argument:
   'monkeypatch'` — the module's own `main()` calls each collected test as `t()`
   (`mcp/tests/test_client.py:601`), so any test taking a fixture blows up. Green under pytest
   (`./.venv/bin/python -m pytest mcp/tests tests -q`). Pre-existing, reproduced against this
   ticket's baseline.
8. **The READ_ONLY gate has a whitelist that tests cannot see yet.** `write_tool`
   (`mcp/server.py:59`, whitelist logic `:77-80`) marks the wrapper with `__li_write__ = True`
   (`:92`) but does **not** put `network_free_param` on the wrapper, so a registry test cannot
   assert *which* tools are whitelisted — it can only see *that* a tool is a write. Additionally the
   combination `dry_run=True` **and** `confirm=True` is missing from the matrix in
   `mcp/tests/test_readonly.py` (the dry-run tests at `:241-269` cover plain, boundary, positional
   and `force`, but never `confirm=True` alongside `dry_run=True`). Roughly six lines of
   follow-up.

## ⏳ False-success residues after the `data.errors` fix — the class is narrowed, not closed

**Status:** measured offline against the current tree on 2026-07-31 (fake `vgreq`, no network, no
cookie file) while reviewing the `data.errors` fix. **Deliberately not fixed there:** the ticket
prescribed reusing `create_post`'s pattern verbatim, so these residues are inherited, not new — but
`create_poll` and `delete_repost` now inherit them too, and the shared extractor is the one cheap
place to close them. Nothing here changes what is **sent**.

1. **A 200 whose body is not parsable JSON reads as success.** `_gql_errors`
   (`mcp/lib/client.py:367`) returns `[]` on any exception, so `r.json()` raising (login
   interstitial, HTML error page) is indistinguishable from "no errors" and yields `ok: True`.
   Measured: a fake 200 whose `.json()` raises → `create_poll` `{"status": 200, "ok": True}`.
   For an unattended agent with an ageing cookie this is the realistic case, and it is exactly the
   "failure that looks like a success" class.
2. **A top-level `errors` next to `data: null` is not seen.** The extractor looks only inside
   `data`. Measured: `{"data": null, "errors": [{"message": "NOPE"}]}` with status 200 →
   `create_post` and `create_poll` both `ok: True`. The **captured** shape in this repo is
   `data.errors` (`04-WRITE-OPERATIONS.md`), so reading the union of both is defensive, not an
   invented field semantics — but it is unproven for LinkedIn and must be labelled as such.
3. **The error text crosses the tool boundary unvalidated and uncapped.** `errors[0].get("message")`
   is a server-controlled value: a non-string (`dict`, `list`) propagates as-is into the tool
   response, and an arbitrarily long message rides along in full. Nothing redacts or truncates it
   (`grep -rn "redact\|scrub" mcp/ lib/ tools/` → 0 hits, same gap as in
   `SESSION-AND-ERRORS-DESIGN.md` §2).
4. **Only the extraction is centralised, the verdict is not.** `ok = 2xx AND not errors` and
   `errors[0]["message"]` still stand once per method, so there is no single place that answers
   "did this write succeed?" — which is why 1–3 have to be fixed four times or not at all.
5. **The class guard against a *future* blind write is a literal-text heuristic, so it can fail
   open.** `test_every_graphql_write_checks_data_errors` (`mcp/tests/test_client.py:556`) parses
   `client.py` with `ast`, iterates the `ast.FunctionDef` nodes in the `LinkedInClient` class body,
   and flags a method whose source segment contains `action=execute`, `.post(` and `"ok"` but not
   `_gql_errors`. Each of those three is a substring match, so the guard misses a method that
   (a) builds the URL from a constant or a helper — no literal `action=execute` in the body,
   (b) returns `dict(ok=…)` or writes `'ok'` in single quotes, (c) is declared `async def`
   (`ast.AsyncFunctionDef` is not iterated), or (d) sits outside that one class body. It caught the
   two instances that existed; do not read it as "the class is closed". Structural alternative, if
   the class does reappear: make the *verdict* helper of item 4 the only place that may build a
   GraphQL write's `ok`, and assert that against the real artifact instead of against its text.

**Cheapest fix, zero live calls, nothing sent changes:** widen the chokepoint into a verdict helper
(e.g. `_gql_result(r, ok_codes) -> (ok, error, parse_failed)`) that (a) reads
`data.errors` **and** a top-level `errors`, (b) reports a 200 with an unparsable body as **not**
`ok` (or at minimum attaches a `note` saying the body could not be read), and (c) coerces the
message to `str` and truncates it at a fixed budget. Then the four writes only pass their allowed
status codes. This closes 1–4 in one place and is fully testable offline with the existing fake
`vgreq` pattern. **Do not** let it change any URL or body — the frozen-shape test
(`mcp/tests/test_client.py:578`) is the guard.

## ⏳ Stale tool counts in the docs ("26 tools")

**Status:** diagnosed, not fixed — foreign scope of the read-only ticket (2026-07-30).

`README.md` (5×), `docs/MCP-DESIGN.md` (3×), `docs/00-OVERVIEW.md` and `mcp/README.md` still say
**26 tools** (`grep -n '26 tools\|26 MCP tools\|26 @mcp.tool' README.md docs mcp/README.md`). The registry
holds **29** (10 reads + 19 writes) — `create_comment`, `delete_comment` and `react_to_comment`
were added later and never counted. Two tests now hold the exact set
(`mcp/tests/test_server.py` `EXPECTED`, and the read/write split in `mcp/tests/test_readonly.py`),
so the number is no longer guesswork.
**To fix:** replace every occurrence (including the badge line and the mermaid label
`26 @mcp.tool` in `README.md`) with the tested split, and re-check the per-domain tool lists in the
same sections — they omit the three comment tools too.
Same class: `mcp/README.md` states `test_client.py (19/19)` while that file holds more tests than
that. Fix it the same way — quote no count that no test holds;
`./.venv/bin/python -m pytest mcp/tests tests -q` prints the current one.

## ⏳ Citation drift — rule adopted as a convention, enforcement NOT built

**Status:** the rule below is adopted as a writing convention (2026-07-31). **No test enforces it.**
A machine guard was written and then deliberately left out of the shipping commit — see "Why the
guard is not in the tree" at the end of this entry. Every anchor, doc and code, is checked by hand.

Why this exists: in this repo the citation *is* the evidence. A reference that pins a Markdown file
to a line number decays silently — any edit that inserts lines above that number shifts the target,
the anchor still resolves, and a reader who verifies a row marked VERIFIED finds *different* text
under it. That happened while the `data.errors` / `delete_repost` ticket was written: its doc edits
shifted `COVERAGE-MAP.md` and `STATUS-MATRIX.md` downwards and made ten previously correct anchors
point at foreign text. Same false-success class as a write that reports `ok` on a body carrying
`ValidationError`, one level up: in the evidence instead of in the code.

**The rule.** A doc-to-doc reference names the **file and the section** (e.g. `docs/COVERAGE-MAP.md`,
section "Current state (live)", bullet "Proven factor — the body") and carries **no line number**.
A heading survives edits above it; a line number does not. Code references are the one exception —
`mcp/lib/client.py:596-603` is useless without the numbers.

**What holds today: nothing but discipline.** No test rejects a new `<file>.md:<line>` reference,
and no test checks that an existing anchor still points at the intended text. Doc anchors and code
anchors (`mcp/lib/client.py:NN`) alike drift on every edit above them. Two were corrected by hand
here (`react_to_message` was cited as `mcp/lib/client.py:596-605` in `STATUS-MATRIX.md` and in this
file; the method ends at `:603`, `:605` is `def delete_post`).

**Why the guard is not in the tree.** A `mcp/tests/test_doc_citations.py` was written that rejects
*new* line citations and grandfathers the pre-existing ones in a `FROZEN_DOC_LINE_CITATIONS`
allowlist. It is preserved on the branch `wip/p4-citation-guard` and was kept out of the shipping
commit for two reasons. First, the freeze list is checked for **existence only** — target file
exists, cited line is inside it — so it cannot tell whether an anchor points at the *intended* text;
with 25 live entries, a green suite would stop meaning "the anchors are correct" while looking like
it does. In a repo where the citation *is* the evidence, that is the false-success class one level
up: in the proof rather than in the code. Second, it was foreign scope in a ticket about
`data.errors`, and it is the change the review gates failed on.

**A version worth building** would carry a short **quoted anchor text** with each reference and
match that against the target, so it verifies meaning instead of existence — and it would then
cover code anchors too. That is the ticket to write; grandfathering is not.

**To close:** convert the remaining `<file>.md:<line>` references to file + section as their
surrounding prose is next touched, and build the quoted-anchor version above. Neither is started.

## ⏳ Seven writing tools have no `confirm` gate

**Status:** observation, deliberately unchanged (2026-07-30) — needs an owner decision.

`like`, `unlike`, `follow_company`, `endorse_skill`, `save_post`, `create_poll` and
`react_to_message` fire a real write on the **first** call; the other twelve writes require
`confirm=True`. `endorse_skill` is the sharpest case: it writes on a **third party's** profile.
`LINKEDIN_READ_ONLY` now covers all seven in unattended operation, but with the flag off they are
still one call away.
**To decide:** whether these get `confirm=True` as well (changes the tool contract for every
existing caller) or stay ungated by intent. Not a defect — a design decision.

## ⏳ Session age / cookie inventory in `session_status` — designed, NOT built

**Status:** fully specified against the current tree, no code written (2026-07-31).
**Design + evidence:** [`SESSION-AND-ERRORS-DESIGN.md`](SESSION-AND-ERRORS-DESIGN.md) §1.

`session_status` returns only `logged_in`, `read_only` and `hint` (`mcp/server.py:197-201`). Wanted: a
cookie inventory in the shape the Indeed MCP reports (`count`, `hosts`, `file_age_h`,
`soonest_expiry_days`, `markers_missing`).

**The design partially refuses the request, on evidence — read §1 before implementing:**
`soonest_expiry_days` and `hosts` have **no data source** in this repo, because both cookie
producers keep only `{name: value}` and discard `expires` and `domain`
(`lib/cookies_extract.py:35`, `mcp/lib/session_browser.py:142-143`). They must be reported as
`null` **with the reason**, never as a number. And `li_at` is **not** a JWT
(`01-AUTH-AND-COOKIES.md:10`), so nothing is derivable from it either. The mtime of
`/tmp/li_cookies.json` is **not** session age — `mcp/session_daemon.py:43` rewrites the file on a
cycle — so the field has to be called `cookie_file_age_h`.

**Buildable today:** `count`, `markers_missing` (`li_at` + `JSESSIONID`), `cookie_file_age_h`, and
whether `LI_OWNER_URN` is set (unset silently blocks **every** `delete_comment`, including the
owner's own — `mcp/lib/client.py:38`, guard `:326`, `:328-334`).
**Two prerequisites before any file-derived field:** unify the two cookie-path notions
(`VG_COOKIES` vs. the unused `self.cookies_path`, §1.8) and make every reader accept **both**
payload shapes — `lib/vgreq.py:11-15` reads the flat dict and breaks on a list (§1.7).

## ⏳ Error taxonomy with `session_suspect` — designed, NOT built

**Status:** fully specified against the current tree, no code written (2026-07-31).
**Design + evidence:** [`SESSION-AND-ERRORS-DESIGN.md`](SESSION-AND-ERRORS-DESIGN.md) §2, table L1–L13.

Today `mcp/lib/client.py:72-76` collapses "no cookie file", "network/timeout", "missing marker" and
a genuine auth failure into one `except Exception: return False`, which surfaces as
`logged_in: false` — i.e. **as a session problem** in all four cases (`mcp/server.py:197-201`). That
is the mechanism behind "every 403 means the session is dead".

**The headline finding:** of every evidenced failure mode, **exactly one** is real session death —
the **302 → `/uas/login`** (`05-VERIFICATION.md:91`, arriving as a 302 because
`lib/vgreq.py:41,49,52` pass `allow_redirects=False`). The **403 is explicitly not** a session
problem but a missing/malformed `csrf-token` (`01-AUTH-AND-COOKIES.md:13-14`).

**Three things not to get wrong** (all in §2):
- ⚠️ The content-type step must **not** be copied 1:1 from Indeed: Voyager answers
  `application/vnd.linkedin.normalized+json+2.1` (`01-AUTH-AND-COOKIES.md:80`), so a naive
  `"application/json" in ctype` would classify every successful Voyager response as non-JSON.
- The most important class is the **GraphQL 200 carrying `data.errors`** — the status actively lies
  (`04-WRITE-OPERATIONS.md:114-117`). Body signal is checked **before** status. (The missing checks
  in `create_poll` / `delete_repost` were fixed on 2026-07-31; the **residues** of the class are
  tracked above under "False-success residues" and are the part a taxonomy has to absorb.)
- 🔒 **Redaction must be built with it, not after.** `grep -rn "redact\|scrub" mcp/ lib/ tools/` → 0
  hits. Bodies must never enter a message (`status` / `endpoint` / `len(body)` only); if an excerpt
  is needed, redact **then** truncate.

Not to be re-admitted as facts: the vgreq-header cause of the SDUI 500 (unverified, contradicted —
`COVERAGE-MAP.md`, section "Current state (live)", bullet "Unproven factor — the headers") and the
`currentActor` cause (a red herring per
`mcp/lib/client.py:433-434`); carry the latter as one causeless class "SDUI replay incomplete".

## Notes
- The MCP is a pure API client: no browser, no clicking (refactor 01980e5). Session login/
  refresh is external (session_daemon.py keeps /tmp/li_cookies.json fresh).
- Read-only mode (`LINKEDIN_READ_ONLY`) is an operating mode of `mcp/server.py`, not a library
  guarantee: `tools/*.py` and tests importing `LinkedInClient` directly are not covered by it.
  Documented as such in `26-READ-ONLY-MODE.md` §7 — do not restate it more strongly elsewhere.
