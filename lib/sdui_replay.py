#!/usr/bin/env python3
"""sdui_replay.py — replay a captured SDUI profile-form write WITHOUT a browser.

Proven working for profile CREATE (saveProfileLanguageForm -> HTTP 200, live change).
Idea: take a captured request body (the blueprint), swap the per-session auto-binding uuid
for a fresh one, set the real values in the top-level `states[]`, and POST via vgreq.

Usage:
    from sdui_replay import replay_form, load_capture
    entry = load_capture('<your-capture>.json', 'saveProfileLanguageForm')  # a capture list
    replay_form(entry, value_overrides={'...Formname...': 'Latein'})

See docs/BROWSERLESS-REPLAY.md for the full findings and caveats (typeahead ids, delete
states[]).
"""
import json, uuid, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
import vgreq

_UUID_RE = re.compile(r"auto-binding-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

def _swap_uuid(raw: str) -> str:
    """Replace every auto-binding-<uuid> with ONE fresh uuid (keeps intra-request refs consistent)."""
    new = f"auto-binding-{uuid.uuid4()}"
    return _UUID_RE.sub(new, raw)

def full_url(capture_entry: dict) -> str:
    u = capture_entry["url"]
    return "https://www.linkedin.com/" + u.split("linkedin.com/")[1]

def replay_form(capture_entry: dict, value_overrides: dict | None = None, dry_run: bool = False):
    """Replay one captured SDUI form POST. `value_overrides` maps a substring of a states[]
    key -> new value. Returns the requests.Response (or the rebuilt body if dry_run)."""
    raw = _swap_uuid(capture_entry["postData"])
    body = json.loads(raw)
    if value_overrides:
        for st in body.get("states", []):
            for needle, val in value_overrides.items():
                if needle in st.get("key", ""):
                    st["value"] = val
    if dry_run:
        return body
    return vgreq.post(full_url(capture_entry), body=json.dumps(body),
                      extra_headers={"accept": "application/json"})

def load_capture(path: str, sduiid_needle: str) -> dict:
    """Pick the one entry whose url contains sduiid_needle from a saved capture list."""
    for m in json.load(open(path)):
        if sduiid_needle in (m.get("url") or ""):
            return m
    raise KeyError(sduiid_needle)

if __name__ == "__main__":
    # demo: dry-run rebuild of a language add (no network)
    e = load_capture(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "saveProfile")
    print(json.dumps(replay_form(e, dry_run=True), ensure_ascii=False)[:600])
