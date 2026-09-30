"""Phase 29: the filename a page publishes under, and the anchor a heading gets.

Both are *predictions of what the platform will do*, not choices this tool makes,
and that is why they are pinned this hard. AEM builds a URL from the TOC chain of
filenames, 50 characters a segment, and generates anchors from heading text --
so a wrong answer here is a wrong address a reader has bookmarked, not an
internal detail.

The cases that look oddly specific are real corpus names.
"""

import pytest

from docushift.utils.anchors import anchor_run, slugify_heading
from docushift.utils.naming import MAX_SEGMENT, qualify, shorten, slugify

# -- filenames -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "stem", "expected"),
    [
        # An apostrophe closes up rather than splitting: `developer-s-guide` would
        # read as three words. The corpus publishes `_section_developeru0027s_guide`,
        # which is the same title with the escape left in.
        ("Developer's Guide", "", "developers-guide"),
        ("_section_developeru0027s_guide", "developers_guide", "developers-guide"),
        # A "title" that is really a stem falls back, and only then is edit history
        # stripped -- these four are real MadCap filenames.
        ("Know_the_Basics", "Know_the_Basics", "know-the-basics"),
        ("", "1__Copy_Files_Before_Installation", "copy-files-before-installation"),
        ("", "Prior_to_Upgrade_", "prior-to-upgrade"),
        ("", "Configuring_HTTPS_updated", "configuring-https"),
        # Trademark glyphs go before the fold, or `™` decomposes to the letters TM.
        ("TIBCO ActiveSpaces® Enterprise Edition", "", "tibco-activespaces-enterprise-edition"),
        ("Messaging & Events", "", "messaging-and-events"),
        ("Overview of the Grid", "", "overview-of-the-grid"),
        # The name that made the case for this phase: published as
        # `upgrading-to-release-5-12-4.md` while its title said 5.13.0.
        ("Upgrading to Release 5.13.0", "", "upgrading-to-release-5-13-0"),
    ],
)
def test_a_title_becomes_the_name_a_reader_sees(title: str, stem: str, expected: str) -> None:
    assert slugify(title, stem) == expected


def test_a_word_that_merely_looks_like_an_escape_is_left_alone() -> None:
    """`u([0-9a-f]{4})` also matches the tail of a real word. Narrowing the
    pattern to the Latin-1 and punctuation blocks is what stops a title being
    corrupted in the course of fixing an escape."""
    assert slugify("Ubuntu1234 Notes") == "ubuntu1234-notes"


# -- the 50-character rule ------------------------------------------------------


def test_a_name_that_fits_is_left_exactly_as_it_is() -> None:
    """`Cache_Loader_Write_through_and_Bulk_Operations` is 46 and keeps its `and`.

    Dropping stopwords unconditionally would shorten names nobody asked to be
    shortened; the rule only fires when the limit is actually exceeded.
    """
    slug = slugify("Cache Loader Write-through and Bulk Operations")

    assert slug == "cache-loader-write-through-and-bulk-operations"
    assert len(slug) == 46


@pytest.mark.parametrize(
    "title",
    [
        "Configuring SSL on Existing Non-SSL GridServer Manager",
        "Configuring Permissions for Processor Utilization Thresholds",
    ],
)
def test_the_two_long_names_come_in_under_the_cut(title: str) -> None:
    """The spec's golden pair. AEM cuts a segment at 50 and the leaf stops being
    the filename; published, these two became `configuring_ssl_on_existing_non-
    ssl_gridserver_man` and `configuring_permissions_for_processor_utilization_`
    -- the second ending on a separator.

    Dropping stopwords brings both under the cut, so the platform truncates
    nothing and the filename *is* the URL leaf.
    """
    slug = slugify(title)

    assert len(slug) <= MAX_SEGMENT
    assert not slug.endswith("-")


def test_a_name_too_long_even_without_stopwords_cuts_at_a_word() -> None:
    slug = shorten("deployment-scenario-for-running-activespaces-processes-as-services", 50)

    assert len(slug) <= 50
    assert not slug.endswith("-")
    # A whole word, never a fragment of one.
    assert all(part for part in slug.split("-"))


def test_only_a_single_oversized_word_is_ever_cut_mid_word() -> None:
    assert shorten("a" * 70, 50) == "a" * 50


def test_the_first_word_survives_even_when_it_is_a_stopword() -> None:
    """An address beginning `/guide` reads worse than one beginning `/the-guide`."""
    slug = shorten("the-" + "-".join(["configuration"] * 5), 50)

    assert slug.startswith("the-configuration")


# -- disambiguation -------------------------------------------------------------


def test_a_generic_name_takes_its_parents_prefix() -> None:
    assert qualify("overview", "installation-guide") == "installation-guide-overview"


def test_qualifying_shortens_the_parent_and_not_the_page() -> None:
    """The slug is what the page is *about*; the parent is context. When the pair
    will not fit, the context gives way."""
    slug = qualify("overview", "an-extremely-long-parent-section-title-here", limit=30)

    assert slug.endswith("-overview")
    assert len(slug) <= 30


def test_qualifying_gives_up_rather_than_returning_a_stub() -> None:
    """No room for even one character of parent: the bare slug beats `x-overview`."""
    assert qualify("a" * 50, "parent") == "a" * 50


# -- anchors --------------------------------------------------------------------


def test_an_anchor_deletes_punctuation_where_a_filename_would_separate_on_it() -> None:
    """The concrete reason this is not `utils/slug.py`. A directory name turns
    `10.4.0` into `10-4-0`; an anchor drops the dots entirely. `_` is a word
    character to the platform and survives, where a filename would split on it.
    """
    assert slugify_heading("Release 10.4.0") == "release-1040"
    assert slugify_heading("Know_the_Basics") == "know_the_basics"
    assert slugify("Release 10.4.0") == "release-10-4-0"


def test_inline_markup_leaves_no_trace_in_an_anchor() -> None:
    assert slugify_heading("**Bold** and `code`") == "bold-and-code"


def test_a_repeated_heading_is_numbered_from_the_second_occurrence() -> None:
    """First bare, then `-1`, `-2`: the platform's rule, and the reason the suffix
    is positional and moves when a section is inserted above."""
    assert anchor_run(["Location", "Syntax", "Location", "Location"]) == [
        "location", "syntax", "location-1", "location-2",
    ]


def test_a_heading_that_slugs_to_nothing_holds_its_place() -> None:
    """Returned index-aligned with its input, so a caller can map heading N to
    anchor N without tracking which ones were dropped."""
    assert anchor_run(["Real", "***", "Real"]) == ["real", "", "real-1"]
