"""session_daemon.py — keep the persistent stealth session alive for capture tooling.

Starts the patchright persistent context on CDP port 9222 and holds it open so that
tools/capture_session.py (which attaches over CDP /json) can drive it — this is the bridge
that puts the whole audit on the stealth, always-logged-in session.

Run as a background process:
    .venv/bin/python session_daemon.py
It prints READY when the session is up + logged in, refreshes /tmp/li_cookies.json, then idles.
SIGTERM/Ctrl-C to stop (flushes cookies to disk on exit).
"""
import sys, os, time, signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.session_browser import SessionBrowser

PROFILE = os.path.expanduser("~/.hermes/li-mcp-profile")
_stop = False


def _handle(*_):
    global _stop
    _stop = True


def main():
    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    sb = SessionBrowser(profile_dir=PROFILE, headless=False, cdp_port=9222)
    sb.start()
    if not sb._has_li_at():
        print("NOT_LOGGED_IN run bootstrap_login.py first", flush=True)
        sb.stop()
        return 1
    ok = sb.is_logged_in()
    sb.dump_cookies("/tmp/li_cookies.json")
    print(f"READY logged_in={ok} cdp=9222 cookies=/tmp/li_cookies.json", flush=True)

    # idle loop; refresh cookies periodically so vgreq stays fresh
    last = time.time()
    while not _stop:
        time.sleep(1)
        if time.time() - last > 300:  # every 5 min
            try:
                sb.dump_cookies("/tmp/li_cookies.json")
            except Exception as e:
                print(f"[warn] cookie refresh: {e}", flush=True)
            last = time.time()

    sb.stop()
    print("STOPPED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
