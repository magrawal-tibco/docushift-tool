"""Write a batch file for scratch/overnight.sh (close-out plan, lane A): one verify run per product.

    python scratch/overnight_batch.py <out-file> --target ../tibco-docs-aem/ --bu tibco \
        --family flogo --family hawk ... [--all-versions] [--recheck]

Newest only (default): a line per product whose newest published version is `not-verified` or
`stale` (with --recheck: whatever its status), run as `--product <slug> --latest-only`, so each
process is short. --all-versions: a line per remaining version (`--product --version`) instead,
for Stage 2. Products are written family by family, in the order the families are given.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from docushift.utils.csvio import natural_version_key  # noqa: E402

LEFT = {"not-verified", "stale"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--target", required=True)
    ap.add_argument("--bu", required=True)
    ap.add_argument("--family", action="append", required=True)
    ap.add_argument("--all-versions", action="store_true")
    ap.add_argument("--recheck", action="store_true")
    ap.add_argument("--exclude-product", action="append", default=[])
    a = ap.parse_args()

    with open(ROOT / "config" / "versions.csv", encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["_verify_status"] and r["_bu"] == a.bu and r["slug"] not in a.exclude_product
                # Karan's list (DOCOPS-364): a version declined by hand is removed in K2, never checked.
                and not (r.get("migrate_decision") == "do_not_migrate"
                         and r.get("migrate_decision_source") == "manual")]
    by_product: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_product[(r["_family"], r["slug"])].append(r)

    lines = [f"# {a.bu}: {', '.join(a.family)}"]
    counts = defaultdict(int)
    for family in a.family:
        for (fam, slug), versions in sorted(by_product.items()):
            if fam != family:
                continue
            versions.sort(key=lambda r: natural_version_key(r["version"]))
            if a.all_versions:
                for r in versions[:-1]:          # the newest is Stage 1's
                    if a.recheck or r["_verify_status"] in LEFT:
                        lines.append(f"verify --target-dir {a.target} --product {slug} --version {r['version']}")
                        counts[family] += 1
            elif a.recheck or versions[-1]["_verify_status"] in LEFT:
                # The exact version, not --latest-only: the newest published one may be on
                # Karan's remove list, and --latest-only would still pick it.
                lines.append(f"verify --target-dir {a.target} --product {slug} --version {versions[-1]['version']}")
                counts[family] += 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    for family in a.family:
        print(f"{family:20} {counts[family]:4}")
    print(f"{'total':20} {sum(counts.values()):4}  -> {a.out}")


if __name__ == "__main__":
    main()
