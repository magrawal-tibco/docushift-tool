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

_ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")

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


def parse_optional_bool(value: object) -> bool | None:
    """Reads a boolean that is allowed to be absent.

    Distinct from `parse_bool` because for the Stage 4 inventory columns
    (architecture.md §3.9) a blank cell means "never measured", which is not the
    same answer as `false`. Anything unrecognized reads as `None` for the same
    reason: inventing a `false` would claim a measurement nobody took.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    token = str(value).strip().lower()
    if not token:
        return None
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS - {""}:
        return False
    return None


def format_optional_bool(value: bool | None) -> str:
    """Writes a nullable boolean, preserving the empty cell."""
    return "" if value is None else format_bool(value)


def parse_optional_int(value: object) -> int | None:
    """Reads a count that is allowed to be absent, tolerating spreadsheet damage.

    Excel renders a count column as `4310.0` or `4,310` given the chance. Both are
    accepted; a negative or unparseable value reads as `None` rather than `0`,
    keeping "never measured" distinct from "measured zero" (§3.9).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if value is None:
        return None
    token = str(value).strip().replace(",", "")
    if not token:
        return None
    try:
        number = int(float(token))
    except ValueError:
        return None
    return number if number >= 0 else None


def format_optional_int(value: int | None) -> str:
    """Writes a nullable count, preserving the empty cell."""
    return "" if value is None else str(value)


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
    # The docsite reports release dates as ISO timestamps (`2025-02-06T09:21:53.000Z`).
    # The catalog records the day; the time of day is noise in a spreadsheet column.
    if _ISO_TIMESTAMP.match(text):
        return text[:10]
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
