"""Remove named published versions from TIBCO repos (DOCOPS-323; the DOCOPS-316 method).

For each (repo, slug, version): delete every `<doc-class>/<segment>` folder, its row in that
doc-class's `version.yml`, and the `301.yml` / `redirects.yml` rows pointing into it. A doc-class
left with no version folder is reported, not removed.

    python scratch/remove_versions.py            # dry run
    python scratch/remove_versions.py --apply
"""
import os
import re
import shutil
import sys

sys.path.insert(0, "src")
from docushift.utils.slug import version_segment  # noqa: E402

TREE = "C:/github/tibco-docs-aem"
APPLY = "--apply" in sys.argv
TARGETS = [
    ("en-us-tib-bw-plugin-userdocs", "tibco-activematrix-businessworks-plug-in-for-mobile-integration", "1.2.2"),
    ("en-us-tib-bw-plugin-userdocs", "tibco-activematrix-businessworks-plug-in-for-mongodb", "6.1.0"),
    ("en-us-tib-bw-plugin-userdocs", "tibco-activematrix-businessworks-plug-in-for-netsuite", "1.1.0"),
    ("en-us-tib-bw-plugin-userdocs", "tibco-activematrix-businessworks-plug-in-for-odata", "6.3.0"),
    ("en-us-tib-businessconnect-userdocs", "tibco-businessconnect-trading-community-management", "6.1.1"),
    ("en-us-tib-mainframe-userdocs", "tibco-mainframe-red", "2.5.1"),
]


def drop_rows(path, pred):
    """Remove YAML list items (`- ` blocks) for which pred(block_text) is true."""
    text = open(path, encoding="utf-8").read()
    out, block, removed = [], None, 0

    def flush():
        nonlocal block, removed
        if block is not None:
            if pred("".join(block)):
                removed += 1
            else:
                out.extend(block)
        block = None

    for line in text.splitlines(keepends=True):
        if line.startswith("- "):
            flush()
            block = [line]
        elif block is not None and line.startswith("  "):
            block.append(line)
        else:
            flush()
            out.append(line)
    flush()
    if removed and APPLY:
        open(path, "w", encoding="utf-8", newline="").write("".join(out))
    return removed


totals = {"folders": 0, "version.yml": 0, "301.yml": 0, "redirects.yml": 0}
for repo, slug, version in TARGETS:
    seg = version_segment(version)
    product = os.path.join(TREE, repo, "en-us", slug)
    found = 0
    for dc in sorted(os.listdir(product)):
        dd = os.path.join(product, dc)
        if not os.path.isdir(os.path.join(dd, seg)):
            continue
        found += 1
        totals["folders"] += 1
        if APPLY:
            shutil.rmtree(os.path.join(dd, seg))
        vy = os.path.join(dd, "version.yml")
        if os.path.exists(vy):
            totals["version.yml"] += drop_rows(vy, lambda b, s=seg: re.search(rf'path:\s*"?/{re.escape(s)}"?\s*$', b, re.M))
        for name, prefix in (("301.yml", f"/en-us/{slug}/{dc}/{seg}/"), ("redirects.yml", f"us/en/{slug}/{dc}/{seg}/")):
            f = os.path.join(dd, name)
            if os.path.exists(f):
                totals[name] += drop_rows(f, lambda b, p=prefix: re.search(rf"^\s*to:\s*{re.escape(p)}", b, re.M))
        left = [s for s in os.listdir(dd) if os.path.isdir(os.path.join(dd, s)) and (APPLY or s != seg)]
        if not left:
            print("  doc-class left with no version:", repo, slug, dc)
    print(f"{repo} {slug} {version}: {found} folder(s)")
print("totals:", totals, "| APPLIED" if APPLY else "| dry run")
