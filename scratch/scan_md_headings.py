"""Heading-level skips as they actually survive into Markdown.

The HTML census in `scan_dt_headings.py` overcounts: a DocBook `<h3>Caution</h3>`
is an admonition title the engine turns into a callout, never a heading. This
scan reads the emitted `.md` instead, so what it reports is what a reader sees.

Run: python scratch/scan_md_headings.py [root ...]
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")

roots = [pathlib.Path(a) for a in sys.argv[1:]] or [pathlib.Path("output")]

for root in roots:
    gaps = collections.Counter()
    bad_files = []
    total = 0
    for path in root.rglob("*.md"):
        total += 1
        in_fence = False
        levels: list[tuple[int, str]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = HEAD.match(line)
            if match:
                levels.append((len(match.group(1)), match.group(2)))
        previous = 0
        worst = None
        for level, title in levels:
            if previous and level > previous + 1:
                gaps[f"h{previous}->h{level}"] += 1
                worst = worst or (previous, level, title)
            previous = level
        if worst:
            bad_files.append((path, worst))

    print(f"\n===== {root} =====")
    print(f"{len(bad_files)} of {total} files skip a heading level")
    for jump, count in gaps.most_common(20):
        print(f"  {count:6d}  {jump}")
    print("  -- first 15 offenders --")
    for path, (a, b, title) in bad_files[:15]:
        print(f"  h{a}->h{b}  {title[:40]:42} {path}")
