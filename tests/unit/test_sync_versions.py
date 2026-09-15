"""Stage 6b's `version.yml`: the dates, the order, and what survives a re-sync.

The assertions that matter here are the negative ones -- what the assembler does
*not* rewrite -- because every one of them corresponds to a way the file could
silently lose an entry somebody depends on.
"""

import yaml

from docushift.models import ProductVersion
from docushift.sync import versions as version_file
from docushift.sync.versions import VersionRow


def make(number: str, date: str | None = "2025-11-04", archived: bool = False) -> ProductVersion:
    return ProductVersion(slug="tibco-ems", version=number, release_date=date, is_archived=archived)


# -- dates ----------------------------------------------------------------------


def test_the_three_release_date_formats_the_active_column_actually_carries() -> None:
    """1,377 ISO, 372 epoch-millisecond, 13 empty, measured 2026-09-15."""
    assert version_file.release_month("2026-02-06") == "Feb 2026"
    assert version_file.release_month("1703548800000") == "Dec 2023"
    assert version_file.release_month("") == ""
    assert version_file.release_month(None) == ""


def test_an_iso_timestamp_and_a_month_name_both_reduce_to_the_month() -> None:
    """The archived side of the catalog writes both; neither may render as garbage."""
    assert version_file.release_month("2025-02-06T09:21:53.000Z") == "Feb 2025"
    assert version_file.release_month("November 2022") == "Nov 2022"


def test_an_epoch_outside_living_memory_is_undated_rather_than_wrong() -> None:
    """A column that changed meaning must not publish 1970 as though it were data."""
    assert version_file.release_month("1") == ""
    assert version_file.release_month("99999999999999999") == ""
    assert version_file.release_month("not a date") == ""


def test_the_title_is_the_catalog_version_verbatim_plus_the_month() -> None:
    """Never trimmed to `10.4`: `10.4.0` and `10.4.1` are routinely both active."""
    assert version_file.title_for(make("10.4.0", "2026-02-06")) == "10.4.0 (Feb 2026)"


def test_an_undated_version_keeps_its_title_without_the_bracket() -> None:
    assert version_file.title_for(make("10.4.0", "")) == "10.4.0"


# -- the generated block ---------------------------------------------------------


def test_versions_sort_numerically_descending_not_lexically() -> None:
    """`10.4.0` outranks `9.3.0`, which string order gets backwards."""
    rows = version_file.generated_rows(
        [make("9.3.0"), make("10.4.0"), make("10.10.0")], {"9-3-0", "10-4-0", "10-10-0"}
    )

    assert [row.path for row in rows] == ["/10-10-0", "/10-4-0", "/9-3-0"]


def test_a_non_numeric_version_string_sorts_last_and_is_still_listed() -> None:
    """20 active rows are parse artifacts; the folder is published either way."""
    rows = version_file.generated_rows(
        [make("Server"), make("10.4.0"), make("9.3.0")], {"server", "10-4-0", "9-3-0"}
    )

    assert [row.path for row in rows] == ["/10-4-0", "/9-3-0", "/server"]


def test_the_two_unpublishable_version_strings_become_folder_names() -> None:
    """`Cloud™` and `(iPaaS)` are each their product's only active version."""
    rows = version_file.generated_rows([make("Cloud™"), make("(iPaaS)")], {"cloud", "ipaas"})

    assert {row.path for row in rows} == {"/cloud", "/ipaas"}


def test_an_archived_version_never_reaches_the_drop_down() -> None:
    """Archived releases live in the `-resources` archives tree (§6.2.3)."""
    rows = version_file.generated_rows([make("10.4.0"), make("8.6.0", archived=True)], {"10-4-0", "8-6-0"})

    assert [row.path for row in rows] == ["/10-4-0"]


def test_a_version_the_target_has_never_been_synced_is_absent_not_dangling() -> None:
    rows = version_file.generated_rows([make("10.4.0"), make("9.3.0")], {"10-4-0"})

    assert [row.path for row in rows] == ["/10-4-0"]


# -- reading what is already there -----------------------------------------------


def test_an_absent_or_empty_file_reads_as_no_rows_rather_than_as_a_refusal() -> None:
    assert version_file.parse("") == []
    assert version_file.parse("versions:\n") == []


def test_a_file_that_will_not_parse_refuses_to_be_rewritten() -> None:
    """`None` is the signal to leave the file alone: it is somebody's only copy."""
    assert version_file.parse("versions:\n- title: [unclosed\n") is None
    assert version_file.parse("- not a mapping\n") is None
    assert version_file.parse("versions: a string\n") is None
    assert version_file.parse("versions:\n- title: no path here\n") is None


# -- the merge -------------------------------------------------------------------


def test_with_no_previous_file_the_generated_block_is_the_file() -> None:
    generated = [VersionRow("10.4.0 (Feb 2026)", "/10-4-0")]

    assert version_file.merge([], generated, {"/10-4-0"}) == generated


def test_a_hand_written_row_keeps_its_side_of_the_generated_block() -> None:
    """AEM's schema invites a human in; the first re-sync must not evict them."""
    existing = [
        VersionRow("Latest", "https://docs.example/latest"),
        VersionRow("10.3.1 (Aug 2025)", "/10-3-1"),
        VersionRow("Archive", "https://docs.example/archive"),
    ]
    generated = [VersionRow("10.4.0 (Feb 2026)", "/10-4-0"), VersionRow("10.3.1 (Aug 2025)", "/10-3-1")]

    merged = version_file.merge(existing, generated, {"/10-4-0", "/10-3-1"})

    assert [row.path for row in merged] == [
        "https://docs.example/latest", "/10-4-0", "/10-3-1", "https://docs.example/archive",
    ]


def test_a_version_whose_folder_was_removed_loses_its_row() -> None:
    """The disk is the record. `owned_paths` still recognizes the row as ours."""
    existing = [VersionRow("10.3.1 (Aug 2025)", "/10-3-1"), VersionRow("10.4.0 (Feb 2026)", "/10-4-0")]
    generated = [VersionRow("10.4.0 (Feb 2026)", "/10-4-0")]
    owned = version_file.owned_paths({"10-4-0"}, [make("10.4.0"), make("10.3.1")])

    assert version_file.merge(existing, generated, owned) == generated


def test_a_bare_segment_nobody_recognizes_is_preserved_rather_than_adjudicated() -> None:
    """The failure directions are not symmetric: a stale row is a wart, a deleted
    row is somebody's only copy. `validate` names a row resolving to nothing."""
    existing = [VersionRow("Preview", "/preview-build")]
    owned = version_file.owned_paths({"10-4-0"}, [make("10.4.0")])

    merged = version_file.merge(existing, [VersionRow("10.4.0", "/10-4-0")], owned)

    assert [row.path for row in merged] == ["/preview-build", "/10-4-0"]


def test_owned_paths_covers_the_disk_and_the_catalog_together() -> None:
    owned = version_file.owned_paths({"10-4-0", "9-9-9"}, [make("10.4.0"), make("10.3.1")])

    assert owned == {"/10-4-0", "/9-9-9", "/10-3-1"}


def test_a_path_written_without_its_leading_slash_is_still_recognized() -> None:
    existing = [VersionRow("10.4.0", "10-4-0")]

    assert version_file.merge(existing, [], {"/10-4-0"}) == []


# -- rendering -------------------------------------------------------------------


def test_the_rendered_file_is_yaml_and_quotes_every_scalar(repo_root) -> None:
    """A version title is `10.4.0`, which bare YAML reads as a float."""
    rows = [VersionRow("10.4 (Feb 2026)", "/10-4"), VersionRow('Odd: "title"', "/odd")]

    text = version_file.render(rows, repo_root / "config" / "aem_templates")
    loaded = yaml.safe_load(text)

    assert loaded["versions"] == [
        {"title": "10.4 (Feb 2026)", "path": "/10-4"},
        {"title": 'Odd: "title"', "path": "/odd"},
    ]


def test_a_one_entry_drop_down_is_still_a_file(repo_root) -> None:
    """178 of 458 products have exactly one active version; absence and presence
    must not mean different things to AEM."""
    text = version_file.render([VersionRow("1.0.0", "/1-0-0")], repo_root / "config" / "aem_templates")

    assert yaml.safe_load(text)["versions"] == [{"title": "1.0.0", "path": "/1-0-0"}]


def test_a_rendered_file_round_trips_through_the_parser(repo_root) -> None:
    """The two halves of the read-before-write rule have to agree about the format."""
    rows = [VersionRow("10.4.0 (Feb 2026)", "/10-4-0")]

    text = version_file.render(rows, repo_root / "config" / "aem_templates")

    assert version_file.parse(text) == rows
