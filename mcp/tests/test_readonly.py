"""test_readonly.py — offline proof for LINKEDIN_READ_ONLY (read-only mode of the MCP server).

Every test here ENFORCES the constraint instead of assuming it: the transport is replaced
(fake vgreq module + lib.client.requests) and every test asserts ZERO outgoing calls, so a
write that slipped through the gate would be visible, not silent. No network, no cookie file,
no browser.

The gate is proven on BOTH paths: the module-level function (what a direct import sees) and
`mcp.call_tool` — the MCP boundary an agent actually goes through. They are the same object
today, but that is a consequence of decorator order, not a guarantee.

Run:  .venv/bin/python -m pytest mcp/tests/test_readonly.py -q
"""
import asyncio
import os
import sys
import types

import pytest
from fastmcp.exceptions import ToolError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import server  # noqa: E402

_URN = "urn:li:activity:1111111111111111111"

# The 10 reading tools — ALL allowed under read-only (server.py:99-148, :186-215).
READ_CALLS = {
    "get_me": lambda: server.get_me(),
    "get_my_posts": lambda: server.get_my_posts(1),
    "get_conversations": lambda: server.get_conversations(),
    "get_profile": lambda: server.get_profile(""),
    "get_notifications": lambda: server.get_notifications(1),
    "get_connections_summary": lambda: server.get_connections_summary(),
    "get_post_comments": lambda: server.get_post_comments(_URN),
    "get_link_preview": lambda: server.get_link_preview("https://example.com/x"),
    "session_status": lambda: server.session_status(),
    "refresh_session": lambda: server.refresh_session(),
}

# The 19 writing tools — ALL blocked under read-only. confirm=True is passed wherever the tool
# has a confirm gate, otherwise the test would only re-test the confirm gate (proof worthless).
# Kwargs, not lambdas: the SAME argument set is replayed through the module-level function and
# through mcp.call_tool, so neither path can drift away from the other untested.
WRITE_KWARGS = {
    "create_comment": {"activity_urn": _URN, "text": "text", "confirm": True},
    "delete_comment": {"comment_id": "222", "activity_urn": _URN, "confirm": True},
    "like": {"activity_urn": _URN},
    "unlike": {"activity_urn": _URN},
    "follow_company": {"company_id": "1035"},
    "connect": {"member_urn": "urn:li:fsd_profile:X", "confirm": True},
    "endorse_skill": {"vanity_name": "other-user", "profile_id": "OTHER_ID", "skill_id": "48"},
    "remove_connection": {"vanity_name": "other-user", "confirm": True},
    "save_post": {"activity_id": "999"},
    "repost": {"activity_id": "999", "confirm": True},
    "delete_repost": {"repost_urn": "urn:li:activity:2", "confirm": True},
    "create_post": {"text": "hello", "confirm": True},
    "edit_post": {"activity_id": "222", "share_id": "333", "text": "new text", "confirm": True},
    "create_poll": {"question": "Q?", "options": ["A", "B"]},
    "delete_post": {"activity_id": "222", "tracking_id": "trk", "confirm": True},
    "send_dm": {"conversation_urn": "urn:li:msg_conversation:(urn:li:fsd_profile:ME,1)",
                "text": "hi", "confirm": True},
    "recall_message": {"message_urn": "urn:li:msg_message:(x,2)", "confirm": True},
    "react_to_message": {"message_urn": "urn:li:msg_message:(x,2)"},
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


@pytest.fixture
def transport(monkeypatch):
    """Replace EVERY outgoing path with a recorder and return the call log.

    Covers both transports the client uses: the vgreq module (mcp/lib/client.py:79-82) and the
    raw requests.post used for SDUI writes (mcp/lib/client.py:22, e.g. :342 area / unlike).
    """
    import lib.client as cl
    calls = {"get": [], "post": [], "delete": [], "requests": []}
    fake = types.ModuleType("vgreq")
    fake.get = lambda url, *a, **k: (calls["get"].append(url) or _Resp())
    fake.post = lambda url, body=None, *a, **k: (calls["post"].append((url, body)) or _Resp())
    fake.delete = lambda url, *a, **k: (calls["delete"].append(url) or _Resp())
    monkeypatch.setattr(cl, "vgreq", fake)
    monkeypatch.setattr(cl, "_HAVE_VGREQ", True)
    for verb in ("get", "post", "delete", "request"):
        monkeypatch.setattr(cl.requests, verb,
                            lambda url, *a, **k: (calls["requests"].append(url) or _Resp()))
    # patch the class of the LIVE client instance: other tests reload lib.client, which rebinds
    # cl.LinkedInClient to a NEW class object while server.li still holds the original one.
    for klass in {cl.LinkedInClient, type(server.li)}:
        monkeypatch.setattr(klass, "_sdui_min_headers",
                            staticmethod(lambda: {"csrf-token": "ajax:x", "Cookie": "k=v"}))
    return calls


def _sent(calls) -> list:
    return calls["get"] + calls["post"] + calls["delete"] + calls["requests"]


def _mutating(calls) -> list:
    """Only the verbs that change something at LinkedIn. A GET is NOT proof of a write: every
    write tool first calls li.ensure_session() → a GET on /me (mcp/lib/client.py:74)."""
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


# Write tools that are gated like every other write but deliberately send NO MUTATING call:
# their request cannot succeed as configured, so the client refuses before the transport
# (client.py delete_repost — the repost-delete queryId hash is in no capture). At THIS (tool)
# level the ensure_session() GET on /me still goes out (mcp/server.py:298); the client method
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
