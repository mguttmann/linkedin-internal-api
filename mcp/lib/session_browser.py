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


if __name__ == "__main__":  # manual smoke (needs a display + human login)
    sb = SessionBrowser().start()
    print("logged in?", sb.is_logged_in())
    if sb.is_logged_in():
        print("cookies:", sorted(sb.cookies())[:5], "…")
        print("dumped:", sb.dump_cookies())
    sb.stop()
