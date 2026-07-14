"""session_browser.py — persistent, stealth LinkedIn session via patchright.

Solves the failure mode we hit during the audit: when a hand-started Chrome crashes, the
LinkedIn session logs out and a human has to log back in. patchright's persistent context keeps
the profile logged in across restarts AND stays undetected (Cloudflare/bot-detection).

Design principle (see docs/MCP-DESIGN.md): this browser is the SESSION SOURCE and the
BROWSER-FALLBACK executor — NOT the hot path. Reads/writes go through pure requests (vgreq)
using the cookies this class dumps.

Usage:
    sb = SessionBrowser()
    sb.start()                       # launches persistent Chrome (first run: human logs in once)
    if not sb.is_logged_in():
        ...                          # surface "please log in" to the MCP client
    cookies = sb.cookies()           # dict for vgreq
    sb.dump_cookies("/tmp/li_cookies.json")
    sb.stop()
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

# patchright is a drop-in Playwright replacement; import guarded so the module can be
# imported (and unit-tested) even where the browser driver isn't installed.
try:
    from patchright.sync_api import sync_playwright  # type: ignore
    _HAVE_PATCHRIGHT = True
except Exception:  # pragma: no cover
    sync_playwright = None  # type: ignore
    _HAVE_PATCHRIGHT = False


DEFAULT_PROFILE_DIR = os.path.expanduser("~/.hermes/li-mcp-profile")
FEED_URL = "https://www.linkedin.com/feed/"
ME_URL = "https://www.linkedin.com/voyager/api/me"


class NotLoggedInError(RuntimeError):
    """Raised when the persistent session is not authenticated to LinkedIn."""


class SessionBrowser:
    """A persistent, stealth Chrome context that stays logged in to LinkedIn.

    Per patchright best practice: real Chrome via channel="chrome", persistent user_data_dir,
    no custom user_agent / headers, no_viewport. Do NOT tweak the fingerprint — that's what
    keeps it undetected.
    """

    def __init__(self, profile_dir: str = DEFAULT_PROFILE_DIR, headless: bool = False,
                 cdp_port: Optional[int] = None):
        self.profile_dir = profile_dir
        self.headless = headless
        self.cdp_port = cdp_port  # if set, expose a CDP /json endpoint so our capture tooling can attach
        self._pw = None
        self._ctx = None
        self._page = None

    # --- lifecycle -------------------------------------------------------
    def start(self) -> "SessionBrowser":
        if not _HAVE_PATCHRIGHT:
            raise RuntimeError(
                "patchright not available — run `patchright install chromium` in the mcp venv"
            )
        assert sync_playwright is not None
        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        # launch_persistent_context: the whole point — cookies survive restarts.
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            channel="chrome",
            headless=self.headless,
            no_viewport=True,
            # expose CDP AND allow our capture tooling's WS origin (else 403 on the ws handshake)
            args=([f"--remote-debugging-port={self.cdp_port}",
                   f"--remote-allow-origins=http://127.0.0.1:{self.cdp_port}"]
                  if self.cdp_port else []),
            # deliberately NO user_agent / extra headers (patchright stealth rule)
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def stop(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._ctx = self._page = self._pw = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # --- auth ------------------------------------------------------------
    def is_logged_in(self, timeout_s: float = 12.0) -> bool:
        """True if the persistent profile currently has a valid LinkedIn session.

        Checks for the li_at cookie AND that /feed doesn't bounce to /login.
        """
        if not self._page:
            raise RuntimeError("call start() first")
        names = {c["name"] for c in self._ctx.cookies()}
        if "li_at" not in names:
            return False
        self._page.goto(FEED_URL, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        time.sleep(1.5)
        return "/login" not in (self._page.url or "")

    def _has_li_at(self) -> bool:
        """Non-invasive check: is the li_at cookie present? Does NOT navigate (safe to poll
        while a human is typing credentials in the window)."""
        if not self._ctx:
            return False
        return "li_at" in {c["name"] for c in self._ctx.cookies()}

    def wait_for_login(self, poll_s: float = 3.0, max_wait_s: float = 300.0) -> bool:
        """Block until the human has logged in in the visible window (first-run helper).
        Polls cookie presence only — never navigates the page out from under the user."""
        deadline = time.time() + max_wait_s
        while time.time() < deadline:
            if self._has_li_at():
                return True
            time.sleep(poll_s)
        return False

    # --- cookies (the product) ------------------------------------------
    def cookies(self) -> dict:
        """Return the current LinkedIn cookies as a {name: value} dict for vgreq."""
        if not self._ctx:
            raise RuntimeError("call start() first")
        jar = {c["name"]: c["value"] for c in self._ctx.cookies()
               if "linkedin.com" in c.get("domain", "")}
        if "li_at" not in jar:
            raise NotLoggedInError("no li_at cookie — session not logged in")
        return jar

    def inject_cookies(self, jar: dict, domain: str = ".linkedin.com",
                       settle: bool = True) -> int:
        """Seed the persistent context with an existing {name: value} cookie jar.

        Use this to carry a still-valid session (e.g. from /tmp/li_cookies.json) into the
        patchright profile WITHOUT a fresh login. Because this is a persistent context, the
        cookies get written to disk and survive restarts. Returns the count injected.

        httpOnly cookies (li_at) added via add_cookies are NOT reliably flushed to the
        persistent SQLite store on their own. With settle=True we then load /feed so the
        server re-affirms the session via Set-Cookie — THAT write persists across restarts.
        """
        if not self._ctx:
            raise RuntimeError("call start() first")
        secure_httponly = {"li_at", "JSESSIONID", "bscookie", "li_gc"}
        items = [{
            "name": n, "value": v, "domain": domain, "path": "/",
            "secure": True,
            "httpOnly": n in secure_httponly,
        } for n, v in jar.items() if v]
        self._ctx.add_cookies(items)
        if settle and self._page:
            # real navigation -> server Set-Cookie -> persistent write of li_at
            self._page.goto(FEED_URL, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2.0)
        return len(items)

    def dump_cookies(self, path: str = "/tmp/li_cookies.json") -> str:
        """Write cookies to disk in the shape vgreq expects. Returns the path."""
        jar = self.cookies()
        Path(path).write_text(json.dumps(jar, indent=2))
        return path

    # --- browser-fallback executor (P4: SDUI form flows) ----------------
    @property
    def page(self):
        """Raw patchright page, for the few SDUI form flows requests can't replay yet."""
        if not self._page:
            raise RuntimeError("call start() first")
        return self._page

    def post_comment_ui(self, activity_urn: str, text: str, timeout_ms: int = 30000) -> dict:
        """Post a TOP-LEVEL comment by driving the real UI (the only reliable way).

        createComment can't be POST-replayed: LinkedIn binds the text to a server-side
        state key (commentBoxText-<...>, MemoryNamespace) that only exists once the comment
        box has rendered. So we open the post, focus the comment editor, type like a human,
        and click the submit button. Returns {ok, status, note}. Requires a live session.
        """
        if not self._page:
            raise RuntimeError("call start() first")
        import random
        page = self._page
        activity_id = activity_urn.split(":")[-1]
        page.goto(f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
                  wait_until="domcontentloaded", timeout=timeout_ms)
        time.sleep(3.0)
        # focus the top-level comment editor (first contenteditable comment box under the post)
        editor = page.locator(
            '.comments-comment-box [contenteditable="true"], '
            '[contenteditable="true"][aria-label*="Kommentar"], '
            '[contenteditable="true"][aria-label*="omment"], '
            '.tiptap.ProseMirror[contenteditable="true"]'
        ).first
        editor.wait_for(state="visible", timeout=timeout_ms)
        editor.scroll_into_view_if_needed()
        editor.click()
        time.sleep(random.uniform(0.6, 1.2))
        # type char-by-char with jitter (human pacing)
        for ch in text:
            page.keyboard.type(ch)
            time.sleep(random.uniform(0.02, 0.09))
        time.sleep(random.uniform(1.0, 1.8))
        # the submit button appears once there's text; match DE + EN labels
        btn = page.locator(
            'button.comments-comment-box__submit-button--cr, '
            'button.comments-comment-box__submit-button, '
            'button:has-text("Kommentieren"), button:has-text("Comment")'
        ).first
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        time.sleep(3.0)
        return {"ok": True, "status": 200, "note": "submitted via UI — verify with get_post_comments"}

    def delete_comment_ui(self, activity_urn: str, comment_text: str = "",
                          comment_id: str = "", timeout_ms: int = 30000) -> dict:
        """Delete one of the owner's comments by driving the UI (deleteComment 500s on replay,
        same currentActor issue as create).

        Locates the comment by its VISIBLE TEXT (comment_text) — NOT by numeric id. The raw
        comment id never appears as an href/data-id in the SDUI-rendered DOM, so the old
        id-based search always timed out. We match the text, walk up to the comment container,
        hover to reveal its ⋯ options button, open the menu, click Delete, and confirm.

        comment_text: the visible text (or a distinctive substring) of the comment to delete.
        comment_id: accepted for backwards-compat / logging only; not used for locating.
        Returns {ok, status, note}.
        """
        if not self._page:
            raise RuntimeError("call start() first")
        if not comment_text:
            return {"ok": False, "status": None,
                    "note": "comment_text required — the browser fallback locates the comment "
                            "by visible text (the numeric id is not in the rendered DOM)"}
        import random
        page = self._page
        activity_id = activity_urn.split(":")[-1]
        page.goto(f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
                  wait_until="domcontentloaded", timeout=timeout_ms)
        time.sleep(3.0)
        # locate the comment by its visible text, scrolling the comments area until it renders
        text_node = page.get_by_text(comment_text, exact=False).first
        found = False
        for _ in range(8):
            try:
                if text_node.count():
                    found = True
                    break
            except Exception:
                pass
            page.mouse.wheel(0, 1400); time.sleep(1.0)
            text_node = page.get_by_text(comment_text, exact=False).first
        if not found:
            return {"ok": False, "status": None,
                    "note": f"comment matching text {comment_text!r} not found in DOM to delete"}
        text_node.scroll_into_view_if_needed()
        # walk up to the comment container (article.comments-comment-entity or the comment-item div)
        article = text_node.locator(
            "xpath=ancestor-or-self::*[contains(@class,'comments-comment-entity') "
            "or contains(@class,'comments-comment-item')][1]"
        ).first
        try:
            article.wait_for(state="visible", timeout=8000)
        except Exception:
            # fall back to the nearest article ancestor
            article = text_node.locator("xpath=ancestor::article[1]").first
        article.scroll_into_view_if_needed()
        # hover to reveal the ⋯ options control (it's hidden until hover on many layouts)
        try:
            article.hover()
        except Exception:
            pass
        time.sleep(random.uniform(0.4, 0.8))
        # open the ⋯ options menu within this comment (DE 'Kommentaroptionen'/'Optionen', EN 'options'/'More')
        menu_btn = article.locator(
            'button[aria-label*="Kommentaroptionen"], button[aria-label*="ptionen"], '
            'button[aria-label*="options"], button[aria-label*="Options"], '
            'button[aria-label*="More"], button.comments-comment-options-dropdown__trigger, '
            'button[aria-haspopup="true"]'
        ).first
        menu_btn.wait_for(state="visible", timeout=8000)
        menu_btn.click()
        time.sleep(random.uniform(0.6, 1.1))
        # click "Löschen" / "Delete" in the opened dropdown
        page.get_by_role("button", name=re.compile(r"(Löschen|Delete)", re.I)).first.click()
        time.sleep(random.uniform(0.6, 1.1))
        # confirm dialog
        page.get_by_role("button", name=re.compile(r"(Löschen|Delete)", re.I)).last.click()
        time.sleep(2.5)
        return {"ok": True, "status": 200, "note": "deleted via UI — verify with get_post_comments"}


if __name__ == "__main__":  # manual smoke (needs a display + human login)
    sb = SessionBrowser().start()
    print("logged in?", sb.is_logged_in())
    if sb.is_logged_in():
        print("cookies:", sorted(sb.cookies())[:5], "…")
        print("dumped:", sb.dump_cookies())
    sb.stop()
