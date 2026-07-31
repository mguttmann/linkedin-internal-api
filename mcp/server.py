"""server.py — FastMCP app exposing the LinkedIn internal API as MCP tools.

Run:  python server.py           (stdio, for Claude Desktop / Cursor / Hermes)
      python server.py --http    (HTTP transport, for remote/shared use)

Tools are thin wrappers over LinkedInClient — a PURE requests-based API client. No browser,
no clicking. Reads and writes are wired, each backed by a live-captured request body.
People-facing and destructive tools require confirm=True (guardrail, see docs/MCP-DESIGN.md §5).
Setting LINKEDIN_READ_ONLY blocks every writing tool outright (read-only mode, see below).

Nothing connects at import time. Session login/refresh is handled OUTSIDE the MCP by
session_daemon.py, which keeps /tmp/li_cookies.json fresh.
"""

from __future__ import annotations

import functools
import inspect
import os
import sys

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from lib.client import LinkedInClient

mcp = FastMCP("linkedin 🔗")
li = LinkedInClient()

# Upload guardrail (docs/MCP-DESIGN.md §5), OUR OWN choice — NOT a measured LinkedIn limit:
# nothing above this size has been uploaded from here, so we refuse instead of guessing. It
# bounds create_post_with_image, which reads the whole file into memory before the PUT.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


# ── Read-only mode (operational guardrail, see docs/MCP-DESIGN.md §5) ────
# LINKEDIN_READ_ONLY only ever switches writes OFF — it never grants anything. Off means:
# unset, empty, "0" or "false" (case-insensitive). ANY other value means ON; an unrecognised
# value warns on stderr and still counts as ON, so a typo (=ja/yes/on/2) can never hand out
# write access by accident.
_READ_ONLY_OFF = {"0", "false"}
_READ_ONLY_ON = {"1", "true", "yes", "on"}
_read_only_warned: set[str] = set()


def read_only_enabled() -> bool:
    """True while LINKEDIN_READ_ONLY blocks the writing tools. Read from os.environ on EVERY
    call — never cached at import time, so a long-lived server and tests can change the mode.

    HONEST LIMIT: read-only is an operating mode of THIS MCP SERVER, not a library guarantee.
    It gates the @mcp.tool functions in this file. Code that imports LinkedInClient directly
    (mcp/tests, tools/*.py) bypasses it — that path is not protected by this flag.
    """
    raw = (os.environ.get("LINKEDIN_READ_ONLY") or "").strip()
    if not raw or raw.lower() in _READ_ONLY_OFF:
        return False
    if raw.lower() not in _READ_ONLY_ON and raw not in _read_only_warned:
        _read_only_warned.add(raw)
        print(f"[linkedin-mcp] LINKEDIN_READ_ONLY={raw!r} is not a recognised value — treating "
              "it as ON (all writing tools blocked).", file=sys.stderr)
    return True


def write_tool(fn=None, *, network_free_param: str | None = None):
    """Mark a tool as WRITING and hard-block it while read-only mode is on.

    Blocking raises ToolError — loudly. It must never return {"ok": False, ...} (that is what a
    failed real call looks like, mcp/lib/client.py:344-350, and a caller would retry) and never
    {"ok": True, ...} (a gate that fakes success is worse than no gate).

    network_free_param names a parameter of THIS tool that selects a path explicitly audited as
    network-free (an opt-in whitelist — the gate never trusts a parameter *name* on its own).
    When it is truthy the call is allowed under read-only and its result carries read_only=True,
    so a caller cannot mistake it for "a later dry_run=False would work too".
    """
    def deco(f):
        sig = inspect.signature(f)

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if read_only_enabled():
                if network_free_param is not None:
                    bound = sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    if bound.arguments.get(network_free_param):
                        out = f(*args, **kwargs)
                        if isinstance(out, dict):
                            out["read_only"] = True
                        return out
                raise ToolError(
                    f"{f.__name__} is blocked: this MCP server runs in READ-ONLY mode because "
                    "LINKEDIN_READ_ONLY is set. This is intentional (agent/cron safety), not a "
                    "transient failure — do not retry. Unset LINKEDIN_READ_ONLY (or set it to 0) "
                    "to allow writing tools again.")
            return f(*args, **kwargs)

        wrapper.__li_write__ = True
        return wrapper

    return deco if fn is None else deco(fn)


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
@write_tool
def create_comment(activity_urn: str, text: str, confirm: bool = False) -> dict:
    """Post a top-level comment on a post (activity_urn = urn:li:activity:<id>, or a bare id).
    People-facing → requires confirm=True. Returns status + the new comment URN when resolvable.
    Pure API (SDUI createComment, verified browserless 200). No browser."""
    if not confirm:
        return {"needs_confirmation": True, "activity_urn": activity_urn, "preview": text}
    li.ensure_session()
    return li.create_comment(activity_urn, text)


@mcp.tool
@write_tool(network_free_param="dry_run")
def delete_comment(comment_id: str, activity_urn: str, confirm: bool = False,
                   dry_run: bool = False, force: bool = False) -> dict:
    """Delete a comment. comment_id = the numeric comment id; activity_urn = the post it's on
    (urn:li:activity:<id>). Destructive → requires confirm=True.

    SAFETY GUARD: by default only the OWNER's own comments can be deleted. Deleting someone
    else's comment (e.g. a reply on your post) is refused unless force=True — this prevents
    accidentally removing a real person's comment during testing.

    Pure API: browserless Voyager REST DELETE (verified 204). dry_run=True builds+returns the
    request without sending. No browser fallback."""
    if dry_run:
        return li.delete_comment(comment_id, activity_urn, dry_run=True)
    if not confirm:
        return {"needs_confirmation": True, "comment_id": comment_id, "activity_urn": activity_urn}
    li.ensure_session()
    return li.delete_comment(comment_id, activity_urn, force=force)


@mcp.tool
def get_link_preview(url: str) -> dict:
    """Fetch LinkedIn's rich link-preview metadata (title/image/desc) for a URL, as the composer
    shows it when you paste a link. Browserless read."""
    li.ensure_session()
    return li.get_link_preview(url)


@mcp.tool
def get_job(job_id: str, description_chars: int = 4000) -> dict:
    """Read ONE job posting as a flat projection (title, company, location, employment_status,
    remote_allowed, listed_at, applies, views, salary, reposted, description_text). Browserless.

    job_id accepts a numeric id, a urn:li:fsd_jobPosting:<id> URN or a full
    linkedin.com/jobs/view/… URL. Unusable input returns an error WITHOUT any call.

    The result is IDENTITY-CHECKED: if the response describes a different job than the requested
    one — or names two job ids that disagree — ok=False and NO url is returned. The url is always
    built from the id you asked for, never from an id found in the response. A response that
    identifies the job but yields no readable field is also ok=False ("could not read" is not "a
    job without details"). Unknown values are null, never false; `salary_present` tells "salary
    exists but is not readable" apart from "no salary"."""
    li.ensure_session()
    return li.get_job(job_id, description_chars)


@mcp.tool
def get_job_recommendations(count: int = 20, pagination_token: str = "") -> dict:
    """Return LinkedIn's own job recommendations for the owner (the jobs feed) as flat cards.
    Browserless read. `count` = how many to fetch; pass the returned pagination_token for the
    next page.

    `state` distinguishes an ANSWER from a failure: "hits"/"empty" means the result list was
    really read (ok=True), "unknown"/"drift"/"ambiguous" mean it could NOT be read (ok=False, with
    the re-capture hint) — an empty list is never reported as "no jobs" unless it was read as
    empty. `read_entries` and `discarded` balance `count` against the raw list that was read: on a
    partial loss ok stays True but `note` names how many entries were dropped."""
    li.ensure_session()
    return li.get_job_recommendations(count, pagination_token)


@mcp.tool
def session_status() -> dict:
    """Check whether the LinkedIn session is live (a /me probe). Pure API, no browser.

    read_only mirrors LINKEDIN_READ_ONLY: when true, every writing tool is blocked (it raises) —
    check this instead of probing the mode with a write.

    session_suspect answers the one question worth asking: does THIS failure mean re-login?
    It is True only for the single evidenced case, a redirect to the login page. A missing
    cookie file (error_code=session_file_missing) is a SETUP problem, and a 403
    (error_code=csrf_missing) is a header problem — neither is a dead session, so neither sets
    the flag. Follow `hint`, not the status code.

    logged_in is the classification itself (`ok`), not a second rule about the status code: a
    2xx that carries no readable JSON body is a failed probe, so it reports logged_in=false WITH
    an error_code — never a healthy session with no signal. Whenever error_code is set, hint is
    set too.

    Never prints cookie values, and never a response body or an excerpt of one — only the
    status, the endpoint name, the body length and the classification."""
    diag = li.probe_session()
    # error_code/hint hang on the CLASSIFICATION, not on logged_in. Masking them behind
    # logged_in would discard the classification exactly when it contradicts the success
    # statement — a failed probe would surface as a healthy session with no signal at all.
    failed = diag["code"] != "ok"
    return {"logged_in": diag["logged_in"],
            "read_only": read_only_enabled(),
            "session_suspect": diag["session_suspect"],
            "error_code": diag["code"] if failed else None,
            "retryable": diag["retryable"],
            "hint": diag["remediation"] if failed else None}


@mcp.tool
def refresh_session() -> dict:
    """Re-check the session against the current cookie file (does NOT launch a browser).

    Login/refresh is handled OUTSIDE the MCP by session_daemon.py, which keeps the cookie file
    fresh. This tool just re-probes /me; if it's still logged_in=false, follow `hint` — it names
    the classified cause instead of blaming the cookies for every failure. Same keys as before;
    call session_status() for the full classification including session_suspect."""
    diag = li.probe_session()
    # The hint is the CLASSIFICATION, not a fixed sentence: "cookies still stale" for a timeout
    # or a missing cookie file is the same misattribution session_status() exists to stop.
    return {"logged_in": diag["logged_in"],
            "hint": None if diag["code"] == "ok" else diag["remediation"]}


# ── Engagement writes (verified endpoints, live-captured bodies) ─────────
@mcp.tool
@write_tool
def like(activity_urn: str, confirm: bool = False) -> dict:
    """Like a post by its activity URN (e.g. urn:li:activity:123…). Verified endpoint.
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "activity_urn": activity_urn}
    li.ensure_session()
    return li.like(activity_urn)


@mcp.tool
@write_tool
def unlike(activity_urn: str, confirm: bool = False) -> dict:
    """Remove your LIKE reaction from a post by its activity URN. Verified endpoint.
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "activity_urn": activity_urn, "action": "unlike"}
    li.ensure_session()
    return li.unlike(activity_urn)


@mcp.tool
@write_tool
def follow_company(company_id: str, follow: bool = True, confirm: bool = False) -> dict:
    """Follow (follow=True) or unfollow (follow=False) a company by its numeric id.
    Browserless, verified endpoint. People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "company_id": company_id, "follow": follow}
    li.ensure_session()
    return li.follow_company(company_id, follow)


@mcp.tool
@write_tool
def connect(member_urn: str, note: str = "", confirm: bool = False) -> dict:
    """Send a connection invite (optionally with a note) to a person by profile URN.
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "member_urn": member_urn, "note": note}
    li.ensure_session()
    return li.connect(member_urn, note)


@mcp.tool
@write_tool
def endorse_skill(vanity_name: str, profile_id: str, skill_id: str,
                  confirm: bool = False) -> dict:
    """Endorse a skill on someone's profile. vanity_name+profile_id identify the person,
    skill_id is the skill's position id. Browserless, verified.
    Writes on a FOREIGN profile → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "vanity_name": vanity_name, "skill_id": skill_id}
    li.ensure_session()
    return li.endorse_skill(vanity_name, profile_id, skill_id)


@mcp.tool
@write_tool
def remove_connection(vanity_name: str, first_name: str = "", last_name: str = "",
                      confirm: bool = False) -> dict:
    """Remove a first-degree connection by vanity name. Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "vanity_name": vanity_name}
    li.ensure_session()
    return li.remove_connection(vanity_name, first_name, last_name)


@mcp.tool
@write_tool
def save_post(activity_id: str, save: bool = True, confirm: bool = False) -> dict:
    """Save (save=True) or unsave (save=False) a post for later, by its numeric activity id.
    Browserless, verified. Requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "activity_id": activity_id, "save": save}
    li.ensure_session()
    return li.save_post(activity_id, save)


@mcp.tool
@write_tool
def repost(activity_id: str, confirm: bool = False) -> dict:
    """Instant-repost a post to the owner's feed. People-facing → requires confirm=True.
    Pure API (SDUI createInstantRepost). If it 500s, re-capture the full body as a template."""
    if not confirm:
        return {"needs_confirmation": True, "activity_id": activity_id}
    li.ensure_session()
    return li.repost(activity_id)


@mcp.tool
@write_tool
def delete_repost(repost_urn: str, confirm: bool = False) -> dict:
    """Delete one of the owner's reposts by its repost URN. Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "repost_urn": repost_urn}
    li.ensure_session()
    return li.delete_repost(repost_urn)


@mcp.tool
@write_tool
def create_post(text: str, visibility: str = "PUBLIC", poll_urn: str = "",
                confirm: bool = False) -> dict:
    """Publish a post on the owner's LinkedIn. Optionally attach a poll via poll_urn (from
    create_poll). People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "preview": text, "visibility": visibility}
    li.ensure_session()
    return li.create_post(text, visibility, poll_urn)


@mcp.tool
@write_tool
def create_post_with_image(text: str, image_path: str, visibility: str = "PUBLIC",
                           confirm: bool = False) -> dict:
    """Publish a post with an image (browserless single-part upload, verified live by the owner
    on 2026-07-18: asset URN D4E22AQGKhtES62GYIw, the post went live).
    image_path: local path to a PNG/JPEG/GIF/WEBP file; larger than MAX_IMAGE_BYTES or not an
    image by its own first bytes → refused without any outgoing call.
    People-facing → requires confirm=True."""
    probe = li.inspect_image(image_path)  # local stat + 12 bytes, no outgoing call, never raises
    if not confirm:
        # The confirmation names the FILE NAME, its measured TYPE and SIZE — never a directory:
        # the payload lands in the MCP transcript, and the caller has to be able to judge WHAT
        # would become a public post. A path adds nothing to that judgement.
        return {"needs_confirmation": True, "preview": text, "image_name": probe["name"],
                "image_kind": probe["kind"], "image_bytes": probe["size"],
                "image_status": probe["status"], "visibility": visibility}
    # Guardrail (docs/MCP-DESIGN.md §5): the REFUSAL lives here, the byte access in the client.
    if not probe["ok"]:
        return {"ok": False, "step": "read", "status": probe["status"], "error": probe["error"]}
    if probe["size"] > MAX_IMAGE_BYTES:
        return {"ok": False, "step": "read", "status": "image_too_large",
                "error": f"{probe['name']} is {probe['size']} bytes; this MCP refuses to upload "
                         f"more than {MAX_IMAGE_BYTES} bytes"}
    li.ensure_session()
    return li.create_post_with_image(text, image_path, visibility)


@mcp.tool
@write_tool
def edit_post(activity_id: str, share_id: str, text: str, confirm: bool = False) -> dict:
    """Edit an existing post's text. Needs activity_id + share_id (from the post URN / get_my_posts).
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "activity_id": activity_id, "preview": text}
    li.ensure_session()
    return li.edit_post(activity_id, share_id, text)


@mcp.tool
@write_tool
def create_poll(question: str, options: list, duration: str = "ONE_WEEK",
                confirm: bool = False) -> dict:
    """Create a poll (returns its pollSummary URN). options: 2–4 strings; duration:
    ONE_DAY/THREE_DAYS/ONE_WEEK/TWO_WEEKS. Pass the returned poll_urn to create_post to publish.
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "question": question, "options": options,
                "duration": duration}
    li.ensure_session()
    return li.create_poll(question, options, duration)


@mcp.tool
@write_tool
def delete_post(activity_id: str, tracking_id: str, confirm: bool = False) -> dict:
    """Delete one of the owner's posts. Needs the numeric activity_id + the update's tracking_id
    (both from get_my_posts). Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "activity_id": activity_id}
    li.ensure_session()
    return li.delete_post(activity_id, tracking_id)


@mcp.tool
@write_tool
def send_dm(conversation_urn: str, text: str, confirm: bool = False) -> dict:
    """Send a direct message in an existing conversation. People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "conversation": conversation_urn, "preview": text}
    li.ensure_session()
    return li.send_dm(conversation_urn, text)


@mcp.tool
@write_tool
def recall_message(message_urn: str, confirm: bool = False) -> dict:
    """Delete (recall) a message you sent, for everyone. Destructive → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "message_urn": message_urn}
    li.ensure_session()
    return li.recall_message(message_urn)


@mcp.tool
@write_tool
def react_to_message(message_urn: str, emoji: str = "👏", confirm: bool = False) -> dict:
    """React to a message with an emoji (toggle: re-send the same emoji to remove it).
    People-facing → requires confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "message_urn": message_urn, "emoji": emoji,
                "toggle": True}
    li.ensure_session()
    return li.react_to_message(message_urn, emoji)


@mcp.tool
@write_tool
def react_to_comment(comment_id: str, activity_urn: str, confirm: bool = False) -> dict:
    """Like a comment — browserless (SDUI reactions.create). comment_id = the numeric comment id;
    activity_urn = the post the comment is on (urn:li:activity:<id>). People-facing → confirm=True."""
    if not confirm:
        return {"needs_confirmation": True, "comment_id": comment_id, "activity_urn": activity_urn}
    li.ensure_session()
    return li.react_to_comment(comment_id, activity_urn)


def main():
    if "--http" in sys.argv:
        mcp.run(transport="http", port=8765)
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    main()
