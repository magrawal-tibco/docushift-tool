"""Tests for the slug and family-folder-name helpers."""

import pytest

from docushift.utils.slug import family_folder, slugify


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("data_management", "data-management"),
        ("Data Management", "data-management"),
        ("messaging", "messaging"),
        ("  Spaced  Out  ", "spaced-out"),
        ("already-hyphenated", "already-hyphenated"),
        ("mixed__separators--here", "mixed-separators-here"),
    ],
)
def test_slugify_normalizes_separators_and_case(value: str, expected: str) -> None:
    assert slugify(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("TIBCO EBX®", "tibco-ebx"),
        ("ibi™ WebFOCUS®", "ibi-webfocus"),
        ("TIBCO Enterprise Message Service™", "tibco-enterprise-message-service"),
    ],
)
def test_slugify_folds_trademark_characters_without_leaving_separators(value: str, expected: str) -> None:
    """`EBX®` must become `ebx`, not `ebx-` -- a trailing separator would leak into folder names."""
    assert slugify(value) == expected


def test_slugify_yields_empty_for_a_value_with_no_ascii_alphanumerics() -> None:
    assert slugify("---") == ""
    assert slugify("") == ""


def test_family_folder_composes_locale_bu_and_family() -> None:
    assert family_folder("en-us", "tibco", "data_management") == "en-us-tibco-data-management"
    assert family_folder("en-us", "ibi", "webfocus") == "en-us-ibi-webfocus"
    assert family_folder("ja-jp", "tibco", "messaging") == "ja-jp-tibco-messaging"


@pytest.mark.parametrize(
    ("locale", "bu", "family", "missing"),
    [
        ("en-us", "tibco", "", "family"),
        ("en-us", "", "messaging", "bu"),
        ("", "tibco", "messaging", "locale"),
        ("en-us", "", "", "bu, family"),
    ],
)
def test_family_folder_rejects_empty_components(locale: str, bu: str, family: str, missing: str) -> None:
    """`en-us-tibco-` would be created silently and then collect every stray product."""
    with pytest.raises(ValueError, match=missing):
        family_folder(locale, bu, family)
