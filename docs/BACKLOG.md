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

`delete_post(activity_id, tracking_id)` (`mcp/lib/client.py:583`) puts the tracking id in
`serverRequest.requestedArguments.payload.updateKeyContainer.items[0].trackingId`, next to the
activity id (`:596-600`).

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
string (`:538-551`), and `create_comment` fills the *same* `updateKey.items[].trackingId` structure
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

**Status:** diagnosed 2026-07-30. **Contains a code defect, deliberately not fixed here** (see the
code-defect list below).

1. **The intermediate read repost→share is ABSENT.** The required key is doubly nested:
   `urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:<shareId>,<repostId>)`
   (`mcp/lib/client.py:746`, `10-POST-INTERACTIONS.md`) — both parts are needed. No read in this
   repo maps a repost to those two values: neither endpoint catalog contains any
   `repost`/`instantRepost`/`reshare` entry, and the `createInstantRepost` response is not
   documented to return the URN. Precedent points the other way: on post-create the URN arrives not
   in the mutation response but in a follow-up `…closed-sharebox.server-action` call
   (`04-WRITE-OPERATIONS.md`) — an analogous follow-up for reposts was never captured.
2. **`_REPOST_DEL_QID` has no hash** — see the code-defect list. Even a perfect URN would fail.

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

## 🔩 react_to_message — HTTP 500, cause open (and it is NOT an SDUI route)

**Status:** first live observation 2026-07-30 (owner-reported 500). Diagnosed, nothing changed.

**Correction of a plausible-sounding fix path:** the suggested remedy "full captured SDUI body as a
template plus minimal headers, like `unlike`" **cannot apply here.** `react_to_message` is
**Voyager REST**, not SDUI: `mcp/lib/client.py:574-581` posts
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
   (`06-MESSAGING.md`, `mcp/lib/client.py:567`). What was actually passed is not knowable from this
   repo — the exact input is needed. **Free cross-check:** the same URN string must be able to feed
   `recall_message` (`mcp/lib/client.py:565-572`, same route family, documented 204).
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
as "verified", none corrected here): the docstring `mcp/lib/client.py:575`, `README.md:120`,
`mcp/README.md:73`, `README.md:183` ("send, recall, react … all browserless"), `04-WRITE-OPERATIONS.md` ("Send / recall / react DM … ✅ verified browserless")
and `BROWSERLESS-REPLAY.md:71` (Messaging row summarised as "fully browserless"). `STATUS-MATRIX.md`,
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

1. **`_REPOST_DEL_QID` has no hash → `delete_repost` cannot work.**
   `mcp/lib/client.py:742` sets the bare family name `"voyagerFeedDashReposts"`, used in the URL
   (`:749`) and in the body (`:751`), while every other `queryId` in the file carries a
   `<family>.<hash>` — and `02-VOYAGER-API.md` states the hash *is* the API. The real hash exists
   nowhere in this repo (all occurrences are `<hash>` placeholders). The method only checks
   `status in (200,201,204)` (`:753`) and has no rotation fallback (unlike `get_conversations`,
   `:112-117`), so a failure surfaces as a plain `ok: False`.
2. **No `data.errors` check in `create_poll` and `delete_repost` — same class: false success.**
   `04-WRITE-OPERATIONS.md` warns explicitly that a GraphQL **200 can carry a ValidationError** and
   that `data.errors` MUST be checked ("Verified the hard way"). `create_post`
   (`mcp/lib/client.py:466-481`) and `edit_post` (`:501-509`) do check it; `create_poll`
   (`:511-529`) and `delete_repost` (`:744-754`) do **not** — they report `ok` purely from the HTTP
   status.
3. **Unproven header causality asserted in a docstring.** `_sdui_min_headers`
   (`mcp/lib/client.py:377-381`) states as fact that vgreq's Voyager headers "make the SDUI endpoint
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
   (`mcp/tests/test_client.py:497`), so any test taking a fixture blows up. Green under pytest
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
Same class: `mcp/README.md` states `test_client.py (19/19)`; that file now holds 31 tests.

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
  in `create_poll` / `delete_repost` are already tracked above — same class, separate fix.)
- 🔒 **Redaction must be built with it, not after.** `grep -rn "redact\|scrub" mcp/ lib/ tools/` → 0
  hits. Bodies must never enter a message (`status` / `endpoint` / `len(body)` only); if an excerpt
  is needed, redact **then** truncate.

Not to be re-admitted as facts: the vgreq-header cause of the SDUI 500 (unverified, contradicted —
`COVERAGE-MAP.md:47-54`) and the `currentActor` cause (a red herring per
`mcp/lib/client.py:409-410`); carry the latter as one causeless class "SDUI replay incomplete".

## Notes
- The MCP is a pure API client: no browser, no clicking (refactor 01980e5). Session login/
  refresh is external (session_daemon.py keeps /tmp/li_cookies.json fresh).
- Read-only mode (`LINKEDIN_READ_ONLY`) is an operating mode of `mcp/server.py`, not a library
  guarantee: `tools/*.py` and tests importing `LinkedInClient` directly are not covered by it.
  Documented as such in `26-READ-ONLY-MODE.md` §7 — do not restate it more strongly elsewhere.
