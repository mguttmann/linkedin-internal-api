#!/usr/bin/env python3
"""tests/test_capture_session.py — canonical verification for the capture tooling.

No pytest dependency: plain asserts + a __main__ runner so it works with just
`python3 tests/test_capture_session.py` (exit 0 = green). Covers the pure logic of
CaptureSession (tab/lock/click_label/capture_reads) WITHOUT needing a live browser —
the CDP paths are exercised in real audit runs, not here.
"""
import sys, os, inspect, time, importlib

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "tools"))
import capture_session as cs  # noqa: E402


def _fake():
    """A CaptureSession shell that skips CDP __init__, for testing _drain logic."""
    f = cs.CaptureSession.__new__(cs.CaptureSession)
    f.mutations, f.reads, f.capture_reads, f._resp_hdr = {}, {}, False, {}
    return f


def _ev(method, url):
    return {"method": "Network.requestWillBeSent",
            "params": {"requestId": url, "request": {"method": method, "url": url}}}


def test_api_surface():
    for s in ("CaptureSession", "browser_lock", "_new_tab", "_list_pages"):
        assert hasattr(cs, s), f"missing {s}"
    for m in ("click_xy", "click_label", "focus_tab", "resp_body", "dump",
              "nav", "ev", "pump", "clear", "close", "type_text"):
        assert hasattr(cs.CaptureSession, m), f"missing method {m}"
    assert "new_tab" in inspect.signature(cs.CaptureSession.__init__).parameters


def test_browser_lock():
    # Use an isolated lock path so this never collides with live audit agents
    # holding the real /tmp/li_browser.lock.
    orig = cs._LOCK_PATH
    cs._LOCK_PATH = "/tmp/hermes-test-browser.lock"
    try:
        t0 = time.time()
        with cs.browser_lock(timeout=5):
            pass
        with cs.browser_lock(timeout=5):  # re-acquire after release
            pass
        assert time.time() - t0 < 5
    finally:
        cs._LOCK_PATH = orig


def test_drain_mutations_and_reads():
    f = _fake()
    f._drain(_ev("GET", "https://www.linkedin.com/voyager/api/identity/panels?q=viewer"))
    assert not f.reads, "GET must be ignored by default"
    f._drain(_ev("POST", "https://www.linkedin.com/voyager/api/voyagerSocialDashReactions"))
    assert len(f.mutations) == 1, "POST mutation must be captured"
    f.capture_reads = True
    f._drain(_ev("GET", "https://www.linkedin.com/voyager/api/identity/wvmpCards?q=viewer"))
    assert any("wvmpCards" in u for u in f.reads), "GET must be captured when enabled"
    f._drain(_ev("GET", "https://www.linkedin.com/voyager/api/TrackingPixel"))
    assert not any("TrackingPixel" in u for u in f.reads), "infra GET must be filtered"


def test_click_label_js_is_balanced():
    cap = {}

    class F(cs.CaptureSession):
        def __init__(self):  # skip CDP
            pass

        def ev(self, js):
            cap["js"] = js
            return ""  # simulate "no element found"

        def click_xy(self, x, y):
            pass

    assert F().click_label("Löschen", contains=False) == "not-found"
    js = cap["js"]
    assert js.count("(") == js.count(")"), "unbalanced parens"
    assert js.count("{") == js.count("}"), "unbalanced braces"
    assert '"Löschen"' in js, "needle not embedded"


def test_human_pause_respects_toggle_and_randomizes():
    import time as _t
    # PACING off → no sleep
    cs.PACING = False
    t0 = _t.time(); cs.human_pause("page"); assert _t.time() - t0 < 0.2
    # PACING on → sleeps within the configured band, and varies run-to-run
    cs.PACING = True
    cs.PAUSE_MIN, cs.PAUSE_MAX = 0.05, 0.15   # keep the test fast
    samples = []
    for _ in range(5):
        a = _t.time(); cs.human_pause("page"); samples.append(_t.time() - a)
    assert all(0.04 <= s <= 0.3 for s in samples), f"pause out of band: {samples}"
    assert len(set(round(s, 3) for s in samples)) > 1, "pauses not randomized"
    cs.PACING = False   # leave off for other tests / imports


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
