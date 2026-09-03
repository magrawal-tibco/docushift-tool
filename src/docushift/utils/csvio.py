"""CSV round-trip hygiene helpers.

Excel is the expected editor for `config/products.csv` and `config/versions.csv`,
which imposes the defenses in docs/architecture.md §3.6: a UTF-8 BOM so `®` and
`™` survive a double-click open, permissive reads paired with normalized writes,
and a stable sort so a no-op fetch produces no diff.
"""

import csv
import re
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

# Excel writes TRUE/FALSE; humans write yes/y/1. Read all of them, write only
# lowercase true/false.
_TRUE_TOKENS = frozenset({"true", "1", "yes", "y", "t"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "n", "f", ""})

# Tried in order. The slash formats exist because a US-locale Excel rewrites an
# ISO date as 11/4/2025; month-first is therefore the right first guess, and a
# day > 12 falls through to the day-first attempt.
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y")

_VERSION_PART = re.compile(r"(\d+)")


def parse_bool(value: object, default: bool = False) -> bool:
    """Reads a boolean permissively. Unrecognized values fall back to `default`."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    token = str(value).strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return default


def format_bool(value: bool) -> str:
    """Writes a boolean in the one form the catalog uses."""
    return "true" if value else "false"


def normalize_date(value: object) -> str:
    """Normalizes a date to ISO, passing unparseable values through verbatim.

    The archive API returns values like `June 2022`, which are not full dates and
    must survive untouched rather than being coerced or dropped.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def natural_version_key(version: str) -> tuple:
    """Sort key that orders `10.4.0` above `9.1.0` rather than lexically below it.

    Digit runs compare numerically, everything else lexically, so pre-release
    suffixes (`2.0.0-rc1`) still order sensibly.
    """
    parts = _VERSION_PART.split(str(version).strip())
    key: list[tuple[int, int | str]] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return tuple(key)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Reads a catalog CSV. `utf-8-sig` strips the BOM and tolerates its absence."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return [{(k or ""): (v or "") for k, v in row.items()} for row in csv.DictReader(handle)]


def write_rows(path: Path, columns: Sequence[str], rows: Iterable[dict[str, str]]) -> None:
    """Writes a catalog CSV with a BOM, a fixed column order, and CRLF endings.

    Fields outside `columns` are dropped rather than appended, so a stray column
    added in a spreadsheet cannot silently become part of the schema.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
