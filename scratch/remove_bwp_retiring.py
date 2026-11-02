"""DOCOPS-316: remove published bw-plugin versions that are not selected and whose
release_status is retirement-announced (or retired). Deletes the version folders,
their version.yml drop-down rows, and 301.yml / redirects.yml rows pointing into them.

    python scratch/remove_bwp_retiring.py            # dry run
    python scratch/remove_bwp_retiring.py --apply
"""
import csv, os, re, shutil, sys

sys.path.insert(0, "src")
from docushift.utils.slug import version_segment  # noqa: E402

ROOT = "C:/github/tibco-docs-aem/en-us-tib-bw-plugin-userdocs/en-us"
APPLY = "--apply" in sys.argv
STATUSES = {"retirement-announced", "retired"}

rows = list(csv.DictReader(open("config/versions.csv", encoding="utf-8-sig")))
by = {(r["slug"], version_segment(r["version"])): r for r in rows}


def selected(r):
    return r["convert_eligible"] == "true" and r["_status"] not in ("retired", "not-selected")


def drop_rows(path, pred):
    """Remove YAML list items (`- ` blocks) for which pred(block_text) is true."""
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines(keepends=True)
    out, block, removed = [], None, 0
    def flush():
        nonlocal block, removed
        if block is not None:
            if pred("".join(block)):
                removed += 1
            else:
                out.extend(block)
        block = None
    for ln in lines:
        if ln.startswith("- "):
            flush(); block = [ln]
        elif block is not None and ln.startswith("  "):
            block.append(ln)
        else:
            flush(); out.append(ln)
    flush()
    if removed and APPLY:
        open(path, "w", encoding="utf-8", newline="").write("".join(out))
    return removed


targets = []
for prod in sorted(os.listdir(ROOT)):
    pd = os.path.join(ROOT, prod)
    if not os.path.isdir(pd):
        continue
    for dc in sorted(os.listdir(pd)):
        dd = os.path.join(pd, dc)
        if not os.path.isdir(dd):
            continue
        for seg in sorted(os.listdir(dd)):
            r = by.get((prod, seg))
            if os.path.isdir(os.path.join(dd, seg)) and r and not selected(r) and r["release_status"] in STATUSES:
                targets.append((prod, dc, seg, r["version"]))

versions = sorted({(p, v) for p, _, _, v in targets})
print(f"{len(versions)} versions, {len(targets)} version folders")
for p, v in versions:
    print(f"  {p} {v}")

counts = {"version.yml": 0, "301.yml": 0, "redirects.yml": 0}
for prod, dc, seg, _ in targets:
    dd = os.path.join(ROOT, prod, dc)
    if APPLY:
        shutil.rmtree(os.path.join(dd, seg))
    vy = os.path.join(dd, "version.yml")
    if os.path.exists(vy):
        counts["version.yml"] += drop_rows(vy, lambda b: re.search(rf'path:\s*"?/{re.escape(seg)}"?\s*$', b, re.M))
    for name, prefix in (("301.yml", f"/en-us/{prod}/{dc}/{seg}/"), ("redirects.yml", f"us/en/{prod}/{dc}/{seg}/")):
        f = os.path.join(dd, name)
        if os.path.exists(f):
            counts[name] += drop_rows(f, lambda b, p=prefix: re.search(rf"^\s*to:\s*{re.escape(p)}", b, re.M))
print("rows removed:", counts)

# doc-classes left with no version folder
for prod in sorted({t[0] for t in targets}):
    for dc in sorted({t[1] for t in targets if t[0] == prod}):
        dd = os.path.join(ROOT, prod, dc)
        left = [s for s in os.listdir(dd) if os.path.isdir(os.path.join(dd, s))] if os.path.isdir(dd) else []
        gone = {t[2] for t in targets if t[0] == prod and t[1] == dc}
        if not (set(left) - (gone if not APPLY else set())):
            print("doc-class left empty:", prod, dc)
print("APPLIED" if APPLY else "dry run")
