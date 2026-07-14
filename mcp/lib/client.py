"""client.py — LinkedInClient facade: requests-first, browser-fallback.

The single entry point the MCP tools call. Picks the execution path per operation:
  - read + safe writes  -> pure requests via vgreq (browserless, primary)
  - session refresh / SDUI form deletes -> SessionBrowser (patchright, fallback)

See docs/MCP-DESIGN.md. Read AND write tools are wired: each carries a live-captured request
body (verified endpoint names + schemas from docs/04, 06-25). A few SDUI writes (unlike, repost)
need the browser's currentActor binding and return an honest note on the browserless 500; the
rest run browserless. Nothing here connects on import.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import uuid
from pathlib import Path
from typing import Optional

import requests

# Reuse the proven pure-requests client from the internal-api repo (sibling ../lib).
_REPO_LIB = os.path.join(os.path.dirname(__file__), "..", "..", "lib")
sys.path.insert(0, os.path.abspath(_REPO_LIB))
try:
    import vgreq  # type: ignore
    _HAVE_VGREQ = True
except Exception:  # pragma: no cover
    vgreq = None  # type: ignore
    _HAVE_VGREQ = False

from .session_browser import SessionBrowser, NotLoggedInError  # noqa: E402

BASE = "https://www.linkedin.com/voyager/api"
# Owner identity comes from the environment — no PII hard-coded in the repo.
# Set LI_OWNER_URN (urn:li:fsd_profile:<id>) and LI_OWNER_VANITY (public vanity name)
# before running; the placeholders below are inert and will not resolve to a real profile.
ME = os.environ.get("LI_OWNER_URN", "urn:li:fsd_profile:REPLACE_WITH_YOUR_PROFILE_URN")
VANITY = os.environ.get("LI_OWNER_VANITY", "your-vanity-name")
# queryId hash for post creation — changes on LinkedIn deployments; re-grab via
# tools/capture_write_action.py if create_post starts 404-ing.
SHARES_QID = "voyagerContentcreationDashShares.80089eb2e82a2dfa23cb621fb09eb7bf"
# edit reuses the Shares mutation under a different deploy hash (captured live, docs/24)
SHARES_EDIT_QID = "voyagerContentcreationDashShares.f2afb8a73071c94140f970bdb7e48fb3"
POLL_QID = "voyagerFeedDashPollsPollSummary.f8ad99cf791d833d37dddb373d06fb3a"


class LinkedInClient:
    """Facade over vgreq (requests) + SessionBrowser (patchright).

    lazy: the browser is only started when a session refresh is actually needed, so importing
    and listing tools never launches Chrome.
    """

    def __init__(self, cookies_path: str = "/tmp/li_cookies.json"):
        self.cookies_path = cookies_path
        self._browser: Optional[SessionBrowser] = None

    # --- session ---------------------------------------------------------
    def ensure_session(self, allow_browser: bool = True) -> bool:
        """Make sure vgreq has valid cookies. Returns True if the session is live.

        Tries the existing cookie file first (cheap). Only spins up the patchright browser to
        refresh if needed AND allowed.
        """
        if not _HAVE_VGREQ:
            raise RuntimeError("vgreq not importable — check repo layout")
        if self._session_ok():
            return True
        if not allow_browser:
            return False
        # refresh cookies from the persistent browser session
        self._browser = self._browser or SessionBrowser()
        self._browser.start()
        if not self._browser.is_logged_in():
            raise NotLoggedInError("LinkedIn session expired — log in in the browser window")
        self._browser.dump_cookies(self.cookies_path)
        return self._session_ok()

    def _session_ok(self) -> bool:
        try:
            return self._vg().get(f"{BASE}/me").status_code == 200
        except Exception:
            return False

    @staticmethod
    def _vg():
        """Return the vgreq module, guaranteed non-None (raises if unavailable)."""
        if vgreq is None:
            raise RuntimeError("vgreq not importable — check repo layout")
        return vgreq

    # --- reads (browserless, wired) -------------------------------------
    def get_me(self) -> dict:
        return self._vg().get(f"{BASE}/me").json()

    def get_my_posts(self, count: int = 10) -> dict:
        """Own posts (full text) via voyagerFeedDashProfileUpdates — the thing Composio can't do.
        Exact URL shape captured live (docs/02): includeWebMetadata + ordered variables + queryId hash.
        """
        enc = urllib.parse.quote(ME, safe="")
        url = (f"{BASE}/graphql?includeWebMetadata=true"
               f"&variables=(count:{count},start:0,profileUrn:{enc})"
               f"&queryId=voyagerFeedDashProfileUpdates.20c70fe0314184158516a7ec004c0408")
        return self._vg().get(url).json()

    # messengerConversations queryId hash rotates on LinkedIn deployments; re-grab via capture
    # if get_conversations starts 404-ing.
    _CONV_QID = "messengerConversations.0d5e6781bbee71c3e51c8843c6519f48"

    def get_conversations(self) -> dict:
        """Inbox conversations via GraphQL messengerConversations (docs/06/23).
        The bare REST endpoint 400s; the working call is GraphQL with mailboxUrn.
        Returns {"ok": False, "note": ...} if the queryId hash has rotated (404).
        """
        enc = urllib.parse.quote(ME, safe="")
        # messaging has its OWN graphql path (voyagerMessagingGraphQL), not the generic /graphql
        url = f"{BASE}/voyagerMessagingGraphQL/graphql?queryId={self._CONV_QID}&variables=(mailboxUrn:{enc})"
        r = self._vg().get(url)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "status": r.status_code,
                    "note": "messengerConversations queryId hash rotated — re-capture the current "
                            "hash (docs/23) and update _CONV_QID"}

    def get_profile(self, vanity_name: str = "") -> dict:
        """Read any profile by its vanityName (the public /in/<name> identifier).
        Empty vanity_name falls back to the owner (VANITY from the environment).
        Uses the identity dash profiles endpoint (verified read, docs/02/23).
        """
        vanity = urllib.parse.quote(vanity_name or VANITY, safe="")
        url = (f"{BASE}/identity/dash/profiles?q=memberIdentity"
               f"&memberIdentity={vanity}"
               f"&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-96")
        return self._vg().get(url).json()

    def get_notifications(self, count: int = 10) -> dict:
        """Own notifications feed (verified REST read, docs/23).
        Needs q=filterVanityName + decorationId (a bare call returns 400).
        """
        url = (f"{BASE}/voyagerIdentityDashNotificationCards?q=filterVanityName"
               f"&count={count}"
               f"&decorationId=com.linkedin.voyager.dash.deco.identity.notifications."
               f"CardsCollectionWithInjectionsNoPills-24")
        return self._vg().get(url).json()

    def get_connections_summary(self) -> dict:
        """Connection + invitation counts (verified REST read, docs/23)."""
        return self._vg().get(f"{BASE}/relationships/connectionsSummary").json()

    def get_post_comments(self, activity_urn: str) -> dict:
        """Read the comments on a post (verified Voyager read, docs/04).
        activity_urn: urn:li:activity:<id>.
        """
        enc = urllib.parse.quote(activity_urn, safe="")
        url = f"{BASE}/feed/comments?q=comments&updateId={enc}"
        return self._vg().get(url).json()

    # --- comment creation: SDUI createComment, browserless (VERIFIED 2026-07-14) ------
    # The web SDUI createComment request IS replayable with pure requests. The earlier
    # "needs a browser" claim was WRONG: the comment text is NOT only a MemoryNamespace
    # *ref* — the same request also carries the text as a real literal under
    # requestedStateValues (…"value":{"text":"<TEXT>"}…). And the state-key token
    # (commentBoxText-<TOKEN>) is NOT render-bound: it is a self-mintable protobuf of
    # {timestamp varint + 16 random bytes} — exactly like the send_dm trackingId.
    # Proven live: verbatim replay → 200 + comment appeared; freshly-minted token + new
    # text → 200 + comment appeared. So we template the captured body and swap 5 fields.
    _SDUI_COMMENT_URL = ("https://www.linkedin.com/flagship-web/rsc-action/actions/"
                         "server-request?sduiid=com.linkedin.sdui.comments.createComment")

    @staticmethod
    def _mint_comment_token() -> str:
        """Mint a commentBoxText state-key token: protobuf {field1:{field1:now_ms}, field2:16 rand}.
        Reverse-engineered from two live captures (both decoded to a ts varint + a 16-byte id).
        base64url without padding, matching the wire form LinkedIn emits.
        """
        import base64 as _b64, secrets as _sec, time as _t

        def _varint(n: int) -> bytes:
            out = b""
            while True:
                b = n & 0x7F
                n >>= 7
                out += bytes([b | (0x80 if n else 0)])
                if not n:
                    return out
        now_ms = int(_t.time() * 1000)
        inner = b"\x08" + _varint(now_ms)                 # field1 (varint) = timestamp
        ts_field = b"\x0a" + bytes([len(inner)]) + inner   # field1 (len-delim) = inner msg
        tok = ts_field + b"\x12\x10" + _sec.token_bytes(16)  # field2 (len-delim, 16) = trackingId
        return _b64.urlsafe_b64encode(tok).decode().rstrip("=")

    def create_comment_browserless(self, activity_urn: str, text: str,
                                   dry_run: bool = False,
                                   body_form: str = "sdui") -> dict:
        """Post a top-level comment via the SDUI createComment route — NO browser.

        VERIFIED browserless 2026-07-14 (see the note above). Loads the captured request
        body template (lib/templates/create_comment_sdui.json.tpl) and substitutes 5 fields:
        ACTIVITY_ID, TEXT (json-escaped), a freshly-minted TOKEN, a random TRACKING_ID and
        OPTIMISTIC_KEY. Posts the raw string with vgreq (csrf + cookies auto-applied).

        The read model returns each comment as `com.linkedin.voyager.feed.Comment` with the
        text under `commentV2.text`. The SDUI createComment write carries the text as a real
        literal too (verified live browserless), so no browser is needed.

        Args:
            activity_urn: urn:li:activity:<id> (or a bare numeric id).
            text: the comment text (a plain literal — json-escaped into the body).
            dry_run: if True, BUILD and return {url, body_sent, ...} WITHOUT sending, so the
                     caller can inspect the exact request before any live write.
            body_form: 'sdui' (the verified createComment route). Kept for signature stability.

        Returns: {status, ok, comment_urn?, via:'sdui-browserless', url, body_sent[, note]}.
        """
        import json as _json
        import os as _os
        import re as _re
        import uuid as _uuid

        activity_id = activity_urn.rsplit(":", 1)[-1] if ":" in activity_urn else activity_urn
        url = self._SDUI_COMMENT_URL

        # Load the captured request-body template (5 placeholders) and fill it.
        tpl_path = _os.path.join(_os.path.dirname(__file__),
                                 "templates", "create_comment_sdui.json.tpl")
        with open(tpl_path, "r", encoding="utf-8") as fh:
            tpl = fh.read()
        token = self._mint_comment_token()
        # 16-byte base64 trackingId (LinkedIn wire form, e.g. "ZRBhCzd8QiyaxRVu4Oh4iw==")
        import base64 as _b64
        import secrets as _sec
        tracking_id = _b64.b64encode(_sec.token_bytes(16)).decode()
        optimistic_key = "auto-component-" + str(_uuid.uuid4())
        # json.dumps then strip the surrounding quotes → a properly escaped JSON string body-safe.
        text_escaped = _json.dumps(text)[1:-1]
        body = (tpl.replace("{{TOKEN}}", token)
                   .replace("{{ACTIVITY_ID}}", activity_id)
                   .replace("{{TRACKING_ID}}", tracking_id)
                   .replace("{{OPTIMISTIC_KEY}}", optimistic_key)
                   .replace("{{TEXT}}", text_escaped))

        if dry_run:
            return {"status": "dry_run", "ok": None, "via": "sdui-browserless",
                    "url": url, "body_sent": body,
                    "note": "dry_run — request built but NOT sent; inspect body_sent then "
                            "re-run with dry_run=False to post live"}
        # raw string body (already JSON) — is_json=False so vgreq doesn't re-encode it
        r = self._vg().post(url, body, is_json=False)
        ok = r.status_code in (200, 201)
        out = {"status": r.status_code, "ok": ok, "via": "sdui-browserless",
               "url": url, "activity_id": activity_id}
        # the created comment URN comes back in the response body
        try:
            m = (_re.search(r"urn:li:comment:\([^)]*\)", r.text) or
                 _re.search(r"urn:li:fsd_comment:\([^)]*\)", r.text) or
                 _re.search(r"urn:li:fs_objectComment:\([^)]*\)", r.text))
            if m:
                out["comment_urn"] = m.group(0)
        except Exception:
            pass
        if not ok:
            out["note"] = ("sdui createComment returned non-2xx — token/template may have "
                           "rotated (re-capture with tools/capture); create_comment() falls "
                           "back to the browser")
        return out

    def create_comment(self, activity_urn: str, text: str) -> dict:
        """Post a top-level comment. Tries the BROWSERLESS Voyager-REST route first, then falls
        back to driving the real UI (browser) only if that fails.

        Primary path (no Chrome): create_comment_browserless() → classic Voyager `feed/comments`
        collection with the text as a real literal in the body (`commentV2.text`).

        Fallback: the web SDUI createComment action binds the text to a server-side state key
        (commentBoxText-<...>, MemoryNamespace) that only exists after the comment box has
        rendered — the text is never in the SDUI request body (confirmed by live capture
        2026-07-14, api-docs/_writes/comment_create.json). So the fallback opens the post in the
        logged-in browser, types into the editor, and clicks submit. activity_urn: urn:li:activity:<id>.
        """
        activity_id = activity_urn.rsplit(":", 1)[-1] if ":" in activity_urn else activity_urn
        # 1) browserless first — the whole point of this method
        try:
            rest = self.create_comment_browserless(f"urn:li:activity:{activity_id}", text)
        except Exception as exc:  # vgreq/session problem — degrade to browser
            rest = {"ok": False, "status": None, "via": "voyager-rest",
                    "note": f"voyager-rest raised: {exc}"}
        if rest.get("ok"):
            rest["activity_id"] = activity_id
            return rest
        # 2) browser fallback (SDUI needs the rendered comment box + currentActor binding)
        self._browser = self._browser or SessionBrowser()
        self._browser.start()
        if not self._browser.is_logged_in():
            raise NotLoggedInError("LinkedIn session expired — log in in the browser window")
        res = self._browser.post_comment_ui(f"urn:li:activity:{activity_id}", text)
        return {"status": res.get("status"), "ok": res.get("ok", False),
                "activity_id": activity_id, "via": "browser-fallback",
                "browserless_attempt": {"status": rest.get("status"),
                                        "body_sent": rest.get("body_sent")},
                "note": res.get("note", "")}

    @staticmethod
    def _comment_delete_urn(comment_id: str, activity_urn: str) -> str:
        """Build the comment URN the classic Voyager DELETE route wants.

        The feed/comments DELETE endpoint is keyed by the comment's *canonical* urn form
        (the `urn` field in the feed/comments read, NOT entityUrn/dashEntityUrn):
            urn:li:comment:(activity:<postId>,<commentId>)
        Note the order — activity FIRST, then the comment id. The other two forms
        (fs_objectComment: id-first / fsd_comment: dash) are rejected by this route (400/500).
        """
        activity_id = activity_urn.split(":")[-1] if ":" in activity_urn else activity_urn
        return f"urn:li:comment:(activity:{activity_id},{comment_id})"

    def _comment_author_id(self, comment_id: str, activity_urn: str) -> Optional[str]:
        """Return the author's profile-id (ACoAA…) for a comment on a post, or None if the
        comment can't be found. Used by delete_comment's safety guard to refuse deleting
        OTHER people's comments. Reads get_post_comments and matches on the comment's `urn`.
        """
        cid = str(comment_id)
        try:
            data = self.get_post_comments(activity_urn)
        except Exception:
            return None
        for x in data.get("included", []):
            if "Comment" not in x.get("$type", ""):
                continue
            urn = x.get("urn", "")
            # urn:li:comment:(activity:<post>,<commentId>) — match the trailing comment id
            if urn.rstrip(")").rsplit(",", 1)[-1] == cid:
                return x.get("commenterProfileId")
        return None

    def delete_comment(self, comment_id: str, activity_urn: str,
                       dry_run: bool = False, comment_text: str = "",
                       force: bool = False) -> dict:
        """Delete a comment — two-stage, robust, with an OWNER-ONLY safety guard.

        SAFETY GUARD (default): only deletes comments whose author is the owner
        (LI_OWNER_URN). Deleting someone ELSE's comment requires force=True. This exists
        because a test once deleted a real person's comment on the owner's post — the guard
        makes that impossible by accident. The guard reads the comment's author first; if the
        comment can't be found (already gone / unreadable), the delete proceeds (idempotent).

        PRIMARY (browserless): classic Voyager REST DELETE, verified live (204):
            DELETE /voyager/api/feed/comments/<url-enc urn:li:comment:(activity:<postId>,<commentId>)>
        This replaces the old SDUI comments.deleteComment POST, which 500s on a pure-requests
        replay because it needs the browser's `currentActor` metadata binding (same limitation
        as unlike/repost — see api-docs/_writes/comment_delete.json).

        FALLBACK (browser): if the REST call fails AND `comment_text` is given, drive the real
        UI, locating the comment by its VISIBLE TEXT (not its id — the numeric id is not in the
        rendered DOM). See SessionBrowser.delete_comment_ui.

        comment_id: the numeric comment id (e.g. from get_post_comments' `urn`/`entityUrn`).
        activity_urn: urn:li:activity:<postId> the comment lives on (a bare id also works).
        dry_run: build the DELETE request and return it WITHOUT sending (for inspection/tests).
        comment_text: visible text of the comment — enables the browser fallback.
        force: bypass the owner-only guard to delete another person's comment (opt-in).
        """
        # --- owner-only safety guard (unless forced or just building a dry_run) ---
        if not force and not dry_run:
            owner_id = ME.rsplit(":", 1)[-1]  # ACoAA… part of LI_OWNER_URN
            author_id = self._comment_author_id(comment_id, activity_urn)
            if author_id is not None and author_id != owner_id:
                return {"ok": False, "status": "blocked", "comment_id": str(comment_id),
                        "author_id": author_id, "owner_id": owner_id,
                        "via": "guard",
                        "note": ("refused: this comment is NOT the owner's (author "
                                 f"{author_id} != owner {owner_id}). Pass force=True to "
                                 "delete someone else's comment on purpose.")}
        comment_urn = self._comment_delete_urn(comment_id, activity_urn)
        url = f"{BASE}/feed/comments/{urllib.parse.quote(comment_urn, safe='')}"
        if dry_run:
            return {"dry_run": True, "method": "DELETE", "url": url,
                    "comment_urn": comment_urn, "comment_id": str(comment_id),
                    "endpoint": "voyager.feed.comments.delete",
                    "note": "request built, not sent (dry_run)"}
        r = self._vg().delete(url)
        ok = r.status_code in (200, 201, 204)
        out = {"status": r.status_code, "ok": ok, "comment_id": str(comment_id),
               "comment_urn": comment_urn, "via": "voyager-rest",
               "endpoint": "voyager.feed.comments.delete"}
        if ok or not comment_text:
            if not ok:
                out["note"] = ("REST delete failed; pass comment_text to enable the browser "
                               "fallback (locates the comment by visible text)")
            return out
        # REST failed and we have the visible text → browser fallback (by text, not id)
        self._browser = self._browser or SessionBrowser()
        self._browser.start()
        if not self._browser.is_logged_in():
            raise NotLoggedInError("LinkedIn session expired — log in in the browser window")
        fb = self._browser.delete_comment_ui(activity_urn, comment_text=comment_text)
        return {"status": fb.get("status"), "ok": fb.get("ok", False),
                "comment_id": str(comment_id), "via": "browser-ui-fallback",
                "rest_status": r.status_code, "note": fb.get("note", "")}

    # queryId for the composer's link-preview lookup (rotates on deploys; re-grab via capture).
    _URLPREVIEW_QID = "voyagerContentcreationDashUpdateUrlPreview.b092c1aea4b6c087ec0d09614b3b3320"

    def get_link_preview(self, url: str) -> dict:
        """Fetch the composer's rich link-preview metadata for a URL (title/image/desc).
        VERIFIED browserless read (GET, 200) — what LinkedIn shows when you paste a link.
        """
        enc = urllib.parse.quote(url, safe="")
        full = (f"{BASE}/graphql?includeWebMetadata=true"
                f"&variables=(url:{enc})&queryId={self._URLPREVIEW_QID}")
        return self._vg().get(full).json()

    # --- writes (all verified endpoints from docs/04, 06-19) ------------
    # Full endpoint map: docs/COVERAGE-MAP.md. Each write below carries a live-captured body.
    def like(self, activity_urn: str) -> dict:
        """Like a post by activity URN. Verified endpoint (HTTP 201).
        POST voyagerSocialDashReactions?threadUrn={urlencoded activity urn}  {reactionType:LIKE}
        """
        enc = urllib.parse.quote(activity_urn, safe="")
        url = f"{BASE}/voyagerSocialDashReactions?threadUrn={enc}"
        r = self._vg().post(url, {"reactionType": "LIKE"})
        return {"status": r.status_code, "ok": r.status_code in (200, 201),
                "activity_urn": activity_urn}

    @staticmethod
    def _sdui_min_headers() -> dict:
        """Minimal headers the flagship-web SDUI route accepts: csrf + cookies + content-type.
        vgreq's Voyager headers (accept: …normalized+json, x-restli-protocol-version) make the
        SDUI endpoint 500 — the SDUI route wants the plain web-client shape, not the REST one.
        """
        import json as _json
        cookie_file = os.environ.get("VG_COOKIES", "/tmp/li_cookies.json")
        li = _json.load(open(cookie_file))
        cookies = {c["name"]: c["value"] for c in li} if isinstance(li, list) else li
        csrf = cookies.get("JSESSIONID", "").strip('"')
        return {"Content-Type": "application/json", "csrf-token": csrf,
                "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}

    def _post_sdui_template(self, tpl_name: str, activity_id: str, sduiid: str):
        """POST a captured SDUI request body (templates/<tpl_name>) with {{ACTIVITY_ID}} filled,
        using minimal SDUI headers. Returns the raw requests.Response.
        Reverse-engineered pattern: SDUI writes replay verbatim from the captured full body
        (partial hand-built bodies 500); only the activity id differs per call.
        """
        tpl_path = os.path.join(os.path.dirname(__file__), "templates", tpl_name)
        with open(tpl_path, "r", encoding="utf-8") as fh:
            body = fh.read().replace("{{ACTIVITY_ID}}", activity_id)
        url = ("https://www.linkedin.com/flagship-web/rsc-action/actions/server-request"
               f"?sduiid={sduiid}")
        return requests.post(url, data=body.encode("utf-8"),
                             headers=self._sdui_min_headers(), timeout=25)

    def unlike(self, activity_urn: str) -> dict:
        """Remove a LIKE reaction — BROWSERLESS (VERIFIED 2026-07-14, live 200, reaction gone).

        The old code 500'd not because of a missing currentActor binding (that field is empty
        in the real browser request too) but because it (a) sent a hand-built partial body and
        (b) used vgreq's Voyager headers. Fix: replay the captured full SDUI body from a template
        with minimal headers (csrf + cookies + content-type).
        """
        activity_id = activity_urn.rsplit(":", 1)[-1]
        r = self._post_sdui_template("unlike_sdui.json.tpl", activity_id,
                                     "com.linkedin.sdui.reactions.delete")
        ok = r.status_code in (200, 201, 204)
        out = {"status": r.status_code, "ok": ok, "via": "sdui-browserless",
               "activity_urn": activity_urn, "endpoint": "sdui.reactions.delete"}
        if not ok:
            out["note"] = ("sdui unlike returned non-2xx — template may have rotated "
                           "(re-capture); the browser path remains as fallback")
        return out

    def create_post(self, text: str, visibility: str = "PUBLIC", poll_urn: str = "") -> dict:
        """Publish a post. VERIFIED endpoint (Voyager GraphQL, docs/04).
        visibility: PUBLIC → ANYONE, CONNECTIONS → connections-only.
        poll_urn: optional urn:li:fsd_pollSummary:<id> (from create_poll) to post a poll.
        Returns status + the created activity/share URN when resolvable.
        """
        vis = "CONNECTIONS_ONLY" if str(visibility).upper().startswith("CONNECT") else "ANYONE"
        url = f"{BASE}/graphql?action=execute&queryId={SHARES_QID}"
        post = {
            "allowedCommentersScope": "ALL",
            "intendedShareLifeCycleState": "PUBLISHED",
            "origin": "FEED",
            "visibilityDataUnion": {"visibilityType": vis},
            "commentary": {"text": text, "attributesV2": []},
        }
        if poll_urn:
            post["media"] = {"mediaUrn": poll_urn, "category": "URN_REFERENCE"}
        body = {"variables": {"post": post}, "queryId": SHARES_QID, "includeWebMetadata": True}
        r = self._vg().post(url, body)
        # CRITICAL: a 200 can still carry a GraphQL ValidationError in the body — check it,
        # otherwise create_post reports a false success (learned the hard way).
        errors = []
        try:
            errors = (r.json().get("data", {}) or {}).get("errors") or []
        except Exception:
            pass
        ok = r.status_code in (200, 201) and not errors
        out = {"status": r.status_code, "ok": ok, "visibility": vis}
        if ok:
            out["note"] = ("posted; the activity/share URN comes from the follow-up "
                           "closed-sharebox SDUI call (docs/04) — call get_my_posts to confirm")
        elif errors:
            out["error"] = errors[0].get("message", "GraphQL validation error")
        else:
            out["error"] = "post failed — queryId hash may be stale (re-grab via capture)"
        return out

    def edit_post(self, activity_id: str, share_id: str, text: str) -> dict:
        """Edit an existing post's text. VERIFIED (Shares mutation + resourceKey/updateUrn, docs/24).
        activity_id + share_id identify the post (both from get_my_posts / the post URN).
        """
        url = f"{BASE}/graphql?action=execute&queryId={SHARES_EDIT_QID}"
        update_urn = (f"urn:li:fsd_update:(urn:li:activity:{activity_id},"
                      "MEMBER_SHARES_PROFILE_ACTIVITY,EMPTY,DEFAULT,false)")
        body = {
            "variables": {
                "entity": {
                    "entity": {"commentary": {"text": text, "attributesV2": []}},
                    "resourceKey": f"urn:li:share:{share_id}",
                },
                "updateUrn": update_urn,
            },
            "queryId": SHARES_EDIT_QID,
            "includeWebMetadata": True,
        }
        r = self._vg().post(url, body)
        errors = []
        try:
            errors = (r.json().get("data", {}) or {}).get("errors") or []
        except Exception:
            pass
        ok = r.status_code in (200, 201) and not errors
        return {"status": r.status_code, "ok": ok, "activity_id": activity_id,
                "error": (errors[0].get("message") if errors else None)}

    def create_poll(self, question: str, options: list, duration: str = "ONE_WEEK") -> dict:
        """Create a poll and return its pollSummary URN. VERIFIED (docs/24).
        options: 2–4 strings. duration: ONE_DAY / THREE_DAYS / ONE_WEEK / TWO_WEEKS.
        Feed it into create_post(poll_urn=...) to publish the poll as a post.
        """
        url = f"{BASE}/graphql?action=execute&queryId={POLL_QID}"
        body = {"variables": {"poll": {"question": question, "duration": duration,
                                       "options": list(options)}},
                "queryId": POLL_QID, "includeWebMetadata": True}
        r = self._vg().post(url, body)
        out = {"status": r.status_code, "ok": r.status_code in (200, 201)}
        try:
            import re as _re
            m = _re.search(r"urn:li:fsd_pollSummary:\d+", r.text)
            if m:
                out["poll_urn"] = m.group(0)
        except Exception:
            pass
        return out

    def send_dm(self, conversation_urn: str, text: str) -> dict:
        """Send a message in an existing conversation. VERIFIED endpoint (Voyager, docs/06).
        conversation_urn: urn:li:msg_conversation:(urn:li:fsd_profile:<ME>,<threadId>).
        Uses a client-generated originToken as an idempotency key (prevents double-send).
        Returns the created message URN when resolvable (needed for recall).
        """
        url = f"{BASE}/voyagerMessagingDashMessengerMessages?action=createMessage"
        # trackingId: 16 RAW bytes as a latin-1 string (NOT base64) — the browser sends raw bytes;
        # without it (or base64-encoded) → HTTP 400.
        tracking = uuid.uuid4().bytes.decode("latin-1")
        body = {
            "message": {
                "body": {"attributes": [], "text": text},
                "renderContentUnions": [],
                "conversationUrn": conversation_urn,
                "originToken": str(uuid.uuid4()),
            },
            "mailboxUrn": ME,
            "trackingId": tracking,
            "dedupeByClientGeneratedToken": False,
        }
        r = self._vg().post(url, body)
        out = {"status": r.status_code, "ok": r.status_code in (200, 201),
               "conversation_urn": conversation_urn}
        # dig out the created message URN (for recall)
        try:
            import re as _re
            m = _re.search(r"urn:li:msg_message:\([^)]+\)", r.text)
            if m:
                out["message_urn"] = m.group(0)
        except Exception:
            pass
        return out

    def recall_message(self, message_urn: str) -> dict:
        """Delete (recall) a sent message for everyone. VERIFIED (Voyager action=recall, docs/06).
        message_urn: urn:li:msg_message:(urn:li:fsd_profile:<ME>,<msgId>).
        """
        url = f"{BASE}/voyagerMessagingDashMessengerMessages?action=recall"
        r = self._vg().post(url, {"messageUrn": message_urn})
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "message_urn": message_urn}

    def react_to_message(self, message_urn: str, emoji: str = "👏") -> dict:
        """React to a message with an emoji (toggle). VERIFIED (Voyager action=reactWithEmoji, docs/06).
        Re-sending the same emoji removes the reaction.
        """
        url = f"{BASE}/voyagerMessagingDashMessengerMessages?action=reactWithEmoji"
        r = self._vg().post(url, {"messageUrn": message_urn, "emoji": emoji})
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "message_urn": message_urn, "emoji": emoji}

    def delete_post(self, activity_id: str, tracking_id: str) -> dict:
        """Delete a post. VERIFIED endpoint (SDUI update.deletePost, docs/04).
        Needs the numeric activityId + the update's trackingId (both from get_my_posts).
        """
        url = ("https://www.linkedin.com/flagship-web/rsc-action/actions/server-request"
               "?sduiid=com.linkedin.sdui.update.deletePost")
        body = {
            "requestId": "com.linkedin.sdui.update.deletePost",
            "serverRequest": {
                "requestId": "com.linkedin.sdui.update.deletePost",
                "requestedArguments": {
                    "$type": "proto.sdui.actions.requests.RequestedArguments",
                    "payload": {
                        "updateKeyContainer": {"feedType": 3, "items": [{
                            "feedUpdateUrn": {"updateUrnActivityUrn": {
                                "__typename": "proto_com_linkedin_common_ActivityUrn",
                                "activityUrn": {"activityId": activity_id}}},
                            "trackingId": tracking_id}]},
                        "shareLifeCycleState": "ShareLifeCycleState_PUBLISHED",
                        "isUpdateInCarousel": False,
                    },
                    "requestedStateKeys": [],
                },
            },
        }
        r = self._vg().post(url, body)
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "activity_id": activity_id, "endpoint": "sdui.update.deletePost"}

    def follow_company(self, company_id: str, follow: bool = True) -> dict:
        """Follow (or unfollow) a company. VERIFIED endpoint (Voyager PARTIAL_UPDATE, docs/08).
        company_id = numeric id (e.g. '1035' for Microsoft). follow=False unfollows.
        """
        state_urn = f"urn:li:fsd_followingState:urn:li:fsd_company:{company_id}"
        url = f"{BASE}/feed/dash/followingStates/{urllib.parse.quote(state_urn, safe='')}"
        body = {"patch": {"$set": {"following": bool(follow)}}}
        r = self._vg().post(url, body)
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "company_id": company_id, "following": bool(follow)}

    # --- network actions (captured live docs/25) ------------------------
    def connect(self, member_urn: str, note: str = "") -> dict:
        """Send a connection invite, optionally with a note. VERIFIED (Voyager, docs/25).
        member_urn: urn:li:fsd_profile:<id>. People-facing — gate behind confirm in the tool.
        """
        url = (f"{BASE}/voyagerRelationshipsDashMemberRelationships"
               f"?action=verifyQuotaAndCreateV2")
        body = {"invitee": {"inviteeUnion": {"memberProfile": member_urn}}}
        if note:
            body["customMessage"] = note
        r = self._vg().post(url, body)
        return {"status": r.status_code, "ok": r.status_code in (200, 201),
                "member_urn": member_urn, "with_note": bool(note)}

    def endorse_skill(self, vanity_name: str, profile_id: str, skill_id: str) -> dict:
        """Endorse a skill on someone's profile. VERIFIED (SDUI endorseSkill, docs/25).
        vanity_name + profile_id identify the person; skill_id is the skill's position id.
        """
        url = self._sdui_url("com.linkedin.sdui.requests.profile.endorseSkill")
        body = {
            "requestId": "com.linkedin.sdui.requests.profile.endorseSkill",
            "serverRequest": {
                "requestId": "com.linkedin.sdui.requests.profile.endorseSkill",
                "requestedArguments": {
                    "$type": "proto.sdui.actions.requests.RequestedArguments",
                    "payload": {"vanityName": vanity_name, "profileId": profile_id,
                                "skillId": str(skill_id)},
                    "requestedStateKeys": [],
                },
            },
        }
        r = self._vg().post(url, body)
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "vanity_name": vanity_name, "skill_id": str(skill_id)}

    def remove_connection(self, vanity_name: str, first_name: str = "",
                          last_name: str = "") -> dict:
        """Remove a first-degree connection. VERIFIED (SDUI RemoveConnectionVanityName, docs/25).
        Keyed by vanity name (+ display name for the confirm UI). Destructive — gate behind confirm.
        """
        url = self._sdui_url("com.linkedin.sdui.mynetwork.RemoveConnectionVanityName")
        body = {
            "requestId": "com.linkedin.sdui.mynetwork.RemoveConnectionVanityName",
            "serverRequest": {
                "requestId": "com.linkedin.sdui.mynetwork.RemoveConnectionVanityName",
                "requestedArguments": {
                    "$type": "proto.sdui.actions.requests.RequestedArguments",
                    "payload": {"disconnectVanityName": vanity_name,
                                "disconnectFirstName": first_name,
                                "disconnectLastName": last_name,
                                "closeCurrentMenuOnCompletion": True},
                    "requestedStateKeys": [],
                },
            },
        }
        r = self._vg().post(url, body)
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "vanity_name": vanity_name}

    # --- post interactions (SDUI, verified docs/10) ---------------------
    @staticmethod
    def _sdui_url(sduiid: str) -> str:
        return ("https://www.linkedin.com/flagship-web/rsc-action/actions/server-request"
                f"?sduiid={sduiid}")

    def save_post(self, activity_id: str, save: bool = True) -> dict:
        """Save / unsave a post ("Für später speichern"). VERIFIED (SDUI update.saveState, docs/10).
        save=False unsaves. Body carries the activityId as a real literal → browserless.
        """
        url = self._sdui_url("com.linkedin.sdui.update.saveState")
        body = {
            "requestId": "com.linkedin.sdui.update.saveState",
            "serverRequest": {
                "requestId": "com.linkedin.sdui.update.saveState",
                "requestedArguments": {
                    "$type": "proto.sdui.actions.requests.RequestedArguments",
                    "payload": {
                        "isSaved": bool(save),
                        "saveObjectUrn": {"saveEntityUrnFeedUpdateUrn": {
                            "feedUpdateUrn": {"updateUrnActivityUrn": {
                                "activityUrn": {"activityId": activity_id}}}}},
                    },
                    "requestedStateKeys": [],
                },
            },
        }
        r = self._vg().post(url, body)
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "activity_id": activity_id, "saved": bool(save)}

    def repost(self, activity_id: str) -> dict:
        """Instant repost ("Sofort teilen"). VERIFIED endpoint (SDUI createInstantRepost, docs/10).
        NOTE: like unlike, this SDUI action needs the browser's currentActor binding — pure
        requests returns 500. Use the browser fallback for a reliable repost.
        """
        url = self._sdui_url("com.linkedin.sdui.feed.requests.createInstantRepost")
        body = {
            "requestId": "com.linkedin.sdui.feed.requests.createInstantRepost",
            "serverRequest": {
                "requestId": "com.linkedin.sdui.feed.requests.createInstantRepost",
                "requestedArguments": {
                    "$type": "proto.sdui.actions.requests.RequestedArguments",
                    "payload": {"threadUrn": {"threadUrnActivityThreadUrn": {
                        "activityUrn": {"activityId": activity_id}}}},
                    "requestedStateKeys": [],
                },
            },
        }
        r = self._vg().post(url, body)
        ok = r.status_code in (200, 201, 204)
        out = {"status": r.status_code, "ok": ok, "activity_id": activity_id,
               "endpoint": "sdui.createInstantRepost"}
        if not ok:
            out["note"] = ("browserless repost not supported (SDUI needs currentActor binding, "
                           "like unlike) — use the browser path")
        return out

    # queryId for repost-delete rotates on deploys; re-grab via capture if it 404s.
    _REPOST_DEL_QID = "voyagerFeedDashReposts"

    def delete_repost(self, repost_urn: str) -> dict:
        """Delete a repost. VERIFIED (Voyager GraphQL DELETE-by-key, docs/10).
        repost_urn: urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:<shareId>,<repostId>).
        NOTE: needs the current voyagerFeedDashReposts.<hash> — set _REPOST_DEL_QID.
        """
        url = f"{BASE}/graphql?action=execute&queryId={self._REPOST_DEL_QID}"
        body = {"variables": {"resourceKey": repost_urn},
                "queryId": self._REPOST_DEL_QID, "includeWebMetadata": True}
        r = self._vg().post(url, body)
        return {"status": r.status_code, "ok": r.status_code in (200, 201, 204),
                "repost_urn": repost_urn}

    def close(self):
        if self._browser:
            self._browser.stop()
            self._browser = None
