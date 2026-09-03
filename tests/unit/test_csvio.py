"""Unit tests for CSV round-trip hygiene.

Every case here corresponds to a hazard in docs/architecture.md §3.6 -- these are
the specific ways a spreadsheet damages a catalog file.
"""

from pathlib import Path

import pytest

from docushift.utils.csvio import (
    format_bool,
    natural_version_key,
    normalize_date,
    parse_bool,
    read_rows,
    write_rows,
)


@pytest.mark.parametrize("raw", ["true", "TRUE", "True", "1", "yes", "Y", " t "])
def test_parse_bool_accepts_truthy_spellings(raw: str) -> None:
    assert parse_bool(raw) is True


@pytest.mark.parametrize("raw", ["false", "FALSE", "0", "no", "N", "", "  "])
def test_parse_bool_accepts_falsy_spellings(raw: str) -> None:
    assert parse_bool(raw) is False


def test_parse_bool_unrecognized_uses_default() -> None:
    """An archived row defaults convert_eligible to false, an active one to true."""
    assert parse_bool("maybe", default=True) is True
    assert parse_bool("maybe", default=False) is False


def test_format_bool_always_lowercase() -> None:
    assert format_bool(True) == "true"
    assert format_bool(False) == "false"


def test_normalize_date_passes_iso_through() -> None:
    assert normalize_date("2025-11-04") == "2025-11-04"


def test_normalize_date_repairs_excel_locale_reformat() -> None:
    """Excel rewrites 2025-11-04 as 11/4/2025 in a US locale."""
    assert normalize_date("11/4/2025") == "2025-11-04"


def test_normalize_date_handles_day_first_when_unambiguous() -> None:
    assert normalize_date("25/12/2024") == "2024-12-25"


def test_normalize_date_passes_free_text_through_verbatim() -> None:
    """The archive API returns values like 'June 2022'; they must survive untouched."""
    assert normalize_date("June 2022") == "June 2022"
    assert normalize_date(None) == ""


def test_natural_version_sort_puts_10_above_9() -> None:
    versions = ["9.1.0", "10.4.0", "8.6.0", "10.2.1"]

    ordered = sorted(versions, key=natural_version_key, reverse=True)

    assert ordered == ["10.4.0", "10.2.1", "9.1.0", "8.6.0"]


def test_natural_version_sort_orders_prerelease_below_release() -> None:
    assert natural_version_key("2.0.0") < natural_version_key("2.0.0-rc1")


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "products.csv"
    rows = [{"product_code": "ebx", "display_name": "TIBCO EBX®"}]

    write_rows(path, ("product_code", "display_name"), rows)

    assert read_rows(path) == rows


def test_write_emits_bom_so_excel_renders_trademarks(tmp_path: Path) -> None:
    """Without the BOM, Excel double-click renders 'TIBCO EBX®' as 'TIBCO EBXÂ®'."""
    path = tmp_path / "products.csv"

    write_rows(path, ("display_name",), [{"display_name": "TIBCO EBX®"}])

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_read_tolerates_a_missing_bom(tmp_path: Path) -> None:
    path = tmp_path / "products.csv"
    path.write_text("product_code,display_name\nems,EMS\n", encoding="utf-8", newline="")

    assert read_rows(path) == [{"product_code": "ems", "display_name": "EMS"}]


def test_write_drops_columns_outside_the_schema(tmp_path: Path) -> None:
    """A stray column added in a spreadsheet must not silently join the schema."""
    path = tmp_path / "products.csv"

    write_rows(path, ("product_code",), [{"product_code": "ems", "notes": "mine"}])

    assert read_rows(path) == [{"product_code": "ems"}]


def test_read_missing_file_is_empty_not_an_error(tmp_path: Path) -> None:
    assert read_rows(tmp_path / "absent.csv") == []


def test_rewrite_is_byte_identical(tmp_path: Path) -> None:
    """A load-then-save cycle with no changes must produce no diff churn."""
    path = tmp_path / "versions.csv"
    columns = ("product_code", "version", "convert_eligible")
    rows = [{"product_code": "ems", "version": "10.4.0", "convert_eligible": "true"}]

    write_rows(path, columns, rows)
    first = path.read_bytes()
    write_rows(path, columns, read_rows(path))

    assert path.read_bytes() == first
