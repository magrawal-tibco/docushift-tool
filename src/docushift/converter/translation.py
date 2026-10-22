"""How much of a localized build is actually translated (Phase 57).

A localized Flare build mirrors the English one file for file: `html/ja-jp/x.htm`
beside `html/en-us/x.htm`. Packages ship partly translated builds -- WebFOCUS
Client 9.3.8's German, French and Spanish roots are almost entirely English -- and
the user's decision was to publish them as shipped and say how much is not
translated.

The English build is the reference, so no language is detected: a page whose
converted body is identical to its English counterpart's was not translated. That
is as true of German as of Japanese, and it cannot mistake a short page of product
names for English text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from docushift.utils.longpath import long_path

# The English build's own root names, tried in this order in place of the
# localized root's segment.
ENGLISH_ROOTS = ("en-us", "en")

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


def english_root(root: Path) -> Path | None:
    """The English build beside a localized root: `html/ja-jp` -> `html/en-us`, or `None`."""
    try:
        siblings = {entry.name.lower(): entry for entry in root.parent.iterdir() if entry.is_dir()}
    except OSError:
        return None
    for name in ENGLISH_ROOTS:
        if name in siblings and siblings[name] != root:
            return siblings[name]
    return None


@dataclass
class Share:
    """One localized version, measured against its English build."""

    pages: int = 0
    identical: int = 0
    unmatched: int = 0

    @property
    def percent(self) -> int:
        return round(100 * self.identical / self.pages) if self.pages else 0


def counterpart(source: str, locale: str, english: dict[str, str]) -> str | None:
    """The English source path matching a localized one, or `None`.

    The localized root's own segment is swapped for an English root's name:
    `pkg/html/ja-jp/bi-portal/x.htm` -> `pkg/html/en-us/bi-portal/x.htm`.
    `english` is keyed on the lower-cased source, because the package's own case
    is not consistent (`en-US`); its values are the real keys.
    """
    parts = source.split("/")
    for index, part in enumerate(parts):
        if part.lower() != locale.lower():
            continue
        for name in ENGLISH_ROOTS:
            candidate = "/".join([*parts[:index], name, *parts[index + 1:]]).lower()
            if candidate in english:
                return english[candidate]
        return None
    return None


def measure(
    local_map: dict[str, str],
    english_map: dict[str, str],
    local_dir: Path,
    english_dir: Path,
    locale: str,
) -> Share:
    """Compares every converted localized page with its English counterpart.

    The maps are `source -> output` (the §9.3 output map) of each run; the
    directories are the two converted version trees. A page with no English
    counterpart, or whose counterpart was not written, is `unmatched`.
    """
    share = Share()
    folded = {key.lower(): key for key in english_map}
    for source, output in local_map.items():
        share.pages += 1
        english = counterpart(source, locale, folded)
        if english is None:
            share.unmatched += 1
            continue
        mine = _body(local_dir / output)
        theirs = _body(english_dir / english_map[english])
        if mine is None or theirs is None:
            share.unmatched += 1
        elif mine == theirs:
            share.identical += 1
    return share


def _body(path: Path) -> str | None:
    """The page without its frontmatter, which carries the source path and differs."""
    try:
        text = long_path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return _FRONTMATTER.sub("", text.replace("\r\n", "\n"), count=1).strip()
