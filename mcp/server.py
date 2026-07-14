"""server.py — FastMCP app exposing the LinkedIn internal API as MCP tools.

Run:  python server.py           (stdio, for Claude Desktop / Cursor / Hermes)
      python server.py --http    (HTTP transport, for remote/shared use)

Tools are thin wrappers over LinkedInClient (requests-first, patchright browser-fallback).
Reads and writes are wired, each backed by a live-captured request body. People-facing and
destructive tools require confirm=True (guardrail, see docs/MCP-DESIGN.md §5).

Nothing connects at import time — the browser/session is lazy.
"""

from __future__ import annotations

import sys

from fastmcp import FastMCP

from lib.client import LinkedInClient

mcp = FastMCP("linkedin 🔗")
li = LinkedInClient()


# ── Reads (browserless, wired) ───────────────────────────────────────────
@mcp.tool
def get_me() -> dict:
    """Return the owner's core LinkedIn profile (name, headline, plainId, profile URN)."""
    li.ensure_session()
    return li.get_me()


@mcp.tool
def get_my_posts(count: int = 10) -> dict:
    """Return the owner's most recent posts (full text) via voyagerFeedDashProfileUpdates —
    the endpoint the official/Composio API cannot access. `count` = how many to fetch."""
    li.ensure_session()
    return li.get_my_posts(count)


@mcp.tool
def get_conversations() -> dict:
    """List the owner's messaging conversations (inbox)."""
    li.ensure_session()
    return li.get_conversations()


@mcp.tool
def get_profile(vanity_name: str = "") -> dict:
    """Read a full profile by its vanityName (the public /in/<name> identifier).
    Defaults to the owner. Returns experience, education, skills, etc."""
    li.ensure_session()
    return li.get_profile(vanity_name)


@mcp.tool
def get_notifications(count: int = 10) -> dict:
    """Return the owner's recent notifications (reactions, comments, mentions, invites)."""
    li.ensure_session()
    return li.get_notifications(count)


@mcp.tool
def get_connections_summary() -> dict:
    """Return the owner's connection + pending-invitation counts."""
    li.ensure_session()
    return li.get_connections_summary()


@mcp.tool
def get_post_comments(activity_urn: str) -> dict:
    """Read the comments on a post by its activity URN (urn:li:activity:<id>). Browserless."""
    li.ensure_session()
    return li.get_post_comments(activity_urn)


@mcp.tool
def create_comment(activity_urn: str, text: str, confirm: bool = False) -> dict:
    """Post a top-level comment on a post (activity_urn = urn:li:activity:<id>, or a bare id).
    People-facing → requires confirm=True. Returns status + the new comment URN when resolvable.
    Note: SDUI action; if it 500s it needs the browser currentActor binding (see docs/07)."""
    if not confirm:
        return {"needs_confirmation": True, "activity_urn": activity_urn, "preview": text}
    li.ensure_session()
    return li.create_comment(activity_urn, text)


@mcp.tool
def delete_comment(comment_id: str, activity_urn: str, confirm: bool = False,
                   comment_text: str = "", dry_run: bool = False) -> dict:
    """Delete a comment. comment_id = the numeric comment id; activity_urn = the post it's on
    (urn:li:activity:<id>). Destructive → requires confirm=True.

    Primary path is the browserless Voyager REST DELETE (verified 204). If it fails and
    comment_text (the comment's visible text) is supplied, falls back to the browser UI, which
    locates the comment by that text. dry_run=True builds+returns the request without sending."""
    if dry_run:
        return li.delete_comment(comment_id, activity_urn, dry_run=True, comment_text=comment_text)
    if not confirm:
        return {"needs_confirmation": True, "comment_id": comment_id, "activity_urn": activity_urn}
    li.ensure_session()
    return li.delete_comment(comment_id, activity_urn, comment_text=comment_text)


@mcp.tool
def get_link_preview(url: str) -> dict:
    """Fetch LinkedIn's rich link-preview metadata (title/image/desc) for a URL, as the composer
    shows it when you paste a link. Browserless read."""
    li.ensure_session()
    return li.get_link_preview(url)


@mcp.tool
def session_status() -> dict:
    """Check whether the LinkedIn session is live (does NOT launch the browser)."""
    ok = li.ensure_session(allow_browser=False)
    return {"logged_in": ok,
            "hint": None if ok else "run refresh_session to log in via the browser"}


@mcp.tool
def refresh_session() -> dict:
    """Refresh LinkedIn cookies from the persistent patchright browser (launches Chrome;
    on first run, log in once in the window). Use when session_status reports logged_in=false."""
    ok = li.ensure_session(allow_browser=True)
    return {"logged_in": ok}


# ── Engagement writes (verified endpoints, live-captured bodies) ─────────
@mcp.tool
def like(activity_urn: str) -> dict:
    """Like a post by its activity URN (e.g. urn:li:activity:123…). Verified endpoint."""
    li.ensure_session()
    return li.like(activity_urn)


@mcp.tool
def unlike(activity_urn: str) -> dict:
    """Remove your LIKE reaction from a post by its activity URN. Verified endpoint."""
    li.ensure_session()
    return li.unlike(activity_urn)


@mcp.tool
def follow_company(company_id: str, follow: bool = True) -> dict:
    """Follow (follow=True) or unfollow (follow=False) a company by its numeric id.
    Browserless, verified endpoint."""
    li.ensure_session()
    return li.follow_company(company_id, follow)


@mcp.tool
def connect(member_urn: str, note: str = "", confirm: bool = False) -> dict:
    """Send a connection invite (optionally with a note) to a person by profile URN.
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "member_urn": member_urn, "note": note}
    li.ensure_session()
    return li.connect(member_urn, note)


@mcp.tool
def endorse_skill(vanity_name: str, profile_id: str, skill_id: str) -> dict:
    """Endorse a skill on someone's profile. vanity_name+profile_id identify the person,
    skill_id is the skill's position id. Browserless, verified."""
    li.ensure_session()
    return li.endorse_skill(vanity_name, profile_id, skill_id)


@mcp.tool
def remove_connection(vanity_name: str, first_name: str = "", last_name: str = "",
                      confirm: bool = False) -> dict:
    """Remove a first-degree connection by vanity name. Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "vanity_name": vanity_name}
    li.ensure_session()
    return li.remove_connection(vanity_name, first_name, last_name)


@mcp.tool
def save_post(activity_id: str, save: bool = True) -> dict:
    """Save (save=True) or unsave (save=False) a post for later, by its numeric activity id.
    Browserless, verified."""
    li.ensure_session()
    return li.save_post(activity_id, save)


@mcp.tool
def repost(activity_id: str, confirm: bool = False) -> dict:
    """Instant-repost a post to the owner's feed. People-facing → requires confirm=True.
    (Browserless returns 500; reliable via the browser path.)"""
    if not confirm:
        return {"needs_confirmation": True, "activity_id": activity_id}
    li.ensure_session()
    return li.repost(activity_id)


@mcp.tool
def delete_repost(repost_urn: str, confirm: bool = False) -> dict:
    """Delete one of the owner's reposts by its repost URN. Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "repost_urn": repost_urn}
    li.ensure_session()
    return li.delete_repost(repost_urn)


@mcp.tool
def create_post(text: str, visibility: str = "PUBLIC", poll_urn: str = "",
                confirm: bool = False) -> dict:
    """Publish a post on the owner's LinkedIn. Optionally attach a poll via poll_urn (from
    create_poll). People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "preview": text, "visibility": visibility}
    li.ensure_session()
    return li.create_post(text, visibility, poll_urn)


@mcp.tool
def edit_post(activity_id: str, share_id: str, text: str, confirm: bool = False) -> dict:
    """Edit an existing post's text. Needs activity_id + share_id (from the post URN / get_my_posts).
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "activity_id": activity_id, "preview": text}
    li.ensure_session()
    return li.edit_post(activity_id, share_id, text)


@mcp.tool
def create_poll(question: str, options: list, duration: str = "ONE_WEEK") -> dict:
    """Create a poll (returns its pollSummary URN). options: 2–4 strings; duration:
    ONE_DAY/THREE_DAYS/ONE_WEEK/TWO_WEEKS. Pass the returned poll_urn to create_post to publish."""
    li.ensure_session()
    return li.create_poll(question, options, duration)


@mcp.tool
def delete_post(activity_id: str, tracking_id: str, confirm: bool = False) -> dict:
    """Delete one of the owner's posts. Needs the numeric activity_id + the update's tracking_id
    (both from get_my_posts). Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "activity_id": activity_id}
    li.ensure_session()
    return li.delete_post(activity_id, tracking_id)


@mcp.tool
def send_dm(conversation_urn: str, text: str, confirm: bool = False) -> dict:
    """Send a direct message in an existing conversation. People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "conversation": conversation_urn, "preview": text}
    li.ensure_session()
    return li.send_dm(conversation_urn, text)


@mcp.tool
def recall_message(message_urn: str, confirm: bool = False) -> dict:
    """Delete (recall) a message you sent, for everyone. Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "message_urn": message_urn}
    li.ensure_session()
    return li.recall_message(message_urn)


@mcp.tool
def react_to_message(message_urn: str, emoji: str = "👏") -> dict:
    """React to a message with an emoji (toggle: re-send the same emoji to remove it)."""
    li.ensure_session()
    return li.react_to_message(message_urn, emoji)


def main():
    if "--http" in sys.argv:
        mcp.run(transport="http", port=8765)
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    main()
