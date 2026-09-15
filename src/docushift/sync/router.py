"""Stage 6c's first step: which doc-class a non-converted document lands in.

`design.md` §10.4. A package ships PDFs and readmes beside its help output, and
nothing converts them -- they are copied as they are. This module answers the one
question that decides where: **the folder a file came from, then its name.**

The folder is the first discriminator, and not the extension. `pdf/` is where the
authored deliverables are and `doc/` is where the boilerplate is, so a licence PDF
and a licence TXT reach the same place while a user-guide PDF and a readme TXT do
not. An extension rule would have to explain that; the folder rule states it.

Four rules the corpus forced, each of which a plausible implementation breaks:

- **Both folders nest, and both must be looked for at both depths.** 1,123 of
  1,822 versions put `pdf/` and `doc/` at the package root; 373 nest them as
  `doc/pdf/` **and `doc/doc/`**. The first written spec located `V/doc/pdf` but
  only `V/doc`, which leaves **676 files in 346 versions across 120 products**
  unroutable -- readmes and reminder notices, 376 of them release information.
- **`\\b` is not a usable boundary.** `_` is a word character, so `\\b` does not
  match between `_` and `rel` and `tib_ems_relnotes.pdf` is not a release note.
  Measured cost across both folders: **2,921 files**, misrouted into `user-guides`
  from `pdf/` and into `reference-documents` from `doc/`.
- **Only files directly inside the folders are documents.** The one subdirectory
  that looks like it should qualify, `doc/relnotes/` in 12 versions, holds
  `Default.htm`, `csh.js` and `.mcwebhelp`: a Flare output root, and Stage 5's.
  Of the 117 document-extension files one level further down, 116 are in the
  out-of-scope `ebx-addon`.
- **A file an engine output root owns is the converter's, never a document.**
  `flogo-oracledb/1.2.1` ships its Flare help *as* `doc/`. This is the precedence
  `extractor/inventory.py` already applies -- `owning_root` before the router
  directories -- so a file cannot be an output-root file in the inventory and a
  published document in the tree.

`user-guides` is the **default, not a match**, which is why there is no
unclassified bucket: an unfamiliar guide name is published, not dropped.
"""

import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from pathlib import Path

from docushift.engines.roots import find_output_roots, owning_root
from docushift.models import SourceEngine

USER_GUIDES = "user-guides"
RELEASE_INFORMATION = "release-information"
REFERENCE_DOCUMENTS = "reference-documents"

# Ordered as a reader meets them, and as the report prints them.
DOCUMENT_DOC_CLASSES = (USER_GUIDES, RELEASE_INFORMATION, REFERENCE_DOCUMENTS)

# The optional separator. The corpus spells these names with underscores, hyphens,
# dots *and spaces* -- `mft platform server v7.1 for windows release notes.pdf` is
# a real filename -- so a pattern accepting only `_` and `-` misses them.
_SEP = r"[\s_.-]?"

# `relnotes` is listed bare and the spelled-out form is anchored on a separator
# class rather than on `\b`; see the module docstring for what `\b` costs.
_RELEASE_NOTES = re.compile(rf"(relnotes|(^|[\s_.-])rel(ease)?{_SEP}notes?)", re.IGNORECASE)
_README = re.compile(r"readme", re.IGNORECASE)
_VPAT = re.compile(r"vpat", re.IGNORECASE)
# `licence` and `licencing` are both spelled both ways in the corpus:
# `tib_nimbus_9.1.0_licencing_doc.pdf` beside `tib_control_9.0.1_licensing_doc.pdf`.
_LICENCE = re.compile(r"licen[cs](e|ing)", re.IGNORECASE)
_REMINDER_NOTICE = re.compile(rf"remind(er)?{_SEP}notice", re.IGNORECASE)
# **Titling only** (`design.md` §10.5). `doc/` already routes everything non-readme
# to `reference-documents`, so recognizing `rtu` changes no destination -- which is
# why it is applied in `kind_of` and never in `doc_class_for`.
_RTU = re.compile(r"(^|[\s_.-])rtu([\s_.-]|$)", re.IGNORECASE)


class SourceFolder(StrEnum):
    """Which of the two folders a file came from. The first discriminator."""

    PDF = "pdf"
    DOCUMENT = "doc"


class Kind(IntEnum):
    """What a file is, where its name says so -- and the order items are listed in.

    **One rank table, shared by all three doc-classes.** Each doc-class holds a
    subset of the kinds, so a single list gives `release-information` its release
    notes first and `reference-documents` its VPAT first without a per-doc-class
    branch. The member values *are* the rank.
    """

    VPAT = 0
    LICENCE = 1
    REMINDER_NOTICE = 2
    RTU = 3
    RELEASE_NOTES = 4
    README = 5
    # Everything the patterns do not recognize -- by construction, almost all of
    # `user-guides`. Titled from the PDF or the filename instead (§10.5).
    UNKNOWN = 6


# The canonical name of a kind is a better title than anything derivable from the
# filename, and it covers 100% of `release-information` and 97.7% of
# `reference-documents` before a PDF is ever opened.
KIND_TITLES: dict[Kind, str] = {
    Kind.VPAT: "VPAT (Accessibility Conformance Report)",
    Kind.LICENCE: "License Agreement",
    Kind.REMINDER_NOTICE: "Reminder Notice",
    Kind.RTU: "Right to Use Terms",
    Kind.RELEASE_NOTES: "Release Notes",
    Kind.README: "Readme",
}


@dataclass(frozen=True)
class RoutedFile:
    """One file, and where it goes."""

    path: Path
    doc_class: str
    kind: Kind
    folder: SourceFolder


def is_release_note(stem: str) -> bool:
    """The release-note test, which covers the readme: both mean the same here."""
    return bool(_RELEASE_NOTES.search(stem) or _README.search(stem))


def kind_of(stem: str) -> Kind:
    """What the filename says this is. **Never consulted for routing.**

    Tested in rank order, which is also precedence order: a file matching two
    patterns is titled by the more specific one. Keeping this separate from
    `doc_class_for` is what lets `rtu` improve 235 titles while moving no file.
    """
    if _VPAT.search(stem):
        return Kind.VPAT
    if _LICENCE.search(stem):
        return Kind.LICENCE
    if _REMINDER_NOTICE.search(stem):
        return Kind.REMINDER_NOTICE
    if _RTU.search(stem):
        return Kind.RTU
    if _RELEASE_NOTES.search(stem):
        return Kind.RELEASE_NOTES
    if _README.search(stem):
        return Kind.README
    return Kind.UNKNOWN


def doc_class_for(stem: str, folder: SourceFolder) -> str:
    """§10.4's route, first match wins. The four patterns and nothing else."""
    if folder is SourceFolder.DOCUMENT:
        # Deliberately one test. Licence, reminder notice, RTU and the CSV/XLSX
        # strays all share one destination, so asking anything beyond *is this the
        # readme* would add branches that cannot change the answer.
        return RELEASE_INFORMATION if is_release_note(stem) else REFERENCE_DOCUMENTS
    if _VPAT.search(stem) or _LICENCE.search(stem) or _REMINDER_NOTICE.search(stem):
        return REFERENCE_DOCUMENTS
    if is_release_note(stem):
        return RELEASE_INFORMATION
    return USER_GUIDES


def source_folders(tree: Path) -> list[tuple[SourceFolder, Path]]:
    """The four places documents live, **root before nested in both pairs**.

    The order is the de-duplication rule (§10.5): where a filename appears at both
    depths, the root copy is the one that is published. 25 versions carry both PDF
    folders and share 178 filenames, and 24 carry the same readme in `doc/` and
    `doc/doc/`.
    """
    return [
        (SourceFolder.PDF, tree / "pdf"),
        (SourceFolder.PDF, tree / "doc" / "pdf"),
        (SourceFolder.DOCUMENT, tree / "doc"),
        (SourceFolder.DOCUMENT, tree / "doc" / "doc"),
    ]


def _files_directly_in(directory: Path) -> list[Path]:
    """The directory's own files, sorted. Subdirectories are somebody else's."""
    try:
        return sorted((child for child in directory.iterdir() if child.is_file()),
                      key=lambda path: path.name.lower())
    except OSError:
        return []


def route_version(tree: Path, engine: SourceEngine) -> list[RoutedFile]:
    """Every document in one extracted version, in root-before-nested order.

    Duplicates are **not** removed here: the caller de-duplicates per doc-class
    (`design.md` §10.5, `sync/documents.py`), and the order this returns is what
    makes "root wins" mean something there.

    The output roots are located **lazily**, on the first candidate file. 156 of
    1,822 versions route nothing at all, and `find_output_roots` walks the whole
    tree -- reading HTML heads, for DocBook -- so paying for it before knowing
    there is anything to guard would be the cost of the guard without its benefit.
    """
    roots: list[Path] | None = None
    routed: list[RoutedFile] = []
    for folder, directory in source_folders(tree):
        for path in _files_directly_in(directory):
            if roots is None:
                roots = find_output_roots(tree, engine)
            if owning_root(path, roots) is not None:
                continue
            stem = path.stem
            routed.append(
                RoutedFile(
                    path=path,
                    doc_class=doc_class_for(stem, folder),
                    kind=kind_of(stem),
                    folder=folder,
                )
            )
    return routed
