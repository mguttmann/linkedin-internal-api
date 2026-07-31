"""client.py — LinkedInClient: a PURE requests-based LinkedIn API client. NO browser.

The single entry point the MCP tools call. Every operation talks to LinkedIn's internal API
directly via vgreq (requests), reading cookies from the session file that the external
session_daemon.py keeps fresh. It never launches Chrome, never clicks, never falls back to a
browser — if the session is dead or an endpoint 500s, tools return an honest error.

See docs/MCP-DESIGN.md. Read AND write tools are wired: each carries a live-captured request
body (verified endpoint names + schemas from docs/04, 06-25). Nothing here connects on import.
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

from . import errors, jobs_parse

# Reuse the proven pure-requests client from the internal-api repo (sibling ../lib).
_REPO_LIB = os.path.join(os.path.dirname(__file__), "..", "..", "lib")
sys.path.insert(0, os.path.abspath(_REPO_LIB))
try:
    import vgreq  # type: ignore
    _HAVE_VGREQ = True
except Exception:  # pragma: no cover
    vgreq = None  # type: ignore
    _HAVE_VGREQ = False

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
    """Pure requests-based LinkedIn client (vgreq). NO browser, ever.

    The MCP is a clean API client: it reads cookies from the session file (kept fresh by the
    separate session_daemon.py) and talks to the internal API directly. It never launches
    Chrome, never clicks, never falls back to a browser. If the session is dead, tools return
    an honest error pointing at the daemon — the login/refresh concern lives OUTSIDE the MCP.
    """

    def __init__(self, cookies_path: str = "/tmp/li_cookies.json"):
        self.cookies_path = cookies_path

    # --- session ---------------------------------------------------------
    def ensure_session(self, allow_browser: bool = False) -> bool:
        """Return True if the session cookies are live (a /me probe returns 200).

        Pure check — NEVER launches a browser. Session login/refresh is the job of the
        external session_daemon.py, which keeps the cookie file fresh. The allow_browser
        parameter is retained for signature compatibility but is ignored.
        """
        if not _HAVE_VGREQ:
            raise RuntimeError("vgreq not importable — check repo layout")
        return self._session_ok()

    _SESSION_PROBE_ENDPOINT = "voyager.me.get"

    def probe_session(self) -> dict:
        """Probe /me and CLASSIFY the outcome instead of collapsing it into one False.

        The diagnosis behind ensure_session(): a missing cookie file (FileNotFoundError from
        lib/vgreq.py _load), a missing cookie marker (KeyError from the same place) and a
        network/timeout error used to end up on the same `False`, which session_status then
        reported as "session stale, go log in again" for all of them
        (docs/SESSION-AND-ERRORS-DESIGN.md, section 2.5).

        Returns errors.classify()'s flat dict plus `logged_in`. Only the login redirect carries
        session_suspect=True; it contains NO response body (section 2.6). Not yet live-tested.

        ONE rule forms the success statement: `logged_in` is exactly `code == "ok"`. A second
        rule (the earlier `status == 200`) could OVERRULE the classification and report a probe
        that failed — a 200 serving a login interstitial, a truncated body — as a healthy
        session: the "failure that looks like a success" class. `ok` is only reached by a 2xx
        with a readable JSON object body and no error carrier (mcp/lib/errors.py classify).
        """
        endpoint = self._SESSION_PROBE_ENDPOINT
        try:
            r = self._vg().get(f"{BASE}/me")
        except Exception as exc:  # noqa: BLE001 — the type IS the diagnosis, see classify_exception
            diag = errors.classify(exc=exc, endpoint=endpoint)
        else:
            diag = errors.classify(response=r, endpoint=endpoint)
        return {"logged_in": diag["code"] == "ok", **diag}

    def _session_ok(self) -> bool:
        return self.probe_session()["logged_in"]

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
                           "rotated; re-capture with tools/capture. (No browser fallback: this "
                           "is a pure API client.)")
        return out

    def create_comment(self, activity_urn: str, text: str) -> dict:
        """Post a top-level comment — BROWSERLESS (SDUI createComment, verified live 2026-07-14).

        Pure API: replays the captured SDUI body with a self-minted token + minimal headers.
        No browser, no clicking. If the API call fails, returns an honest error (the caller can
        re-capture the template) — it never falls back to Chrome.
        activity_urn: urn:li:activity:<id>.
        """
        activity_id = activity_urn.rsplit(":", 1)[-1] if ":" in activity_urn else activity_urn
        res = self.create_comment_browserless(f"urn:li:activity:{activity_id}", text)
        res["activity_id"] = activity_id
        return res

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
                       dry_run: bool = False, force: bool = False) -> dict:
        """Delete a comment — BROWSERLESS, with an OWNER-ONLY safety guard.

        SAFETY GUARD (default): only deletes comments whose author is the owner
        (LI_OWNER_URN). Deleting someone ELSE's comment requires force=True. This exists
        because a test once deleted a real person's comment on the owner's post — the guard
        makes that impossible by accident. The guard reads the comment's author first; if the
        comment can't be found (already gone / unreadable), the delete proceeds (idempotent).

        Route (pure API, verified live 204):
            DELETE /voyager/api/feed/comments/<url-enc urn:li:comment:(activity:<postId>,<commentId>)>

        comment_id: the numeric comment id (e.g. from get_post_comments' `urn`/`entityUrn`).
        activity_urn: urn:li:activity:<postId> the comment lives on (a bare id also works).
        dry_run: build the DELETE request and return it WITHOUT sending (for inspection/tests).
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
        if not ok:
            out["note"] = ("REST delete returned non-2xx — verify the comment id/urn via "
                           "get_post_comments. (No browser fallback: this is a pure API client.)")
        return out

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

    # --- jobs reads (route from Manuel's own live evidence 2026-07-30, HTTP 200) ----------
    # LEGACY REST resource /jobs/jobPostings/<id> — NOT the dash resource
    # voyagerJobsDashJobPostings and NOT /graphql. Both exist; they are different routes.
    _JOB_POSTING_DECO = "com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65"
    # jobs-feed queryId hashes rotate on LinkedIn deployments (data/endpoints_voyager.json:746,
    # :996) — re-grab both via tools/crawl_recursive.py if the feed starts 404-ing.
    _JOBS_FEED_QID = "voyagerJobsDashJobsFeed.8b4a94e0e9d8395f1e7482987dd2f815"
    _JOBS_FEED_PAGE_QID = "voyagerJobsDashJobsFeed.711cec89dd87dcf89df6a9d6e7ab5682"

    @staticmethod
    def _read_json(r) -> tuple[Optional[dict], Optional[str]]:
        """(parsed body, error sentence). A non-JSON 200 is a failed read, not an empty one."""
        try:
            body = r.json()
        except Exception:
            return None, ("the response body was not JSON — the session is most likely stale "
                          "(a login/interstitial page); check session_status()")
        if not isinstance(body, dict):
            return None, f"the response body was a {type(body).__name__}, not a JSON object"
        return body, None

    def get_job(self, job_id: str | int, description_chars: int = 4000) -> dict:
        """Read ONE job posting as a flat projection. 🔍 route (Manuel's live evidence 2026-07-30).

        GET /voyager/api/jobs/jobPostings/<id>?decorationId=…WebFullJobPosting-65

        job_id accepts an int, a numeric string, a jobPosting URN or a full job URL; unusable
        input returns an honest error dict WITHOUT any HTTP call.

        IDENTITY IS ENFORCED: if the response body carries a job id different from the requested
        one — or two identifying ids that disagree with each other — this returns ok=False and NO
        `url` at all. The body id is never adopted and the url is never built from it (Manuel's
        explicit instruction) — otherwise a caller would receive a link to a different job than
        the one it just read. A body without any identifying id, and a body that identifies the
        job but yields no readable field, are reported as such (`identity`, `error`), never as a
        success.

        Returns {status, ok, job_id, url, title, company, location, employment_status,
        remote_allowed, listed_at, applies, views, salary, salary_present, reposted,
        description_text, description_truncated} on success, else {status, ok: False, error, note}.
        """
        try:
            jid = jobs_parse.normalize_job_id(job_id)
        except ValueError as e:
            return {"status": "invalid_input", "ok": False, "requested": str(job_id),
                    "error": str(e),
                    "note": ("nothing was sent. Pass a numeric job id, a urn:li:fsd_jobPosting:<id>"
                             " URN or a linkedin.com/jobs/view/<…>-<id>/ URL")}
        chars, clamp_note = jobs_parse.effective_description_chars(description_chars)
        url = (f"{BASE}/jobs/jobPostings/{jid}"
               f"?decorationId={self._JOB_POSTING_DECO}")
        r = self._vg().get(url)
        base = {"status": r.status_code, "job_id": jid, "endpoint": "voyager.jobs.jobPostings.get"}
        if r.status_code != 200:
            return {**base, "ok": False,
                    "error": f"HTTP {r.status_code} for job {jid}",
                    "note": ("the job may be closed/unavailable, or the decorationId has rotated "
                             "— re-capture the request with tools/crawl_recursive.py")}
        raw, parse_error = self._read_json(r)
        if parse_error:
            return {**base, "ok": False, "error": parse_error, "note": parse_error}
        inband = jobs_parse.inband_error(raw)
        if inband:
            return {**base, "ok": False, "error": inband,
                    "note": ("HTTP 200 carrying an error envelope — a 200 alone is not a read; "
                             "check the session and re-capture the decorationId")}
        read = jobs_parse.read_job_posting(raw, jid, chars)
        if not read["ok"]:
            out = {**base, "ok": False, "identity": read["identity"], "error": read["reason"],
                   "note": ("no fields and no url are returned unless the body identifies the "
                            "requested job AND carries readable content — a url must never be "
                            "built from an id found in the body")}
            if read["identity"] == "mismatch":
                out["body_job_id"] = read["body_job_id"]
                out["body_job_ids"] = read["body_job_ids"]
            return out
        out = {**base, "ok": True, **read["fields"]}
        if clamp_note:
            out["note"] = clamp_note
        return out

    def get_job_recommendations(self, count: int = 20, pagination_token: str = "") -> dict:
        """LinkedIn's own job recommendations for the owner. 🔍 captured route (endpoints:746).

        GET /voyager/api/graphql?includeWebMetadata=true&variables=(count:<n>,start:0)
            &queryId=voyagerJobsDashJobsFeed.<hash>
        With pagination_token the captured cursor variant (endpoints:996) is used instead.

        'No jobs' and 'could not read' are DIFFERENT answers here: `state` is "hits"/"empty"
        (ok=True, the read container itself was empty) or "unknown"/"drift"/"ambiguous" (ok=False,
        with the re-capture path). A silent `count: 0` for a full page is exactly the failure this
        guards. `read_entries`/`discarded` balance `count` against the raw container; a partial
        loss stays ok=True but names itself in `note`.
        """
        try:
            n = int(count)
        except (TypeError, ValueError):
            n = -1
        if isinstance(count, bool) or n <= 0:
            return {"status": "invalid_input", "ok": False, "requested": repr(count),
                    "error": "count must be a positive number",
                    "note": "nothing was sent"}
        if pagination_token:
            enc = urllib.parse.quote(str(pagination_token), safe="")
            url = (f"{BASE}/graphql?includeWebMetadata=true&variables=(paginationToken:{enc})"
                   f"&queryId={self._JOBS_FEED_PAGE_QID}")
        else:
            url = (f"{BASE}/graphql?includeWebMetadata=true&variables=(count:{n},start:0)"
                   f"&queryId={self._JOBS_FEED_QID}")
        r = self._vg().get(url)
        base = {"status": r.status_code, "endpoint": "voyager.graphql.jobsFeed",
                "requested_count": n}
        if r.status_code != 200:
            return {**base, "ok": False, "state": "unknown", "count": 0, "results": [],
                    "error": f"HTTP {r.status_code} for the jobs feed",
                    "note": ("the queryId hash may have rotated — re-grab it with "
                             "tools/crawl_recursive.py and update _JOBS_FEED_QID")}
        raw, parse_error = self._read_json(r)
        if parse_error:
            return {**base, "ok": False, "state": "unknown", "count": 0, "results": [],
                    "error": parse_error, "note": parse_error}
        inband = jobs_parse.inband_error(raw)
        if inband:
            return {**base, "ok": False, "state": "unknown", "count": 0, "results": [],
                    "error": inband,
                    "note": ("HTTP 200 carrying an error envelope — a 200 alone is not a read; "
                             "re-grab the queryId hash with tools/crawl_recursive.py")}
        read = jobs_parse.read_job_collection(raw, limit=n)
        out = {**base, "ok": read["ok"], "state": read["state"], "count": read["count"],
               "results": read["results"], "read_entries": read["read_entries"],
               "discarded": read["discarded"], "paging_total": read["paging_total"],
               "pagination_token": read["pagination_token"]}
        if read["reason"]:
            # A reason on a SUCCESSFUL read is a partial loss, not a failure: it belongs in `note`
            # only. Calling it an `error` on ok=True would train the agent to ignore the field.
            out["note"] = read["reason"]
            if not read["ok"]:
                out["error"] = read["reason"]
        return out

    # --- writes (all verified endpoints from docs/04, 06-19) ------------
    # Full endpoint map: docs/COVERAGE-MAP.md. Each write below carries a live-captured body.
    @staticmethod
    def _gql_errors(r) -> list:
        """Extract `data.errors` from a Voyager GraphQL response — the false-success chokepoint.

        CRITICAL (docs/04, learned the hard way): a GraphQL write answers HTTP 200 and STILL
        carries a ValidationError in the body. Every GraphQL write must therefore compute
        ok = 2xx AND not self._gql_errors(r); the first entry's `message` is the error text.
        Returns [] when the body is not JSON or carries no errors.
        """
        try:
            return (r.json().get("data", {}) or {}).get("errors") or []
        except Exception:
            return []

    @staticmethod
    def _qid_has_hash(query_id: str) -> bool:
        """True when a queryId carries the '<family>.<deploy hash>' suffix LinkedIn requires.

        A bare family name (no dot) is not a usable queryId — the call is doomed before it is
        sent. Callers use this to fail honestly instead of firing a hopeless request.
        """
        family, _, hash_part = query_id.partition(".")
        return bool(family and hash_part)

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

    def _post_sdui_template(self, tpl_name: str, subs: dict, sduiid: str):
        """POST a captured SDUI request body (templates/<tpl_name>) with placeholders filled
        from `subs` ({{KEY}} → value), using minimal SDUI headers. Returns requests.Response.
        Reverse-engineered pattern: SDUI writes replay verbatim from the captured full body
        (partial hand-built bodies 500); only the ids differ per call.
        """
        tpl_path = os.path.join(os.path.dirname(__file__), "templates", tpl_name)
        with open(tpl_path, "r", encoding="utf-8") as fh:
            body = fh.read()
        for key, val in subs.items():
            body = body.replace(key, val)
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
        r = self._post_sdui_template("unlike_sdui.json.tpl", {"{{ACTIVITY_ID}}": activity_id},
                                     "com.linkedin.sdui.reactions.delete")
        ok = r.status_code in (200, 201, 204)
        out = {"status": r.status_code, "ok": ok, "via": "sdui-browserless",
               "activity_urn": activity_urn, "endpoint": "sdui.reactions.delete"}
        if not ok:
            out["note"] = ("sdui unlike returned non-2xx — template may have rotated "
                           "(re-capture); the browser path remains as fallback")
        return out

    def react_to_comment(self, comment_id: str, activity_urn: str) -> dict:
        """React (LIKE) to a comment — BROWSERLESS (VERIFIED 2026-07-14, live 200, reaction set).

        Same SDUI pattern as unlike: replay the captured reactions.create body from a template
        (comment id + post activity id filled in) with minimal headers. The reaction targets the
        comment via threadUrnCommentThreadUrn (commentUrn = {commentId, thread}), not the post.
        """
        activity_id = activity_urn.rsplit(":", 1)[-1]
        r = self._post_sdui_template(
            "react_comment_sdui.json.tpl",
            {"{{COMMENT_ID}}": str(comment_id), "{{ACTIVITY_ID}}": activity_id},
            "com.linkedin.sdui.reactions.create")
        ok = r.status_code in (200, 201, 204)
        out = {"status": r.status_code, "ok": ok, "via": "sdui-browserless",
               "comment_id": str(comment_id), "activity_urn": activity_urn,
               "endpoint": "sdui.reactions.create"}
        if not ok:
            out["note"] = ("sdui react_to_comment returned non-2xx — template may have rotated "
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
        errors = self._gql_errors(r)
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

    def upload_video(self, video_path: str) -> dict:
        """Upload a video file to LinkedIn (browserless, 3-step flow, docs/24).
        1) register upload -> asset URN + upload URL + recipes
        2) PUT the raw file bytes to the upload URL
        3) return {ok, asset_urn, recipes} ready to pass to create_post(media=...).
        Does NOT create the post — call create_post_with_video for the full flow.
        """
        import os as _os
        import requests as _rq
        if not _os.path.isfile(video_path):
            return {"ok": False, "error": f"file not found: {video_path}"}
        fsize = _os.path.getsize(video_path)
        fname = _os.path.basename(video_path)
        # 1) register
        url = f"{BASE}/voyagerVideoDashMediaUploadMetadata?action=upload"
        body = {"mediaUploadType": "VIDEO_SHARING", "fileSize": fsize, "filename": fname}
        r = self._vg().post(url, body)
        if r.status_code not in (200, 201):
            return {"ok": False, "step": "register", "status": r.status_code,
                    "error": r.text[:200]}
        val = (r.json().get("data", {}) or {}).get("value", {}) or {}
        asset_urn = val.get("urn")
        recipes = val.get("recipes", [])
        parts = val.get("partUploadRequests", []) or []
        if not asset_urn or not parts:
            return {"ok": False, "step": "register", "error": "no asset/upload URL in response",
                    "raw": r.text[:300]}
        # 2) PUT each part (LinkedIn splits video into ~4 MB byte-range chunks) and collect ETags
        _, cookie_str = __import__("importlib").import_module("vgreq")._load()
        with open(video_path, "rb") as fh:
            data = fh.read()
        etags = []
        for i, part in enumerate(parts):
            first = part.get("firstByte", 0)
            last = part.get("lastByte", len(data) - 1)
            chunk = data[first:last + 1]
            hdrs = dict(part.get("headers", {"Content-Type": "application/octet-stream"}))
            hdrs["cookie"] = cookie_str
            pr = _rq.put(part["uploadUrl"], data=chunk, headers=hdrs, timeout=300)
            if pr.status_code not in (200, 201, 204):
                return {"ok": False, "step": f"put-part-{i}", "status": pr.status_code,
                        "asset_urn": asset_urn, "error": pr.text[:200]}
            # LinkedIn returns each part's handle in the Location header (signedId), not ETag
            sid = pr.headers.get("Location") or pr.headers.get("ETag") or pr.headers.get("etag")
            if sid:
                etags.append(sid.strip('"'))
        # 3) finalize the multipart upload (tell LinkedIn all parts are in)
        fin_url = f"{BASE}/voyagerVideoDashMediaUploadMetadata?action=finalizeUpload"
        fin_body = {"finalizeUploadMetadata": {
            "mediaArtifact": val.get("mediaArtifactUrn"),
            "asset": asset_urn,
            "uploadedPartsUploadUrns": etags,
        }}
        fr = self._vg().post(fin_url, fin_body)
        return {"ok": True, "asset_urn": asset_urn, "recipes": recipes,
                "size": fsize, "parts": len(parts), "etags": len(etags),
                "finalize_status": fr.status_code, "finalize_body": fr.text[:150]}

    def create_post_with_video(self, text: str, video_path: str,
                               visibility: str = "PUBLIC",
                               wait_processing: int = 40) -> dict:
        """Full flow: upload a video, wait for it to process, then publish a post with it.
        Returns the create_post result plus the asset URN used.
        """
        import time as _t
        up = self.upload_video(video_path)
        if not up.get("ok"):
            return {"ok": False, "phase": "upload", **up}
        asset_urn = up["asset_urn"]
        recipes = up.get("recipes", [])
        # give LinkedIn a moment to process the freshly uploaded video before attaching
        if wait_processing:
            _t.sleep(wait_processing)
        vis = "CONNECTIONS_ONLY" if str(visibility).upper().startswith("CONNECT") else "ANYONE"
        url = f"{BASE}/graphql?action=execute&queryId={SHARES_QID}"
        post = {
            "allowedCommentersScope": "ALL",
            "intendedShareLifeCycleState": "PUBLISHED",
            "origin": "FEED",
            "visibilityDataUnion": {"visibilityType": vis},
            "commentary": {"text": text, "attributesV2": []},
            "media": {"category": "VIDEO", "mediaUrn": asset_urn, "recipes": recipes},
        }
        body = {"variables": {"post": post}, "queryId": SHARES_QID, "includeWebMetadata": True}
        r = self._vg().post(url, body)
        errors = []
        try:
            errors = (r.json().get("data", {}) or {}).get("errors") or []
        except Exception:
            pass
        ok = r.status_code in (200, 201) and not errors
        out = {"ok": ok, "status": r.status_code, "visibility": vis,
               "asset_urn": asset_urn, "phase": "post"}
        if ok:
            out["note"] = ("posted with video; confirm live via get_my_posts / browser. "
                           "Video may still be transcoding for a minute after publish.")
        elif errors:
            out["error"] = errors[0].get("message", "GraphQL validation error")
        else:
            out["error"] = f"post failed (HTTP {r.status_code}) — {r.text[:150]}"
        return out

    def upload_image(self, image_path: str) -> dict:
        """Upload an image (browserless, single-part). VERIFIED live 2026-07-18 (scrybe post).
        Unlike video, images use mediaUploadType=IMAGE_SHARING and a singleUploadUrl —
        one PUT, no multipart finalize needed. Returns the digitalmediaAsset URN.
        """
        fsize = os.path.getsize(image_path)
        url = f"{BASE}/voyagerVideoDashMediaUploadMetadata?action=upload"
        r = self._vg().post(url, {
            "mediaUploadType": "IMAGE_SHARING",
            "fileSize": fsize,
            "filename": os.path.basename(image_path),
        })
        if r.status_code not in (200, 201):
            return {"ok": False, "step": "register", "status": r.status_code,
                    "error": r.text[:200]}
        val = (r.json().get("data", {}) or {}).get("value", {}) or {}
        asset_urn = val.get("urn")
        single = val.get("singleUploadUrl")
        if not asset_urn or not single:
            return {"ok": False, "step": "register", "error": "no asset/singleUploadUrl",
                    "raw": r.text[:300]}
        hdrs = dict(val.get("singleUploadHeaders") or {})
        hdrs.setdefault("Content-Type", "application/octet-stream")
        with open(image_path, "rb") as fh:
            pr = requests.put(single, data=fh.read(), headers=hdrs, timeout=120)
        if pr.status_code not in (200, 201, 204):
            return {"ok": False, "step": "put", "status": pr.status_code,
                    "asset_urn": asset_urn, "error": pr.text[:200]}
        return {"ok": True, "asset_urn": asset_urn, "size": fsize}

    def create_post_with_image(self, text: str, image_path: str,
                               visibility: str = "PUBLIC") -> dict:
        """Full flow: upload an image, then publish a post with it. VERIFIED live 2026-07-18
        (scrybe post, activity 7484249869516365824). Same Shares mutation as create_post,
        media.category=IMAGE + feedshare-image recipe; no processing wait needed.
        """
        up = self.upload_image(image_path)
        if not up.get("ok"):
            return {"ok": False, "phase": "upload", **up}
        asset_urn = up["asset_urn"]
        vis = "CONNECTIONS_ONLY" if str(visibility).upper().startswith("CONNECT") else "ANYONE"
        url = f"{BASE}/graphql?action=execute&queryId={SHARES_QID}"
        post = {
            "allowedCommentersScope": "ALL",
            "intendedShareLifeCycleState": "PUBLISHED",
            "origin": "FEED",
            "visibilityDataUnion": {"visibilityType": vis},
            "commentary": {"text": text, "attributesV2": []},
            "media": {"category": "IMAGE", "mediaUrn": asset_urn,
                      "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"]},
        }
        body = {"variables": {"post": post}, "queryId": SHARES_QID, "includeWebMetadata": True}
        r = self._vg().post(url, body)
        errors = []
        try:
            errors = (r.json().get("data", {}) or {}).get("errors") or []
        except Exception:
            pass
        ok = r.status_code in (200, 201) and not errors
        out = {"ok": ok, "status": r.status_code, "visibility": vis,
               "asset_urn": asset_urn, "phase": "post"}
        if ok:
            import re as _re
            urns = sorted(set(_re.findall(r"urn:li:(?:share|activity):\d+", r.text)))
            out["urns"] = urns[:4]
            out["note"] = "posted with image; confirm live via independent read."
        elif errors:
            out["error"] = errors[0].get("message", "GraphQL validation error")
        else:
            out["error"] = f"post failed (HTTP {r.status_code}) — {r.text[:150]}"
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
        errors = self._gql_errors(r)
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
        # Same false-success trap as create_post: a 200 can carry a GraphQL ValidationError.
        errors = self._gql_errors(r)
        ok = r.status_code in (200, 201) and not errors
        out = {"status": r.status_code, "ok": ok}
        if errors:
            out["error"] = errors[0].get("message", "GraphQL validation error")
            return out
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
        """Instant repost ("Sofort teilen") — SDUI createInstantRepost.
        NOTE: this SDUI action can 500 on a plain vgreq replay (needs the currentActor binding
        in the full captured body). Pure API only — no browser. If it 500s, re-capture the full
        SDUI body as a template (same pattern as unlike/react_to_comment) and replay that.
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
            out["note"] = ("repost 500'd on plain replay — re-capture the full SDUI body as a "
                           "template and replay with minimal headers (like unlike). No browser.")
        return out

    # queryId for repost-delete. The deploy hash is MISSING (only the bare family below) and it
    # is in NO capture in this repo — it must never be guessed. Re-grab it by deleting a repost
    # in the real client with tools/capture_write_action.py, then set the full value here.
    _REPOST_DEL_QID = "voyagerFeedDashReposts"

    def delete_repost(self, repost_urn: str) -> dict:
        """Delete a repost via the Voyager GraphQL DELETE-by-key mutation (shape from docs/10).

        NOT OPERATIONAL: _REPOST_DEL_QID carries only the family, not the '.<hash>' suffix every
        queryId needs, so the call would be rejected. Rather than send a doomed request (and
        report its failure as a transport problem), this refuses up front — nothing is sent.
        repost_urn: urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:<shareId>,<repostId>).
        """
        if not self._qid_has_hash(self._REPOST_DEL_QID):
            return {"status": "not_configured", "ok": False, "retryable": False,
                    "repost_urn": repost_urn, "endpoint": "voyager.graphql.reposts.delete",
                    "note": ("delete_repost is not ready for use: the queryId is the bare family "
                             f"'{self._REPOST_DEL_QID}' with no '.<hash>' suffix, and the hash is "
                             "in no capture in this repo. NOTHING was sent and retrying will not "
                             "help. Re-capture it with tools/capture_write_action.py (delete a "
                             "repost in the real client), then set _REPOST_DEL_QID to the "
                             "captured voyagerFeedDashReposts.<hash>.")}
        url = f"{BASE}/graphql?action=execute&queryId={self._REPOST_DEL_QID}"
        body = {"variables": {"resourceKey": repost_urn},
                "queryId": self._REPOST_DEL_QID, "includeWebMetadata": True}
        r = self._vg().post(url, body)
        # Same false-success trap as create_post: a 200 can carry a GraphQL ValidationError.
        errors = self._gql_errors(r)
        ok = r.status_code in (200, 201, 204) and not errors
        out = {"status": r.status_code, "ok": ok, "repost_urn": repost_urn}
        if errors:
            out["error"] = errors[0].get("message", "GraphQL validation error")
        return out
