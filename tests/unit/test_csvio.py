"""Unit tests for CSV round-trip hygiene.

Every case here corresponds to a hazard in docs/architecture.md §3.6 -- these are
the specific ways a spreadsheet damages a catalog file.
"""

from pathlib import Path

import pytest

from docushift.utils.csvio import (
    format_bool,
    format_optional_bool,
    format_optional_int,
    natural_version_key,
    normalize_date,
    parse_bool,
    parse_optional_bool,
    parse_optional_int,
    read_rows,
    release_year,
    write_rows,
)


@pytest.mark.parametrize("raw", ["true", "TRUE", "True", "1", "yes", "Y", " t "])
def test_parse_bool_accepts_truthy_spellings(raw: str) -> None:
    assert parse_bool(raw) is True


@pytest.mark.parametrize("raw", ["false", "FALSE", "0", "no", "N", " f "])
def test_parse_bool_accepts_falsy_spellings(raw: str) -> None:
    assert parse_bool(raw, default=True) is False


@pytest.mark.parametrize("raw", ["", "  "])
def test_a_blank_cell_falls_back_to_the_default(raw: str) -> None:
    """R1-02: blank read as `false` outright, so the caller's default never applied."""
    assert parse_bool(raw, default=True) is True
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


def test_normalize_date_converts_epoch_milliseconds() -> None:
    """R1-11 / R2-08: 926 catalog rows arrived as `1399420800000` and were stored raw."""
    assert normalize_date("1399420800000") == "2014-05-07"
    assert normalize_date(1703548800000) == "2023-12-26"


@pytest.mark.parametrize("raw", ["12345", "99999999999999", "0000000000000"])
def test_normalize_date_leaves_implausible_digit_runs_alone(raw: str) -> None:
    """A digit run that is not a plausible epoch is a column that changed meaning, not a date."""
    assert normalize_date(raw) == raw


@pytest.mark.parametrize(
    ("raw", "year"),
    [
        ("2023-06-12", "2023"),
        ("June 2023", "2023"),
        ("Jun 2023", "2023"),
        ("1399420800000", "2014"),
        ("11/4/2025", "2025"),
        ("", ""),
        ("not a date", ""),
    ],
)
def test_release_year_reads_every_dialect_the_catalog_and_homepage_use(raw: str, year: str) -> None:
    """R1-05: the year check sliced `[:4]` and compared `June` with `2023`."""
    assert release_year(raw) == year


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


# -- nullable inventory columns (architecture.md §3.9) ------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", None), ("   ", None), (None, None), ("true", True), ("FALSE", False), ("junk", None)],
)
def test_optional_bool_keeps_blank_distinct_from_false(raw, expected) -> None:
    """A blank inventory cell means 'never extracted', which is not 'false'."""
    assert parse_optional_bool(raw) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", None), ("0", 0), ("4310", 4310), ("4,310", 4310), ("4310.0", 4310), ("-1", None), ("x", None)],
)
def test_optional_int_keeps_blank_distinct_from_zero(raw, expected) -> None:
    """Excel renders a count as '4,310' or '4310.0' given the chance; both are real."""
    assert parse_optional_int(raw) == expected


def test_optional_formatters_preserve_the_empty_cell() -> None:
    assert format_optional_bool(None) == ""
    assert format_optional_int(None) == ""
    assert format_optional_bool(False) == "false"
    assert format_optional_int(0) == "0"


# -- a file saved in the ANSI code page (X2-04) --------------------------------


def test_a_csv_saved_by_excel_as_ansi_reads_through_the_cp1252_fallback(tmp_path: Path) -> None:
    """X2-04. Excel's "CSV (Comma delimited)" writes Windows-1252, so `™` is byte
    0x99, and the strict UTF-8 read crashed every command with a traceback that
    named no file. The fallback reads it exactly; the next write is UTF-8 again."""
    path = tmp_path / "products.csv"
    path.write_bytes("slug,display_name\r\nems,TIBCO EMS\u2122\r\n".encode("cp1252"))

    assert read_rows(path) == [{"slug": "ems", "display_name": "TIBCO EMS\u2122"}]


def test_a_file_in_neither_encoding_is_refused_naming_the_file_and_the_fix(tmp_path: Path) -> None:
    """X2-04. Five bytes are undefined in Windows-1252 too; what is left after the
    fallback is a clean refusal that says which file and how to re-save it."""
    from docushift.utils.csvio import NotUtf8

    path = tmp_path / "versions.csv"
    path.write_bytes(b"slug,version\r\nems,10\x81\r\n")

    with pytest.raises(NotUtf8) as raised:
        read_rows(path)

    assert str(path) in str(raised.value)
    assert "CSV UTF-8" in str(raised.value)
