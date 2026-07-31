"""jobs_parse.py — pure parsing/projection helpers for the Jobs reads. NO network, NO browser.

Voyager's job responses are normalized JSON (`data` + `included[]`) and large (the jobs-feed
capture in data/endpoints_voyager.json is 110 KB). The MCP hands the agent a small flat
projection instead — and it must never lie about what it could not read.

Everything here is a pure function: no `requests`, no `vgreq`, no import side effects, so the
parsers are testable against synthetic fixtures without the fake-transport machinery in
mcp/tests/test_client.py.

Three rules shape this module, and all three come from a reproduced false success:

1. THE WITNESS IS BOUND TO WHAT WAS READ. `read_job_collection` picks exactly ONE container node
   (`find_collection`) and reads hits, paging and the pagination token out of THAT SAME object.
   Counting `elements` lists "somewhere in the body" while reading at another root is what once
   turned three real cards into `ok=True, count=0`.
2. `get_job` NEEDS AN IDENTIFYING WITNESS, not a quantitative one. `read_job_posting` compares the
   job id carried by the read entity against the REQUESTED one; a divergence is an error
   (`identity="mismatch"`), never a silent correction, and the caller's `url` is always built from
   the requested id (`job_url`).
3. EVERY DERIVED VALUE IS A FUNCTION OF THE COMPLETE NODE, AND AMBIGUITY OR LOSS HAS A STATE.
   This is the chokepoint that rule 1 needs in order to mean anything, and it was missing: a
   verdict computed on a REDUCTION of what was read (a filtered list, the first matching key, the
   first of several candidates) is the same unbound claim one level deeper. So:
     * counts and the empty/non-empty verdict run on the RAW `elements` of the read container,
       never on the projectable subset, and discarded entries are named in `reason`;
     * every id, container, token and company name is collected over ALL candidate positions of
       the same node via `_distinct(...)`; exactly one distinct value is an answer, two are
       `ambiguous`/`mismatch`, zero is `absent`/`unknown`. No "first one wins" anywhere.
   Consequence to keep in mind when editing: no verdict may depend on JSON key order, because
   LinkedIn's serialisation order is not a fact we control.

Status of the shapes parsed here: 🔍 for the job-posting route (Manuel's own live evidence
2026-07-30, HTTP 200) and for the jobs feed (capture, data/endpoints_voyager.json:746). The
PARSING itself is NOT yet live-tested — the fixtures are synthetic. See docs/27-JOBS.md.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional

# urn:li:fsd_jobPosting:<digits> / urn:li:fs_normalized_jobPosting:<digits> / urn:li:jobPosting:…
_JOB_URN_RE = re.compile(r"urn:li:(?:fsd_|fs_normalized_)?jobPosting:(\d+)")
_DIGITS_RUN_RE = re.compile(r"\d{5,}")

# Values that are PLUMBING, never a human-readable field: URNs and $type class names. A value of
# this shape under an allowed key (e.g. "salary") is a leak a key-name allowlist cannot catch.
# NOTE: a leading "$" is NOT plumbing — "$60,000/yr" is a legitimate salary text.
_PLUMBING_VALUE_RE = re.compile(r"^(?:urn:|com\.linkedin\.)")

# Named human-readable fields inside a small enum-ish object (employmentStatus & friends).
_NAMED_TEXT_KEYS = ("localizedname", "name", "text", "localizedlabel", "label")

# Named salary-text fields we accept. "first string wins" harvested $type/entityUrn instead.
_SALARY_TEXT_KEYS = ("formattedsalary", "formattedpay", "formattedbasesalary", "salarytext",
                     "paytext", "compensationtext", "salaryrange", "payrange",
                     "formattedannualbasesalary")
# Inside the salaryInsights subtree the surrounding object already says what the text is about,
# so the generic `displayText` is readable THERE — never on a card.
_SALARY_SUBTREE_KEYS = _SALARY_TEXT_KEYS + ("displaytext",)

# Key names that IDENTIFY an entity. Only these are read for a job id — a greedy scan over every
# string value would pick up a "similar jobs" URN and report a mismatch for a correct read.
# EXACT match, deliberately not a suffix/substring test: "similarJobPostingUrn" ENDS in
# "jobpostingurn" and "relatedJobPostingUrn" CONTAINS "jobposting", so both were read as identity
# — which aborted correct reads in one direction and masked a real divergence in the other.
_ID_URN_KEYS = ("entityurn", "objecturn", "jobpostingurn", "trackingurn")
_ID_NUMERIC_KEYS = ("jobpostingid", "jobid")

# Fields whose presence proves the body actually DESCRIBES the job (not just references it).
# Projected key names, checked on the projection so "read" means the same thing as "returned".
_CONTENT_FIELDS = ("title", "location", "employment_status", "remote_allowed", "listed_at",
                   "applies", "views", "salary", "reposted", "description_text")

# Upper bound on the description even with truncation switched off (0/negative): an unbounded
# field would blow the agent's context window.
MAX_DESCRIPTION_CHARS = 20000

# Depth/width limits for every traversal in here — a hostile or drifted body must not spin.
_MAX_DEPTH = 5
_MAX_WIDTH = 50


def _distinct(values: Any) -> list:
    """The distinct non-None values of an iterable, duplicates collapsed.

    THE CHOKEPOINT of rule 3: every derived value in this module is first COLLECTED over all
    candidate positions of the read node and then passed through here. Callers decide on
    `len(...)` and on set equality only — never on "the first one" — so no verdict can depend on
    the order in which LinkedIn serialised its keys.
    """
    out: list = []
    for val in values:
        if val is not None and val not in out:
            out.append(val)
    return out


def job_url(job_id: str | int) -> str:
    """Canonical public job URL for a numeric job id."""
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


def normalize_job_id(value: str | int) -> str:
    """Return the bare numeric job id from an int, a numeric string, a URN or a job URL.

    Accepts: 1234, "1234", "urn:li:fsd_jobPosting:1234", "urn:li:jobPosting:1234",
    "https://www.linkedin.com/jobs/view/senior-dev-at-example-1234567890/",
    ".../jobs/collections/recommended/?currentJobId=1234567890".
    Raises ValueError on anything unusable — the caller turns that into an honest error dict
    (no HTTP call, no traceback at the tool boundary).

    The id is read ONLY at an identifying position: a jobPosting URN, the `currentJobId`
    parameter, or the path segment after `/jobs/view/`. There is deliberately NO "last digit run
    wins" fallback: real copied job links carry `?geoId=…&position=1&savedSearchId=…`, and a
    greedy scan returns those instead of the job id — a wrong but plausible id read as fact.

    A URL that names TWO DIFFERENT job ids at identifying positions (…/jobs/view/4123456789/
    ?currentJobId=9876543210) raises instead of letting one position win: R2's hard abort has to
    hold on the INPUT side too, where the body-id guard cannot see the divergence any more — the
    body would agree with the (wrongly) chosen id and the caller would get content plus url for a
    job it never asked for.
    """
    if isinstance(value, bool):  # bool is an int subclass — never a job id
        raise ValueError("job_id must be a number, URN or job URL")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("job_id must be a positive number")
        return str(value)
    s = str(value or "").strip()
    if not s:
        raise ValueError("job_id is empty")
    if s.isdigit():
        if int(s) <= 0:
            raise ValueError("job_id must be a positive number")
        return str(int(s))
    m = _JOB_URN_RE.search(s)
    if m:
        return m.group(1)
    if s.startswith("urn:"):
        # only a job-ish URN — urn:li:activity:… / urn:li:fsd_profile:… are NOT job ids
        tail = s.rsplit(":", 1)[-1]
        if tail.isdigit() and "job" in s.lower():
            return tail
        raise ValueError(f"{s!r} is not a jobPosting URN")
    parsed = urllib.parse.urlparse(s)
    qs = urllib.parse.parse_qs(parsed.query)
    found: list[str] = []
    for key in ("currentJobId", "jobId"):
        for cand in qs.get(key) or []:
            cand = cand.strip()
            if cand.isdigit() and int(cand) > 0:
                found.append(str(int(cand)))
                continue
            m = _JOB_URN_RE.search(cand)
            if m:
                found.append(m.group(1))
    parts = [p for p in parsed.path.split("/") if p]
    for i in range(len(parts) - 1):
        # /jobs/view/<slug-or-id>[/…] — the identifying segment, ignoring every query parameter
        if parts[i] == "jobs" and parts[i + 1] == "view" and i + 2 < len(parts):
            runs = _DIGITS_RUN_RE.findall(parts[i + 2])
            if runs:
                found.append(runs[-1])
            break
    ids = _distinct(found)
    if len(ids) == 1:
        return ids[0]
    if len(ids) > 1:
        raise ValueError(f"{s!r} names more than one job id ({', '.join(ids)}) — refusing to pick "
                         "one: pass the id you mean")
    raise ValueError(f"cannot read a job id from {s!r}")


def attributed_text(value: Any, _depth: int = 0) -> str:
    """Extract plain text from LinkedIn's Attributed Text objects — NEVER str()/repr on them.

    An Attributed Text value is {"text": "...", "attributes": [...]} (sometimes nested one more
    level). Anything else — None, a list, a dict without a readable `text` — yields "" instead of
    leaking a Python repr into the agent's context.
    """
    if _depth > 3:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("text")
        if isinstance(inner, str):
            return inner
        if inner is not None:
            return attributed_text(inner, _depth + 1)
    return ""


def _str_or_none(value: Any) -> Optional[str]:
    """A human-readable string, or None. URNs and `com.linkedin.…` class names are NOT values."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s or _PLUMBING_VALUE_RE.match(s):
        return None
    return s


def _named_text(value: Any, _depth: int = 0) -> Optional[str]:
    """Human-readable name out of a small enum-ish object — never str()/repr on the object.

    LinkedIn sends `employmentStatus` as a URN string, as {"localizedName": …} or as a decorated
    object; `str()` on it leaks a Python repr including entityUrn into a user-facing field.
    """
    if _depth > 2:
        return None
    if isinstance(value, str):
        return _str_or_none(value)
    if isinstance(value, dict):
        for key, val in value.items():
            if key.startswith("$"):
                continue
            if key.lower() in _NAMED_TEXT_KEYS:
                got = _named_text(val, _depth + 1)
                if got:
                    return got
    return None


def _int_or_none(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _bool_or_none(value: Any) -> Optional[bool]:
    """Unknown is None — never False. A missing flag is not a negative answer."""
    return value if isinstance(value, bool) else None


def tri_bool(value: Any) -> Optional[bool]:
    """A real boolean out of a value LinkedIn may send as the STRING "True"/"False" — else None.

    Manuel's capture delivers `repostedJob` as a string, so `if value:` would read "False" as
    True. Only the four spellings below are answers; everything else is "unknown" (None), never
    False.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes"):
            return True
        if low in ("false", "no"):
            return False
    return None


def _flat_salary(value: Any, _depth: int = 0,
                 keys: tuple[str, ...] = _SALARY_SUBTREE_KEYS) -> Optional[str]:
    """Salary text from NAMED fields only (allowlist + value-shape filter). 🔩 shape not captured.

    "First string wins" harvested plumbing: `$type` (com.linkedin.…SalaryInsights) and
    `entityUrn` sit above the real text in the same object. Only a key from `keys` whose value is
    not URN/class-name shaped is accepted. Called ONLY on a salaryInsights subtree — that is why
    the default key set may include the generic `displayText`.
    """
    if _depth > 3:
        return None
    if isinstance(value, dict):
        for key, val in value.items():
            if key.startswith("$"):
                continue
            if isinstance(val, str) and any(t in key.lower() for t in keys):
                got = _str_or_none(val)
                if got:
                    return got
            if isinstance(val, (dict, list)):
                got = _flat_salary(val, _depth + 1, keys)
                if got:
                    return got
    elif isinstance(value, list):
        for val in value[:5]:
            got = _flat_salary(val, _depth + 1, keys)
            if got:
                return got
    return None


def effective_description_chars(value: Any) -> tuple[int, Optional[str]]:
    """Resolve the REQUESTED description budget to the one actually applied, plus a declaration.

    A clamp inside the projection is invisible to the caller: a request for "no truncation" (0)
    or 999999 came back truncated with `description_truncated: True` and no word about why. Every
    clamp returns its own sentence, which the client puts into its `note`.
    """
    if isinstance(value, bool):
        return MAX_DESCRIPTION_CHARS, (f"description_chars={value!r} is not a number — the hard "
                                       f"ceiling of {MAX_DESCRIPTION_CHARS} characters was applied")
    try:
        chars = int(value)
    except (TypeError, ValueError):
        return MAX_DESCRIPTION_CHARS, (f"description_chars={value!r} is not a number — the hard "
                                       f"ceiling of {MAX_DESCRIPTION_CHARS} characters was applied")
    if chars <= 0:
        return MAX_DESCRIPTION_CHARS, (f"description_chars={chars} (no truncation) is still "
                                       f"bounded at {MAX_DESCRIPTION_CHARS} characters")
    if chars > MAX_DESCRIPTION_CHARS:
        return MAX_DESCRIPTION_CHARS, (f"description_chars={chars} exceeds the hard ceiling of "
                                       f"{MAX_DESCRIPTION_CHARS} characters — the ceiling was "
                                       f"applied")
    return chars, None


def inband_error(raw: Any) -> Optional[str]:
    """Message of an error envelope that arrived WITH HTTP 200 — else None.

    Voyager answers a rotated decorationId or a missing permission with 200 plus
    {"status": 403, "message": …, "data": {"$type": "…ErrorResponse"}}. GraphQL (the jobs feed)
    uses the other standard envelope: 200 plus a non-empty `errors[]`. Treating either as a
    successful read is the failure this guard exists for.
    """
    if not isinstance(raw, dict):
        return None
    errors = raw.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        emsg = first.get("message") if isinstance(first.get("message"), str) else None
        return "GraphQL errors[] in a 200 response" + (f": {emsg}" if emsg else "")
    status = raw.get("status")
    msg = raw.get("message") if isinstance(raw.get("message"), str) else None
    types = [str(raw.get("$type") or "")]
    data = raw.get("data")
    if isinstance(data, dict):
        types.append(str(data.get("$type") or ""))
    is_error_type = any(t.endswith("ErrorResponse") or t.endswith("Error") for t in types if t)
    if isinstance(status, int) and not isinstance(status, bool) and status >= 400:
        return f"in-band error status {status}" + (f": {msg}" if msg else "")
    if is_error_type:
        return "in-band error envelope" + (f": {msg}" if msg else "")
    return None


# ── identity ─────────────────────────────────────────────────────────────
def identifying_job_ids(ent: Any) -> list[str]:
    """ALL distinct job ids an entity carries at IDENTIFYING positions (rule 3).

    Read only from a key that IS an identity — exactly `entityUrn`, `objectUrn`, `jobPostingUrn`,
    `trackingUrn`, `jobPostingId`, `jobId`. Two deliberate boundaries, and both were violated
    before:
      * the key test is EXACT. `similarJobPostingUrn`/`relatedJobPostingUrn` are REFERENCES to
        other jobs; reading them as identity aborted correct reads and, in the other direction,
        let a reference carrying the requested id mask a diverging real `entityUrn`.
      * every identifying position is collected, not the first one. Returning early made the
        identity verdict a function of JSON key order.
    An empty list means "no identifying witness" — a reportable state, never a match. More than
    one entry means the body contradicts itself, which the caller must treat as a mismatch.
    """
    if not isinstance(ent, dict):
        return []
    found: list[str] = []
    for key, val in ent.items():
        low = key.lower()
        if low in _ID_NUMERIC_KEYS:
            if isinstance(val, int) and not isinstance(val, bool) and val > 0:
                found.append(str(val))
            elif isinstance(val, str) and val.strip().isdigit() and int(val.strip()) > 0:
                found.append(str(int(val.strip())))
            continue
        if isinstance(val, str) and low in _ID_URN_KEYS:
            m = _JOB_URN_RE.search(val)
            if m:
                found.append(m.group(1))
    return _distinct(found)


def identifying_job_id(ent: Any) -> Optional[str]:
    """The SOLE identifying job id of an entity — None when there is none OR more than one.

    Convenience over `identifying_job_ids` for the collection path, where there is no requested
    id to compare against: a card whose identity is absent or self-contradictory is not readable
    and is counted as a discarded entry (never silently dropped, see `read_job_collection`).
    """
    ids = identifying_job_ids(ent)
    return ids[0] if len(ids) == 1 else None


# ── company enrichment (a JOIN on the read entity's own reference, not a guess) ──
def _company_index(raw: dict) -> dict[str, str]:
    """entityUrn -> company name for every `included[]` entry whose `$type` ends in Company."""
    out: dict[str, str] = {}
    for ent in raw.get("included") or []:
        if not isinstance(ent, dict):
            continue
        if not str(ent.get("$type", "")).endswith("Company"):
            continue
        name = _str_or_none(ent.get("name"))
        # the URN is a KEY here, not a value we hand out — _str_or_none would reject it
        urn = ent.get("entityUrn") if isinstance(ent.get("entityUrn"), str) else None
        if name:
            out[urn or f"__unkeyed_{len(out)}"] = name
    return out


def _referenced_company_names(ent: Any, companies: dict[str, str],
                              _depth: int = 0) -> list[str]:
    """Every company name the entity REFERENCES, at any depth — the join, not a guess.

    The employer reference is NOT a top-level string in a real body (it sits nested, e.g. under a
    companyDetails object), so a top-level-only scan never joined and left the pool fallback as
    the ACTIVE path — which is how a body naming company 99 could return the name of company 77.
    """
    out: list[str] = []
    if _depth > _MAX_DEPTH:
        return out
    if isinstance(ent, dict):
        for key, val in ent.items():
            if key.startswith("$"):
                continue
            if isinstance(val, str):
                if val in companies:
                    out.append(companies[val])
                elif "companyname" in key.lower():
                    got = _str_or_none(val)
                    if got:
                        out.append(got)
            elif isinstance(val, (dict, list)):
                out.extend(_referenced_company_names(val, companies, _depth + 1))
    elif isinstance(ent, list):
        for val in ent[:_MAX_WIDTH]:
            out.extend(_referenced_company_names(val, companies, _depth + 1))
    return out


def _company_name(ent: dict, companies: dict[str, str],
                  fallback_sole_company: bool = False) -> Optional[str]:
    """Company name for a job entity — joined on a URN the ENTITY ITSELF references, or None.

    Rule 3 applies to this value too: ALL referenced names are collected and exactly one distinct
    name is an answer. Two different referenced employers (a staffing agency plus the hiring
    company) are ambiguous, so the field stays None rather than naming a plausible one.

    `fallback_sole_company` (only for a SINGLE-posting body, where `included[]` describes that one
    job's employer — Manuel's capture note) permits the pool as the witness ONLY when it holds
    EXACTLY ONE company. The note says WHERE the name sits, not that there is only ever one entry;
    "the first company in the pool" was an unbound claim, and with similar-jobs employers in the
    same pool it is a wrong one. It is off for a collection entirely: handing every card the pool's
    company would invent an employer per card.
    """
    names = _distinct(_referenced_company_names(ent, companies))
    if len(names) == 1:
        return names[0]
    if names:
        return None
    if fallback_sole_company and len(companies) == 1:
        return next(iter(companies.values()))
    return None


# ── the ONE read container (R1: one node, read + witness from the same object) ──
def find_collections(raw: Any, max_depth: int = _MAX_DEPTH) -> list[dict]:
    """EVERY candidate read container in this body: dicts holding an `elements` list, shallow first.

    Breadth-first. A candidate whose `elements` list HOLDS entries is not descended into: a
    nested `elements` list is then that container's own content (a card's insight list), not a
    sibling candidate. A candidate whose `elements` list is EMPTY hides nothing, so the search
    continues into its other keys — only the (empty) value of `elements` itself is never entered.
    That asymmetry is the fix for the false success where an empty outer container swallowed a
    filled one nested below it and `state="empty"` was claimed over readable cards; the reason for
    not descending ("it would be card content") has no content to protect when the list is empty.
    `included[]` is skipped on the way down: it is the flat entity POOL.

    All candidates are returned instead of the first hit because "the first `elements` list wins"
    made the read depend on dict insertion order — an empty promo container next to a filled feed
    container produced `ok=True, state="empty"` in one key order and three hits in the other.
    The caller decides (`_select_collection`); a body whose collection path is not unique is
    reported as `ambiguous`, never read.
    """
    found: list[dict] = []
    queue: list[tuple[Any, int]] = [(raw, 0)]
    while queue:
        node, depth = queue.pop(0)
        if isinstance(node, dict):
            elements = node.get("elements")
            if isinstance(elements, list):
                found.append(node)
                if elements:
                    continue
                # fall through: keep descending. `elements` is empty, so queueing it below adds
                # nothing — the value of a FILLED `elements` is still never entered (continue).
            if depth < max_depth:
                for key, val in node.items():
                    if key == "included" or key.startswith("$"):
                        continue
                    if isinstance(val, (dict, list)):
                        queue.append((val, depth + 1))
        elif isinstance(node, list) and depth < max_depth:
            for val in node[:_MAX_WIDTH]:
                if isinstance(val, (dict, list)):
                    queue.append((val, depth + 1))
    return found


def _select_collection(candidates: list[dict]) -> tuple[Optional[dict], str]:
    """THE selection rule, in ONE place: which of the candidates is the container to read from.

    Returns (node, verdict) with verdict
      * "read"      — `node` is the one to read hits, `paging` and the cursor from
      * "ambiguous" — two candidates hold entries; which one is the jobs collection is undecidable
      * "none"      — no candidate at all: we could not read (never "empty")

    Selection is evidence-bound, not positional: the sole candidate that actually HOLDS entries
    wins; if no candidate holds any, the shallowest one is the read container (nothing anywhere,
    so nothing to confuse). This function exists because the same rule used to be written twice
    (here and inline in `read_job_collection`), which is exactly how two verdicts on one body can
    drift apart.
    """
    if not candidates:
        return None, "none"
    filled = [c for c in candidates if c["elements"]]
    if len(filled) > 1:
        return None, "ambiguous"
    return (filled[0] if filled else candidates[0]), "read"


def find_collection(raw: Any, max_depth: int = _MAX_DEPTH) -> Optional[dict]:
    """The ONE node to read from, or None when that choice is not unique.

    Thin wrapper over `_select_collection` — the selection rule itself lives there and nowhere
    else, so this helper can never disagree with `read_job_collection`.

    Returns the NODE, not a list — the caller reads hits, `paging` and the pagination token out
    of this same object, so the witness can never describe a different root than the read.
    """
    return _select_collection(find_collections(raw, max_depth))[0]


def paging_total(node: Any) -> Optional[int]:
    """`paging.total` of THIS node — server-side evidence, including an explicit 0.

    Read only from the container node itself, never "anywhere in the body". `paging.count` is
    deliberately not read: it is the page size the CLIENT asked for, so reading it back as "the
    server says there are hits" would let a caller-supplied value pose as evidence.
    None means unknown, not zero.
    """
    paging = node.get("paging") if isinstance(node, dict) else None
    if isinstance(paging, dict):
        val = paging.get("total")
        if isinstance(val, int) and not isinstance(val, bool) and val >= 0:
            return val
    return None


def _pagination_tokens(node: Any, max_depth: int) -> list[str]:
    """Every paginationToken of the container itself — `elements` is NOT descended into."""
    out: list[str] = []
    if max_depth < 0:
        return out
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "elements" or key.startswith("$"):
                continue
            if key.lower() == "paginationtoken":
                if isinstance(val, str) and val:
                    out.append(val)
                continue
            out.extend(_pagination_tokens(val, max_depth - 1))
    elif isinstance(node, list):
        for val in node[:_MAX_WIDTH]:
            out.extend(_pagination_tokens(val, max_depth - 1))
    return out


def find_pagination_token(node: Any, max_depth: int = _MAX_DEPTH) -> Optional[str]:
    """The SOLE page cursor of the READ container (the feed nests it under `metadata`) — else None.

    Two boundaries, both rule 3: `elements` is skipped, because a token hanging off a CARD is that
    card's tracking payload and paging on it would re-request the wrong thing; and two different
    tokens in the container are ambiguous, so no cursor is returned rather than a guessed one.
    """
    tokens = _distinct(_pagination_tokens(node, max_depth))
    return tokens[0] if len(tokens) == 1 else None


# ── projections ──────────────────────────────────────────────────────────
def _salary_pair(ent: dict) -> tuple[Optional[str], bool]:
    """(salary text or None, salary_present). Present-but-unreadable stays distinguishable.

    The `salaryInsights` shape is NOT captured, so `salary` may well be None while LinkedIn did
    send something. `salary_present` says which of the two it is (Manuel's R6).
    """
    raw_salary = ent.get("salaryInsights")
    if raw_salary is None:
        return None, False
    return _flat_salary(raw_salary) or _str_or_none(raw_salary), True


def project_posting_fields(ent: dict, job_id: str, description_chars: int = 4000) -> dict:
    """Flatten ONE job-posting entity into the ticket's stable key set.

    `job_id`/`url` come from the caller's REQUESTED, normalized id — never from the body (R2/R5).
    `description` is read via attributed_text(); a missing or oddly shaped field becomes
    None/"" instead of a crash, a repr or a False lie (R4/R6).
    """
    chars, _ = effective_description_chars(description_chars)
    full_text = attributed_text(ent.get("description"))
    truncated = len(full_text) > chars
    salary, salary_present = _salary_pair(ent)
    employment = (_str_or_none(ent.get("formattedEmploymentStatus"))
                  or _named_text(ent.get("employmentStatus")))
    return {
        "job_id": job_id,
        "url": job_url(job_id),
        "title": _str_or_none(ent.get("title")) or (attributed_text(ent.get("title")) or None),
        "company": None,  # filled by read_job_posting from included[]
        "location": _str_or_none(ent.get("formattedLocation")),
        "employment_status": employment,
        "remote_allowed": _bool_or_none(ent.get("workRemoteAllowed")),
        # listedAt is passed through unchanged — the unit (epoch ms) is inferred, not captured.
        "listed_at": ent.get("listedAt") if isinstance(ent.get("listedAt"), (int, str)) else None,
        "applies": _int_or_none(ent.get("applies")),
        "views": _int_or_none(ent.get("views")),
        "salary": salary,
        "salary_present": salary_present,
        "reposted": tri_bool(ent.get("repostedJob")),
        "description_text": full_text[:chars] if truncated else full_text,
        "description_truncated": truncated,
    }


def _content_fields_read(fields: dict) -> list[str]:
    """Which CONTENT fields the projection actually filled — the qualitative witness of a read.

    Not a threshold and not a score: the names are reported, so "the posting says nothing" stays
    distinguishable from "we could not read it" (R3 applied to the single posting, which had no
    content witness at all — an identified body whose entity sits in `included[]` returned
    ok=True with an entirely empty projection).
    """
    got = [k for k in _CONTENT_FIELDS if fields.get(k) not in (None, "")]
    if fields.get("salary_present") and "salary" not in got:
        got.append("salary_present")
    return got


def _posting_entities(raw: dict, requested_job_id: str) -> list[dict]:
    """`included[]` entries that ARE the requested posting: $type JobPosting, identity == requested.

    A normalized body may carry only a reference in `data` and the entity itself in the pool. Only
    entries whose ENTIRE identity is the requested id qualify — similar/recommended postings in the
    same pool identify other jobs and are filtered out by that test, not by position.
    """
    out: list[dict] = []
    for ent in raw.get("included") or []:
        if not isinstance(ent, dict):
            continue
        if not str(ent.get("$type", "")).endswith("JobPosting"):
            continue
        if set(identifying_job_ids(ent)) == {str(requested_job_id)}:
            out.append(ent)
    return out


def read_job_posting(raw: Any, requested_job_id: str, description_chars: int = 4000) -> dict:
    """Read ONE job posting and BIND the witness to the requested id (R2).

    Returns {"ok", "identity", "body_job_id", "body_job_ids", "read_fields", "reason", "fields"}
    where identity is
      * "match"     — the body identifies exactly the requested job AND was readable → ok=True
      * "mismatch"  — it carries a DIFFERENT id, or two identifying ids that disagree → ok=False,
                      fields=None. Manuel's explicit instruction: abort hard, never correct, never
                      warn, and never build a url from the body id — otherwise his scout gets a
                      link to a different job than the one it judged. Self-contradiction counts as
                      a mismatch because it cannot be resolved without guessing.
      * "absent"    — no identifying witness at all → ok=False. Not a mismatch, but not a success
                      either: nothing proves this body describes the requested job.
      * "ambiguous" — several `included[]` entities claim the requested id and hold content; which
                      one is the posting is not decidable → ok=False.
    A body that identifies the job but yields NO content field is also ok=False (identity="match",
    read_fields=[]): "the posting states nothing" and "we could not read it" are different answers.
    """
    raw = raw if isinstance(raw, dict) else {}
    requested = str(requested_job_id)
    outer = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    if not isinstance(outer, dict):
        outer = {}
    ent = outer
    if "title" not in outer and isinstance(outer.get("data"), dict):
        ent = outer["data"]
    # The identifying witness is collected over EVERY node this unwrap walked through, BEFORE the
    # reduction to `ent` — otherwise an id sitting on the discarded wrapper is never compared with
    # the requested one, and a body naming a DIFFERENT job passes as identity="match" (R2 demands
    # a hard abort on any diverging body id, no matter at which level it sits).
    data_ids = _distinct(identifying_job_ids(outer) + identifying_job_ids(ent))

    def _mismatch(ids: list[str]) -> dict:
        named = ", ".join(ids)
        return {"ok": False, "identity": "mismatch",
                "body_job_id": ids[0] if len(ids) == 1 else None, "body_job_ids": ids,
                "read_fields": [], "fields": None,
                "reason": (f"the response identifies job(s) {named}, not (only) the requested "
                           f"{requested} — aborted on purpose: adopting a body id would hand out "
                           "a url pointing at a different job than the one that was read")}

    if data_ids and set(data_ids) != {requested}:
        return _mismatch(data_ids)

    fields = project_posting_fields(ent, requested, description_chars)
    read_fields = _content_fields_read(fields)
    ids = data_ids
    if not read_fields:
        # `data` only references the posting — the entity may sit in the pool (normalized body).
        candidates = []
        for pooled in _posting_entities(raw, requested):
            pooled_fields = project_posting_fields(pooled, requested, description_chars)
            if _content_fields_read(pooled_fields):
                candidates.append((pooled, pooled_fields))
        if len(candidates) > 1:
            return {"ok": False, "identity": "ambiguous", "body_job_id": requested,
                    "body_job_ids": [requested], "read_fields": [], "fields": None,
                    "reason": (f"{len(candidates)} entities in included[] claim job {requested} "
                               "and carry content — which one is the posting is not decidable, so "
                               "nothing is returned; re-capture the request and compare the shape")}
        if candidates:
            ent, fields = candidates[0]
            read_fields = _content_fields_read(fields)
            ids = _distinct(data_ids + identifying_job_ids(ent))

    if not ids:
        return {"ok": False, "identity": "absent", "body_job_id": None, "body_job_ids": [],
                "read_fields": read_fields, "fields": None,
                "reason": ("the response carries no identifying job id (no entityUrn/objectUrn/"
                           "jobPostingUrn/trackingUrn/jobPostingId), so nothing proves it "
                           f"describes job {requested} — an HTTP 200 alone is not a read")}
    if set(ids) != {requested}:
        return _mismatch(ids)
    if not read_fields:
        return {"ok": False, "identity": "match", "body_job_id": requested,
                "body_job_ids": ids, "read_fields": [], "fields": None,
                "reason": (f"the response identifies job {requested} but not one field of it could "
                           "be read (no title, description, location, status, counters or salary) "
                           "— that is 'could not read', not 'a posting without details'; "
                           "re-capture the request with the current decorationId")}
    fields["company"] = _company_name(ent, _company_index(raw), fallback_sole_company=True)
    return {"ok": True, "identity": "match", "body_job_id": requested, "body_job_ids": ids,
            "read_fields": read_fields, "fields": fields, "reason": None}


def project_job_card(ent: dict, companies: dict[str, str]) -> Optional[dict]:
    """Project ONE collection element to a flat card, or None when it carries no job id.

    Same field semantics as the posting projection (unknown is None, no repr, no str() on
    Attributed Text). `url` is built from the card's OWN identifying id — for a collection there
    is no requested id to compare against, which is exactly why the id must sit at an identifying
    key (identifying_job_id) and is never scavenged from an arbitrary string.
    """
    jid = identifying_job_id(ent)
    if not jid:
        return None
    salary, salary_present = _salary_pair(ent)
    return {
        "job_id": jid,
        "url": job_url(jid),
        "title": _str_or_none(ent.get("title")) or (attributed_text(ent.get("title")) or None),
        "company": _company_name(ent, companies),
        "location": (_str_or_none(ent.get("formattedLocation"))
                     or _str_or_none(ent.get("location"))),
        "remote_allowed": _bool_or_none(ent.get("workRemoteAllowed")),
        # passed through unchanged (unit inferred, not captured)
        "listed_at": ent.get("listedAt") if isinstance(ent.get("listedAt"), (int, str)) else None,
        "reposted": tri_bool(ent.get("repostedJob")),
        "salary": salary,
        "salary_present": salary_present,
    }


def read_job_collection(raw: Any, limit: int | None = None) -> dict:
    """Read a job collection (the recommendations feed) — ONE container, ONE witness (R1/R3).

    Returns {"ok", "state", "count", "results", "container_found", "read_entries", "discarded",
    "paging_total", "pagination_token", "reason"} with state one of:
      * "hits"      — the read container held entries and at least one projected     → ok=True
      * "empty"     — the read container itself held NO entries (and no candidate's paging.total
                      contradicts that). 'empty' may only be claimed because it was READ. → ok=True
      * "unknown"   — no container node at all: we could not read. NOT empty.        → ok=False
      * "ambiguous" — two candidate containers hold entries; which one is the jobs collection is
                      not decidable, so none is read.                               → ok=False
      * "drift"     — the container (or a candidate's paging.total) says there ARE jobs but not one
                      entry was projectable — the parser lost the shape.             → ok=False

    `read_entries` is the RAW length of the container's `elements`, `discarded` how many of them
    could not be projected. Both verdict and balance are computed on the raw list, never on the
    projectable subset: filtering first made a container of three URN strings report
    `ok=True, state="empty", count=0` — the rejected false success, one level deeper. A partial
    loss keeps ok=True (the read did happen) but always names itself in `reason`, so a genuine
    one-card page stays distinguishable from a three-card page that mostly failed to parse.
    """
    raw = raw if isinstance(raw, dict) else {}
    candidates = find_collections(raw)
    node, choice = _select_collection(candidates)
    if choice == "none":
        return {"ok": False, "state": "unknown", "count": 0, "results": [],
                "container_found": False, "read_entries": 0, "discarded": 0,
                "paging_total": None, "pagination_token": None,
                "reason": ("no collection container was found in the response (no `elements` list "
                           "under `data`), so this is 'could not read', NOT 'no jobs' — "
                           "re-capture the feed request and compare the container path")}
    if choice == "ambiguous":
        filled = [c for c in candidates if c["elements"]]
        return {"ok": False, "state": "ambiguous", "count": 0, "results": [],
                "container_found": True, "read_entries": sum(len(c["elements"]) for c in filled),
                "discarded": 0, "paging_total": None, "pagination_token": None,
                "reason": (f"{len(filled)} candidate containers in this response hold entries — "
                           "which one is the jobs collection is not decidable, so none was read "
                           "(picking one would depend on JSON key order); re-capture the feed "
                           "request and compare the container path")}
    entries = node["elements"] if isinstance(node, dict) else []
    total = paging_total(node)
    token = find_pagination_token(node)
    companies = _company_index(raw)
    results: list[dict] = []
    seen: set[str] = set()
    discarded = 0
    for ent in entries:
        card = project_job_card(ent, companies) if isinstance(ent, dict) else None
        if card is None:
            discarded += 1
            continue
        if card["job_id"] in seen:
            continue
        seen.add(card["job_id"])
        results.append(card)
    out = {"count": len(results), "container_found": True, "read_entries": len(entries),
           "discarded": discarded, "paging_total": total, "pagination_token": token}
    if not entries:
        # The container was READ and held nothing, and no candidate anywhere in this body holds
        # entries (`_select_collection` would have picked that one instead — including candidates
        # nested UNDER an empty container, which the search no longer stops at). What is left that
        # can contradict an empty read is server-side evidence, counted over ALL candidates: a
        # total>0 next to an empty read list is drift, never an answer.
        contradicting = [t for t in (paging_total(c) for c in candidates) if t]
        if contradicting:
            out.update({"ok": False, "state": "drift", "results": [], "count": 0,
                        "reason": (f"the response reports paging.total={contradicting[0]} but the "
                                   "read container held no entries at all — the response shape "
                                   "drifted; re-capture the feed request")})
            return out
        out.update({"ok": True, "state": "empty", "results": [], "count": 0, "reason": None})
        return out
    if not results:
        seen_total = f" (paging.total={total})" if total else ""
        out.update({"ok": False, "state": "drift", "results": [], "count": 0,
                    "reason": (f"the read container held {len(entries)} entries{seen_total} but "
                               "none of them could be projected (no identifying job id at a "
                               "readable position), so this is 'could not read', NOT 'no jobs' — "
                               "re-capture the feed request and compare the element shape")})
        return out
    if limit is not None and limit > 0:
        results = results[:limit]
    reason = None
    if discarded:
        reason = (f"{discarded} of {len(entries)} entries in the read container could not be "
                  f"projected (no identifying job id at a readable position) and are NOT part of "
                  f"count={len(results)} — re-capture the feed request and compare the element "
                  "shape")
    out.update({"ok": True, "state": "hits", "results": results, "count": len(results),
                "reason": reason})
    return out
