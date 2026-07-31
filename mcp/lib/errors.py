"""errors.py — the LinkedIn error taxonomy: one classification, exactly one `session_suspect`.

Why this module exists: in this API a 403 means "the csrf-token header is missing or malformed",
NOT "the session is dead" (docs/01-AUTH-AND-COOKIES.md, section on the csrf-token header;
docs/SESSION-AND-ERRORS-DESIGN.md, section 2.2). Callers that treat every failure as session
death re-login for nothing. Exactly ONE evidenced mode is real session death: a redirect whose
`Location` points at the login page (section 2.1) — and only that class carries
`session_suspect=True`.

PURE by contract: no network, no file access, no cookies, no imports beyond typing. Callers hand
in a response object (duck-typed: `status_code`, `headers`, `json()`, `text`) or the exception
that happened BEFORE the request went out.

REDACTION (docs/SESSION-AND-ERRORS-DESIGN.md, section 2.6): a response body — or any excerpt of
it — NEVER leaves this module. A LinkedIn body can carry profile URNs, real names and message
text, and the return value ends up in the MCP transcript. Only the status code, the endpoint
name, the body LENGTH and this module's own classification are emitted.

PROVENANCE: `evidence` is machine-readable and must never over-claim. Only classes that
docs/SESSION-AND-ERRORS-DESIGN.md, section 2.3 lists as an OBSERVED row (L1–L13) carry
`evidence=VERIFIED`. Rows the design labels INFERRED or ABSENT, and classes derived from a
signal the design does not list as observed at all, carry `INFERRED` / `ANTICIPATED` — never as
an observed fact — and always `session_suspect=False`. Read the per-class comments below: each
one names the row it stands on, or says that no row backs it.
"""

from __future__ import annotations

from typing import Any, Optional

# --- provenance labels (same discipline as docs/STATUS-MATRIX.md) ---------------------------
VERIFIED = "verified"
INFERRED = "inferred"
ANTICIPATED = "anticipated — never observed in this repo"

# The only class that means "re-login". Kept as a constant so the invariant is testable.
SESSION_SUSPECT_CODE = "session_expired"

# A redirect is session death only when it points here (section 2.1). vgreq calls with
# allow_redirects=False (lib/vgreq.py get/post/delete), so the 3xx actually arrives.
LOGIN_PATHS = ("/uas/login", "/login")

# Voyager answers `application/vnd.linkedin.normalized+json+2.1` (the accept header sent in
# lib/vgreq.py _headers). A naive `"application/json" in ctype` would file EVERY successful
# Voyager response as non-JSON — the most expensive copy-paste error in this taxonomy
# (docs/SESSION-AND-ERRORS-DESIGN.md, section 2.4, step 3). Match the +json family instead.
_JSON_MARKER = "json"

# code -> (session_suspect, retryable, evidence, remediation)
_CLASSES: dict[str, dict[str, Any]] = {
    "ok": dict(
        session_suspect=False, retryable=False, evidence=VERIFIED,
        remediation="nothing to do"),
    # L1 — the ONLY evidenced session death.
    SESSION_SUSPECT_CODE: dict(
        session_suspect=True, retryable=False, evidence=VERIFIED,
        remediation="re-login: (re)start the external session_daemon.py so it re-fetches the "
                    "cookie file"),
    # L1 counterpart: a 3xx whose Location is not a login path — or is not readable at all.
    # It does not MEET the one evidenced session-death signal, which is not the same as proving
    # the session healthy, so this class acquits nothing.
    "redirect_unexpected": dict(
        session_suspect=False, retryable=False, evidence=INFERRED,
        remediation="a redirect whose Location is not a login path (or is not readable) — "
                    "re-capture the route and read the Location yourself; this classification "
                    "decides nothing about the session either way"),
    # L2 — the reflex this taxonomy exists to stop.
    "csrf_missing": dict(
        session_suspect=False, retryable=False, evidence=VERIFIED,
        remediation="re-fetch JSESSIONID and strip the surrounding quotes for the csrf-token "
                    "header — the session itself may be perfectly alive"),
    # L3 — the cheat sheet lists no 401 row at all.
    "unauthorized": dict(
        session_suspect=False, retryable=False, evidence=ANTICIPATED,
        remediation="probe GET /voyager/api/me and classify that answer; do not re-login on a "
                    "401 alone"),
    # L4/L5 — one class, no cause claim (sections 3.1, 3.2).
    "sdui_replay_incomplete": dict(
        session_suspect=False, retryable=False, evidence=VERIFIED,
        remediation="re-capture the full SDUI body and replay it verbatim; a hand-built partial "
                    "body 500s"),
    # L6 — wrong URN form / guessed shape.
    "bad_request": dict(
        session_suspect=False, retryable=False, evidence=VERIFIED,
        remediation="fix the parameters — check the URN form and key order against the captured "
                    "request"),
    # L9 — INFERRED: no observed rotation-404 is documented.
    "query_id_rotated": dict(
        session_suspect=False, retryable=False, evidence=INFERRED,
        remediation="re-capture the current queryId/sduiid hash (tools/capture_write_action.py, "
                    "tools/crawl_recursive.py) — or the path is wrong"),
    # L10 — one cheat-sheet row, never observed.
    "rate_limited": dict(
        session_suspect=False, retryable=True, evidence=ANTICIPATED,
        remediation="back off and retry later"),
    # L7 — the status code actively lies: HTTP 200 carrying data.errors.
    "graphql_validation": dict(
        session_suspect=False, retryable=False, evidence=VERIFIED,
        remediation="input error — a GraphQL write answers 200 even on a validation error; fix "
                    "the variables. The error text stays out of this classification on purpose"),
    # A 2xx without a readable JSON object body is a FAILED read, not an empty one
    # (mcp/lib/client.py _read_json). Section 2.3 has NO observed row for this — L8 is the SDUI
    # 200 no-op, a different thing — so the class is INFERRED and acquits nothing: an
    # interstitial or login page reads exactly like this.
    "non_json_response": dict(
        session_suspect=False, retryable=False, evidence=INFERRED,
        remediation="the route answered 2xx but the body is not a readable JSON object — an "
                    "interstitial or login page looks like this too; re-capture the request and "
                    "check session_status(). This classification decides nothing about the "
                    "session either way"),
    # L12 — the current state of this machine.
    "session_file_missing": dict(
        session_suspect=False, retryable=False, evidence=VERIFIED,
        remediation="setup, not session: the cookie file is absent — (re)start the external "
                    "session_daemon.py, or point VG_COOKIES at the right file"),
    # L11 — cookies_extract.py warns about a missing JSESSIONID and writes the file anyway.
    "session_markers_missing": dict(
        session_suspect=False, retryable=False, evidence=VERIFIED,
        remediation="setup, not session: the cookie file lacks li_at or JSESSIONID — re-extract "
                    "the cookies"),
    # L13 — network / timeout.
    "transport_unavailable": dict(
        session_suspect=False, retryable=True, evidence=VERIFIED,
        remediation="network or timeout — retry; nothing is known about the session"),
    # Default. An unrecognised failure is NEVER session death (section 2.4, step 6).
    "unknown": dict(
        session_suspect=False, retryable=False, evidence=INFERRED,
        remediation="unrecognised failure — capture the request and classify it before assuming "
                    "anything about the session"),
}

_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "csrf_missing",
    404: "query_id_rotated",
    429: "rate_limited",
    500: "sdui_replay_incomplete",
}


def _result(code: str, *, status: Any = None, endpoint: str = "",
            body_len: Optional[int] = None, evidence: Optional[str] = None) -> dict:
    """Build the flat classification dict. Carries NO body and no body excerpt.

    `evidence` may be DOWNGRADED per call: the same code can be reached from an observed signal
    and from a merely plausible variant of it (see the top-level-`errors` path in classify()).
    The class default is the observed reading; a variant passes the weaker label explicitly.
    """
    spec = _CLASSES[code]
    return {"code": code, "session_suspect": spec["session_suspect"],
            "retryable": spec["retryable"], "remediation": spec["remediation"],
            "evidence": evidence or spec["evidence"], "status": status, "endpoint": endpoint,
            "body_len": body_len}


def _body_len(response: Any) -> Optional[int]:
    """Length of the response body — the length, never the body itself."""
    try:
        text = response.text
    except Exception:
        return None
    try:
        return len(text)
    except Exception:
        return None


def _location(response: Any) -> str:
    """The Location header, case-insensitively (requests uses a case-insensitive dict, fakes
    and fixtures often a plain one)."""
    headers = getattr(response, "headers", None) or {}
    try:
        for key in ("Location", "location"):
            value = headers.get(key)
            if value:
                return str(value)
    except Exception:
        return ""
    return ""


def _location_path(location: str) -> str:
    """The path of a Location URL, lower-cased, without query or fragment.

    Both halves of this matter and both were wrong when matched as a raw substring of the whole
    header (measured, 2026-07-31):
      * case — `HTTPS://WWW.LINKEDIN.COM/UAS/LOGIN` missed `/uas/login` and a real session death
        was classified as harmless. That is the fail-OPEN direction, the dangerous one.
      * query — `https://www.linkedin.com/feed/?next=/uas/login` matched and reported session
        death for a redirect to the feed.
    Pure string work on purpose: this module imports nothing beyond typing.
    """
    text = str(location or "").strip().lower()
    marker = "://"
    if marker in text:                        # absolute URL: skip scheme + authority
        rest = text.split(marker, 1)[1]
        slash = rest.find("/")
        text = rest[slash:] if slash != -1 else "/"
    for cut in ("?", "#"):                    # path ends at query or fragment
        if cut in text:
            text = text.split(cut, 1)[0]
    return text


def _is_login_redirect(location: str) -> bool:
    """True when the Location's PATH is a login path — not merely contains the string somewhere."""
    path = _location_path(location)
    if not path:
        return False
    return any(path == p or path.startswith(p + "/") for p in LOGIN_PATHS)


def _content_type(response: Any) -> str:
    headers = getattr(response, "headers", None) or {}
    try:
        for key in ("Content-Type", "content-type"):
            value = headers.get(key)
            if value:
                return str(value).lower()
    except Exception:
        return ""
    return ""


def _parse_body(response: Any) -> Optional[dict]:
    """The parsed JSON OBJECT, or None when the body is not one.

    None is a FAILED read, never a success: an unparsable, truncated or empty body — and a
    login/interstitial page served with a JSON content-type — all land here. Swallowing the
    parse error and calling the answer `ok` would be the "failure that looks like a success"
    class (mcp/lib/client.py _read_json says the same for the read path).
    """
    try:
        body = response.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def _errors_field(body: dict) -> Optional[str]:
    """Which error carrier the 2xx body has: "data.errors" (L7, observed), "errors" (top-level,
    NOT observed in this repo) or None.

    Only the PRESENCE is reported; the message text is a body excerpt and stays out (2.6).
    """
    try:
        data = body.get("data")
        if isinstance(data, dict) and data.get("errors"):
            return "data.errors"
        if body.get("errors"):
            return "errors"
    except Exception:
        return None
    return None


def classify_exception(exc: BaseException, endpoint: str = "") -> dict:
    """Classify an exception raised BEFORE the response existed (L11–L13).

    Separates the three causes that mcp/lib/client.py used to collapse into one `False`:
    missing cookie file, missing cookie marker, network/timeout. None of them is session death.
    """
    if isinstance(exc, FileNotFoundError):
        return _result("session_file_missing", status="no_request", endpoint=endpoint)
    if isinstance(exc, KeyError):
        return _result("session_markers_missing", status="no_request", endpoint=endpoint)
    # requests' RequestException family derives from OSError, so timeouts and connection
    # errors land here too (lib/vgreq.py get/post/delete, timeout=25).
    if isinstance(exc, (OSError, TimeoutError)):
        return _result("transport_unavailable", status="no_request", endpoint=endpoint)
    return _result("unknown", status="no_request", endpoint=endpoint)


def classify(response: Any = None, exc: Optional[BaseException] = None,
             endpoint: str = "") -> dict:
    """Classify one attempt: `{code, session_suspect, retryable, remediation, evidence,
    status, endpoint, body_len}`.

    Detection order (docs/SESSION-AND-ERRORS-DESIGN.md, section 2.4) — deliberately NOT
    Indeed's order:

    1. an exception from before the request (no response at all),
    2. redirect FIRST, because vgreq passes allow_redirects=False, so a 3xx really arrives —
       `Location` on a login path is the one and only `session_suspect=True`,
    3. content-type AND parsability, restricted to 2xx: a successful-looking answer without a
       readable JSON object body is a failed read, never an `ok`. The check accepts the
       `vnd.linkedin.…+json…` family, not the bare `application/json` string. On a 4xx/5xx the
       STATUS carries the information, so the content-type must not shadow it — otherwise a 403
       served as HTML would be filed as "non-JSON" instead of `csrf_missing`, and E2 would be
       lost,
    4. body signal before status: a 2xx carrying `data.errors` — or a top-level `errors` — is a
       failure however friendly the status looks,
    5. the status,
    6. default: unknown is NOT session death.
    """
    if exc is not None:
        return classify_exception(exc, endpoint=endpoint)
    if response is None:
        return _result("unknown", status=None, endpoint=endpoint)

    status = getattr(response, "status_code", None)
    length = _body_len(response)
    if not isinstance(status, int):
        return _result("unknown", status=status, endpoint=endpoint, body_len=length)

    if 300 <= status < 400:
        location = _location(response)
        if _is_login_redirect(location):
            return _result(SESSION_SUSPECT_CODE, status=status, endpoint=endpoint,
                           body_len=length)
        return _result("redirect_unexpected", status=status, endpoint=endpoint, body_len=length)

    if 200 <= status < 300:
        if _JSON_MARKER not in _content_type(response):
            return _result("non_json_response", status=status, endpoint=endpoint,
                           body_len=length)
        body = _parse_body(response)
        if body is None:
            # The content-type PROMISED JSON and the body is not a readable JSON object. Calling
            # that `ok` would report a failure as a healthy session.
            return _result("non_json_response", status=status, endpoint=endpoint,
                           body_len=length)
        carrier = _errors_field(body)
        if carrier == "data.errors":
            return _result("graphql_validation", status=status, endpoint=endpoint,
                           body_len=length)
        if carrier == "errors":
            # Same code, weaker provenance: a top-level `errors` on a 2xx is not an observed row
            # in section 2.3 — it is the plausible sibling of L7, so never labelled as observed.
            return _result("graphql_validation", status=status, endpoint=endpoint,
                           body_len=length, evidence=INFERRED)
        return _result("ok", status=status, endpoint=endpoint, body_len=length)

    # Only 500 is mapped: the documented 500 is the incomplete SDUI replay. Any other 5xx is
    # unknown — inventing a cause for it would be exactly the forbidden move.
    return _result(_STATUS_CODES.get(status, "unknown"), status=status, endpoint=endpoint,
                   body_len=length)
