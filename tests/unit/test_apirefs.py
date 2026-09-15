"""Stage 6d's naming and de-duplication rules (`design.md` §10.7).

Every case here is a shape the in-scope corpus actually ships -- 165 roots in 49
versions across 13 products, re-measured 2026-09-15 -- because the two rules under
test are the ones where the obvious answer is wrong. The leaf name looks like the
folder name until you count the collisions (16 of 49 versions), and every root
looks distinct until you compare their sizes (19 of 165 are copies).
"""

from pathlib import Path, PurePosixPath

import pytest

from docushift.sync import apirefs


def javadoc(root: Path, pages: int = 2, filler: str = "x") -> Path:
    """An API tree `apiref.has_api_marker` recognises, sized by `pages` and `filler`."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "index-all.html").write_text("<html></html>", encoding="utf-8")
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    for n in range(pages):
        (root / f"Class{n}.html").write_text(filler * (10 + n), encoding="utf-8")
    return root


# -- the name (§10.7) -----------------------------------------------------------


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("html/api-reference/java", "java"),
        ("api/java/lib", "java-lib"),
        ("api/java/sample", "java-sample"),
        ("doc/html/api/c", "c"),
        ("html/api-docs/dotnet", "dotnet"),
        ("bpmhelp/api/javascript", "javascript"),
        ("tools/deduplication/lib", "tools-deduplication-lib"),
        # A trailing container is dropped like any other: the tree is the .NET doc,
        # and `html` is where ems's packager filed it.
        ("html/api/dotnetdoc/html", "dotnetdoc"),
        # Every segment is a container, so there is nothing left to name it after
        # and the leaf -- the least uninformative of them -- is taken as-is.
        ("html/apidocs", "apidocs"),
        ("HTML/API/Java", "java"),
    ],
)
def test_the_name_comes_from_the_path_with_the_containers_dropped(relative, expected) -> None:
    """`lib` is the corpus's commonest leaf (34 of 165) and names nothing."""
    assert apirefs.display_name(PurePosixPath(relative)) == expected


def test_the_full_name_keeps_every_segment() -> None:
    """The fallback. Unique across all 49 versions; readable in none of them."""
    assert apirefs.full_name(PurePosixPath("html/api-docs/java")) == "html-api-docs-java"


# -- de-duplication, which runs first (§10.7) -----------------------------------


def test_a_nested_copy_of_a_root_is_dropped_in_favour_of_the_shallower_one(tmp_path: Path) -> None:
    """`rtview/5.9.1-august-2011` contains itself four times over."""
    tree = tmp_path / "5.9.1"
    outer = javadoc(tree / "html" / "javadocs")
    javadoc(tree / "rtview-5-9-1" / "html" / "javadocs")

    selected = apirefs.select(tree, [outer, tree / "rtview-5-9-1" / "html" / "javadocs"])

    assert [root.source for root in selected] == [outer]
    assert [root.name for root in selected] == ["javadocs"]


def test_two_trees_of_the_same_name_and_different_size_are_both_kept(tmp_path: Path) -> None:
    """Size, count and leaf together -- not the name alone, or `tps` loses three."""
    tree = tmp_path / "6.2.0"
    small = javadoc(tree / "api" / "java" / "lib", pages=2)
    large = javadoc(tree / "api" / "java" / "sample", pages=5)

    selected = apirefs.select(tree, [small, large])

    assert [root.name for root in selected] == ["java-lib", "java-sample"]


def test_the_whole_version_falls_back_to_the_full_path_when_a_name_collides(tmp_path: Path) -> None:
    """`tps/6.0.0`: `api/api/java/lib` survives the size check beside `api/java/lib`.

    Uniform within the version, not per-root. Naming one sibling `java-lib` and the
    other `api-api-java-lib` would leave a reader unable to tell which scheme they
    were reading, which is worse than two long names.
    """
    tree = tmp_path / "6.0.0"
    shallow = javadoc(tree / "api" / "java" / "lib", pages=2)
    nested = javadoc(tree / "api" / "api" / "java" / "lib", pages=3)

    selected = apirefs.select(tree, [nested, shallow])

    assert [root.name for root in selected] == ["api-java-lib", "api-api-java-lib"]
    # Shallowest first, whatever order the record arrived in.
    assert [root.source for root in selected] == [shallow, nested]


def test_a_recorded_root_that_is_gone_or_foreign_is_dropped_silently(tmp_path: Path) -> None:
    """A record can outlive the extract; a recorded path is not a promise."""
    tree = tmp_path / "1.0.0"
    real = javadoc(tree / "html" / "javadoc")
    elsewhere = javadoc(tmp_path / "other" / "javadoc")

    selected = apirefs.select(tree, [real, tree / "html" / "gone", elsewhere])

    assert [root.source for root in selected] == [real]


def test_a_version_that_is_entirely_one_api_tree_is_named_after_its_own_folder(tmp_path: Path) -> None:
    """The relative path is `.`, which names nothing and joins to nothing."""
    tree = javadoc(tmp_path / "tibrv-javadoc")

    selected = apirefs.select(tree, [tree])

    assert [root.name for root in selected] == ["tibrv-javadoc"]


def test_the_measurement_is_the_files_and_the_bytes(tmp_path: Path) -> None:
    tree = tmp_path / "1.0.0"
    root = javadoc(tree / "api" / "java", pages=2)
    expected = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())

    (selected,) = apirefs.select(tree, [root])

    assert (selected.files, selected.bytes) == (4, expected)


# -- currency, compared before staging (§10.7) ----------------------------------


def test_a_placed_tree_is_current_when_the_folders_and_the_sizes_match(tmp_path: Path) -> None:
    """1.39 GiB corpus-wide: the count and the byte total answer it without reading."""
    tree = tmp_path / "1.0.0"
    root = javadoc(tree / "api" / "java")
    (selected,) = apirefs.select(tree, [root])

    destination = tmp_path / "published"
    javadoc(destination / "java")

    assert apirefs.current([selected], destination)


def test_a_placed_tree_is_not_current_when_a_file_changed_size(tmp_path: Path) -> None:
    tree = tmp_path / "1.0.0"
    root = javadoc(tree / "api" / "java")
    (selected,) = apirefs.select(tree, [root])

    destination = tmp_path / "published"
    javadoc(destination / "java", filler="xx")

    assert not apirefs.current([selected], destination)


def test_a_placed_tree_is_not_current_when_a_root_was_added_or_removed(tmp_path: Path) -> None:
    tree = tmp_path / "1.0.0"
    root = javadoc(tree / "api" / "java")
    (selected,) = apirefs.select(tree, [root])

    destination = tmp_path / "published"
    javadoc(destination / "java")
    javadoc(destination / "c")

    assert not apirefs.current([selected], destination)
    assert not apirefs.current([selected], tmp_path / "nothing-here")


# -- the published address, shared by the copy and the rewrite ------------------


def test_the_url_is_the_placement_path_with_the_host_in_front() -> None:
    """One function for both, so a link cannot point at a folder that was not made."""
    assert apirefs.published_url(
        "https://docs.example.com/", "en-us-tib-messaging-userdocs-resources",
        "en-us", "tibco-ems", "10-4-0", "java",
    ) == (
        "https://docs.example.com/en-us-tib-messaging-userdocs-resources"
        "/en-us/tibco-ems/api-references/10-4-0/java"
    )


def test_an_unset_host_leaves_the_path_alone_rather_than_inventing_one() -> None:
    """Empty is the shipped state; a leading slash would be a guess about the root."""
    assert apirefs.published_url(
        "", "en-us-tib-messaging-userdocs-resources", "en-us", "tibco-ems", "10-4-0", "java",
    ) == "en-us-tib-messaging-userdocs-resources/en-us/tibco-ems/api-references/10-4-0/java"
