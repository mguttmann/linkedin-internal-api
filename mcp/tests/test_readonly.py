"""test_readonly.py — offline proof for LINKEDIN_READ_ONLY (read-only mode of the MCP server).

Every test here ENFORCES the constraint instead of assuming it: the transport is replaced
(fake vgreq module + lib.client.requests) and every test asserts ZERO outgoing calls, so a
write that slipped through the gate would be visible, not silent. No network, no cookie file,
no browser.

Two INDEPENDENT locks are proven here: LINKEDIN_READ_ONLY (the operating mode, cron safety) and
the per-tool confirm gate (the interactive case, where read-only is deliberately off). The order
matters and is asserted: the outer read-only gate fires FIRST, so confirm=True never buys a write
under read-only.

The gate is proven on BOTH paths: the module-level function (what a direct import sees) and
`mcp.call_tool` — the MCP boundary an agent actually goes through. They are the same object
today, but that is a consequence of decorator order, not a guarantee.

Run:  .venv/bin/python -m pytest mcp/tests/test_readonly.py -q
"""
import asyncio
import os
import re
import sys
import tempfile
import types

import pytest
from fastmcp.exceptions import ToolError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import server  # noqa: E402

_URN = "urn:li:activity:1111111111111111111"

# A synthetic PNG (signature + filler), written to a temp dir at import: NO real photo, no
# fixture binary in the repo, no network. server.create_post_with_image classifies the file by
# its own first bytes, so the write-path test below needs a file that actually passes that check.
_PNG_HEAD = b"\x89PNG\r\n\x1a\n"
_TEST_IMAGE = os.path.join(tempfile.mkdtemp(prefix="li-mcp-image-"), "cat.png")
with open(_TEST_IMAGE, "wb") as _fh:
    _fh.write(_PNG_HEAD + b"\x00" * 40)

# The 12 reading tools — ALL allowed under read-only (server.py get_me … refresh_session).
# The two jobs reads are READS: they must stay on this side of the split, ungated, and each one
# must actually reach the transport (asserted below) — a "read" that mutates fails here.
READ_CALLS = {
    "get_me": lambda: server.get_me(),
    "get_my_posts": lambda: server.get_my_posts(1),
    "get_conversations": lambda: server.get_conversations(),
    "get_profile": lambda: server.get_profile(""),
    "get_notifications": lambda: server.get_notifications(1),
    "get_connections_summary": lambda: server.get_connections_summary(),
    "get_post_comments": lambda: server.get_post_comments(_URN),
    "get_link_preview": lambda: server.get_link_preview("https://example.com/x"),
    # a VALID job id on purpose: with unusable input get_job answers without any HTTP call, and
    # the "must reach the transport" assertion below would prove nothing.
    "get_job": lambda: server.get_job("1234567890"),
    "get_job_recommendations": lambda: server.get_job_recommendations(1),
    "session_status": lambda: server.session_status(),
    "refresh_session": lambda: server.refresh_session(),
}

# The 20 writing tools — ALL blocked under read-only. Every one of them now carries a confirm
# gate, so confirm=True is passed for EVERY entry: without it these tests would stop at the
# confirm gate and prove nothing about read-only (the proof would be silently worthless).
# test_every_write_tool_is_called_with_confirm_true holds that property mechanically.
# Kwargs, not lambdas: the SAME argument set is replayed through the module-level function and
# through mcp.call_tool, so neither path can drift away from the other untested.
WRITE_KWARGS = {
    "create_comment": {"activity_urn": _URN, "text": "text", "confirm": True},
    "delete_comment": {"comment_id": "222", "activity_urn": _URN, "confirm": True},
    "like": {"activity_urn": _URN, "confirm": True},
    "unlike": {"activity_urn": _URN, "confirm": True},
    "follow_company": {"company_id": "1035", "confirm": True},
    "connect": {"member_urn": "urn:li:fsd_profile:X", "confirm": True},
    "endorse_skill": {"vanity_name": "other-user", "profile_id": "OTHER_ID", "skill_id": "48",
                      "confirm": True},
    "remove_connection": {"vanity_name": "other-user", "confirm": True},
    "save_post": {"activity_id": "999", "confirm": True},
    "repost": {"activity_id": "999", "confirm": True},
    "delete_repost": {"repost_urn": "urn:li:activity:2", "confirm": True},
    "create_post": {"text": "hello", "confirm": True},
    # an EXISTING file that also PASSES the image guardrail (see _TEST_IMAGE): with a missing
    # file — or with any non-image, e.g. this .py file — the tool answers honestly without any
    # HTTP call, and test_without_the_flag_writes_reach_the_transport would prove nothing about
    # the read-only gate. The bytes never leave the recorder.
    "create_post_with_image": {"text": "hello", "image_path": _TEST_IMAGE, "confirm": True},
    "edit_post": {"activity_id": "222", "share_id": "333", "text": "new text", "confirm": True},
    "create_poll": {"question": "Q?", "options": ["A", "B"], "confirm": True},
    "delete_post": {"activity_id": "222", "tracking_id": "trk", "confirm": True},
    "send_dm": {"conversation_urn": "urn:li:msg_conversation:(urn:li:fsd_profile:ME,1)",
                "text": "hi", "confirm": True},
    "recall_message": {"message_urn": "urn:li:msg_message:(x,2)", "confirm": True},
    "react_to_message": {"message_urn": "urn:li:msg_message:(x,2)", "confirm": True},
    "react_to_comment": {"comment_id": "888", "activity_urn": _URN, "confirm": True},
}


def _call_write(name):
    """Invoke a write tool the way a direct importer does: the module-level function."""
    return getattr(server, name)(**WRITE_KWARGS[name])


class _Resp:
    status_code = 200
    text = ""
    headers: dict = {}

    def json(self):
        return {}


# Every HTTP verb the recorder below intercepts. A verb the client uses but the fixture does
# NOT patch escapes into a real outgoing request — test_the_transport_fixture_catches_every_verb
# holds this list against mcp/lib/client.py mechanically, so the next new verb fails loudly.
_PATCHED_VERBS = ("get", "post", "put", "patch", "delete", "head", "request")


@pytest.fixture
def transport(monkeypatch):
    """Replace EVERY outgoing path with a recorder and return the call log.

    Covers both transports the client uses: the vgreq module (mcp/lib/client.py:79-82) and the
    raw requests.* calls — requests.post for SDUI writes (mcp/lib/client.py:22, e.g. :342 area /
    unlike) and requests.put for the single-part image upload (upload_image).
    """
    import lib.client as cl
    calls = {"get": [], "post": [], "delete": [], "requests": []}
    fake = types.ModuleType("vgreq")
    fake.get = lambda url, *a, **k: (calls["get"].append(url) or _Resp())
    fake.post = lambda url, body=None, *a, **k: (calls["post"].append((url, body)) or _Resp())
    fake.delete = lambda url, *a, **k: (calls["delete"].append(url) or _Resp())
    fake.put = lambda url, body=None, *a, **k: (calls["requests"].append(url) or _Resp())
    monkeypatch.setattr(cl, "vgreq", fake)
    monkeypatch.setattr(cl, "_HAVE_VGREQ", True)
    for verb in _PATCHED_VERBS:
        monkeypatch.setattr(cl.requests, verb,
                            lambda url, *a, **k: (calls["requests"].append(url) or _Resp()),
                            raising=False)
    # patch the class of the LIVE client instance: other tests reload lib.client, which rebinds
    # cl.LinkedInClient to a NEW class object while server.li still holds the original one.
    for klass in {cl.LinkedInClient, type(server.li)}:
        monkeypatch.setattr(klass, "_sdui_min_headers",
                            staticmethod(lambda: {"csrf-token": "ajax:x", "Cookie": "k=v"}))
    return calls


def test_the_transport_fixture_catches_every_verb_the_client_uses():
    """Class guard, not an instance fix: the recorder must intercept EVERY HTTP verb
    mcp/lib/client.py can reach for. The measured instance was requests.put in upload_image —
    unpatched, it performed a REAL outgoing HTTPS request (DNS resolution attempt) instead of
    being recorded. Any future verb (patch/head/…) fails HERE instead of leaving the sandbox.
    """
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib", "client.py")
    with open(src, encoding="utf-8") as fh:
        used = set(re.findall(r"(?:requests|_vg\(\))\.([a-z]+)\(", fh.read()))
    assert used, "the verb scan found nothing — the regex no longer matches the client"
    escaping = sorted(v for v in used if v not in _PATCHED_VERBS)
    assert not escaping, (
        f"mcp/lib/client.py calls requests/_vg().{escaping} — the transport fixture does not "
        f"patch these verbs, so any test exercising that path leaves the sandbox for real")


def _sent(calls) -> list:
    return calls["get"] + calls["post"] + calls["delete"] + calls["requests"]


def _mutating(calls) -> list:
    """Only the verbs that change something at LinkedIn. A GET is NOT proof of a write: every
    write tool first calls li.ensure_session() → a GET on /me (mcp/lib/client.py:74).
    calls["requests"] carries every raw requests.* call (SDUI POST, image PUT) — all mutating."""
    return calls["post"] + calls["delete"] + calls["requests"]


def _assert_block_message(msg, name):
    assert name in msg, "the error must name the blocked tool"
    assert "LINKEDIN_READ_ONLY" in msg, "the error must name the variable that releases it"
    assert "intentional" in msg, "the error must say the block is on purpose"


# ── the gate itself ──────────────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(WRITE_KWARGS))
def test_every_write_tool_is_blocked_and_sends_nothing(name, monkeypatch, transport):
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    with pytest.raises(ToolError) as ei:  # the TYPE matters: it is what carries the message out
        _call_write(name)
    _assert_block_message(str(ei.value), name)
    assert _sent(transport) == [], f"{name} must issue ZERO outgoing calls under read-only"


@pytest.mark.parametrize("name", sorted(WRITE_KWARGS))
def test_every_write_tool_is_blocked_at_the_mcp_boundary(name, monkeypatch, transport):
    """The path the agent really uses: the tool REGISTRY, not the module attribute.

    Both are the same function today only because @mcp.tool sits above @write_tool. Flip that
    order and mcp.tool registers the UNGATED inner function while server.<name> stays gated —
    every module-level test above would still pass while the boundary writes for real.
    """
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    with pytest.raises(ToolError) as ei:
        asyncio.run(server.mcp.call_tool(name, dict(WRITE_KWARGS[name])))
    _assert_block_message(str(ei.value), name)
    assert _sent(transport) == [], f"{name} must issue ZERO outgoing calls via the MCP boundary"


def test_blocked_write_never_returns_a_dict(monkeypatch, transport):
    # A gate must not look like a failed call ({"ok": False} → caller retries) and must never
    # fake success ({"ok": True}). It raises — and raises ToolError, not a signature error.
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    for name in sorted(WRITE_KWARGS):
        try:
            out = _call_write(name)
        except ToolError:
            continue
        except TypeError as e:  # pragma: no cover — would mean the test's kwargs are wrong
            pytest.fail(f"{name}: signature mismatch, not a gate hit: {e}")
        pytest.fail(f"{name} returned {out!r} instead of raising")


@pytest.mark.parametrize("name", sorted(READ_CALLS))
def test_read_tools_are_not_blocked_under_read_only(name, monkeypatch, transport):
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    out = READ_CALLS[name]()  # must not raise
    assert isinstance(out, dict)
    # a "read" that POSTs/DELETEs is not a read — this turns READ_CALLS from a declaration
    # into a measured claim, so a write tool cannot be smuggled in by listing it here.
    assert _mutating(transport) == [], f"{name} is listed as a READ but used a mutating verb"
    assert transport["get"], f"{name} is listed as a READ but never reached the transport"


def test_session_status_exposes_the_mode(monkeypatch, transport):
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    assert server.session_status()["read_only"] is False
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    assert server.session_status()["read_only"] is True


# ── flag semantics: the flag only ever switches writes OFF ───────────────
@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "2", "ja", " 1 ", "maybe"])
def test_flag_values_that_mean_on(value, monkeypatch):
    # unrecognised values (ja/2/maybe) count as ON — a typo must never grant write access.
    monkeypatch.setenv("LINKEDIN_READ_ONLY", value)
    assert server.read_only_enabled() is True


@pytest.mark.parametrize("value", ["off", "OFF", "no", "nein", "disabled", "null", "None", "-1"])
def test_values_that_only_look_like_off_still_mean_on(value, monkeypatch):
    # These are exactly what an operator types when he wants write access BACK. Only "0" and
    # "false" do that; everything else must keep the safe direction.
    monkeypatch.setenv("LINKEDIN_READ_ONLY", value)
    assert server.read_only_enabled() is True, f"{value!r} must NOT grant write access"


@pytest.mark.parametrize("value", ["0", "false", "False", "", "  "])
def test_flag_values_that_mean_off(value, monkeypatch):
    monkeypatch.setenv("LINKEDIN_READ_ONLY", value)
    assert server.read_only_enabled() is False


def test_flag_unset_means_off(monkeypatch):
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    assert server.read_only_enabled() is False


def test_flag_is_read_per_call_not_cached_at_import(monkeypatch):
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    assert server.read_only_enabled() is True
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "0")
    assert server.read_only_enabled() is False, "the flag must be read from os.environ every call"


def test_unrecognised_value_warns_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr(server, "_read_only_warned", set())
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "ja")
    assert server.read_only_enabled() is True
    cap = capsys.readouterr()
    assert "LINKEDIN_READ_ONLY" in cap.err and "ON" in cap.err
    # stdout IS the stdio MCP transport (mcp/server.py, __main__ block) — one stray line there
    # corrupts the protocol.
    assert cap.out == "", f"the warning must never touch stdout, got {cap.out!r}"


def test_warning_is_deduped_but_the_mode_stays_on(monkeypatch, capsys):
    # The dedupe must only suppress the WARNING, never the return value: a refactor that pulled
    # `return True` into the warn branch would hand out write access from the 2nd call on.
    monkeypatch.setattr(server, "_read_only_warned", set())
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "ja")
    assert server.read_only_enabled() is True
    first = capsys.readouterr().err
    assert server.read_only_enabled() is True, "read-only must stay ON on every later call"
    assert server.read_only_enabled() is True
    assert "LINKEDIN_READ_ONLY" in first
    assert capsys.readouterr().err == "", "the warning must be printed only once per value"


# ── the one whitelisted network-free path ────────────────────────────────
def test_dry_run_delete_comment_is_allowed_and_marked(monkeypatch, transport):
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    out = server.delete_comment("222", "urn:li:activity:111", dry_run=True)
    assert out["dry_run"] is True and out["method"] == "DELETE"
    assert out["read_only"] is True, "the caller must see that a real delete stays blocked"
    assert _sent(transport) == [], "dry_run must not touch the network"


def test_dry_run_is_allowed_at_the_mcp_boundary(monkeypatch, transport):
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    res = asyncio.run(server.mcp.call_tool(
        "delete_comment", {"comment_id": "222", "activity_urn": "urn:li:activity:111",
                           "dry_run": True}))
    assert res.structured_content["dry_run"] is True
    assert res.structured_content["read_only"] is True
    assert "read_only" in res.content[0].text
    assert _sent(transport) == [], "dry_run must not touch the network"


def test_dry_run_whitelist_also_holds_for_positional_and_force(monkeypatch, transport):
    # positional call: the gate binds the signature, it does not scan kwargs only.
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    out = server.delete_comment("222", "urn:li:activity:111", False, True)
    assert out["dry_run"] is True and out["read_only"] is True
    # force skips the owner guard (mcp/lib/client.py:334) but must not skip dry_run
    out = server.delete_comment("222", "urn:li:activity:111", dry_run=True, force=True)
    assert out["dry_run"] is True and out["read_only"] is True
    assert _sent(transport) == [], "dry_run must not touch the network, positional or with force"


def test_gate_does_not_trust_a_dry_run_parameter_name(monkeypatch, transport):
    # The whitelist is per-tool and opt-in: only delete_comment declares dry_run as network-free.
    # A tool that merely *had* a dry_run argument must still be blocked.
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")

    @server.write_tool
    def pretend_write(dry_run: bool = False) -> dict:
        return {"ok": True}

    with pytest.raises(ToolError) as ei:
        pretend_write(dry_run=True)
    assert "LINKEDIN_READ_ONLY" in str(ei.value)
    assert _sent(transport) == []


def test_whitelist_naming_a_missing_parameter_fails_safe(monkeypatch, transport):
    # A typo in network_free_param must block, never open.
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")

    @server.write_tool(network_free_param="dry_runn")
    def pretend_write(dry_run: bool = False) -> dict:
        return {"ok": True}

    with pytest.raises(ToolError):
        pretend_write(dry_run=True)
    assert _sent(transport) == []


def test_dry_run_delete_comment_unchanged_without_the_flag(monkeypatch, transport):
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    out = server.delete_comment("222", "urn:li:activity:111", dry_run=True)
    assert out["dry_run"] is True and "read_only" not in out
    assert _sent(transport) == []


# ── regression: without the flag nothing changed ─────────────────────────
def test_without_the_flag_confirm_gates_behave_exactly_as_before(monkeypatch, transport):
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    for call in (lambda: server.create_post(text="hello world"),
                 lambda: server.send_dm(conversation_urn="urn:li:x", text="hi"),
                 lambda: server.delete_post(activity_id="1", tracking_id="t"),
                 lambda: server.create_comment(_URN, "text"),
                 lambda: server.delete_comment("222", _URN),
                 lambda: server.connect("urn:li:fsd_profile:X"),
                 lambda: server.remove_connection("other-user"),
                 lambda: server.repost("999"),
                 lambda: server.delete_repost("urn:li:activity:2"),
                 lambda: server.edit_post("222", "333", "t"),
                 lambda: server.recall_message("urn:li:msg_message:(x,2)"),
                 lambda: server.react_to_comment("888", _URN)):
        assert call().get("needs_confirmation") is True
    assert _sent(transport) == [], "confirm gates must still send nothing"


# ── confirm gate: the second, independent lock (LINKEDIN_READ_ONLY is the first) ──────────
# The seven tools that had no confirm gate before this change (mcp/server.py:218, :229, :240,
# :262, :286, :341, :386). Per case: tool name, kwargs WITHOUT confirm, and the fields the caller
# must see echoed back — for the toggles the echo must name the DIRECTION (follow/save), so
# confirming cannot fire the opposite of what was shown.
NEW_CONFIRM_GATES = {
    "like": ("like", {"activity_urn": _URN}, {"activity_urn": _URN}),
    "unlike": ("unlike", {"activity_urn": _URN}, {"activity_urn": _URN, "action": "unlike"}),
    "follow": ("follow_company", {"company_id": "1035"},
               {"company_id": "1035", "follow": True}),
    "unfollow": ("follow_company", {"company_id": "1035", "follow": False},
                 {"company_id": "1035", "follow": False}),
    "endorse_skill": ("endorse_skill",
                      {"vanity_name": "other-user", "profile_id": "OTHER_ID", "skill_id": "48"},
                      {"vanity_name": "other-user", "skill_id": "48"}),
    "save": ("save_post", {"activity_id": "999"}, {"activity_id": "999", "save": True}),
    "unsave": ("save_post", {"activity_id": "999", "save": False},
               {"activity_id": "999", "save": False}),
    "create_poll": ("create_poll", {"question": "Q?", "options": ["A", "B"]},
                    {"question": "Q?", "options": ["A", "B"], "duration": "ONE_WEEK"}),
    "react_to_message": ("react_to_message", {"message_urn": "urn:li:msg_message:(x,2)"},
                         {"message_urn": "urn:li:msg_message:(x,2)", "emoji": "👏",
                          "toggle": True}),
    # create_post_with_image arrived WITH its gate; it is listed here for the same machinery —
    # and because the whitelist assertion below is what holds the payload to the file NAME plus
    # the MEASURED type and size: image_path is a local path, and a needs_confirmation payload
    # ends up in the transcript. This path does not exist, hence kind=unknown / size 0 — the
    # gate must SAY so instead of inviting a confirmation for a file it could not look at.
    "create_post_with_image": ("create_post_with_image",
                               {"text": "hello", "image_path": "/Users/someone/pics/cat.png"},
                               {"preview": "hello", "image_name": "cat.png",
                                "image_kind": "unknown", "image_bytes": 0,
                                "image_status": "unreadable_file", "visibility": "PUBLIC"}),
}


@pytest.mark.parametrize("case", sorted(NEW_CONFIRM_GATES))
def test_new_confirm_gates_block_and_send_nothing(case, monkeypatch, transport):
    """Without confirm=True the tool must return needs_confirmation and reach NO transport.

    Counted, not inferred: the assertion is on the recorded call log, so a gate placed AFTER
    li.ensure_session() (which GETs /me) would fail here.
    """
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    tool, kwargs, echoed = NEW_CONFIRM_GATES[case]
    out = getattr(server, tool)(**kwargs)
    assert out.get("needs_confirmation") is True, f"{case} acted without confirm=True"
    for key, value in echoed.items():
        assert out.get(key) == value, f"{case}: needs_confirmation must echo {key}={value!r}"
    # WHITELIST, not a blacklist: the payload may contain NOTHING beyond the identifying
    # arguments. A blacklist of forbidden substrings (see the leak test below) cannot catch a
    # field nobody thought of — a cookie path under an unforeseen key, a leaked profile_id, or an
    # `action` marker copied onto the wrong tool would all slip through it. This holds for every
    # future NEW_CONFIRM_GATES entry automatically.
    assert set(out) == {"needs_confirmation"} | set(echoed), \
        f"{case}: payload must name ONLY the identifying arguments, got {sorted(out)}"
    assert _sent(transport) == [], f"{case} must issue ZERO outgoing calls without confirm"


@pytest.mark.parametrize("case", sorted(NEW_CONFIRM_GATES))
def test_new_confirm_gates_hold_at_the_mcp_boundary(case, monkeypatch, transport):
    # Same reasoning as the read-only boundary test: the registry is the path an agent uses.
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    tool, kwargs, _ = NEW_CONFIRM_GATES[case]
    res = asyncio.run(server.mcp.call_tool(tool, dict(kwargs)))
    assert res.structured_content["needs_confirmation"] is True
    assert _sent(transport) == [], f"{case} must issue ZERO outgoing calls without confirm"


# ── leak guard: the CLASS "filesystem path", not a list of known paths ───
# A tool response lands in the MCP transcript. '/tmp/li_cookies.json' was the known instance;
# the class is "any absolute filesystem path" — '/Users/<name>/…' leaks the user name and the
# directory layout just as badly and passed a '/tmp/' blacklist untouched.
_HOME = os.path.expanduser("~")
_POISON_PATH = os.path.join(_HOME, "Pictures", "family-photo-2026.png")
_FORBIDDEN_SUBSTRINGS = ("li_at", "JSESSIONID", "csrf", "Cookie", "ajax:")

# Whitespace tokenisation missed every punctuated or embedded path — measured: "'/private/var/f/
# li.json'", "(/etc/li/cookies.json)", "path=/var/folders/ab/cd/cat.png", "file:///tmp/li/cat.png"
# and "~/Pictures/cat.png" all passed it. A regex over the whole string catches the class.
# Network URLs are not filesystem paths and are removed first; file:// deliberately is one.
_NETWORK_URL = re.compile(r"\b(?!file\b)[a-z][a-z0-9+.\-]*://\S+", re.I)
_PATH_LIKE = re.compile(r"""(?<![A-Za-z0-9])~?(?:/+[^/\s'"()\[\],;]+){2,}""")


def _looks_like_a_filesystem_path(text: str) -> bool:
    """True for an absolute (or ~-rooted) path with more than one segment, anywhere inside the
    string and regardless of surrounding quotes/brackets/`key=`, or for anything under $HOME."""
    if len(_HOME) > 1 and _HOME in text:
        return True
    return _PATH_LIKE.search(_NETWORK_URL.sub(" ", text)) is not None


def _walk_strings(value, where="return"):
    """Every string inside a nested return value, with the key path that carries it."""
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from _walk_strings(sub, f"{where}[{key!r}]")
    elif isinstance(value, (list, tuple, set)):
        for i, sub in enumerate(value):
            yield from _walk_strings(sub, f"{where}[{i}]")
    elif isinstance(value, str):
        yield where, value


def _kwargs_without_confirm(name):
    """WRITE_KWARGS minus confirm, with every *path* argument replaced by a $HOME path.
    Returns (kwargs, poisoned) — poisoned says whether this tool takes a path at all."""
    kwargs = {k: v for k, v in WRITE_KWARGS[name].items() if k != "confirm"}
    poisoned = False
    for key in kwargs:
        if "path" in key:
            kwargs[key], poisoned = _POISON_PATH, True
    return kwargs, poisoned


@pytest.mark.parametrize("name", sorted(WRITE_KWARGS))
def test_no_gated_tool_leaks_a_cookie_or_a_filesystem_path(name, monkeypatch, transport):
    """EVERY gated tool, checked RECURSIVELY: the confirmation payload names the identifying
    arguments only — no cookie values, no absolute paths, no server internals
    (docs/MCP-DESIGN.md §5 / project rule 5). Class guard: a future write tool that echoes a
    path argument back fails here without anyone adding it to a list.
    """
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    kwargs, _ = _kwargs_without_confirm(name)
    out = getattr(server, name)(**kwargs)
    assert out.get("needs_confirmation") is True, f"{name}: this must be the gate's own answer"
    for where, text in _walk_strings(out):
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            assert forbidden not in text, f"{name}: {forbidden!r} must not appear in {where}"
        assert not _looks_like_a_filesystem_path(text), \
            f"{name}: {where} leaks a filesystem path ({text!r})"
    assert _sent(transport) == [], f"{name} must issue ZERO outgoing calls without confirm"


def test_the_path_leak_probe_is_not_vacuous():
    """A leak probe that can never fire proves nothing: pin the predicate and prove that at
    least one gated tool actually receives the poisoned path."""
    assert _looks_like_a_filesystem_path(_POISON_PATH)
    assert _looks_like_a_filesystem_path("/tmp/li_cookies.json"), "the old instance must stay caught"
    assert _looks_like_a_filesystem_path("cookies live in /Users/someone/li_cookies.json")
    # the punctuated / embedded / ~-rooted variants a whitespace split silently let through
    for leak in ("'/private/var/f/li.json'", "(/etc/li/cookies.json)",
                 "path=/var/folders/ab/cd/cat.png", "file:///private/tmp/li/cat.png",
                 "~/Pictures/cat.png", "[/opt/li/state/cookies.json]",
                 'image="/srv/data/cat.png"'):
        assert _looks_like_a_filesystem_path(leak), f"{leak!r} is a path leak and must be caught"
    # and the class must not swallow legitimate payload values: no false positives
    for clean in ("urn:li:activity:1111111111111111111", "cat.png", "CONNECTIONS_ONLY",
                  "urn:li:msg_conversation:(urn:li:fsd_profile:ME,1)",
                  "urn:li:digitalmediaRecipe:feedshare-image",
                  "https://www.linkedin.com/feed/update/urn:li:activity:1", "and/or", "50/50",
                  "voyagerVideoDashMediaUploadMetadata?action=upload", "👏"):
        assert not _looks_like_a_filesystem_path(clean), f"{clean!r} is not a path — false positive"
    probed = sorted(n for n in WRITE_KWARGS if _kwargs_without_confirm(n)[1])
    assert probed, "no gated tool takes a path argument — the probe above proves nothing"


# ── the image guardrail: what we refuse to send, COUNTED in calls ────────
# create_post_with_image is the only tool that turns a caller-named LOCAL FILE into a public
# post. "Readable" is not "valid": the tool classifies the file by its own first bytes and by
# its size BEFORE anything leaves the process (mcp/server.py create_post_with_image,
# mcp/lib/client.py inspect_image). Every test here asserts on the recorded call log, so a
# refusal that still sends something fails. Offline-proven only — never live-tested.
def _refuse(monkeypatch, path):
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    return server.create_post_with_image("hello", path, confirm=True)


def test_the_confirmation_describes_the_image_by_type_and_size_not_by_path(monkeypatch,
                                                                          transport):
    """The gate has to be DECIDABLE: name, measured type and byte count — the three facts a
    human needs to tell a holiday photo from a private key, none of which needs a directory."""
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    out = server.create_post_with_image("hello", _TEST_IMAGE)
    assert out["needs_confirmation"] is True
    assert (out["image_name"], out["image_kind"], out["image_bytes"]) == ("cat.png", "png", 48)
    assert out["image_status"] == "ok"
    assert os.path.dirname(_TEST_IMAGE) not in repr(out), "no directory in the payload"
    assert _sent(transport) == [], "describing the file must cost ZERO calls"


@pytest.mark.parametrize("payload,status", [
    (b"", "empty_file"),                        # would register fileSize=0 and PUT nothing
    (b"-----BEGIN OPENSSH PRIVATE KEY-----\n", "unsupported_type"),
    (b"[core]\n\trepositoryformatversion = 0\n", "unsupported_type"),
])
def test_a_non_image_file_is_refused_without_a_single_outgoing_call(payload, status, tmp_path,
                                                                   monkeypatch, transport):
    # The extension LIES on purpose: the check reads the file's bytes, so renaming anything to
    # .png must not get it uploaded.
    path = tmp_path / "cat.png"
    path.write_bytes(payload)
    out = _refuse(monkeypatch, str(path))
    assert out["ok"] is False and out["status"] == status
    assert _mutating(transport) == [] and _sent(transport) == [], \
        f"a {status} file must cost ZERO calls, not even the session probe"
    assert str(tmp_path) not in repr(out), "the refusal must not echo the directory"
    assert "cat.png" in out["error"], "the caller must learn WHICH file was refused"


def test_an_image_over_the_cap_is_refused_without_a_single_outgoing_call(tmp_path, monkeypatch,
                                                                        transport):
    # The cap is OUR OWN documented choice, not a measured LinkedIn limit — this line is the
    # only place the number lives, so the docs may state it.
    assert server.MAX_IMAGE_BYTES == 10 * 1024 * 1024
    path = tmp_path / "big.png"
    path.write_bytes(_PNG_HEAD + b"\x00" * 200)
    monkeypatch.setattr(server, "MAX_IMAGE_BYTES", 100)
    out = _refuse(monkeypatch, str(path))
    assert out["ok"] is False and out["status"] == "image_too_large"
    assert _sent(transport) == [], "an oversize file must cost ZERO calls"
    assert str(tmp_path) not in repr(out)


def test_a_path_the_os_cannot_even_parse_returns_a_dict_instead_of_a_traceback(monkeypatch,
                                                                              transport):
    # Measured instance of the class "the except clause is narrower than the failure set":
    # open() on a path with an embedded NUL raises ValueError, not OSError, and a raw traceback
    # must never cross the tool boundary (project rule 4).
    out = _refuse(monkeypatch, "/Users/someone/ca\0t.png")
    assert out["ok"] is False and out["status"] == "unreadable_file"
    assert _sent(transport) == []
    assert "/Users/someone" not in repr(out)


@pytest.mark.parametrize("name", sorted(WRITE_KWARGS))
def test_every_write_tool_has_a_confirm_gate_defaulting_to_false(name):
    """Class-closing: a write tool without confirm — or with confirm defaulting to True — fails
    HERE. This is the property Manuel asked for (two independent locks), not a per-tool list."""
    import inspect as _inspect
    params = _inspect.signature(getattr(server, name)).parameters
    assert "confirm" in params, f"{name} has no confirm gate"
    assert params["confirm"].default is False, f"{name}: confirm must default to False"


@pytest.mark.parametrize("name", sorted(WRITE_KWARGS))
def test_every_write_tool_is_called_with_confirm_true(name):
    """Guards the read-only proof itself: if a WRITE_KWARGS entry ever dropped confirm=True, the
    read-only tests above would stop at the confirm gate and silently prove nothing."""
    assert WRITE_KWARGS[name].get("confirm") is True, \
        f"{name}: WRITE_KWARGS must pass confirm=True or the read-only proof is worthless"


@pytest.mark.parametrize("name", sorted(WRITE_KWARGS))
def test_read_only_wins_over_confirm(name, monkeypatch, transport):
    """ORDER IS THE SECURITY STATEMENT: the outer @write_tool gate must fire FIRST. Under
    read-only a call WITH confirm=True must raise ToolError and send nothing — it must not be
    let through, and it must not merely return a needs_confirmation dict either."""
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    assert WRITE_KWARGS[name].get("confirm") is True  # premise of this test
    with pytest.raises(ToolError) as ei:
        _call_write(name)
    _assert_block_message(str(ei.value), name)
    assert _mutating(transport) == [], f"{name}: confirm=True must not buy a write under read-only"
    assert _sent(transport) == [], f"{name} must issue ZERO outgoing calls under read-only"


@pytest.mark.parametrize("case", sorted(NEW_CONFIRM_GATES))
def test_read_only_wins_even_without_confirm(case, monkeypatch, transport):
    """The other half of the ORDER proof: confirm OMITTED, read-only ON.

    test_read_only_wins_over_confirm only covers confirm=True, where a swapped order would show
    up as a write. With confirm missing, a body-first order would return a harmless-looking
    needs_confirmation dict instead of raising — the failure signature that test's own docstring
    names but never exercises. The outer @write_tool gate must answer FIRST regardless of
    confirm, so read-only always reports read-only and never the confirm prompt.
    """
    monkeypatch.setenv("LINKEDIN_READ_ONLY", "1")
    tool, kwargs, _ = NEW_CONFIRM_GATES[case]
    assert "confirm" not in kwargs  # premise of this test
    with pytest.raises(ToolError) as ei:
        getattr(server, tool)(**kwargs)
    _assert_block_message(str(ei.value), tool)
    assert _sent(transport) == [], f"{case} must issue ZERO outgoing calls under read-only"


# Write tools that are gated like every other write but deliberately send NO MUTATING call:
# their request cannot succeed as configured, so the client refuses before the transport
# (client.py delete_repost — the repost-delete queryId hash is in no capture). At THIS (tool)
# level the ensure_session() GET on /me still goes out (mcp/server.py:311); the client method
# itself sends nothing at all — that is asserted one layer down in
# mcp/tests/test_client.py:544 (get + post + delete all empty).
NOT_OPERATIONAL = {"delete_repost"}


@pytest.mark.parametrize("name", sorted(WRITE_KWARGS))
def test_without_the_flag_writes_reach_the_transport(name, monkeypatch, transport):
    # The gate must be inert when the flag is off: every write tool still reaches the network
    # layer (proof that the read-only tests above measure the gate, not a broken call path).
    # Asserted on a MUTATING verb — a GET would only prove the /me session probe ran.
    monkeypatch.delenv("LINKEDIN_READ_ONLY", raising=False)
    out = _call_write(name)
    if name in NOT_OPERATIONAL:
        assert not _mutating(transport), \
            f"{name} must send no MUTATING call while it is not operational"
        assert out["ok"] is False and out["status"] == "not_configured", \
            f"{name} must fail honestly instead of reporting a false success"
        return
    assert _mutating(transport), f"{name} must still perform its WRITE call when read-only is off"


# ── the class-closing test: no future write tool may stay ungated ────────
def test_tool_registry_splits_into_reads_and_gated_writes():
    """A NEW write tool that forgets @write_tool fails HERE, not in production.

    Every registered tool must be either an explicitly listed read or carry the read-only gate
    (__li_write__, set by server.write_tool). Adding a tool therefore forces a decision.
    """
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    # The split carries its NUMBERS here (12 reads / 20 gated writes) — the only place a count
    # is asserted, so the docs may state it. Adding a tool changes this line on purpose.
    assert (len(READ_CALLS), len(WRITE_KWARGS)) == (12, 20)
    assert len(names) == 32, f"the registry must expose 12 reads + 20 gated writes, got {len(names)}"
    assert names == set(READ_CALLS) | set(WRITE_KWARGS), (
        f"tool registry drifted: unexpected={names - set(READ_CALLS) - set(WRITE_KWARGS)}, "
        f"missing={set(READ_CALLS) | set(WRITE_KWARGS) - names}")
    gated = {t.name for t in tools if getattr(t.fn, "__li_write__", False)}
    assert gated == set(WRITE_KWARGS), (
        f"ungated write tools: {set(WRITE_KWARGS) - gated}; "
        f"reads wrongly gated: {gated - set(WRITE_KWARGS)}")
    for name in READ_CALLS:
        assert not getattr(getattr(server, name), "__li_write__", False), \
            f"{name} is a read and must NOT carry the write gate"
