"""DOCOPS-334: remove one published version from a docs repo, as DOCOPS-316 did
(scratch/remove_bwp_retiring.py) but for exactly the version named, never a
status sweep. Deletes the version folder in every doc-class, its version.yml
drop-down row, and redirects.yml rows pointing into it. A version's 301.yml
lives inside its folder (Phase 72) and goes with it.

    python scratch/remove_published_version.py ROOT SLUG VERSION            # dry run
    python scratch/remove_published_version.py ROOT SLUG VERSION --apply
"""
import os, re, shutil, sys

sys.path.insert(0, "src")
from docushift.utils.slug import version_segment  # noqa: E402

root, slug, version = sys.argv[1:4]
APPLY = "--apply" in sys.argv
seg = version_segment(version)


def drop_rows(path, pred):
    """Remove YAML list items (`- ` blocks) for which pred(block_text) is true."""
    lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
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


pd = os.path.join(root, slug)
counts = {"folders": 0, "version.yml": 0, "redirects.yml": 0}
for dc in sorted(os.listdir(pd)):
    dd = os.path.join(pd, dc)
    if not os.path.isdir(os.path.join(dd, seg)):
        continue
    counts["folders"] += 1
    print("folder:", f"{slug}/{dc}/{seg}")
    if APPLY:
        shutil.rmtree(os.path.join(dd, seg))
    vy = os.path.join(dd, "version.yml")
    if os.path.exists(vy):
        counts["version.yml"] += drop_rows(vy, lambda b: re.search(rf'path:\s*"?/{re.escape(seg)}"?\s*$', b, re.M))
    rd = os.path.join(dd, "redirects.yml")
    if os.path.exists(rd):
        prefix = f"us/en/{slug}/{dc}/{seg}/"
        counts["redirects.yml"] += drop_rows(rd, lambda b: re.search(rf"^\s*(from|to):\s*{re.escape(prefix)}", b, re.M))
    left = [s for s in os.listdir(dd) if os.path.isdir(os.path.join(dd, s)) and s != seg]
    if not left:
        print("doc-class left empty:", dc)
print(counts)
print("APPLIED" if APPLY else "dry run")
