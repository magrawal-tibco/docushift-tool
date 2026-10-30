"""Phase 63 pilot: rewrite each published 301 `to` onto stg-docs.ibi.com and resolve it
against the published repo -- page exists, anchor exists. Writes a CSV per run.

usage: python -I check_301_staging.py <repo-root> <product> <out.csv> [version ...]
"""
import csv
import re
import sys
from pathlib import Path

import yaml
sys.path.insert(0, "src")
from docushift.utils.anchors import slugify_heading as slug

STAGING = "https://stg-docs.ibi.com/"
repo, product, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
versions = set(sys.argv[4:])
base = repo / "en-us" / product / "online-help"
prefix = f"us/en/{product}/online-help/"


def _old_slug(text: str) -> str:
    text = re.sub(r"\{#[^}]*\}|<[^>]+>|`", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


anchors: dict[Path, set[str]] = {}


def anchors_of(page: Path) -> set[str]:
    if page not in anchors:
        found, seen = set(), {}
        for line in page.read_text(encoding="utf-8", errors="replace").splitlines():
            for m in re.finditer(r"""(?:id|name)=["']([^"']+)["']|\{#([^}\s]+)\}""", line):
                found.add(m.group(1) or m.group(2))
            h = re.match(r"#{1,6}\s+(.*)", line)
            if h:
                s = slug(h.group(1))
                n = seen.get(s, 0)
                seen[s] = n + 1
                found.add(s if n == 0 else f"{s}-{n}")
        anchors[page] = found
    return anchors[page]


rows = yaml.safe_load((base / "301.yml").read_text(encoding="utf-8"))["redirects"]
results = []
for r in rows:
    to = r["to"]
    path, _, frag = to.partition("#")
    ver = path[len(prefix):].split("/", 1)[0] if path.startswith(prefix) else "?"
    if versions and ver not in versions:
        continue
    if not path.startswith(prefix):
        status = "BAD_PREFIX"
    else:
        rel = path[len(prefix):]
        page = base / (rel[:-5] + ".md" if rel.endswith(".html") else rel)
        if not page.is_file():
            status = "NO_PAGE"
        elif frag and frag not in anchors_of(page):
            status = "NO_ANCHOR"
        else:
            status = "OK"
    results.append({"version": ver, "status": status, "from": r["from"],
                    "staging_to": STAGING + to, "len": len(path) + len(STAGING)})

out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0]))
    w.writeheader()
    w.writerows(results)

from collections import Counter
for (v, s), n in sorted(Counter((x["version"], x["status"]) for x in results).items()):
    print(f"{v}\t{s}\t{n}")
print("longest staging URL:", max(x["len"] for x in results))
froms = Counter(x["from"] for x in results)
print("duplicate from:", sum(1 for n in froms.values() if n > 1))
