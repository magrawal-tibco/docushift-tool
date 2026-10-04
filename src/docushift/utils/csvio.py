"""CSV round-trip hygiene helpers.

Excel is the expected editor for `config/products.csv` and `config/versions.csv`,
which imposes the defenses in docs/architecture.md §3.6: a UTF-8 BOM so `®` and
`™` survive a double-click open, permissive reads paired with normalized writes,
and a stable sort so a no-op fetch produces no diff.
"""

import csv
import io
import re
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from docushift.utils.swap import replace_file

# Excel writes TRUE/FALSE; humans write yes/y/1. Read all of them, write only
# lowercase true/false. A blank cell is in neither set, so it reads as the
# caller's default: it held `""` until Phase 34, which made every blank `false`
# and silently broke the one caller whose default is not -- `convert_eligible`,
# where blank means "eligible if active" (R1-02).
_TRUE_TOKENS = frozenset({"true", "1", "yes", "y", "t"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "n", "f"})

# Tried in order. The slash formats exist because a US-locale Excel rewrites an
# ISO date as 11/4/2025; month-first is therefore the right first guess, and a
# day > 12 falls through to the day-first attempt.
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y")

_ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The docsite writes `releaseDate` as epoch milliseconds on about a fifth of
# versions -- 926 catalog rows held `1399420800000` and the like until Phase 34
# (R1-11, R2-08). Twelve or thirteen digits covers 1973 to 2286; a value whose
# year falls outside the range below is a column that changed meaning, not a
# date, and passes through verbatim like any other unparseable text. The range
# is the one `sync/versions.py` met this dialect with first; that module now reads
# the epoch through `normalize_date` rather than with a copy of its own.
_EPOCH_MS = re.compile(r"^\d{12,13}$")
_EPOCH_YEARS = range(1990, 2101)

# What a docsite homepage and the archive index write: `March 2021`, `Mar 2021`.
_MONTH_YEAR_FORMATS = ("%B %Y", "%b %Y")

_VERSION_PART = re.compile(r"(\d+)")


def parse_bool(value: object, default: bool = False) -> bool:
    """Reads a boolean permissively. Blank and unrecognized values fall back to `default`."""
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
    if token in _FALSE_TOKENS:
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
    must survive untouched rather than being coerced or dropped. Epoch
    milliseconds become the UTC day they name -- UTC so that one catalog does not
    read a different day on two machines.
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
    if _EPOCH_MS.match(text):
        try:
            moment = datetime.fromtimestamp(int(text) / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return text
        return moment.date().isoformat() if moment.year in _EPOCH_YEARS else text
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def release_year(value: object) -> str:
    """The year a date names, as four digits, or `""` when it names none.

    For comparing two dates written at different precisions -- the converter's
    homepage check sets `March 2021` against the catalog's `2021-03-15`. Slicing
    `normalize_date(...)[:4]` read the first as `Marc`, so every month-named date
    raised a false `METADATA_MISMATCH` (Phase 34, R1-05).
    """
    text = normalize_date(value)
    if _ISO_DATE.match(text):
        return text[:4]
    for fmt in _MONTH_YEAR_FORMATS:
        try:
            return str(datetime.strptime(text, fmt).year)
        except ValueError:
            continue
    return ""


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


class NotUtf8(ValueError):
    """A hand-edited file in neither UTF-8 nor Windows-1252, named with the fix."""


def read_text(path: Path) -> str:
    """A file a human may have saved from Excel or Notepad: UTF-8, else Windows-1252.

    X2-04. Excel's default "CSV (Comma delimited)" save writes the ANSI code page,
    which on these machines is Windows-1252, so `™` becomes byte 0x99 and the
    strict `utf-8-sig` read ended every command in a traceback that named no file.
    Read rather than refused, because the decode is exact for the code page Excel
    actually wrote and every writer here puts UTF-8 back on the next save. UTF-8
    is tried first and a cp1252 file almost never passes for it, so a real UTF-8
    file is never reinterpreted. What is left -- the five bytes Windows-1252 does
    not define -- is a clean refusal that names the file and how to re-save it.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError as exc:
        raise NotUtf8(
            f"{path} is neither UTF-8 nor Windows-1252 (byte 0x{raw[exc.start]:02x} at "
            f"offset {exc.start}). Open it and save it again as 'CSV UTF-8' (or UTF-8 text)."
        ) from exc


def read_rows(path: Path) -> list[dict[str, str]]:
    """Reads a catalog CSV. `utf-8-sig` strips the BOM and tolerates its absence.

    Through `read_text`, so a sheet Excel saved as ANSI reads too (X2-04).
    """
    if not path.exists():
        return []
    handle = io.StringIO(read_text(path), newline="")
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


def write_rows_together(tables: Sequence[tuple[Path, Sequence[str], Iterable[dict[str, str]]]]) -> None:
    """Writes several CSVs so that a failure leaves every one of them as it was.

    `write_rows` truncates its target in place, so writing the catalog pair one
    file after the other let a locked `versions.csv` -- Excel holds a write lock
    on whatever it has open (§3.6) -- fail *after* `products.csv` had been
    rewritten, leaving a pair that no longer joins (Phase 34, R1-04). So, in
    three passes: every file is written to a sibling `.tmp` first, which is where
    a full disk or an encoding failure lands; every target is then opened for
    writing and closed, which is where a lock lands; and only then is each temp
    file renamed into place. Not one atomic step across files -- Windows offers
    none -- but the remaining window is two renames wide, not a whole write.

    Raises the underlying `OSError`. The temp files are removed either way.
    """
    staged = [(path, path.with_name(path.name + ".tmp")) for path, _, _ in tables]
    try:
        for (_, columns, rows), (_, tmp) in zip(tables, staged, strict=True):
            write_rows(tmp, columns, rows)
        for path, _ in staged:
            if path.exists():
                with open(path, "r+b"):
                    pass
        for path, tmp in staged:
            replace_file(tmp, path)
    finally:
        for _, tmp in staged:
            tmp.unlink(missing_ok=True)
