"""Stage 6c's document router: the folder, then the name (`design.md` §10.4).

Every pattern test uses a filename **observed in the corpus**, not one invented to
fit the regex. That is the whole discipline of this file: the first implementation
of these rules was written against the expected spellings and misrouted 2,921
files, all of which spell themselves the way the corpus does.
"""

from pathlib import Path

import pytest

from docushift.models import SourceEngine
from docushift.sync.router import (
    REFERENCE_DOCUMENTS,
    RELEASE_INFORMATION,
    USER_GUIDES,
    Kind,
    SourceFolder,
    doc_class_for,
    kind_of,
    route_version,
)


def write(root: Path, *relative: str) -> Path:
    """Creates each named file with a byte in it, and returns the version root."""
    for name in relative:
        path = root.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return root


def routed(tree: Path, engine: SourceEngine = SourceEngine.AUTO) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in route_version(tree, engine):
        result.setdefault(item.doc_class, []).append(item.path.name)
    return result


# -- the name patterns -------------------------------------------------------------


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        # The `\b` trap: `_` is a word character, so a word-boundary anchor does
        # not match between `_` and `rel`. 1,813 files in the PDF folders alone.
        ("tib_ems_relnotes", RELEASE_INFORMATION),
        # Spaces are a real separator in this corpus.
        ("mft platform server v7.1 for windows release notes", RELEASE_INFORMATION),
        ("tibco nimbus control 8.1.3 release notes", RELEASE_INFORMATION),
        # `licencing`, not `licensing` -- both spellings ship.
        ("tib_nimbus_9.1.0_licencing_doc", REFERENCE_DOCUMENTS),
        ("tib_control_9.0.1_licensing_doc", REFERENCE_DOCUMENTS),
        ("tib_ebx-addon_remindernotice", REFERENCE_DOCUMENTS),
        ("TIB_bw_6.8_VPAT", REFERENCE_DOCUMENTS),
        # The residue, and the reason `user-guides` is a default rather than a
        # match: these are genuine guides that merely contain the word "note".
        ("special-notes", USER_GUIDES),
        ("LiveViewWeb_NewNote", USER_GUIDES),
        ("tib_ems_users_guide", USER_GUIDES),
    ],
)
def test_the_pdf_folder_routes_on_the_observed_spellings(stem: str, expected: str) -> None:
    assert doc_class_for(stem, SourceFolder.PDF) == expected


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("readme", RELEASE_INFORMATION),
        ("tib_ems_relnotes", RELEASE_INFORMATION),
        # The document folder asks one question and no more: licence, reminder
        # notice, RTU and the CSV/XLSX strays all share one destination.
        ("tib_nimbus_9.1.0_licencing_doc", REFERENCE_DOCUMENTS),
        ("tib_ebx-addon_remindernotice", REFERENCE_DOCUMENTS),
        ("TIB_bw_rtu", REFERENCE_DOCUMENTS),
        ("third_party_notices", REFERENCE_DOCUMENTS),
    ],
)
def test_the_document_folder_routes_on_one_question(stem: str, expected: str) -> None:
    assert doc_class_for(stem, SourceFolder.DOCUMENT) == expected


def test_the_word_boundary_trap_is_a_regression_test_in_both_folders() -> None:
    """2,921 files, not 1,753: the original survey counted only the PDF folder.

    The consequence differs by folder and neither is benign -- from `pdf/` a
    release note is filed as a user guide, and from `doc/` it is filed as a
    reference document.
    """
    assert doc_class_for("tib_ems_relnotes", SourceFolder.PDF) == RELEASE_INFORMATION
    assert doc_class_for("tib_ems_relnotes", SourceFolder.DOCUMENT) == RELEASE_INFORMATION
    assert doc_class_for("tib_ems_readme", SourceFolder.DOCUMENT) == RELEASE_INFORMATION


def test_rtu_is_recognized_for_titling_and_changes_no_destination() -> None:
    """§10.5's fifth pattern. It improves 235 titles and moves nothing."""
    assert kind_of("TIB_bw_rtu") is Kind.RTU
    assert doc_class_for("TIB_bw_rtu", SourceFolder.DOCUMENT) == REFERENCE_DOCUMENTS
    # In the PDF folder it is not one of the four patterns, so it stays the default
    # -- which is exactly what "changes no routing" has to mean.
    assert doc_class_for("TIB_bw_rtu", SourceFolder.PDF) == USER_GUIDES
    # And the word has to be whole: `virtue.pdf` is not a right-to-use statement.
    assert kind_of("tib_virtue_guide") is Kind.UNKNOWN


def test_kind_precedence_is_the_rank_order() -> None:
    """A file matching two patterns is titled by the more specific one."""
    assert kind_of("tib_bw_vpat_license") is Kind.VPAT
    assert kind_of("tib_bw_license_relnotes") is Kind.LICENCE
    assert kind_of("tib_ems_relnotes") is Kind.RELEASE_NOTES
    assert kind_of("readme") is Kind.README
    assert kind_of("tib_ems_users_guide") is Kind.UNKNOWN


# -- locating the folders ----------------------------------------------------------


def test_the_root_layout_routes_all_three_doc_classes(tmp_path: Path) -> None:
    tree = write(
        tmp_path,
        "pdf/tib_ems_users_guide.pdf",
        "pdf/tib_ems_relnotes.pdf",
        "pdf/TIB_ems_VPAT.pdf",
        "doc/readme.txt",
        "doc/tib_ems_licenses.txt",
    )

    assert routed(tree) == {
        USER_GUIDES: ["tib_ems_users_guide.pdf"],
        RELEASE_INFORMATION: ["tib_ems_relnotes.pdf", "readme.txt"],
        REFERENCE_DOCUMENTS: ["TIB_ems_VPAT.pdf", "tib_ems_licenses.txt"],
    }


def test_the_nested_document_folder_is_doc_doc(tmp_path: Path) -> None:
    """The correction that cost 676 files in 346 versions across 120 products.

    373 versions nest the pair as `doc/pdf/` **and `doc/doc/`**, and a locator that
    carries the shift for the PDF folder and drops it for the document folder
    publishes the nested PDFs and none of the readmes beside them.
    """
    tree = write(
        tmp_path,
        "doc/pdf/tib_ems_users_guide.pdf",
        "doc/doc/readme.txt",
        "doc/doc/tib_ems_remindernotice.txt",
    )

    assert routed(tree) == {
        USER_GUIDES: ["tib_ems_users_guide.pdf"],
        RELEASE_INFORMATION: ["readme.txt"],
        REFERENCE_DOCUMENTS: ["tib_ems_remindernotice.txt"],
    }


def test_the_root_folder_is_yielded_before_the_nested_one(tmp_path: Path) -> None:
    """Which is what makes "root wins" mean something in §10.5's de-duplication."""
    tree = write(tmp_path, "pdf/guide.pdf", "doc/pdf/guide.pdf", "doc/readme.txt", "doc/doc/readme.txt")

    order = [item.path for item in route_version(tree, SourceEngine.AUTO)]

    assert order[0] == tree / "pdf" / "guide.pdf"
    assert order[1] == tree / "doc" / "pdf" / "guide.pdf"
    assert order.index(tree / "doc" / "readme.txt") < order.index(tree / "doc" / "doc" / "readme.txt")


def test_only_files_directly_inside_the_folders_are_documents(tmp_path: Path) -> None:
    """`doc/relnotes/` is the case that tests the rule: 12 versions have one, and
    every one of them is a Flare output root rather than a folder of release notes.
    """
    tree = write(
        tmp_path,
        "doc/readme.txt",
        "doc/relnotes/Default.htm",
        "doc/relnotes/csh.js",
        "pdf/archive/tib_ems_9.0_users_guide.pdf",
    )

    assert routed(tree) == {RELEASE_INFORMATION: ["readme.txt"]}


def test_a_version_that_routes_nothing_routes_nothing(tmp_path: Path) -> None:
    """156 of 1,822 versions. Absence, not an empty doc-class."""
    assert route_version(write(tmp_path, "html/index.html"), SourceEngine.AUTO) == []


def test_a_file_an_engine_output_root_owns_is_not_a_document(tmp_path: Path) -> None:
    """`flogo-oracledb/1.2.1` ships its Flare help *as* `doc/`.

    The same precedence `extractor/inventory.py` applies -- `owning_root` before
    the router directories -- so a file cannot be an output-root file in the
    inventory and a published document in the tree.
    """
    tree = write(
        tmp_path,
        "doc/Data/HelpSystem.xml",
        "doc/Default.htm",
        "doc/tp-html.mclog",
        "doc/readme.txt",
    )

    # Without the guard the readme, the build log and the help system's own entry
    # page all publish as reference documents; with it, `doc/` is the converter's.
    assert routed(tree, SourceEngine.FLARE) == {}
    # And the guard is engine-specific, as root-finding is -- nothing claims the
    # directory when the version is not Flare, which is what makes the first
    # assertion a statement about `owning_root` rather than about these filenames.
    assert routed(tree, SourceEngine.AUTO) == {
        RELEASE_INFORMATION: ["readme.txt"],
        REFERENCE_DOCUMENTS: ["Default.htm", "tp-html.mclog"],
    }
