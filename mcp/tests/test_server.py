"""test_server.py — offline smoke tests for the linkedin-mcp server.

Verifies the server imports, registers its tools, and that the confirmation guardrail on
people-facing tools works — WITHOUT launching a browser or touching LinkedIn.

Run:  .venv/bin/python tests/test_server.py   (exit 0 = green)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import server  # noqa: E402

EXPECTED = {"get_me", "get_my_posts", "get_profile", "get_notifications",
            "get_conversations", "get_connections_summary", "get_post_comments", "get_link_preview",
            "get_job", "get_job_recommendations",
            "session_status", "refresh_session", "like", "unlike", "follow_company",
            "connect", "endorse_skill", "remove_connection",
            "save_post", "repost", "delete_repost",
            "create_post", "create_post_with_image", "delete_post", "edit_post", "create_poll",
            "send_dm", "recall_message", "react_to_message",
            "create_comment", "delete_comment", "react_to_comment"}


def test_tools_registered():
    # exact match, not a subset: a tool added (or lost) must be an explicit decision here —
    # test_readonly.py then forces the read/write split for it.
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED, \
        f"missing tools: {EXPECTED - names}; unexpected tools: {names - EXPECTED}"


def test_every_tool_has_a_description():
    tools = asyncio.run(server.mcp.list_tools())
    for t in tools:
        assert (t.description or "").strip(), f"{t.name} has no description"


def test_people_facing_tools_gate_on_confirm():
    # create_post / send_dm / delete_post must NOT act without confirm=True — they return a
    # needs_confirmation preview and never reach the client. (No session, no browser touched.)
    r = server.create_post(text="hello world", confirm=False)
    assert r.get("needs_confirmation") is True and r.get("preview") == "hello world"
    r2 = server.send_dm(conversation_urn="urn:li:x", text="hi", confirm=False)
    assert r2.get("needs_confirmation") is True
    r3 = server.delete_post(activity_id="123", tracking_id="t", confirm=False)
    assert r3.get("needs_confirmation") is True
    r4 = server.repost(activity_id="123", confirm=False)
    assert r4.get("needs_confirmation") is True
    r5 = server.delete_repost(repost_urn="urn:li:x", confirm=False)
    assert r5.get("needs_confirmation") is True
    r6 = server.connect(member_urn="urn:li:fsd_profile:X", confirm=False)
    assert r6.get("needs_confirmation") is True
    r7 = server.remove_connection(vanity_name="x", confirm=False)
    assert r7.get("needs_confirmation") is True


def test_no_browser_on_import():
    # The client is a PURE API client: it must have NO browser attribute and never reference
    # SessionBrowser. (Importing the server must not pull in patchright / launch anything.)
    assert not hasattr(server.li, "_browser"), "client must not carry a browser handle"
    import lib.client as _cl
    import inspect
    src = inspect.getsource(_cl)
    assert "SessionBrowser" not in src, "client.py must not reference SessionBrowser"
    assert "post_comment_ui" not in src and "delete_comment_ui" not in src, \
        "client.py must not drive the browser UI"


VOYAGER_CTYPE = "application/vnd.linkedin.normalized+json+2.1"


class _FakeResponse:
    def __init__(self, status_code, headers=None, text="", payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def _healthy_me(payload=None):
    """A /me answer that really reads as a live session: Voyager content-type + JSON object."""
    return _FakeResponse(200, {"Content-Type": VOYAGER_CTYPE}, "{}",
                         payload if payload is not None else {})


class _FakeVg:
    """Stand-in for the vgreq module: answers the /me probe, or raises before the request."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def get(self, url, extra_headers=None):
        if self._exc is not None:
            raise self._exc
        return self._response


def _status_with(monkeypatch, **kwargs):
    monkeypatch.setattr(server.li, "_vg", lambda: _FakeVg(**kwargs))
    return server.session_status()


def test_session_status_missing_cookie_file_is_not_a_dead_session(monkeypatch):
    # The current state of this machine: no /tmp/li_cookies.json. That is SETUP, not an expired
    # session — the whole point of the field. (Not yet live-tested; the probe is faked.)
    out = _status_with(monkeypatch, exc=FileNotFoundError("/tmp/li_cookies.json"))
    assert out["logged_in"] is False
    assert out["session_suspect"] is False
    assert out["error_code"] == "session_file_missing"
    assert "setup" in out["hint"]


def test_session_status_login_redirect_is_the_one_session_suspect(monkeypatch):
    out = _status_with(monkeypatch, response=_FakeResponse(
        302, {"Location": "https://www.linkedin.com/uas/login"}))
    assert out["logged_in"] is False
    assert out["session_suspect"] is True
    assert out["error_code"] == "session_expired"


def test_session_status_403_does_not_claim_the_session_is_dead(monkeypatch):
    # Manuel's actual complaint: every 403 read as "session dead". It is a csrf header defect.
    out = _status_with(monkeypatch, response=_FakeResponse(403, {"Content-Type": "text/html"},
                                                          "<html/>"))
    assert out["session_suspect"] is False
    assert out["error_code"] == "csrf_missing"
    assert "JSESSIONID" in out["hint"]


def test_session_status_network_error_is_not_a_dead_session(monkeypatch):
    out = _status_with(monkeypatch, exc=TimeoutError("read timeout"))
    assert out["session_suspect"] is False
    assert out["error_code"] == "transport_unavailable"
    assert out["retryable"] is True


def test_session_status_leaks_no_response_body(monkeypatch):
    secret = "urn:li:fsd_profile:AAA Ada Lovelace private message text"
    out = _status_with(monkeypatch, response=_FakeResponse(
        500, {"Content-Type": "application/vnd.linkedin.normalized+json+2.1"}, secret))
    rendered = repr(out)
    for fragment in ("Ada", "Lovelace", "urn:li:fsd_profile", "private message"):
        assert fragment not in rendered, f"{fragment} leaked into session_status"
    assert set(out) == {"logged_in", "read_only", "session_suspect", "error_code", "retryable",
                        "hint"}


def test_ensure_session_still_returns_a_bool(monkeypatch):
    # Every tool calls ensure_session() — the signature must not change with the diagnosis.
    monkeypatch.setattr(server.li, "_vg", lambda: _FakeVg(exc=FileNotFoundError("x")))
    assert server.li.ensure_session() is False
    monkeypatch.setattr(server.li, "_vg", lambda: _FakeVg(response=_healthy_me()))
    assert server.li.ensure_session() is True


def test_a_failed_probe_is_never_reported_as_a_healthy_session(monkeypatch):
    """No second rule may overrule the classification. A 200 serving an interstitial (HTML, or a
    JSON content-type with an unreadable body) is a FAILED probe: logged_in false, and above all
    error_code + hint present. The earlier `status == 200` reported it as a live session with
    error_code=None — the "failure that looks like a success" class."""
    for response in (_FakeResponse(200, {"Content-Type": "text/html"}, "<html/>"),
                     _FakeResponse(200, {"Content-Type": VOYAGER_CTYPE}, ""),
                     _FakeResponse(200, {"Content-Type": VOYAGER_CTYPE}, "[]", [])):
        out = _status_with(monkeypatch, response=response)
        assert out["logged_in"] is False, response.headers
        assert out["error_code"] == "non_json_response", response.headers
        assert out["hint"], "a classified failure must always carry its hint"
        # E1 is untouched: only the login redirect means re-login.
        assert out["session_suspect"] is False


def test_error_code_and_hint_are_never_masked_when_the_probe_failed(monkeypatch):
    # The invariant, independent of the concrete class: error_code set <=> hint set, and a
    # healthy probe carries neither.
    for kwargs in ({"exc": TimeoutError("t")},
                   {"response": _FakeResponse(403, {"Content-Type": "text/html"}, "<html/>")},
                   {"response": _FakeResponse(204)},
                   {"response": _healthy_me()}):
        out = _status_with(monkeypatch, **kwargs)
        assert (out["error_code"] is None) == (out["hint"] is None), out
        assert (out["error_code"] is None) == out["logged_in"], out


def test_refresh_session_hint_names_the_cause_instead_of_blaming_the_cookies(monkeypatch):
    # Same key set as before ({logged_in, hint}); only the hint stops claiming stale cookies for
    # every failure. A missing cookie file is setup, a timeout is transport.
    monkeypatch.setattr(server.li, "_vg",
                        lambda: _FakeVg(exc=FileNotFoundError("/tmp/li_cookies.json")))
    out = server.refresh_session()
    assert set(out) == {"logged_in", "hint"}
    assert out["logged_in"] is False and "setup" in out["hint"]
    monkeypatch.setattr(server.li, "_vg", lambda: _FakeVg(exc=TimeoutError("t")))
    assert "retry" in server.refresh_session()["hint"]
    monkeypatch.setattr(server.li, "_vg", lambda: _FakeVg(response=_healthy_me()))
    assert server.refresh_session() == {"logged_in": True, "hint": None}


def test_a_2xx_carrying_errors_is_not_a_live_session(monkeypatch):
    # data.errors (observed, L7) and a top-level `errors` (not observed) both beat the status.
    for payload in ({"data": {"errors": [{"message": "x"}]}},
                    {"data": None, "errors": [{"message": "x"}]}):
        out = _status_with(monkeypatch, response=_healthy_me(payload))
        assert out["logged_in"] is False, payload
        assert out["error_code"] == "graphql_validation"
        assert out["session_suspect"] is False


def test_ensure_session_returns_false_instead_of_raising_on_an_unusable_response(monkeypatch):
    """The diff moved classify() OUTSIDE probe_session's try (mcp/lib/client.py, probe_session).
    Every tool calls ensure_session(), so a probe answer that does not duck-type as a response
    must still come back as False, never as an exception."""
    class _NotAResponse:
        pass

    monkeypatch.setattr(server.li, "_vg", lambda: _FakeVg(response=_NotAResponse()))
    assert server.li.ensure_session() is False
    out = server.session_status()
    assert out["session_suspect"] is False, "an unclassifiable answer is not session death"
    assert out["error_code"] == "unknown"


def main():
    # Same env pin as mcp/tests/conftest.py (which pytest applies but this standalone runner
    # does not see): an exported LINKEDIN_READ_ONLY must not decide whether this suite is green.
    os.environ.pop("LINKEDIN_READ_ONLY", None)
    import inspect
    # Tests that take a pytest fixture (monkeypatch) cannot run in this standalone runner —
    # pytest covers them; skipping them here is not a silent pass, they are simply not listed.
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v) and not inspect.signature(v).parameters]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:  # report, never abort the run with a traceback
            print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"=== {passed}/{len(tests)} passed ===")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
