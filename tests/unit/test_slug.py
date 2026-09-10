"""Tests for the slug, workspace-folder and publishing-tree name helpers."""

import pytest

from docushift.utils.slug import (
    docs_tree_name,
    family_workspace_folder,
    is_primary_locale,
    resources_tree_name,
    slugify,
)

TOKENS = {"suffix": "userdocs", "localized_prefix": "loc", "primary_locale": "en-us"}
RESOURCE_TOKENS = {"docs_suffix": "userdocs", "resources_suffix": "resources", "primary_locale": "en-us"}


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


def test_family_workspace_folder_composes_locale_bu_and_family() -> None:
    assert family_workspace_folder("en-us", "tib", "data_management") == "en-us-tib-data-management"
    assert family_workspace_folder("en-us", "ibi", "webfocus") == "en-us-ibi-webfocus"
    # Localized packages are different ZIPs, so the workspace keeps the real locale
    # even though every one of them publishes into the single `loc-` tree.
    assert family_workspace_folder("ja-jp", "tib", "messaging") == "ja-jp-tib-messaging"


def test_family_workspace_folder_carries_no_publishing_suffix() -> None:
    """The workspace stopped being the repo name when one family gained three trees."""
    assert family_workspace_folder("en-us", "tib", "messaging") == "en-us-tib-messaging"
    assert docs_tree_name("en-us", "tib", "messaging", **TOKENS).startswith("en-us-tib-messaging-")


def test_docs_tree_name_appends_the_suffix_for_the_primary_locale() -> None:
    assert docs_tree_name("en-us", "tib", "messaging", **TOKENS) == "en-us-tib-messaging-userdocs"
    assert docs_tree_name("en-us", "ibi", "webfocus", **TOKENS) == "en-us-ibi-webfocus-userdocs"


def test_docs_tree_name_folds_every_other_locale_into_one_loc_tree() -> None:
    """`loc-`, not `ja-jp-`: all localized content shares a single repository."""
    japanese = docs_tree_name("ja-jp", "tib", "messaging", **TOKENS)

    assert japanese == "loc-tib-messaging-userdocs"
    assert docs_tree_name("fr-fr", "tib", "messaging", **TOKENS) == japanese


def test_resources_tree_name_derives_from_the_docs_suffix() -> None:
    assert resources_tree_name("en-us", "tib", "messaging", **RESOURCE_TOKENS) == (
        "en-us-tib-messaging-userdocs-resources"
    )


def test_resources_tree_name_refuses_a_localized_locale() -> None:
    """Returning a name here would hand the caller a repository that never exists."""
    with pytest.raises(ValueError, match="No resources tree exists for locale 'ja-jp'"):
        resources_tree_name("ja-jp", "tib", "messaging", **RESOURCE_TOKENS)


def test_the_suffix_is_a_token_not_a_literal() -> None:
    """The whole family of names moves together, which is what makes it reversible."""
    docs = {**TOKENS, "suffix": "docs"}
    resources = {**RESOURCE_TOKENS, "docs_suffix": "docs"}

    assert docs_tree_name("en-us", "tib", "messaging", **docs) == "en-us-tib-messaging-docs"
    assert docs_tree_name("ja-jp", "tib", "messaging", **docs) == "loc-tib-messaging-docs"
    assert resources_tree_name("en-us", "tib", "messaging", **resources) == "en-us-tib-messaging-docs-resources"


def test_is_primary_locale_is_the_single_localized_predicate() -> None:
    assert is_primary_locale("en-us", "en-us")
    assert is_primary_locale("EN_US", "en-us")
    assert not is_primary_locale("ja-jp", "en-us")


@pytest.mark.parametrize(
    ("locale", "bu", "family", "missing"),
    [
        ("en-us", "tib", "", "family"),
        ("en-us", "", "messaging", "bu"),
        ("", "tib", "messaging", "locale"),
        ("en-us", "", "", "bu, family"),
    ],
)
def test_family_workspace_folder_rejects_empty_components(locale: str, bu: str, family: str, missing: str) -> None:
    """`en-us-tib-` would be created silently and then collect every stray product."""
    with pytest.raises(ValueError, match=missing):
        family_workspace_folder(locale, bu, family)


def test_tree_names_reject_an_empty_suffix() -> None:
    """`en-us-tib-messaging` as a *tree* name is the same bug with a longer name."""
    with pytest.raises(ValueError, match="suffix"):
        docs_tree_name("en-us", "tib", "messaging", **{**TOKENS, "suffix": ""})
    with pytest.raises(ValueError, match="resources"):
        resources_tree_name("en-us", "tib", "messaging", **{**RESOURCE_TOKENS, "resources_suffix": ""})
    with pytest.raises(ValueError, match="prefix"):
        docs_tree_name("ja-jp", "tib", "messaging", **{**TOKENS, "localized_prefix": ""})
