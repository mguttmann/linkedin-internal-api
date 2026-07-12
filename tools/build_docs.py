#!/usr/bin/env python3
"""build_docs.py — Builds endpoint catalogs + markdown docs from the raw captures.

Reads ALL captures, deduplicates by endpoint family, classifies by area and layer
(Voyager/SDUI), and writes:
  - data/endpoints_voyager.json  (machine-readable)
  - data/endpoints_sdui.json     (machine-readable)
  - docs/02-VOYAGER-API.md       (human-readable, grouped by area)

Usage: build_docs.py <capture_glob...> --out <repo_dir>
"""
import json, glob, os, re, sys
from collections import defaultdict

# Verified write endpoints. The crawler only navigates (GET), so these NEVER appear in the
# raw captures — they were found via click-and-record (see docs/05-VERIFICATION.md) and are
# added here so the catalogs stay complete and reproducible across rebuilds.
VERIFIED_WRITES_VOYAGER = [
    {"method": "POST", "family": "voyagerSocialDashReactions", "area": "Feed/Posts",
     "verified": "Set like — HTTP 201"},
    {"method": "POST", "family": "voyagerContentcreationDashShares.<hash>", "area": "Feed/Posts",
     "verified": "Create post — verified (GraphQL)"},
]
VERIFIED_WRITES_SDUI = [
    {"method": "POST", "family": "com.linkedin.sdui.reactions.delete", "area": "Feed/Posts",
     "verified": "Unlike — verified"},
    {"method": "POST", "family": "com.linkedin.sdui.update.deletePost", "area": "Feed/Posts",
     "verified": "Delete post — verified"},
    {"method": "POST", "family": "com.linkedin.sdui.comments.createComment", "area": "Feed/Posts",
     "verified": "Create comment — verified"},
    {"method": "POST", "family": "com.linkedin.sdui.comments.deleteComment", "area": "Feed/Posts",
     "verified": "Delete comment — verified"},
    {"method": "POST", "family": "com.linkedin.sdui.requests.profile.saveProfileIntroForm",
     "area": "Identity/Profile", "verified": "Profile save — schema verified"},
    {"method": "POST", "family": "com.linkedin.sdui.action.sharing.closed-sharebox.server-action",
     "area": "Feed/Posts", "verified": "Post-create follow-up (returns post URN)"},
]

def load_all(paths):
    recs = []
    for p in paths:
        for f in glob.glob(p):
            try:
                data = json.load(open(f))
                if isinstance(data, list):
                    recs.extend(data)
            except Exception:
                pass
    return recs

def area(url, qid=""):
    s = (url + " " + qid).lower()
    checks = [
        ("Identity/Profile", ["identitydash", "identity/dash/profiles", "/me?", "/me ", "profileview"]),
        ("Feed/Posts", ["feeddash", "feed/dash", "profileupdates", "mainfeed", "contentcreation", "sharebox"]),
        ("Messaging", ["messaging", "messenger"]),
        ("Network", ["relationships", "mynetwork", "invitation", "connection"]),
        ("Notifications", ["notification"]),
        ("Search", ["search"]),
        ("Jobs", ["jobs", "jobseeker", "careers"]),
        ("Organization", ["organization", "company"]),
        ("Events", ["events"]),
        ("Groups", ["groups"]),
        ("Premium", ["premium"]),
        ("Analytics", ["analytics", "premiumdashanalytics", "trafficstatistics"]),
        ("Talentbrand", ["talentbrand"]),
        ("Settings/Other", ["settings", "lego", "launchpad", "globalalerts", "segments", "mysettings"]),
    ]
    for name, keys in checks:
        if any(k in s for k in keys):
            return name
    return "Misc"

def family(r):
    u = r["url"]
    if "/rsc-action/" in u or "/sdui" in u.lower():
        m = re.search(r"sduiid=([^&]+)", u)
        return ("SDUI", m.group(1) if m else "rsc-action")
    if "queryId=" in u:
        return ("GQL", u.split("queryId=")[1].split("&")[0])  # with hash
    base = u.split("?")[0].split("/voyager/api/")[-1]
    return ("REST", base)

def main():
    repo = os.path.dirname(os.path.abspath(__file__)) + "/.."
    if "--out" in sys.argv:
        repo = sys.argv[sys.argv.index("--out")+1]
    caps = [a for a in sys.argv[1:] if not a.startswith("--") and a != repo]
    if not caps:
        caps = [os.path.join(repo, "..", "api-docs", "_captures", "2026*.json"),
                os.path.join(repo, "..", "api-docs", "_captures2", "recursive.json")]
    recs = load_all(caps)

    voyager = {}
    sdui = {}
    for r in recs:
        if not r.get("url"): continue
        typ, fam = family(r)
        qid = fam if typ == "GQL" else ""
        rec = {
            "method": r.get("method"), "layer": ("SDUI" if typ=="SDUI" else "VOYAGER"),
            "type": typ, "family": fam, "url_sample": r["url"][:200],
            "area": area(r["url"], qid),
            "response_len": r.get("response_len"),
            "postData": (r.get("postData") or "")[:200] if r.get("postData") else None,
        }
        key = (r.get("method"), typ, fam)
        if typ == "SDUI":
            sdui.setdefault(key, rec)
        else:
            voyager.setdefault(key, rec)

    # Merge in the verified write endpoints (not present in GET-only crawl captures)
    for w in VERIFIED_WRITES_VOYAGER:
        typ = "GQL" if ".<hash>" in w["family"] or "queryId" in w["family"] else "REST"
        rec = {"method": w["method"], "layer": "VOYAGER", "type": typ, "family": w["family"],
               "url_sample": "", "area": w["area"], "response_len": None, "postData": None,
               "verified": w["verified"]}
        voyager.setdefault((w["method"], typ, w["family"]), rec)
    for w in VERIFIED_WRITES_SDUI:
        rec = {"method": w["method"], "layer": "SDUI", "type": "SDUI", "family": w["family"],
               "url_sample": "", "area": w["area"], "response_len": None, "postData": None,
               "verified": w["verified"]}
        sdui.setdefault((w["method"], "SDUI", w["family"]), rec)

    os.makedirs(os.path.join(repo, "data"), exist_ok=True)
    json.dump([v for v in voyager.values()], open(os.path.join(repo,"data","endpoints_voyager.json"),"w"),
              ensure_ascii=False, indent=2)
    json.dump([v for v in sdui.values()], open(os.path.join(repo,"data","endpoints_sdui.json"),"w"),
              ensure_ascii=False, indent=2)

    # Markdown Voyager catalog, grouped by area
    by_area = defaultdict(list)
    for v in voyager.values():
        by_area[v["area"]].append(v)
    order = ["Identity/Profile","Feed/Posts","Messaging","Network","Notifications",
             "Search","Jobs","Organization","Events","Groups","Premium","Analytics",
             "Talentbrand","Settings/Other","Misc"]
    out = ["# 02 — Voyager API — Endpoint Catalog\n",
           f"\n> Auto-generated from live captures. **{len(voyager)} unique Voyager endpoints** "
           f"(REST + GraphQL, incl. hash variants), **{len(sdui)} SDUI actions** (see 03-SDUI-API.md).\n",
           "\nEvery GraphQL `queryId` has the form `<queryName>.<hash>`. The hash changes on "
           "LinkedIn deployments — the queryName stays stable.\n"]
    for a in order:
        items = by_area.get(a)
        if not items: continue
        out.append(f"\n## {a}\n\n*{len(items)} endpoints*\n\n")
        items.sort(key=lambda x: (x["type"], x["family"]))
        for v in items:
            name = v["family"]
            out.append(f"### `{name}`\n")
            out.append(f"- **Method:** `{v['method']}` · **Type:** {v['type']}\n")
            if v.get("verified"):
                out.append(f"- **✅ Verified write:** {v['verified']}\n")
            if v["response_len"]:
                out.append(f"- **Response size (sample):** {v['response_len']} B\n")
            if v["postData"]:
                out.append(f"- **Body sample:** `{v['postData']}`\n")
            out.append("\n")
    open(os.path.join(repo,"docs","02-VOYAGER-API.md"),"w").write("".join(out))

    print(f"Voyager: {len(voyager)} | SDUI: {len(sdui)}")
    print("Areas:", {a: len(by_area[a]) for a in order if by_area.get(a)})

if __name__ == "__main__":
    main()
