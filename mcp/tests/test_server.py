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
            "session_status", "refresh_session", "like", "unlike", "follow_company",
            "connect", "endorse_skill", "remove_connection",
            "save_post", "repost", "delete_repost",
            "create_post", "delete_post", "edit_post", "create_poll",
            "send_dm", "recall_message", "react_to_message"}


def test_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert EXPECTED <= names, f"missing tools: {EXPECTED - names}"


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
    # LinkedInClient must be lazy: importing the server starts no browser.
    assert server.li._browser is None


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
    print(f"=== {passed}/{len(tests)} passed ===")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
