"""Stage 6c's index: titles, de-duplication and order (`design.md` §10.5).

The titling tests use PDFs written here rather than fixtures, because what is
under test is the *chain* -- which source of a title wins -- and a chain is only
testable when each link can be made to disagree with the others.
"""

from pathlib import Path

import pypdf
import pytest
import yaml

from docushift.config import ConfigManager
from docushift.sync.documents import (
    DocumentEntry,
    entries_for,
    group,
    index_title,
    is_junk_title,
    read_pdf_title,
    render_index,
    render_toc,
    title_for,
    title_from_name,
)
from docushift.sync.router import (
    REFERENCE_DOCUMENTS,
    RELEASE_INFORMATION,
    USER_GUIDES,
    Kind,
    RoutedFile,
    SourceFolder,
    doc_class_for,
    kind_of,
)


def pdf(path: Path, title: str | None = None) -> Path:
    """A one-page PDF, with the Info-dictionary `/Title` set when one is given."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if title is not None:
        writer.add_metadata({"/Title": title})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def routed(path: Path, folder: SourceFolder = SourceFolder.PDF) -> RoutedFile:
    """A `RoutedFile` built the way `route_version` builds one."""
    return RoutedFile(
        path=path,
        doc_class=doc_class_for(path.stem, folder),
        kind=kind_of(path.stem),
        folder=folder,
    )


def plain(path: Path, body: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# -- the title chain ---------------------------------------------------------------


def test_the_kind_name_beats_the_pdf_title(tmp_path: Path) -> None:
    """Which is what keeps 13 minutes of PDF reading off the common path.

    The canonical name covers 100% of `release-information` and 97.7% of
    `reference-documents`, and it is also the *better* title: this file's own
    `/Title` is the FrameMaker book it was built from.
    """
    file = pdf(tmp_path / "tib_ems_relnotes.pdf", "ems_relnotes.book")

    assert title_for(routed(file)) == ("Release Notes", "")


def test_an_unrecognized_guide_is_titled_from_its_pdf(tmp_path: Path) -> None:
    file = pdf(tmp_path / "tib_ems_users_guide.pdf", "Enterprise Message Service Users Guide")

    assert title_for(routed(file)) == ("Enterprise Message Service Users Guide", "")


def test_a_blank_title_falls_back_to_the_filename_and_is_not_a_finding(tmp_path: Path) -> None:
    """27.9% of the corpus's PDFs. Normal, so it returns no error to report."""
    file = pdf(tmp_path / "tib_ems_users_guide.pdf")

    assert title_for(routed(file)) == ("tib ems users guide", "")


@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
        "untitled",
        "Untitled",
        "ems_relnotes.book",
        "installation.fm",
        "TIB_ems_ug.pdf",
        "Microsoft Word - reminder notice.doc",
        "Microsoft Word - Document1",
    ],
)
def test_the_junk_filter_rejects_the_authoring_tools_filename(title: str) -> None:
    """59 titles in 35 distinct values, all three shapes: blank, suffix, prefix."""
    assert is_junk_title(title)


@pytest.mark.parametrize(
    "title",
    ["TIBCO Enterprise Message Service Users Guide", "Installation", "Release Notes for 10.4.0"],
)
def test_the_junk_filter_keeps_a_real_title(title: str) -> None:
    assert not is_junk_title(title)


def test_a_junk_title_falls_back_to_the_filename(tmp_path: Path) -> None:
    file = pdf(tmp_path / "tib_ems_install.pdf", "Microsoft Word - install.doc")

    assert title_for(routed(file)) == ("tib ems install", "")


def test_a_pdf_that_will_not_parse_is_published_titled_and_reported(tmp_path: Path) -> None:
    """7 of 5,007, in 4 filenames. The file ships; the damage gets a note."""
    file = plain(tmp_path / "TIB_smap_1.0.0_install_guide.pdf", "not a PDF at all")

    title, error = title_for(routed(file))

    assert title == "TIB smap 1 0 0 install guide"
    assert error
    assert read_pdf_title(file) == ("", error)


def test_a_non_pdf_is_never_opened(tmp_path: Path) -> None:
    """`readme.txt` has no Info dictionary, and the chain must not try for one."""
    file = plain(tmp_path / "special notes.txt")

    assert title_for(routed(file, SourceFolder.PDF)) == ("special notes", "")


def test_the_filename_title_collapses_separators_and_nothing_else(tmp_path: Path) -> None:
    """The measured alternative -- stripping vendor, product and version tokens --
    produced `'adix 2'` and `'dqid 3'`, and 82.9% of its titles were unique."""
    assert title_from_name("tib_ems_10.4.0_users_guide.pdf") == "tib ems 10 4 0 users guide"
    assert title_from_name("mft platform server v7.1 release notes.pdf") == "mft platform server v7 1 release notes"


# -- grouping and order ------------------------------------------------------------


def test_the_root_copy_wins_the_duplicate(tmp_path: Path) -> None:
    """25 versions carry both PDF folders and share 178 filenames between them."""
    root = plain(tmp_path / "pdf" / "guide.pdf")
    nested = plain(tmp_path / "doc" / "pdf" / "GUIDE.PDF")

    grouped = group([routed(root), routed(nested)])

    assert [item.path for item in grouped[USER_GUIDES]] == [root]


def test_an_empty_doc_class_is_absent_rather_than_empty(tmp_path: Path) -> None:
    """An `index.md` linking to nothing is a published dead end, not an empty page."""
    grouped = group([routed(plain(tmp_path / "readme.txt"), SourceFolder.DOCUMENT)])

    assert list(grouped) == [RELEASE_INFORMATION]


def test_the_doc_classes_come_out_in_reading_order(tmp_path: Path) -> None:
    grouped = group(
        [
            routed(plain(tmp_path / "tib_ems_licenses.txt"), SourceFolder.DOCUMENT),
            routed(plain(tmp_path / "readme.txt"), SourceFolder.DOCUMENT),
            routed(plain(tmp_path / "guide.pdf")),
        ]
    )

    assert list(grouped) == [USER_GUIDES, RELEASE_INFORMATION, REFERENCE_DOCUMENTS]


def test_the_shared_rank_table_orders_every_doc_class(tmp_path: Path) -> None:
    """One table, not one per doc-class: `reference-documents` gets its VPAT first
    and `release-information` its release notes first out of the same list."""
    files = [
        routed(plain(tmp_path / "tib_ems_licenses.txt"), SourceFolder.DOCUMENT),
        routed(plain(tmp_path / "tib_ems_rtu.txt"), SourceFolder.DOCUMENT),
        routed(plain(tmp_path / "TIB_ems_VPAT.txt"), SourceFolder.DOCUMENT),
        routed(plain(tmp_path / "tib_ems_remindernotice.txt"), SourceFolder.DOCUMENT),
        routed(plain(tmp_path / "third_party_notices.txt"), SourceFolder.DOCUMENT),
    ]

    entries, unreadable = entries_for(files)

    assert [entry.kind for entry in entries] == [
        Kind.VPAT, Kind.LICENCE, Kind.REMINDER_NOTICE, Kind.RTU, Kind.UNKNOWN,
    ]
    assert unreadable == []


def test_two_files_of_one_kind_are_ordered_by_filename(tmp_path: Path) -> None:
    """They share a canonical title, so the filename is what keeps the order stable
    rather than whatever order the filesystem listed them in."""
    files = [
        routed(plain(tmp_path / "b_remindernotice.txt"), SourceFolder.DOCUMENT),
        routed(plain(tmp_path / "a_remindernotice.txt"), SourceFolder.DOCUMENT),
    ]

    entries, _ = entries_for(files)

    assert [entry.name for entry in entries] == ["a_remindernotice.txt", "b_remindernotice.txt"]
    assert {entry.title for entry in entries} == {"Reminder Notice"}


def test_an_entry_carries_the_two_figures_aem_asked_for(tmp_path: Path) -> None:
    file = plain(tmp_path / "tib_ems_guide.PDF", "0123456789")

    entries, _ = entries_for([routed(file)])

    assert entries[0].type == "pdf"
    assert entries[0].bytes == 10


def test_the_link_is_percent_encoded_and_the_filename_is_not(tmp_path: Path) -> None:
    """`mft platform server v7.1 for windows release notes.pdf` is a real filename,
    and a Markdown link target stops at its first space in every renderer."""
    entry = DocumentEntry(
        source=tmp_path / "x.pdf", name="mft platform server v7.1.pdf",
        title="Release Notes", type="pdf", bytes=1, kind=Kind.RELEASE_NOTES,
    )

    assert entry.link == "mft%20platform%20server%20v7.1.pdf"
    assert entry.name == "mft platform server v7.1.pdf"


# -- rendering ---------------------------------------------------------------------


def test_the_index_names_the_product_the_version_and_the_doc_class() -> None:
    assert index_title("TIBCO EMS™", "10.4.0", USER_GUIDES) == "TIBCO EMS™ 10.4.0 User Guides"
    assert index_title("TIBCO EMS™", "10.4.0", REFERENCE_DOCUMENTS) == "TIBCO EMS™ 10.4.0 Reference Documents"


def test_the_index_writes_its_own_frontmatter(config: ConfigManager, tmp_path: Path) -> None:
    """`index.md.j2` is body-only because the converter's `_render` heads its pages.
    Nothing converts a folder of PDFs, so this template is the only source there is.
    """
    entries, _ = entries_for([routed(plain(tmp_path / "mft server v7.1 release notes.pdf"))])

    rendered = render_index(entries, "TIBCO MFT 7.1 Release Information", RELEASE_INFORMATION,
                            config.aem_templates_dir)

    head, body = rendered.split("---\n")[1], rendered.split("---\n")[2]
    assert yaml.safe_load(head) == {
        "title": "TIBCO MFT 7.1 Release Information",
        "doc_class": "release-information",
        "generated": True,
    }
    assert "# TIBCO MFT 7.1 Release Information" in body
    assert "- [Release Notes](mft%20server%20v7.1%20release%20notes.pdf)" in body


def test_the_toc_is_flat_and_keeps_bytes_an_integer(config: ConfigManager, tmp_path: Path) -> None:
    """A folder of PDFs is a list; `toc.yml.j2`'s tree would render a one-level one
    to say so. And a quoted `bytes` would publish `"10"`, which AEM cannot add up.
    """
    entries, _ = entries_for(
        [
            routed(plain(tmp_path / "TIB_ems_VPAT.pdf", "0123456789")),
            routed(plain(tmp_path / "tib_ems_licenses.pdf")),
        ]
    )

    loaded = yaml.safe_load(render_toc(entries, "TIBCO EMS 10.4.0 Reference Documents",
                                       config.aem_templates_dir))

    assert loaded["items"] == [
        {"title": "VPAT (Accessibility Conformance Report)", "path": "TIB_ems_VPAT.pdf",
         "type": "pdf", "bytes": 10},
        {"title": "License Agreement", "path": "tib_ems_licenses.pdf", "type": "pdf", "bytes": 1},
    ]


def test_an_empty_index_renders_rather_than_raising(config: ConfigManager) -> None:
    """It is never written -- an empty doc-class is absent -- but a template that
    only works on a non-empty list is a trap for whatever calls it next."""
    assert "# Nothing" in render_index([], "Nothing", USER_GUIDES, config.aem_templates_dir)
    assert yaml.safe_load(render_toc([], "Nothing", config.aem_templates_dir))["items"] is None
