"""Unit tests for `utils/longpath.py` and the two writers it protects (Phase 14b).

The defect these pin is a measurement, not a hypothetical: `extract --family ems`
failed on all six versions with `FileNotFoundError` while every *final* path in
the tree was legal. The deepest EMS 10.5.1 member sits at 257 characters under
its destination and at 262 under the `.part` staging sibling extraction builds
into, and `LongPathsEnabled` is `0x0` on the machine that found it.

The deep cases here are written to be meaningful on both platforms -- a 300-plus
character path is simply written and read back -- so they stay honest on CI
without a Windows skip. The assertions that are *about* the prefix are the only
ones gated on `os.name`.
"""

import os
import zipfile
from pathlib import Path

import pytest

from docushift.extractor import safe_extract
from docushift.extractor.safe_unzip import UnsafeArchiveError
from docushift.utils.longpath import long_path, over_limit, walk_files
from docushift.utils.swap import swap

WINDOWS = os.name == "nt"
# Twelve segments of twenty-two characters: 276 before the root is prepended, so
# every tmp_path on any machine puts the leaf well past MAX_PATH.
DEEP = "/".join(["segment_of_some_length"] * 12)


# -- the helper ---------------------------------------------------------------


@pytest.mark.skipif(not WINDOWS, reason="the prefix is a Win32 spelling")
def test_a_path_is_absolutised_and_prefixed() -> None:
    assert str(long_path("C:/tmp/a/b")) == "\\\\?\\C:\\tmp\\a\\b"


@pytest.mark.skipif(not WINDOWS, reason="the prefix is a Win32 spelling")
def test_the_prefix_is_applied_once_however_often_it_is_asked_for() -> None:
    """Idempotent, so a helper may be wrapped by another without composing prefixes."""
    once = long_path("C:/tmp/a")

    assert long_path(once) == once


@pytest.mark.skipif(not WINDOWS, reason="the prefix is a Win32 spelling")
def test_dot_dot_is_collapsed_before_the_prefix_goes_on() -> None:
    """The order is the safety property. `\\\\?\\` stops the OS resolving anything.

    A `..` left in place would be taken as a literal directory name rather than a
    parent, so normalising afterwards is not an option and normalising before is
    not optional.
    """
    assert str(long_path("C:/tmp/a/../b")) == "\\\\?\\C:\\tmp\\b"


@pytest.mark.skipif(not WINDOWS, reason="the prefix is a Win32 spelling")
def test_a_unc_path_gets_the_form_the_prefix_has_for_it() -> None:
    """`\\\\?\\\\\\server\\share` is not a thing; `\\\\?\\UNC\\server\\share` is."""
    assert str(long_path("//server/share/docs")) == "\\\\?\\UNC\\server\\share\\docs"


@pytest.mark.skipif(WINDOWS, reason="everywhere else there is no limit to lift")
def test_elsewhere_it_is_the_same_path_back() -> None:
    assert long_path("/tmp/a/b") == Path("/tmp/a/b")


# -- what it is for ------------------------------------------------------------


def test_a_member_past_max_path_is_extracted_rather_than_refused(tmp_path: Path) -> None:
    """The failure Phase 14b started from, as a test.

    Before the fix this raised `FileNotFoundError` from inside `ZipFile.extract`
    -- which reads as a missing *archive* and sent the first investigation looking
    for one.
    """
    member = f"{DEEP}/topic.html"
    package = tmp_path / "docs.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(member, "<h1>deep</h1>")

    written = safe_extract(package, tmp_path / "out")

    assert written == 1
    assert long_path(tmp_path / "out" / member).read_text(encoding="utf-8") == "<h1>deep</h1>"


def test_the_escape_refusal_still_runs_ahead_of_the_prefix(tmp_path: Path) -> None:
    """The one ordering that must not drift: `\\\\?\\` would stop `..` being collapsed.

    Asserted on a member that is *also* deep, because the check and the prefix now
    act on the same names and a refactor could easily swap them.
    """
    package = tmp_path / "evil.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(f"{DEEP}/../../../../../../../../../../../../../etc/passwd", "x")

    with pytest.raises(UnsafeArchiveError):
        safe_extract(package, tmp_path / "out")

    # Refused before anything was written, deep member or not.
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir())


def test_a_staging_tree_past_max_path_can_still_be_swapped(tmp_path: Path) -> None:
    """The second half of the defect: `.part` is what pushes 257 to 262.

    A fix in `safe_unzip` alone would have built the tree successfully and then
    failed to move it, which is a worse place to fail than the first one.
    """
    staging, target = tmp_path / "out.part", tmp_path / "out"
    leaf = long_path(staging / DEEP)
    leaf.mkdir(parents=True)
    (leaf / "topic.md").write_text("deep", encoding="utf-8")

    swap(staging, target)

    assert long_path(target / DEEP / "topic.md").read_text(encoding="utf-8") == "deep"
    assert not long_path(staging).exists()


# -- the published ceiling (Phase 15d) ----------------------------------------------------


def test_a_tree_that_fits_reports_no_offender(tmp_path: Path) -> None:
    source = tmp_path / "javadoc"
    (source / "html").mkdir(parents=True)
    (source / "html" / "index.html").write_text("x", encoding="utf-8")

    assert over_limit(tmp_path / "published", source, limit=200) is None


def test_the_first_file_over_the_ceiling_is_named_with_its_length(tmp_path: Path) -> None:
    """The offender and the number, because "too long" without either is a finding
    nobody can act on."""
    source = tmp_path / "javadoc"
    source.mkdir()
    (source / ("class_" + "a" * 80 + ".html")).write_text("x", encoding="utf-8")

    found = over_limit(Path("C:/published/api-references/10-4-0/dotnetdoc"), source, limit=60)

    assert found is not None
    path, length = found
    assert path.name.startswith("class_")
    assert length > 60


def test_the_measurement_is_of_the_destination_and_not_of_the_source(tmp_path: Path) -> None:
    """The extracted tree sits under a short workspace path and the published one
    under whatever root the user picked, so the source's own length says nothing."""
    source = tmp_path / "j"
    source.mkdir()
    (source / "a.html").write_text("x", encoding="utf-8")

    assert over_limit(tmp_path / "short", source, limit=400) is None
    assert over_limit(Path("C:/" + "d" * 300), source, limit=260) is not None


def test_a_source_that_is_not_there_is_not_an_overflow(tmp_path: Path) -> None:
    """`select` drops roots that no longer exist; this must not raise on one."""
    assert over_limit(tmp_path / "published", tmp_path / "gone") is None


# -- seeing the files that are over it (Phase 15e) -----------------------------


def test_the_walk_finds_a_file_that_rglob_silently_drops(tmp_path: Path) -> None:
    """The defect 15e closes, and the reason it went a whole phase unnoticed.

    `rglob` does not raise on a path over the ceiling -- it returns a shorter
    list. Measured on one published EMS API tree: 798 entries plain, 801 through
    the prefix, and those 3 are exactly the files `copytree` then failed on. A
    check that cannot see the longest files in the tree it is checking passes.
    """
    deep = long_path(tmp_path / DEEP)
    deep.mkdir(parents=True)
    (deep / "over-the-ceiling.html").write_text("x", encoding="utf-8")

    walked = {relative.name for relative, _ in walk_files(tmp_path)}
    plain = {path.name for path in tmp_path.rglob("*") if path.is_file()}

    assert "over-the-ceiling.html" in walked
    if WINDOWS:
        assert "over-the-ceiling.html" not in plain, "the unprefixed walk should miss it"


def test_the_walk_returns_a_relative_name_and_an_openable_absolute(tmp_path: Path) -> None:
    r"""Two spellings because they have two jobs: the absolute one is the only way
    to open the file, and the relative one is what belongs in a message -- `\\?\`
    in a report is this tool's plumbing, not the reader's path."""
    deep = long_path(tmp_path / DEEP)
    deep.mkdir(parents=True)
    (deep / "topic.html").write_text("body", encoding="utf-8")

    relative, absolute = next(iter(walk_files(tmp_path)))

    assert relative == Path(DEEP.replace("/", os.sep)) / "topic.html"
    assert not str(relative).startswith("\\?\\")
    assert absolute.read_text(encoding="utf-8") == "body"


def test_the_walk_yields_files_and_not_the_directories_over_them(tmp_path: Path) -> None:
    (tmp_path / "html").mkdir()
    (tmp_path / "html" / "a.html").write_text("x", encoding="utf-8")
    (tmp_path / "empty").mkdir()

    assert [relative.as_posix() for relative, _ in walk_files(tmp_path)] == ["html/a.html"]


def test_the_ceiling_check_now_sees_the_long_file_and_names_it_unprefixed(tmp_path: Path) -> None:
    """The two halves of 15e meeting: the prefix is how the source is *read*, the
    limit is what the destination is *held to*. Before this the check walked
    unprefixed and so was blind to the one file that mattered."""
    source = tmp_path / "dotnetdoc"
    deep = long_path(source / DEEP)
    deep.mkdir(parents=True)
    (deep / "over.html").write_text("x", encoding="utf-8")

    found = over_limit(Path("C:/published/api-references/10-4-0/dotnetdoc"), source, limit=260)

    assert found is not None
    path, length = found
    assert path.name == "over.html"
    assert not str(path).startswith("\\?\\")
    assert length > 260
