#!/usr/bin/env python3
"""gen_endpoints_md.py — regenerate docs/ENDPOINTS.md from the endpoint data files.

Reads data/endpoints_voyager.json + data/endpoints_sdui.json, groups by area, and emits the full
reference table. The hand-verified WRITE table at the top is kept in this script (it's curated,
not auto-discovered). Run from the repo root:  python3 tools/gen_endpoints_md.py
"""
import json
import os
import re
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def clean_family(f: str) -> str:
    return re.sub(r"\.[a-f0-9]{20,}", " .<hash>", f)


def area_table(entries) -> str:
    by_area = defaultdict(list)
    for e in entries:
        by_area[e.get("area") or "Misc"].append(e)
    out = []
    total_distinct = 0
    for area in sorted(by_area, key=lambda a: (-len(by_area[a]), a)):
        # dedupe by (method, family-without-hash) so the subtotal matches the rendered rows
        seen = set()
        rows = []
        for e in sorted(by_area[area], key=lambda x: x["family"]):
            fam = clean_family(e["family"])
            key = (e["method"], fam)
            if key in seen:
                continue
            seen.add(key)
            rows.append(f"| {e['method']} | {e['type']} | `{fam}` |")
        total_distinct += len(rows)
        out.append(f"\n### {area} ({len(rows)})\n")
        out.append("| Method | Type | Endpoint |")
        out.append("|---|---|---|")
        out.extend(rows)
    return "\n".join(out), total_distinct


# Curated, hand-verified write/action table (not auto-discovered).
WRITES = open(os.path.join(REPO, "tools", "_endpoints_writes.md")).read() \
    if os.path.exists(os.path.join(REPO, "tools", "_endpoints_writes.md")) else ""


def main():
    v = json.load(open(os.path.join(REPO, "data", "endpoints_voyager.json")))
    s = json.load(open(os.path.join(REPO, "data", "endpoints_sdui.json")))
    v_table, v_distinct = area_table(v)
    s_table, s_distinct = area_table(s)
    raw_total = len(v) + len(s)
    distinct_total = v_distinct + s_distinct
    header = (
        "# ENDPOINTS — full reference\n\n"
        "Complete inventory of every LinkedIn internal endpoint captured for this project: "
        f"**{raw_total} raw captured requests** ({len(v)} Voyager + {len(s)} SDUI) which dedupe to "
        f"**{distinct_total} distinct endpoint families** (the same family often appears under several "
        "rotating GraphQL query-id hashes), plus the **verified write/action endpoints** below.\n\n"
        "- **Voyager** = `/voyager/api/…` REST.li + GraphQL. Auth: cookies + csrf-token "
        "(see `01-AUTH-AND-COOKIES.md`).\n"
        "- **SDUI** = `/flagship-web/rsc-action/…` server-driven UI actions (POST with a `requestId` body).\n"
        "- GraphQL `queryId` hashes rotate on LinkedIn deploys — re-capture if a call starts 404-ing.\n\n"
        "> Auto-generated from `data/endpoints_*.json` + the curated write table. "
        "Regenerate: `python3 tools/gen_endpoints_md.py`.\n\n---\n"
    )
    body = header + WRITES + "\n---\n\n## All discovered READ endpoints\n"
    body += f"\n## Voyager ({v_distinct} distinct / {len(v)} raw)\n" + v_table
    body += f"\n\n## SDUI ({s_distinct} distinct / {len(s)} raw)\n" + s_table
    with open(os.path.join(REPO, "docs", "ENDPOINTS.md"), "w") as f:
        f.write(body)
    print(f"docs/ENDPOINTS.md written: {len(body)} chars, "
          f"{raw_total} raw / {distinct_total} distinct endpoints")


if __name__ == "__main__":
    main()
