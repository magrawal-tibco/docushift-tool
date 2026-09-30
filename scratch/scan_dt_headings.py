"""One-off corpus scan: how are definition terms tagged, and how often do
heading levels skip a rung? Regex-level, no bs4 -- this is a census, not a parse.

Run: python scratch/scan_dt_headings.py
"""
from __future__ import annotations

import collections
import pathlib
import re

ROOT = pathlib.Path("families")

# <tag ... class="... dt ..." ...>  -- capture the element name and the class list
CLASSED = re.compile(
    r"<(\w+)\b[^>]*\bclass\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
REAL = re.compile(r"<(dl|dt|dd)\b", re.IGNORECASE)
HEAD = re.compile(r"<h([1-6])\b", re.IGNORECASE)

WANTED = {"dl", "dt", "dd", "dlentry", "deflist", "defterm", "term",
          "definition", "varlistentry", "varname", "glossterm"}

by_family_tag = collections.Counter()   # (family, element, class-token) -> files
real_tags = collections.Counter()       # (family, tag) -> files
gaps = collections.Counter()            # (family, "h{a}->h{b}") -> occurrences
files_with_gap = collections.Counter()  # family -> files
files_seen = collections.Counter()      # family -> files

for family in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    for path in family.rglob("*.htm*"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_seen[family.name] += 1

        seen_classed = set()
        for element, classes in CLASSED.findall(text):
            for token in classes.split():
                if token.lower() in WANTED:
                    seen_classed.add((element.lower(), token.lower()))
        for element, token in seen_classed:
            by_family_tag[(family.name, element, token)] += 1

        for tag in {t.lower() for t in REAL.findall(text)}:
            real_tags[(family.name, tag)] += 1

        levels = [int(n) for n in HEAD.findall(text)]
        bad = False
        previous = 0
        for level in levels:
            if previous and level > previous + 1:
                gaps[(family.name, f"h{previous}->h{level}")] += 1
                bad = True
            previous = level
        if bad:
            files_with_gap[family.name] += 1

print("== files scanned ==")
for family, count in sorted(files_seen.items()):
    print(f"{count:7d}  {family}")

print("\n== class-based definition markup (files carrying it) ==")
for (family, element, token), count in sorted(
        by_family_tag.items(), key=lambda kv: -kv[1]):
    print(f"{count:7d}  {family:32} <{element} class=\"{token}\">")

print("\n== real dl/dt/dd tags (files carrying them) ==")
for (family, tag), count in sorted(real_tags.items(), key=lambda kv: -kv[1]):
    print(f"{count:7d}  {family:32} <{tag}>")

print("\n== heading-level skips ==")
for family, count in sorted(files_with_gap.items(), key=lambda kv: -kv[1]):
    print(f"{count:7d}/{files_seen[family]:<7d} files  {family}")
print()
for (family, jump), count in sorted(gaps.items(), key=lambda kv: -kv[1])[:40]:
    print(f"{count:7d}  {family:32} {jump}")
