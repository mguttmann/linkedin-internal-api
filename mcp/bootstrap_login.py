"""bootstrap_login.py — open the patchright stealth window and wait for a one-time human login.

Keeps the persistent context alive, polls for li_at non-invasively (never navigates the page
out from under the user), and on success dumps cookies + confirms the session, then keeps
running so the profile stays warm. Ctrl-C or SIGTERM to stop.
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.session_browser import SessionBrowser

PROFILE = os.path.expanduser("~/.hermes/li-mcp-profile")
LOGIN_URL = "https://www.linkedin.com/login"

def main():
    sb = SessionBrowser(profile_dir=PROFILE, headless=False, cdp_port=9222)
    sb.start()
    # send the user straight to the login page
    try:
        sb.page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"[warn] initial nav: {e}", flush=True)
    print("WINDOW_OPEN: patchright stealth window is up — please log in in that window.", flush=True)

    # poll non-invasively for li_at (cookie presence only, no navigation)
    logged = False
    for _ in range(600):  # up to ~30 min
        if sb._has_li_at():
            logged = True
            break
        time.sleep(3)

    if logged:
        # let LinkedIn finish setting session cookies, then persist + verify
        time.sleep(3)
        path = sb.dump_cookies("/tmp/li_cookies.json")
        ok = sb.is_logged_in()
        print(f"LOGIN_OK li_at persisted; cookies={path}; feed_loads={ok}", flush=True)
    else:
        print("LOGIN_TIMEOUT no li_at after 30min", flush=True)

    # keep the context alive so the profile stays warm (background process)
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        sb.stop()

if __name__ == "__main__":
    main()
