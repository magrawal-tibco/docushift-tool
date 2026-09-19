"""Phase 15b: where a version's content starts, and the one shape that is not a wrapper.

The rule has to do two things at once — descend through the wrapper directory 46
of 50 sampled packages carry, and *not* descend through the `doc/` that the five
DataSynapse cache trees carry — so both halves are tested against the shapes that
were actually measured rather than against invented ones.
"""

from pathlib import Path

from docushift.extractor import content_root


def tree(root: Path, *relatives: str) -> Path:
    for relative in relatives:
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_a_single_wrapper_directory_is_descended_through(tmp_path: Path) -> None:
    """The 46-of-50 shape: one child named after the package, content inside it."""
    version = tree(
        tmp_path / "10.4.0",
        "tibco-enterprise-message-service-10-4-0/html/index.html",
        "tibco-enterprise-message-service-10-4-0/pdf/guide.pdf",
    )

    assert content_root.resolve(version).name == "tibco-enterprise-message-service-10-4-0"


def test_a_flat_package_is_its_own_content_root(tmp_path: Path) -> None:
    """The other 4: `doc/`, `html/` and `pdf/` at the root, the shape every step assumed."""
    version = tree(tmp_path / "5.0", "doc/readme.txt", "html/index.html", "pdf/guide.pdf")

    assert content_root.resolve(version) == version


def test_a_lone_content_directory_is_not_a_wrapper(tmp_path: Path) -> None:
    """The counter-example that makes "exactly one child" the wrong rule.

    The five DataSynapse trees hold a single `doc/`, and `router.source_folders`
    looks for `doc/pdf` and `doc/doc` by name. Descending here would move the root
    past the directory the router is about to ask for.
    """
    version = tree(tmp_path / "7.2.0", "doc/pdf/guide.pdf", "doc/doc/readme.txt")

    assert content_root.resolve(version) == version


def test_the_descent_stops_after_one_level(tmp_path: Path) -> None:
    """No sampled package nests two wrappers, and an unbounded walk would run past
    a single-guide package's own content."""
    version = tree(tmp_path / "1.0.0", "outer/inner/html/index.html")

    assert content_root.resolve(version).name == "outer"


def test_a_lone_file_beside_nothing_leaves_the_root_alone(tmp_path: Path) -> None:
    version = tree(tmp_path / "2.0.0", "readme.txt")

    assert content_root.resolve(version) == version


def test_a_directory_with_a_file_beside_it_is_not_a_wrapper(tmp_path: Path) -> None:
    """Two children, so there is no single child to descend through — whatever
    the directory is called."""
    version = tree(tmp_path / "3.0.0", "tibco-thing-3-0-0/html/a.html", "readme.txt")

    assert content_root.resolve(version) == version


def test_the_recorded_form_is_a_name_and_not_a_path(tmp_path: Path) -> None:
    """Stored relative, so a workspace that moves does not carry a dead absolute."""
    wrapped = tree(tmp_path / "10.4.0", "tibco-ems-10-4-0/html/a.html")
    flat = tree(tmp_path / "5.0", "html/a.html", "pdf/a.pdf")

    assert content_root.relative(wrapped) == "tibco-ems-10-4-0"
    assert content_root.relative(flat) == ""


def test_the_recorded_answer_is_used_when_it_still_exists(tmp_path: Path) -> None:
    version = tree(tmp_path / "10.4.0", "tibco-ems-10-4-0/html/a.html")

    assert content_root.of(version, "tibco-ems-10-4-0") == version / "tibco-ems-10-4-0"


def test_a_stale_record_is_ignored_rather_than_trusted(tmp_path: Path) -> None:
    """A record can outlive the tree it describes. Sending a reader into a
    directory that is gone is worse than re-reading the disk."""
    version = tree(tmp_path / "10.4.0", "tibco-ems-10-5-1/html/a.html")

    assert content_root.of(version, "tibco-ems-10-4-0") == version / "tibco-ems-10-5-1"


def test_no_record_falls_back_to_reading_the_tree(tmp_path: Path) -> None:
    """Every tree hand-copied from the predecessor's cache is in this state, and so
    is any folder handed straight to `convert --input-dir`."""
    version = tree(tmp_path / "10.4.0", "tibco-ems-10-4-0/html/a.html")

    assert content_root.of(version, None) == version / "tibco-ems-10-4-0"
    assert content_root.of(version, "") == version / "tibco-ems-10-4-0"
