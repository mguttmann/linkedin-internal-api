# Session Visibility & Error Taxonomy — Design

> ## STATUS, split in two (updated 2026-07-31)
>
> **Section 2 — the error taxonomy — is now BUILT in its narrow form.** What exists:
> `mcp/lib/errors.py` (`classify`, `classify_exception`), the diagnosis behind
> `ensure_session()` (`probe_session` in `mcp/lib/client.py`), and three new fields on
> `session_status` (`mcp/server.py`). The invariants are held by tests
> (`mcp/tests/test_errors.py`, `mcp/tests/test_server.py`) — see **section 2.7** for the exact
> list of what is held and what is not.
> Every one of those tests runs against a **faked transport**: no live LinkedIn call was made, so
> **nothing here became `✅ verified`** and nothing may — per `05-VERIFICATION.md:3-6` that marker
> needs a real executed call with a documented HTTP status. Read the built part as
> **offline-proven, not yet live-tested.**
>
> **Section 1 — the cookie inventory — stays ⛔ NOT BUILT, deliberately.** The owner declined it
> (see section 1.0): `soonest_expiry_days`, `hosts`, `file_age_h`, the cookie count and the
> marker inventory are **non-goals**, not backlog. Sections 1.1–1.9 remain a design brief only.
> Nothing in `lib/cookies_extract.py`, `mcp/lib/session_browser.py` or `mcp/session_daemon.py`
> was touched, and the four inconsistent marker checks of section 1.5 are still four.
> Section 4's scope sketch is annotated per item.
>
> What *is* solid throughout: every claim about **this repo's own code and docs** was read at the
> cited `file:line` against commit `7b662e3`. Claims about LinkedIn's *behaviour* carry a label
> (VERIFIED / CAPTURED / INFERRED / ABSENT, legend below) and several of them are **ABSENT** — that
> is written down as ABSENT, not smoothed over.
>
> Line numbers rot. If a citation does not match what you read, trust the code and fix this file.

**Labels** (same discipline as `STATUS-MATRIX.md`, applied to error signals):

| Label | Means |
|---|---|
| **VERIFIED** | the repo documents a really executed call with its HTTP status. For statements *about source code*: read at the cited line — noted as "code fact". |
| **CAPTURED** | seen in real client traffic; we did not execute it. |
| **INFERRED** | derived from structure, naming or a docstring claim; **not** confirmed. |
| **ABSENT** | no evidence in this repo. Not "false" — *unknown*. |

**Origin.** Two operational requests from the owner, both still open:
(1) make session age visible in `session_status`, (2) an error taxonomy with `session_suspect`, so
that not every 403 reads as "session dead". The sibling repo `indeed-internal-api` solves both and
is used below as a **reference to copy from**. It is **READ-ONLY — never modify it.**

---

## 1. The honest answer to request (1) first: most of it is not derivable today

### 1.0 ⛔ Declined by the owner (2026-07-31) — this whole section is a non-goal

The owner read sections 1.1–1.9 and **dropped request (1) entirely**, accepting the argument that a
number measuring something other than what its name suggests is worse than no number — explicitly
including `file_age_h`, which the 300-second rewrite cycle of section 1.4 would have made *actively*
misleading. Declined, and therefore **not** to be re-proposed as a backlog item:
cookie age, `file_age_h`, `hosts`, `soonest_expiry_days` and the cookie inventory as a whole.

What was asked for instead is the small thing that already lay in this document: **one field that
says whether a given error means session death** — `session_suspect`, plus the express note that a
403 from a missing csrf-token is **not** one. That is section 2, and only section 2 was built
(section 2.7). Sections 1.1–1.9 stay below unchanged as the record of *why* the answer was no.

The requested shape was Indeed's:

```json
"cookies": {"count": 56, "hosts": 14, "file_age_h": 21.73,
            "soonest_expiry_days": -0.98, "markers_missing": []}
```

Of these five fields, **two can be reported honestly today, one is a trap, and two have no data
source in this repo at all.** Building the full shape now would mean inventing numbers.

| Field | Buildable today? | Why |
|---|---|---|
| `count` | **yes** | the cookie file is a dict of names → `len()` |
| `markers_missing` | **yes** | markers are known: `li_at` + `JSESSIONID` (§1.3) |
| `cookie_file_age_h` | **yes, but only under that name** | mtime is *not* session age (§1.4) |
| `hosts` | **no** | `domain` is discarded by both producers (§1.1) |
| `soonest_expiry_days` | **no** | `expires` is discarded by both producers (§1.1) |

### 1.1 `soonest_expiry_days` and `hosts`: the data is thrown away, not missing

**VERIFIED (code fact).** Both cookie producers write a flat `{name: value}` dict and drop every
other cookie attribute:

- `lib/cookies_extract.py:35` — `li = {c["name"]: c["value"] for c in cookies if "linkedin" in
  c.get("domain", "")}`, written out at `:42`. The CDP result at `:34`
  (`Network.getAllCookies`) contains the full records; the comprehension keeps two keys.
- `mcp/lib/session_browser.py:142-143` — the same reduction over `self._ctx.cookies()`; dumped by
  `dump_cookies()` at `mcp/lib/session_browser.py:175-179`.

So the CDP API **does deliver** `expires` — the sibling repo reads exactly that field at
`indeed-internal-api/tools/cookies_extract.py:66` (`"expires": cookie.get("expires", -1)`). The
information is **discarded**, not unavailable. Same for `domain`, which is why `hosts` has no
source either: it is used in the filter condition and then dropped.

### 1.2 ⚠️ `li_at` is **not** a JWT — do not "decode" it

**ABSENT.** No place in this repo decodes `li_at`, there is no documentation of its internal
structure, and no expiry timestamp is documented anywhere.
`docs/01-AUTH-AND-COOKIES.md:10` describes it as `AQEDA…` **(long opaque string)** — not a JWT
shape — and `docs/01-AUTH-AND-COOKIES.md:71` says only, qualitatively, that it "stays valid for
weeks to months".

**Any claim that the expiry is "derivable from the `li_at` JWT" would be an invention.** If an
implementation ever computes a number from `li_at`, that number is fabricated. This warning stands
here precisely because the idea is plausible-sounding and wrong.

### 1.3 Consequence for the implementation: report `null` **with the reason**

Until a data source exists, `soonest_expiry_days` and `hosts` must be reported as `null` — together
with the reason, machine-readable, in the same response. A `0` or an estimate would be exactly the
forbidden thing: **a stored value without the rule that produced it.**

Sketch (design, not built; the values below are illustrative placeholders, held by no test):

```json
"cookies": {
  "count": 12,
  "markers_missing": [],
  "cookie_file_age_h": 0.02,
  "soonest_expiry_days": null,
  "hosts": null,
  "unavailable": {
    "soonest_expiry_days": "cookie file carries no expiry — lib/cookies_extract.py:35 keeps only {name: value}",
    "hosts": "cookie file carries no domain — same line"
  },
  "cookie_file_age_note": "session_daemon.py rewrites this file on a cycle; the age is the age of the WRITE, not of the login"
}
```

Rule: a field that has no source is `null` **plus** an entry in `unavailable`. Never a number.

### 1.4 ⚠️ The trap that hits the request directly: mtime is not session age

**VERIFIED (code fact).** `mcp/session_daemon.py:39-48` is an idle loop that re-dumps the cookie
file on a fixed cycle — the interval is at `mcp/session_daemon.py:43`:
`if time.time() - last > 300:  # every 5 min`, calling `sb.dump_cookies("/tmp/li_cookies.json")`
at `:45`. The file is also written once at startup (`:36`).

Therefore, while the daemon runs, the mtime of `/tmp/li_cookies.json` is **always small** — bounded
by that cycle — completely independent of how old the login is. A field named `file_age_h` would
suggest "your session is this old", and that reading would be wrong on every single call.

**ABSENT: there is no `login_at_ms` anywhere in this repo.** The login path is
`mcp/bootstrap_login.py` (per `mcp/README.md:57`), and it writes no login marker.

**Recommendation:** name the field `cookie_file_age_h`, and ship the daemon note with it (see §1.3).
If a true session age is wanted later, it needs a *second* timestamp written at login time — that
is a change to the login path, not to `session_status`.

### 1.5 What can be reported honestly, today

**`count`** — `len()` over the cookie dict. Trivially available.

**`markers_missing`** — the two decisive cookies are documented: `li_at` (session) and `JSESSIONID`
(CSRF), `docs/01-AUTH-AND-COOKIES.md:6-16`; without the `csrf-token` header derived from
`JSESSIONID` a call gets **HTTP 403** (`docs/01-AUTH-AND-COOKIES.md:13-14`). Today these markers
are checked in **four places, inconsistently** (all VERIFIED, code facts):

| Place | Behaviour when a marker is missing |
|---|---|
| `lib/vgreq.py:13` | `li["JSESSIONID"]` → raw **`KeyError`** before any request |
| `mcp/lib/client.py:410` | `cookies.get("JSESSIONID", "")` → **empty** csrf header, request goes out and 403s |
| `lib/cookies_extract.py:37-41` | missing `li_at` → `exit(1)`; missing `JSESSIONID` → **warning only**, file is written anyway (`:42`) |
| `mcp/lib/session_browser.py:144-145` | checks **only** `li_at`, raises `NotLoggedInError` |

Target: one `SESSION_MARKERS = ("li_at", "JSESSIONID")` constant, one store, `markers_missing` in
the status, and a hard `assert_session()` instead of a stack trace. Reference implementation:
`indeed-internal-api/lib/cookies.py:29` (`SESSION_MARKERS`), `:236` (`missing_markers`),
`:240` (`assert_session`).

**Whether `LI_OWNER_URN` is set** — this belongs in the status because its absence silently
disables a whole tool. **VERIFIED (code fact):** `mcp/lib/client.py:38` defaults `ME` to the inert
placeholder `"urn:li:fsd_profile:REPLACE_WITH_YOUR_PROFILE_URN"` (and `:39` `VANITY` to
`"your-vanity-name"`). The owner guard in `delete_comment` compares the real comment author against
that placeholder — `mcp/lib/client.py:326` derives `owner_id = ME.rsplit(":", 1)[-1]`, and
`:328-334` returns `{"ok": False, "status": "blocked", …}` whenever author ≠ owner. With
`LI_OWNER_URN` unset the comparison can never match, so every comment **whose author the guard can
resolve** is blocked, including the owner's own. Two documented paths still get through: the guard
only runs `if not force and not dry_run` (`mcp/lib/client.py:325`), and it lets the delete proceed
when the author cannot be resolved at all (`:328`, idempotent by design). That is fail-closed and
correct — but without visibility in `session_status` it is inexplicable to the caller.

### 1.6 Build order for the expiry source (do not skip a step)

1. **`lib/cookies_extract.py:35`** — keep the full CDP record per cookie
   (`name, value, domain, path, secure, httpOnly, expires`) plus top-level meta such as
   `captured_at_ms`. Model: `indeed-internal-api/tools/cookies_extract.py:60-67` (the record) and
   `:160-164` (the payload wrapper with `captured_at_ms`).
2. **`mcp/lib/session_browser.py:142-143` / `:175-179`** — the same for the patchright path.
   ⚠️ **That patchright's `context.cookies()` returns `expires` at all is INFERRED, not verified.**
   Prove it with an offline assert against `SessionBrowser`; do not assume it. If it does not, this
   producer keeps writing a reduced record and the status must say which producer wrote the file.
3. **Only then** does `soonest_expiry_days` have a source, and only then may the field carry a
   number. Semantics worth copying: `indeed-internal-api/lib/cookies.py:105`
   (`expires_in_days`) returns **`None` for a session cookie with no expiry** — `None` is a real
   answer there, not an error. A **negative** value is also legitimate: an expired cookie can still
   sit in the file.

### 1.7 ⚠️ Migration warning: the flat dict has a consumer that will break

**VERIFIED (code fact).** `lib/vgreq.py:11-15` reads exactly the flat dict:
`li = json.load(open(COOKIE_FILE))`, then `li["JSESSIONID"]` (`:13`) and `li.items()` (`:14`). Hand
it a list-shaped payload and it breaks immediately — and `vgreq` is the transport under *every*
call.

`mcp/lib/client.py:409` already accepts **both** shapes
(`cookies = {c["name"]: c["value"] for c in li} if isinstance(li, list) else li`), but **no producer
in this repo writes the list form** (§1.1) — so that branch is dead today, and its origin is
INFERRED. A new store must **read both** shapes and **write one**; `lib/vgreq.py` has to learn the
new shape in the *same* change that starts writing it.

### 1.8 ⚠️ Resolve the second cookie path first, or the status lies about which file it read

**VERIFIED (code fact).** There are two independent notions of "the cookie file":

- `lib/vgreq.py:9` — `COOKIE_FILE = os.environ.get("VG_COOKIES", "/tmp/li_cookies.json")`, and
  `mcp/lib/client.py:407` reads the same env var for the SDUI header path.
- `mcp/lib/client.py:57-58` — constructor default `cookies_path: str = "/tmp/li_cookies.json"`,
  stored as `self.cookies_path`. Grep says `cookies_path` appears **only** on those two lines:
  the attribute is never read anywhere.

With `VG_COOKIES` pointing elsewhere, a `session_status` that inspected `self.cookies_path` would
report on a **different file** than the one the requests actually read. Unify on one resolver before
adding any file-derived field.

### 1.9 Blocks to copy from `indeed-internal-api` (reference only, never modify that repo)

Verified present at `indeed-internal-api` commit `d9d0c34`:

| Symbol | Location | Use here |
|---|---|---|
| `SESSION_MARKERS` | `lib/cookies.py:29` | the marker constant |
| `SessionMissing` | `lib/cookies.py:77` | "no file / no session" as its own error, not `logged_in: false` |
| `CookieRecord` | `lib/cookies.py:92` | the full record shape |
| `expires_in_days()` | `lib/cookies.py:105` | `None` = session cookie without expiry |
| `CookieStore.load()` / `.from_payload()` | `lib/cookies.py:136` / `:149` | load + parse the payload wrapper |
| `names()` / `hosts()` | `lib/cookies.py:209` / `:212` | inventory without values |
| `inventory()` | `lib/cookies.py:217` | emits **lengths, never values** |
| `missing_markers()` / `assert_session()` | `lib/cookies.py:236` / `:240` | hard session precondition |
| `captured_at_ms` / `file_age_hours()` | `lib/cookies.py:270` / `:277` | the two timestamps of §1.4 |
| status dict assembly | `mcpserver/tools_session.py:74-81` | field order and naming |
| missing-session path | `mcpserver/tools_session.py:62-65` | `{"present": False, "problem": …}` + remediation |
| "never prints cookie values" promise | `mcpserver/tools_session.py:43` | the docstring guarantee to restate here |

**Do not copy** `cf_clearance_state()` (`indeed-internal-api/lib/cookies.py:332`): it is
Cloudflare-specific and **has no LinkedIn analogue**. Indeed-specific concepts must not ride along
into this taxonomy just because the helper next to them was useful.

---

## 2. Request (2): the error taxonomy

### 2.1 The headline: exactly **one** provable error mode means the session is dead

Of every failure mode this repo can evidence, **only** the redirect to the login page is real
session death:

> **302 → `/uas/login`** — `docs/05-VERIFICATION.md:91` ("302 → /uas/login | Session dead |
> re-login, re-fetch cookies"), confirmed by `docs/01-AUTH-AND-COOKIES.md:72` ("If the session
> expires, a call lands on the login page (302 → `/uas/login`)"). It arrives as a **302** rather
> than as login-page HTML because the transport does not follow redirects:
> `lib/vgreq.py:41`, `:49`, `:52` all pass `allow_redirects=False`.

### 2.2 And the 403 is **not** a session problem

**VERIFIED.** A 403 in this API means the `csrf-token` header is missing or malformed —
`docs/01-AUTH-AND-COOKIES.md:13-14`: the header equals `JSESSIONID` **without the surrounding
quotes** (the `ajax:` prefix stays), and "Without this header → **HTTP 403**". The cheat sheet
agrees: `docs/05-VERIFICATION.md:93` — "403 | CSRF missing | set `csrf-token` header = JSESSIONID".
The exact place where an empty header can be produced is `mcp/lib/client.py:410`
(`cookies.get("JSESSIONID", "")` — no marker, no exception, empty csrf).

So the reflex "every 403 means the session is dead" is **contradicted by this repo's own
evidence**: a 403 says *fix the header* (re-fetch `JSESSIONID`, strip the quotes), while the session
itself may be perfectly alive. That is the single biggest source of guesswork the taxonomy removes,
and it is why `session_suspect` must be a field of its own rather than a function of the status code.

Honest counter-note: `docs/05-VERIFICATION.md:82` does group "302/401/403" together as the trio
after which you should "first check **cookie freshness** (`GET /voyager/api/me` → 200?)". That is
advice about a *cheap probe*, not a classification — and it is exactly why the response to a 403
should be "probe `/me`", not "declare the session dead".

### 2.3 The list (L1–L13)

`session_suspect` column: **YES** = re-login is the right response. **NO** = re-login would not help
and is the wrong reflex. **unknown** = declare it unknown, do not guess.

| # | Signal | `session_suspect` | Evidence | Label |
|---|---|---|---|---|
| **L1** | **302 → `/uas/login`** on a Voyager call (arrives as 302 because `allow_redirects=False`, `lib/vgreq.py:41,49,52`) | **YES — the only evidenced case** | `docs/05-VERIFICATION.md:91`; `docs/01-AUTH-AND-COOKIES.md:72` | VERIFIED |
| **L2** | **403** — `csrf-token` missing or malformed | **NO** — client header defect. Remediation: re-fetch `JSESSIONID`, strip quotes | `docs/01-AUTH-AND-COOKIES.md:13-14`; `docs/05-VERIFICATION.md:93`; producer `mcp/lib/client.py:410` | VERIFIED |
| **L3** | **401** | **unknown** — declare it unknown; remediation is the `/me` probe | **ABSENT**: the cheat-sheet table `docs/05-VERIFICATION.md:87-94` lists **no** 401 row at all; `:82` names "302/401/403" only jointly | ABSENT |
| **L4** | **SDUI 500** on a hand-built partial body instead of the full captured body | **NO** — client payload defect; not retryable without changing the body | `mcp/lib/client.py:417-418` (replay verbatim; "partial hand-built bodies 500"), `:433-436`; `docs/COVERAGE-MAP.md`, section "Current state (live)", bullet "Proven factor — the body" | VERIFIED (body factor) |
| **L4b** | SDUI 500 *"because of vgreq's Voyager headers"* | **NO** | ⚠️ **Do not admit this as an error class** — see §3.1. The causality is unverified and contradicted for `comments.createComment` | INFERRED |
| **L5** | SDUI 500 *"because `requestMetadata.currentActor` is missing"* | **NO** | ⚠️ The **500 is observed**, the **cause is explicitly rejected** in this repo — see §3.2. Carry it as one class with L4: **"SDUI replay incomplete"**, with no cause claim | VERIFIED (500 observed) / INFERRED (cause) |
| **L6** | **400** — wrong URN form; **500** on a *reversed* URN | **NO** — pure parameter error | `docs/07-COMMENTS.md:104` (correct key → **204**), `:108-110`: `fs_objectComment` form → **400**, `fsd_comment` form → **400**, wrong-order `urn:li:comment:(<post>,<id>)` → **500**, garbage → **400**. Same class of guessed-shape 400/404s: `docs/STATUS-MATRIX.md`, section "Important corrections (paths that do NOT work)" | VERIFIED |
| **L7** | **GraphQL 200 carrying `data.errors`** — a false success | **NO** — input error. **The most important row: the status code actively lies** | `docs/04-WRITE-OPERATIONS.md:114-117` ("the GraphQL call returns HTTP 200 even on a validation error — you MUST check `data.errors` … (Verified the hard way.)"). Since 2026-07-31 checked by **every** GraphQL write through one shared extractor `_gql_errors()` (`mcp/lib/client.py:367`): `create_post` (`:491`), `edit_post` (`:522`), `create_poll` (`:538`), `delete_repost` (`:790`) — the last two were blind before. Residues of the class (unparsable 200 body, top-level `errors`, uncapped message) are tracked in `BACKLOG.md`; referenced here only as an error class | VERIFIED |
| **L8** | **200 but a no-op** (SDUI `deleteProfile<X>Form`) | **NO** — but reporting success would be wrong | `docs/BROWSERLESS-REPLAY.md:55-62` ("returns **HTTP 200 but is a no-op**", three variants tried). Note `:63-65`: the legacy read `identity/profiles/{id}/languages` is stale/deprecated (410/400) and is **unfit** for verification. Affects no current MCP tool path | VERIFIED |
| **L9** | **404** from a rotated `queryId` / `sduiid` hash | **NO** — deploy drift | **INFERRED**: no *observed* rotation-404 is documented. What exists are anticipating code notes (`mcp/lib/client.py:40-41`, `:99-100`, `:106`, `:763-765`) and a 404 from a *wrong path* (`docs/STATUS-MATRIX.md`, section "Important corrections (paths that do NOT work)", the `contentcreation/dash/normShares` row). Clean handling to copy: `get_conversations` catches the non-JSON case, `mcp/lib/client.py:112-117` | INFERRED |
| **L10** | **429** rate limit | **NO** | **ABSENT as an observation** — the only mention is one cheat-sheet row, `docs/05-VERIFICATION.md:94`. Declare it the way Indeed does: *anticipated, never seen* (`indeed-internal-api/lib/errors.py:194-200`) | ABSENT |
| **L11** | **`KeyError: 'JSESSIONID'`** before the request | **NO** — setup error → `SessionMarkersMissing` | `lib/vgreq.py:13`; reachable because `lib/cookies_extract.py:40-42` warns and writes the file anyway | VERIFIED (code fact) |
| **L12** | **`FileNotFoundError`** — cookie file absent (the current machine state) | **NO** — setup, not session | `lib/vgreq.py:12`, `mcp/lib/client.py:408`. Up to 2026-07-31 `mcp/lib/client.py:75-76` swallowed it and reported `logged_in: false`, i.e. as a session problem; now separated as `session_file_missing` in `probe_session` (section 2.7). Indeed separates `SessionMissing` (`indeed-internal-api/lib/cookies.py:77`) from `SessionExpired` | VERIFIED (code fact) |
| **L13** | **Network / timeout** (25 s, `lib/vgreq.py:41,49,52`) | **NO** | Was collapsed to `False` by `mcp/lib/client.py:75-76` too; now `transport_unavailable` (section 2.7). Indeed: `TransportUnavailable` / `E-NET` (`indeed-internal-api/lib/errors.py:215-221`) | VERIFIED (code fact) |

### 2.4 Detection order — and the one step that must **not** be copied from Indeed

1. **Before the request:** is the file there? Are `li_at` + `JSESSIONID` there? → `SessionMissing` /
   `SessionMarkersMissing` (L11, L12). No network involved.
2. **Redirect first** — because `allow_redirects=False` (`lib/vgreq.py:41,49,52`) means a 3xx is
   what you actually receive: `300 ≤ status < 400` **and** `Location` contains `/uas/login` or
   `/login` → `SessionExpired`, **`session_suspect = True`** (L1). This is the only branch that sets
   it.
3. **Content-type — LinkedIn-specific. ⚠️ THE MOST EXPENSIVE COPY-PASTE ERROR IN THIS DESIGN.**
   Voyager answers with
   **`application/vnd.linkedin.normalized+json+2.1`** (`docs/01-AUTH-AND-COOKIES.md:80`, the
   required `accept` header; sent at `lib/vgreq.py:25`). A naive
   `if "application/json" in ctype` — the shape Indeed's ordering suggests — would classify
   **every successful Voyager response** as non-JSON. The check must accept the
   `vnd.linkedin.…+json…` family, not the bare `application/json` string.
4. **Body signal before status:** GraphQL 200 with `data.errors` → `ValidationError` (L7). This step
   *must* precede the status check, because the status is 200 and says nothing.
5. **Status last:** 403 → `CsrfMissing` (L2); 400 → `BadRequest` / `BadUrnForm` (L6); 404 →
   `QueryIdRotated` (L9); 500 → `SduiReplayIncomplete` (L4/L5, with L6's special case that a
   *reversed* URN also yields 500); 429 → `RateLimited` (L10, anticipated).
6. **Default: unknown ⇒ NOT session-dead.** An unrecognised failure is a bad-input / unknown error,
   never `session_suspect = True`. Reference: `indeed-internal-api/lib/errors.py:540-542`
   (`if status >= 400: return BadUserInput(…)`, else `None`).

Ordering reference overall: `indeed-internal-api/lib/errors.py:326` (`classify`), invariants
`indeed-internal-api/lib/errors.py:7-16` — of which invariant 1 ("`session_suspect` only for
E5/E6/E12") is the direct model for "only L1 sets the flag".

### 2.5 The actual cause of the guesswork: one `except Exception` collapses three causes

**VERIFIED (code fact).** `mcp/lib/client.py:72-76`:

```python
def _session_ok(self) -> bool:
    try:
        return self._vg().get(f"{BASE}/me").status_code == 200
    except Exception:
        return False
```

Three unrelated causes land on the same `False`:

- **no cookie file** → `FileNotFoundError` from `lib/vgreq.py:12` (L12),
- **network / timeout** → `requests` exception from `lib/vgreq.py:41` (L13),
- **missing marker** → `KeyError` from `lib/vgreq.py:13` (L11),

and a genuine auth failure would produce the same `False` too. That `False` is then surfaced as
`{"logged_in": False, …}` by `session_status` (`mcp/server.py:197-201`) with the hint
"session cookies are stale — the external session_daemon.py refreshes /tmp/li_cookies.json;
(re)start it to log in" (`mcp/server.py:200-201`). **Every** one of the four causes is therefore
reported as *the session is stale, go log in again* — including "you forgot to start the daemon"
and "your wifi dropped".

**This is the mechanism behind the reported guesswork, and the smallest honest fix is to stop
collapsing:** distinguish the exception types, return the class plus `session_suspect`, and let only
L1 set the flag.

> **Built 2026-07-31.** The code block above is history: `probe_session()` in `mcp/lib/client.py`
> classifies the exception type instead of swallowing it, and `session_status` reports the class.
> `ensure_session()` still returns a `bool`. What each of the four causes now reads as, and which
> test holds it, is in section 2.7.

### 2.6 🔒 Redaction is a security requirement of this design, not polish

**ABSENT in this repo:** `grep -rn "redact\|scrub" mcp/ lib/ tools/` returns **0 hits**. There is no
redaction anywhere. A taxonomy that puts response bodies into its messages therefore ships those
bodies straight into the MCP transcript — and LinkedIn response bodies carry profile URNs, real
names, and on messaging routes potentially message text.

The existing repo rule is already strict — "Never emit cookie values into a tool response, a log
line or an error message" — and this extends it to response bodies. **Minimum contract:**

- The body **never** goes into the message. Only `status`, `endpoint`, and `len(body)`.
- If an excerpt is genuinely needed for diagnosis: **redact first, truncate second.** Truncating
  first and redacting after leaves whatever the truncation happened to keep.
  Reference: `indeed-internal-api/lib/errors.py:277` (`_safe()`), and the invariant that mandates it,
  `indeed-internal-api/lib/errors.py:13-16`.
- The same promise the sibling repo makes in its docstring
  (`indeed-internal-api/mcpserver/tools_session.py:43`, "never prints cookie values") should be
  stated in `session_status`'s docstring here — and held by a test.

Build the redaction helper **in the same change** as the first error message that could carry a
body. Retrofitting it later means the untruncated version already reached a transcript.

### 2.7 What was actually built (2026-07-31) — and what holds it

**Scope of the change:** `mcp/lib/errors.py` (new), `mcp/lib/client.py`, `mcp/server.py`,
`mcp/tests/test_errors.py` (new), `mcp/tests/test_server.py`. Nothing else. No redaction framework
(see below), no marker refactor, no cookie inventory.

Two session tools changed behaviour, no other tool did. `session_status` gained fields (below), and
`refresh_session` keeps its exact key set (`logged_in`, `hint`) but its `hint` is now the
classification's remediation instead of the fixed sentence "cookies still stale" — that sentence was
the misattribution this ticket exists to remove, and a test holds the new wording for a missing
cookie file (*setup*) and for a timeout (*retry*). Both tools now call `probe_session()` rather than
`ensure_session()`; see the last item under "Not held" for the one consequence that carries.

**The module.** `mcp/lib/errors.py` is **pure by contract** — no network, no file access, no
cookies; it imports nothing but typing names, and a test asserts that it holds no module objects at
all. `classify(response=…, endpoint=…)` and `classify_exception(exc, endpoint=…)` return one flat
dict: `code`, `session_suspect`, `retryable`, `remediation`, `evidence`, `status`, `endpoint`,
`body_len`. Detection order is section 2.4's, with one deliberate refinement: the content-type step
(2.4 step 3) applies **only to 2xx**. Were it applied to a 4xx as well, a 403 served as `text/html`
would be filed as "non-JSON" instead of `csrf_missing` and section 2.2 — the entire point — would be
lost; on a 4xx/5xx the status carries the information.

**The one `session_suspect`.** `session_expired` is the only class whose `session_suspect` is
`True`, and the module keeps its code in one constant so that the invariant can be tested over the
whole class table rather than over a handful of examples. It is reached only by a `3xx` whose
`Location` points at the login page — which arrives as a 3xx at all because the transport passes
`allow_redirects=False` (section 2.1).

**`session_status` (`mcp/server.py`)** now returns, in addition to `logged_in` and `read_only`:
`session_suspect`, `error_code`, `retryable` and a `hint` that is the class's `remediation`. The
docstring states the redaction promise of section 2.6. The case "cookie file absent" — the current
state of this machine — is now visibly `session_file_missing` with a remediation that says *setup*,
not *log in again*.

**One rule forms the success statement.** `logged_in` is the classification and nothing else:
`probe_session()` returns `code == "ok"` (`mcp/lib/client.py`, `probe_session`), and
`session_status` hangs `error_code` and `hint` on `code != "ok"` (`mcp/server.py`,
`session_status`). The earlier draft of this change kept a *second* rule — `status == 200` — beside
the classification, and masked `error_code`/`hint` behind it. That combination reported a failed
probe as a healthy session with no signal at all whenever the two rules disagreed: a 200 serving a
login interstitial, or a 200 whose body is truncated. Review rejected it as the "failure that looks
like a success" class, and it is gone: a classified failure now always surfaces both its class and
its hint, and a healthy probe carries neither. `session_suspect` was not touched by this — it stays
`True` for the login redirect alone.

**Section 2.5 is no longer the mechanism it describes.** `probe_session()` in `mcp/lib/client.py`
replaces the `except Exception: return False`: the exception **type is the diagnosis**, so a missing
cookie file, a missing cookie marker and a network/timeout error no longer share one `False`.
`ensure_session()` keeps its `bool` signature — every tool calls it — and now reads
`probe_session()["logged_in"]`; the diagnosis is available *next to* the bool, not instead of it.

**Held by passing offline tests** (`mcp/tests/test_errors.py`, `mcp/tests/test_server.py`):

- exactly one class in the table carries `session_suspect=True`, and it is `session_expired`;
- a `Location` on a login path sets the flag (header name read case-insensitively); a redirect
  elsewhere does not;
- a **403 is `csrf_missing`, never session death**, and its remediation names `JSESSIONID` —
  including when the 403 is served as HTML;
- the Voyager content type `application/vnd.linkedin.normalized+json+2.1` counts as JSON. This is
  the copy-paste error of 2.4 step 3 nailed down: a test fails the moment the check is narrowed to
  the bare `application/json` string;
- a 200 carrying `data.errors` is classified before the status is looked at (L7);
- 400 / 401 / 404 / 429 / 500 map to their classes and **none** of them sets the flag; 429 is
  `retryable`;
- provenance stays honest where the design says the mode was never observed: 401 and 429 carry
  `evidence = anticipated — never observed in this repo`, the rotation-404 carries `inferred`;
- an unrecognised status, and an object that does not duck-type as a response at all, come back as
  `unknown` — never as session death and never as an exception: `ensure_session()` returns a plain
  `False` for it, because this path sits under every tool;
- the three pre-request causes are told apart (`session_file_missing`, `session_markers_missing`,
  `transport_unavailable`, all with `status = "no_request"`), and none of them is session death;
- **`logged_in` is exactly `code == "ok"`** — a 2xx served as HTML, a 2xx with an empty or truncated
  body, a 2xx whose body is not a JSON object, and a 2xx carrying `data.errors` or a top-level
  `errors` all report `logged_in=false`;
- **`error_code` is set exactly when `hint` is set, and exactly when `logged_in` is false** — held as
  an invariant over a timeout, a 403, a 204 and a healthy probe, not over one example;
- a failed probe is never reported as a healthy session, and none of these failures sets
  `session_suspect`;
- `refresh_session`'s hint names the classified cause (setup / retry) and keeps the key set
  `{logged_in, hint}`;
- the two classes with no L1–L13 row, `non_json_response` and `redirect_unexpected`, carry
  `evidence = inferred`, and `non_json_response`'s remediation acquits nothing — a test fails if
  either is relabelled as observed;
- **no body leaves the classification**: the result carries exactly the eight keys above, a planted
  profile URN / name / message text appears nowhere in the rendered result, and only `body_len`
  reports the body — held for `classify()` and again at the tool boundary for `session_status`;
- `ensure_session()` still returns a plain `bool`.

**Not held, and honestly so:**

- **Nothing is live-tested.** Every test fakes the transport; no LinkedIn response was seen. The
  classes inherit their labels from section 2.3 and gain no new evidence from this change.
- An **empty-bodied success** (a 204 delete, a body-less 201) currently classifies as
  `non_json_response`. That is pinned as a known limitation with its reason: `classify()` is wired
  only into the `/me` probe, which answers with a JSON body. Whoever reuses the module on a write
  path decides that case *there*. What holds in both readings: an empty-bodied success is never
  session death.
- The success statement is now **stricter** than the earlier draft's: `code == "ok"` demands a
  readable JSON object body, where `status == 200` demanded only the status line. Offline that is the
  correct reading of the classification and it is test-held; what is *not* proven is that no live
  Voyager `/me` answer trips it — unprovable here, because this repo has no live session (see
  "Nothing is live-tested" above). What that risk can reach is **narrower than it looks**, and
  narrower than an earlier version of this section claimed: **no caller reads `ensure_session()`'s
  return value.** Every tool body in `mcp/server.py` calls it as a bare statement and discards the
  `bool`; the `write_tool` decorator (`mcp/server.py`, `write_tool`) consults only
  `read_only_enabled()` and never the session; `mcp/README.md` describes it the same way, as a GET
  the tool emits. A stricter `bool` therefore cannot block a tool. It changes only what
  `session_status`, `refresh_session` and `probe_session` **report** — that is the owner decision,
  and it is theirs, not an agent's.
- **Pre-existing, untouched, and surfaced by the line above:** the session gate protects nothing.
  Because the `bool` is discarded everywhere, a tool proceeds with its real call whatever the probe
  says, and a dead session is discovered by that call failing rather than by the gate. That predates
  this change, is not made better or worse by it, and is its own ticket.
- Two classes in the module — `non_json_response` and `redirect_unexpected` — have **no row** in the
  L1–L13 table; they are complements the implementation needed. Both therefore carry
  `evidence = inferred` in the code, and a test holds that label, so the code's label and this
  document now agree. The earlier draft labelled `non_json_response` `verified` and had its
  remediation state "this is not a session problem"; review rejected both, and the class now acquits
  nothing.
- `redirect_unexpected` is also the class for a 3xx whose `Location` is not readable at all. It
  proves nothing in either direction, and its remediation says so.
- The one signal that may set `session_suspect` is matched as a **substring** of the whole `Location`
  value (`mcp/lib/errors.py`, `classify`), not as a URL path. That is the wording section 2.4 step 2
  uses, and the only wired route is the `/me` probe, but a `Location` that merely *contains*
  `/login` — a company page called `login-inc`, a `?next=/login` query — would read as session death,
  and a differently cased `/UAS/Login` would not. Raised in review, not fixed here; no test covers
  the false-positive direction.
- `session_status` and `refresh_session` call `probe_session()`, which does **not** repeat
  `ensure_session()`'s check that the transport module imported (`mcp/lib/client.py`,
  `ensure_session`). With `vgreq` unimportable those two tools therefore report `unknown` with
  "capture the request and classify it", where they previously raised `RuntimeError("vgreq not
  importable — check repo layout")`. Failing quietly at the tool boundary is right, but this is a
  fourth nameable *setup* cause left in the default bucket — in the ticket whose purpose is telling
  setup causes apart. Not fixed here, and no test holds either reading.
- `classify_exception` buckets by exception type only: any `OSError` reads as
  `transport_unavailable`, so a cookie file that exists but cannot be read (`PermissionError`, a
  directory in its place) reports as a transport problem — and reports it as `retryable` with
  `evidence = verified`, which is the strongest label on the widest bucket. A half-written cookie
  file (a JSON decode error) lands in `unknown`. Both were raised in review and are **not** fixed
  here; the exception *type* is a weaker witness than these labels suggest.
- **No redaction helper was built** (section 2.6 asked for one alongside the first message that
  could carry a body). Instead the rule is kept by construction — the classification emits status,
  endpoint, body length and its own class, nothing else. The leak tests hold that for the **response**
  path, at `classify()` and again at the `session_status` boundary. On the **exception** path the rule
  is held by construction only: `classify_exception` never reads `str(exc)`, but no test asserts it,
  and that path is the one carrying the cookie file path. A redaction helper is still needed the
  moment any excerpt is genuinely wanted.
- The new taxonomy is **not yet the only voice** on one signal. For a 2xx without a readable JSON
  body it says "decides nothing about the session either way", while the untouched `_read_json`
  (`mcp/lib/client.py`, `_read_json`) still returns "the session is most likely stale … check
  session_status()" on the read path — the very reflex this ticket removes, reachable through the
  read tools. Rewiring the read path was out of scope; until it happens, the two messages disagree
  and `session_status` is the one to believe.
- `docs/BACKLOG.md` still lists the "failure that looks like a success" residue for the session probe
  as open. That file is outside this ticket's scope and was deliberately not edited, so its entry for
  this specific residue is stale as of this change; this section is the current reading.

---

## 3. Two claims that must NOT re-enter as facts

Both were downgraded by review. They are listed here so a future implementation does not
re-promote them while reading this design.

### 3.1 "vgreq's Voyager headers cause the SDUI 500" — unverified, and contradicted

Already documented correctly in `docs/COVERAGE-MAP.md`, section "Current state (live)", bullet
"Unproven factor — the headers": the claim is **not verified** and is
**contradicted for `comments.createComment`** by this repo's own code —
`create_comment_browserless` posts the SDUI route (`_SDUI_COMMENT_URL`, `mcp/lib/client.py:161-162`)
through `self._vg().post(url, body, is_json=False)` (`mcp/lib/client.py:242`), i.e. **with** the
Voyager headers rather than via `_sdui_min_headers()`, and that path is documented as live 200
(`mcp/lib/client.py:159-160`, `:191`). The two header paths are covered by *separate* offline tests:
`mcp/tests/test_client.py:374-381` pins the vgreq path by reading the call out of the faked `vgreq`
module's `calls["post"]`, while the minimal-header path is exercised in other tests that monkeypatch
`requests.post` and `_sdui_min_headers`. Note what that does **not** give us: no test holds the
headers as the single changing variable, which is precisely why the experiment below is still open.
The claim survives as an assertion only in the `_sdui_min_headers` docstring
(`mcp/lib/client.py:401-405`) and is tracked in `docs/BACKLOG.md`.

**Consequence for this taxonomy: L4b is not an error class.** Do not route a 500 to a
"wrong headers" diagnosis. The one-variable experiment that would settle it is written out in
`docs/COVERAGE-MAP.md`, section "Current state (live)", bullet "The one-variable test that would
settle it"; until it has run, only the **body** factor is isolated.

Unresolved next door (ABSENT, never reconciled): `docs/03-SDUI-API.md:51-64` lists **ten** required
SDUI headers, while `_sdui_min_headers()` sends **three** (`mcp/lib/client.py:411-412`) and reaches
live 200. One of the two is wrong; the repo does not say which — noted the same way in the closing
sentence of that same "one-variable test" bullet in `docs/COVERAGE-MAP.md`.

### 3.2 "SDUI 500 because `currentActor` is missing" — observation yes, cause no

The 500 is real; the cause is **explicitly rejected in this repo**. `mcp/lib/client.py:433-434`:
the old code 500'd "not because of a missing currentActor binding (that field is empty in the real
browser request too)". The "Key finding" paragraph in `docs/COVERAGE-MAP.md`, section
"Current state (live)", calls the "needs a browser" story
"a **red herring**".

**Carry it as one class, `SduiReplayIncomplete`, merged with L4 and with no cause claim.** The
actionable remediation is the same either way: re-capture the full body and replay it verbatim.

---

## 4. What a first implementation would look like (scope sketch, one item of six built)

Deliberately small, and honest about what it cannot know. Status per item as of 2026-07-31:

1. **One cookie store** — read both payload shapes, write one; one path resolver (§1.7, §1.8).
   ⛔ **not built — declined** (§1.0).
2. **`SESSION_MARKERS`** in one place, `markers_missing` derived from it (§1.5).
   ⛔ **not built — declined** (§1.0); the four checks are still four.
3. **`session_status`** gains `cookies: {count, markers_missing, cookie_file_age_h,
   soonest_expiry_days: null, hosts: null, unavailable: {...}}` plus `owner_urn_set: bool`
   (§1.3, §1.5). ⛔ **not built — declined** (§1.0). What `session_status` did gain instead is
   `session_suspect`, `error_code` and `retryable` (§2.7).
4. **`classify()`** implementing §2.4, returning at least `{class, session_suspect, remediation,
   status, endpoint}` — and **no body** (§2.6). **BUILT — offline-proven, not yet live-tested**
   (§2.7) — as `code` rather than `class`, plus `retryable`, `evidence` and `body_len`.
5. **Redaction helper**, shipped with step 4, never after. ⛔ **not built.** No message in the new
   path can carry a body; tests hold that for the response path, the exception path only by
   construction. The helper is owed to the first excerpt anyone wants (§2.7, "No redaction helper
   was built").
6. **Only then**, as a separate change, the expiry source (§1.6) — including the offline assert that
   patchright really delivers `expires`. ⛔ **not built — declined** (§1.0).

**Constraints, not suggestions.** Everything above is offline-testable: no network, no cookie file,
no browser. The established pattern is a faked `vgreq` module injected into `sys.modules`
(`mcp/tests/test_client.py`) and a faked transport (`mcp/tests/test_readonly.py`). Enforce
"no network" by making the network impossible in the test, not by trusting the code path.

**What the passing suite covers today, for the record — including one real constraint on §1.5:**
`mcp/tests/test_server.py` pins `session_status` in the exact expected tool set, so the tool may not
be renamed or dropped, and since 2026-07-31 also holds its new fields and their invariants (§2.7).
`mcp/tests/test_readonly.py:38` lists it in
`READ_CALLS`, which means the parametrised `test_read_tools_are_not_blocked_under_read_only`
(`mcp/tests/test_readonly.py:165-173`) already holds behaviour: the return value must be a `dict`
(`:169`), it must use no mutating verb (`:172`), and — the binding one — it **must reach the
transport with a GET** (`:173`, "listed as a READ but never reached the transport"). Today that GET
is the `/me` probe, since 2026-07-31 issued by `li.probe_session()` (§2.7) instead of
`li.ensure_session()`, on the same transport and with the same GET. **Consequence for §1.5: an
implementation that answers `session_status` purely from the cookie file, or returns early before
the `/me` probe, breaks `mcp/tests/test_readonly.py:173`.** The cookie inventory has to be added
*alongside* the probe, not instead of it — or that test has to be changed as a deliberate, argued
decision. Beyond that: `mcp/tests/test_readonly.py:176-180` asserts only the `read_only` key.

**Updated 2026-07-31.** `session_status`'s new fields (`session_suspect`, `error_code`,
`retryable`) and the error classes now *are* held, by `mcp/tests/test_server.py` and
`mcp/tests/test_errors.py` — the list is in §2.7, and it is the only list worth trusting.
`logged_in`'s semantics are part of that list: it is the classification (`code == "ok"`), no longer
"the probe answered 200", and the invariant *`error_code` set ⇔ `hint` set ⇔ `logged_in` false* is
held too. Still unbuilt: every cookie-inventory field of §1 — declined, so no test will hold them.
The items §2.7 lists under "Not held" are unheld by name. Every other field in this document remains
unheld until its test is written.

**The one call that would prove any of it: none is needed for §1 or §2.** All of it is derivable
from the local cookie file and from response metadata. The **only** proving live call in this area
is the one-variable header experiment of §3.1 (`docs/COVERAGE-MAP.md`, section "Current state
(live)", bullet "The one-variable test that would settle it") — a like/unlike on the
owner's own post, reversible, no third party — and it settles L4b, not the taxonomy itself. It is
the owner's decision, not an agent's.
