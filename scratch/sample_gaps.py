"""Print a few real heading-skip offenders per family, with their heading runs,
so the census in `scan_dt_headings.py` can be read against actual pages.

Run: python scratch/sample_gaps.py
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path("families")
HEAD = re.compile(r"<h([1-6])\b[^>]*>(.{0,200}?)</h\1>", re.IGNORECASE | re.DOTALL)
TAG = re.compile(r"<[^>]+>")


def skips(levels: list[int]) -> bool:
    previous = 0
    for level in levels:
        if previous and level > previous + 1:
            return True
        previous = level
    return False


for family in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    shown = 0
    for path in family.rglob("*.htm*"):
        if shown >= 3:
            break
        text = path.read_text(encoding="utf-8", errors="replace")
        found = [(int(n), TAG.sub("", t).strip()) for n, t in HEAD.findall(text)]
        if not skips([level for level, _ in found]):
            continue
        shown += 1
        print(f"\n--- {path} ---")
        for level, title in found[:25]:
            print(f"  h{level}  {title[:60]}")
