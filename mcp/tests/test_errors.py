"""test_errors.py — the error taxonomy: one session_suspect, the right detection order, no body.

Offline by construction: mcp/lib/errors.py is pure (no network, no file, no cookies), so these
tests only hand it fake response objects. Nothing here touches the transport.

Run:  ./.venv/bin/python -m pytest mcp/tests/test_errors.py -q
"""
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import lib.errors as errors  # noqa: E402

# The content type EVERY successful Voyager response carries (lib/vgreq.py sends it as accept).
VOYAGER_CTYPE = "application/vnd.linkedin.normalized+json+2.1"

RESULT_KEYS = {"code", "session_suspect", "retryable", "remediation", "evidence", "status",
               "endpoint", "body_len"}


class FakeResponse:
    """Duck-typed stand-in for a requests.Response — status, headers, body."""

    def __init__(self, status_code, headers=None, text="", payload=None, json_raises=False):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self._payload = payload
        self._json_raises = json_raises

    def json(self):
        if self._json_raises or self._payload is None:
            raise ValueError("not json")
        return self._payload


def _json_response(status=200, payload=None, text="{}"):
    return FakeResponse(status, {"Content-Type": VOYAGER_CTYPE}, text, payload if payload
                        is not None else {})


# --- the invariant: exactly ONE class means "re-login" ---------------------------------------
def test_exactly_one_class_carries_session_suspect():
    suspects = [code for code, spec in errors._CLASSES.items() if spec["session_suspect"]]
    assert suspects == [errors.SESSION_SUSPECT_CODE], \
        f"exactly one class may mean session death, got {suspects}"


def test_the_module_is_pure():
    # No module-level imports beyond typing names: no network, no file access, no cookies.
    imported = sorted(k for k, v in vars(errors).items() if isinstance(v, types.ModuleType))
    assert imported == [], f"errors.py must import no modules, found {imported}"


# --- L1: the only evidenced session death ----------------------------------------------------
def test_redirect_to_login_is_the_one_session_suspect():
    for location in ("https://www.linkedin.com/uas/login?fromSignIn=true",
                     "https://www.linkedin.com/login"):
        out = errors.classify(FakeResponse(302, {"Location": location}), endpoint="e")
        assert out["code"] == errors.SESSION_SUSPECT_CODE
        assert out["session_suspect"] is True
        assert out["retryable"] is False
        assert "re-login" in out["remediation"]


def test_location_header_is_read_case_insensitively():
    out = errors.classify(FakeResponse(303, {"location": "/uas/login"}))
    assert out["session_suspect"] is True


def test_a_redirect_elsewhere_is_not_session_death():
    out = errors.classify(FakeResponse(302, {"Location": "https://www.linkedin.com/feed/"}))
    assert out["code"] == "redirect_unexpected"
    assert out["session_suspect"] is False


def test_a_redirect_acquits_nothing_and_says_so_without_a_location_header():
    """Not meeting the one session-death signal is not the same as proving the session healthy.
    A 3xx whose Location cannot be read must not be described as "no session problem"."""
    for headers in ({}, {"Location": "https://www.linkedin.com/feed/"}):
        out = errors.classify(FakeResponse(302, headers))
        assert out["code"] == "redirect_unexpected"
        assert out["session_suspect"] is False
        assert out["evidence"] == errors.INFERRED
        assert "no session problem" not in out["remediation"], \
            "a redirect classification must not acquit the session"


# --- L2: the reflex this taxonomy exists to stop ---------------------------------------------
def test_403_is_a_csrf_defect_and_never_session_suspect():
    out = errors.classify(FakeResponse(403, {"Content-Type": "text/html"}, "<html/>"))
    assert out["code"] == "csrf_missing"
    assert out["session_suspect"] is False
    assert "JSESSIONID" in out["remediation"]
    # A 403 served as HTML must NOT be shadowed by the content-type step — the status decides.


# --- detection order, step 3: the most expensive copy-paste error ----------------------------
def test_the_voyager_content_type_counts_as_json():
    # `"application/json" in ctype` would file EVERY successful Voyager answer as non-JSON.
    out = errors.classify(_json_response(200, payload={"data": {}}))
    assert out["code"] == "ok", "vnd.linkedin.normalized+json+2.1 must count as JSON"
    assert out["session_suspect"] is False


def test_a_non_json_2xx_is_a_failed_read_not_a_session_problem():
    out = errors.classify(FakeResponse(200, {"Content-Type": "text/html"}, "<html/>"))
    assert out["code"] == "non_json_response"
    assert out["session_suspect"] is False


def test_a_2xx_whose_body_is_unreadable_is_never_called_ok():
    """The stale-cookie case: the content-type promises Voyager JSON, the body is empty,
    truncated or not an object. Calling that `ok` reports a failure as a healthy session."""
    for response in (FakeResponse(200, {"Content-Type": VOYAGER_CTYPE}, "", json_raises=True),
                     FakeResponse(200, {"Content-Type": VOYAGER_CTYPE}, "{trunc",
                                  json_raises=True),
                     FakeResponse(200, {"Content-Type": VOYAGER_CTYPE}, "[]", payload=[])):
        out = errors.classify(response, endpoint="voyager.me.get")
        assert out["code"] == "non_json_response", out
        assert out["session_suspect"] is False


def test_the_2xx_without_a_json_body_class_is_not_labelled_as_observed():
    """docs/SESSION-AND-ERRORS-DESIGN.md, section 2.3 has no observed row for a 2xx without a
    JSON body (L8 is the SDUI 200 no-op). So the label must be INFERRED and the remediation must
    not acquit the session — a machine-readable `verified` on an unobserved class is the worst
    defect this repo can ship."""
    out = errors.classify(FakeResponse(200, {"Content-Type": "text/html"}, "<html/>"))
    assert out["evidence"] == errors.INFERRED
    assert "not a session problem" not in out["remediation"]


# --- detection order, step 4: body signal before status --------------------------------------
def test_graphql_200_with_data_errors_beats_the_status():
    payload = {"data": {"errors": [{"message": "urn:li:fsd_profile:SECRET is invalid"}]}}
    out = errors.classify(_json_response(200, payload=payload), endpoint="graphql")
    assert out["code"] == "graphql_validation"
    assert out["session_suspect"] is False
    assert out["evidence"] == errors.VERIFIED, "data.errors on a 200 IS an observed row (L7)"


def test_a_top_level_errors_field_also_beats_the_status_but_with_a_weaker_label():
    """`{"data": null, "errors": [...]}` on a 200 is the plausible sibling of L7, not an observed
    row: same code, provenance downgraded — never sold as an observed fact."""
    out = errors.classify(_json_response(200, payload={"data": None,
                                                      "errors": [{"message": "SECRET"}]}),
                          endpoint="graphql")
    assert out["code"] == "graphql_validation"
    assert out["evidence"] == errors.INFERRED
    assert out["session_suspect"] is False
    assert "SECRET" not in repr(out)


# --- detection order, step 5: the status -----------------------------------------------------
def test_status_classes_and_their_flags():
    cases = {400: "bad_request", 401: "unauthorized", 404: "query_id_rotated",
             429: "rate_limited", 500: "sdui_replay_incomplete"}
    for status, code in cases.items():
        out = errors.classify(FakeResponse(status, {"Content-Type": VOYAGER_CTYPE}, "x"))
        assert out["code"] == code, f"HTTP {status}"
        assert out["session_suspect"] is False, f"HTTP {status} must not mean session death"
    assert errors.classify(FakeResponse(429))["retryable"] is True


def test_modes_the_design_never_observed_are_marked_as_such():
    # 401 and 429 exist in the taxonomy but must never read as observed facts.
    for status in (401, 429):
        assert errors.classify(FakeResponse(status))["evidence"] == errors.ANTICIPATED
    # the rotation-404 is INFERRED, not observed either
    assert errors.classify(FakeResponse(404))["evidence"] == errors.INFERRED


# --- detection order, step 6: the default ----------------------------------------------------
def test_unknown_failures_are_never_session_death():
    for response in (FakeResponse(503), FakeResponse(418), FakeResponse(None), None):
        out = errors.classify(response)
        assert out["code"] == "unknown", out
        assert out["session_suspect"] is False


# --- the three causes that used to collapse into one False (L11-L13) -------------------------
def test_pre_request_exceptions_are_told_apart():
    assert errors.classify(exc=FileNotFoundError("/tmp/li_cookies.json"))["code"] \
        == "session_file_missing"
    assert errors.classify(exc=KeyError("JSESSIONID"))["code"] == "session_markers_missing"
    assert errors.classify(exc=TimeoutError("read timeout"))["code"] == "transport_unavailable"
    assert errors.classify(exc=ConnectionError("no route"))["code"] == "transport_unavailable"
    for exc in (FileNotFoundError("x"), KeyError("y"), TimeoutError("z")):
        out = errors.classify(exc=exc)
        assert out["session_suspect"] is False, f"{type(exc).__name__} is not session death"
        assert out["status"] == "no_request"


def test_missing_cookie_file_is_setup_not_an_expired_session():
    out = errors.classify(exc=FileNotFoundError("/tmp/li_cookies.json"))
    assert "setup" in out["remediation"]
    assert out["code"] != errors.SESSION_SUSPECT_CODE


# --- redaction: no body, ever (design section 2.6) -------------------------------------------
def test_no_response_body_reaches_the_classification():
    secret = "urn:li:fsd_profile:AAA_real_name_Ada_Lovelace_message_text"
    body = '{"data": {"errors": [{"message": "%s"}]}}' % secret
    response = FakeResponse(200, {"Content-Type": VOYAGER_CTYPE}, body,
                            {"data": {"errors": [{"message": secret}]}})
    out = errors.classify(response, endpoint="graphql")
    assert set(out) == RESULT_KEYS, "no extra key may smuggle a body out"
    rendered = repr(out)
    assert secret not in rendered
    for fragment in ("Ada", "Lovelace", "urn:li:fsd_profile"):
        assert fragment not in rendered, f"{fragment} leaked into the classification"
    # the LENGTH is allowed, the body is not
    assert out["body_len"] == len(body)


def test_an_empty_bodied_2xx_is_filed_as_non_json_a_deliberate_limitation():
    """A 204 and a body-less 201 currently classify as `non_json_response`.

    That is a KNOWN LIMITATION, not an accident, and it is pinned here so the next ticket sees
    it: classify() is wired only into the /me session probe (mcp/lib/client.py, probe_session),
    which answers 200 with a JSON body. The repo documents empty-bodied successes elsewhere —
    `DELETE …/feed/comments/<urn>` answers 204 (docs/07-COMMENTS.md, section on deleting a
    comment) and `like()` answers 201 (mcp/lib/client.py, like) — so whoever reuses this module
    on a write path must decide that case there, not silently inherit this one.

    What must hold in BOTH readings: an empty-bodied success is never session death.
    """
    for status in (204, 201):
        out = errors.classify(FakeResponse(status), endpoint="write")
        assert out["code"] == "non_json_response", (
            f"HTTP {status} classification changed — update this test and the write-path "
            f"decision it documents, do not just re-pin the number")
        assert out["session_suspect"] is False
        assert out["retryable"] is False
    # A 201 that DOES carry a Voyager JSON body is a plain success.
    assert errors.classify(_json_response(201, payload={"value": {}}))["code"] == "ok"


def test_classify_returns_unknown_for_something_that_is_not_a_response():
    """classify() sits on the failure path of ensure_session(), which every tool calls, so it
    must not be able to CREATE a failure. An object that does not duck-type as a response
    (no status_code, no headers, no text) has to come back as `unknown` — not as an exception,
    and above all not as session death."""
    class _NotAResponse:
        pass

    for candidate in (_NotAResponse(), object(), "", 0):
        out = errors.classify(candidate, endpoint="e")
        assert out["code"] == "unknown", candidate
        assert out["session_suspect"] is False
        assert set(out) == RESULT_KEYS


def test_body_length_survives_an_unreadable_body():
    out = errors.classify(FakeResponse(500, {}, "boom", json_raises=True))
    assert out["body_len"] == len("boom")
    assert out["code"] == "sdui_replay_incomplete"


def test_login_redirect_is_matched_on_the_path_not_as_a_raw_substring():
    """Both directions of the same defect, measured against the substring match this replaced.

    Fail-OPEN was the dangerous one: an upper-cased Location missed `/uas/login`, so a real
    session death read as harmless and nothing would re-login. Fail-CLOSED was the mirror: a
    redirect to the feed carrying `/uas/login` in a query parameter claimed session death.
    """
    dead = (
        "HTTPS://WWW.LINKEDIN.COM/UAS/LOGIN",                  # upper case
        "https://WWW.LinkedIn.com/uas/Login?fromSignIn=true",  # mixed case + query
        "/uas/login",                                          # relative
        "/UAS/LOGIN?x=1",                                      # relative, upper, query
        "https://www.linkedin.com/uas/login/",                 # trailing slash
    )
    for location in dead:
        out = errors.classify(FakeResponse(302, {"Location": location}))
        assert out["code"] == errors.SESSION_SUSPECT_CODE, location
        assert out["session_suspect"] is True, location

    alive = (
        "https://www.linkedin.com/feed/?next=/uas/login",   # login path only in the query
        "https://www.linkedin.com/feed/#/login",            # only in the fragment
        "https://www.linkedin.com/login-help",              # /login is a prefix, not the path
        "https://www.linkedin.com/checkpoint/challenge",    # unrelated redirect
    )
    for location in alive:
        out = errors.classify(FakeResponse(302, {"Location": location}))
        assert out["code"] == "redirect_unexpected", location
        assert out["session_suspect"] is False, location
