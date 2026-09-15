"""Stage 6c's second step: the three document doc-classes, indexed.

`design.md` §10.5. A copied PDF with no index is unreachable -- `online-help` gets
navigation because Stage 6a synthesizes it from the source TOC, and these three
have no source TOC to synthesize from. So each doc-class folder that receives a
file also receives an `index.md`, a `toc.yml` and a `metadata.yml`, built from
§10.4's routed list.

Four rules, three of them about what a title is *not* taken from:

- **Not from the PDF, where the filename already says what the file is.** The
  router's patterns identify the kind, and the kind's canonical name is the better
  title: it covers 100% of `release-information` and 97.7% of
  `reference-documents` before a PDF is opened. Opening 5,007 PDFs takes 13
  minutes; opening the ~5,090 that need it takes the same 13 minutes, and opening
  all 12,130 would take three times that to produce worse titles.
- **Not from a byte-level `/Title` regex.** A PDF's outline bookmarks are `/Title`
  entries too and usually precede the Info dictionary, so a regex returns
  `'Basic Tab'` and `'Table of contents'` while reporting 57% success -- confidently
  wrong labels no reviewer would flag. `pypdf` reads the Info dictionary.
- **Not from a cleaned-up filename.** A pass that stripped the vendor prefix, the
  product tokens and the version produced `'adix 2'`, `'dqid 3'` and
  `'1 0 0 installation'`: 82.9% of 3,352 derived titles appeared exactly once. The
  cleverness is what generates the garbage; `tib_ems_users_guide` with its
  separators spaced reads acceptably as it is.
- **De-duplicate before copying, not after.** One entry per lower-cased filename
  per doc-class, taking the first -- which is the root folder, because
  `router.source_folders` returns it first.

Blank is the normal state and is never a finding: 27.9% of the corpus's PDFs carry
no `/Title` at all. A read that *raises* is a finding, because it says the shipped
file is damaged -- 7 of 5,007, and only one of them raises a `pypdf` error type.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from docushift.sync.router import (
    DOCUMENT_DOC_CLASSES,
    KIND_TITLES,
    Kind,
    RoutedFile,
)
from docushift.utils.templating import template

# What a doc-class is called in prose, for the index heading.
DOC_CLASS_LABELS: dict[str, str] = {
    "user-guides": "User Guides",
    "release-information": "Release Information",
    "reference-documents": "Reference Documents",
}

# A title ending in one of these is the authoring tool's source filename, not the
# document's name: `.book` and `.fm` are FrameMaker, `.indd` InDesign, `.mif`
# Interleaf. Every junk title in the corpus -- 59 of them, in 35 distinct values
# -- is one of these three shapes.
_JUNK_SUFFIXES = (".book", ".fm", ".doc", ".docx", ".pdf", ".indd", ".mif")
_JUNK_PREFIX = "Microsoft Word - "

_SEPARATORS = re.compile(r"[_.-]+")


@dataclass(frozen=True)
class DocumentEntry:
    """One line of the index: a file, a title, and the two figures AEM asked for."""

    source: Path
    # The published filename, unchanged. The copy keeps the name it shipped with:
    # a reader following a link from a support article is following the filename.
    name: str
    title: str
    # The extension without its dot, lower-cased -- `pdf`, `txt`, `xlsx`.
    type: str
    bytes: int
    kind: Kind

    @property
    def link(self) -> str:
        """The filename, percent-encoded for a Markdown link target.

        Not cosmetic: `mft platform server v7.1 for windows release notes.pdf` is a
        real filename, and a Markdown link whose target contains a space stops at
        the space in every renderer.
        """
        return quote(self.name)


# -- titles ---------------------------------------------------------------------


def is_junk_title(title: str) -> bool:
    """A `/Title` that is the source filename rather than the document's name."""
    text = title.strip()
    if not text:
        return True
    if text.lower() == "untitled":
        return True
    if text.lower().endswith(_JUNK_SUFFIXES):
        return True
    return text.startswith(_JUNK_PREFIX)


def read_pdf_title(path: Path) -> tuple[str, str]:
    """The Info-dictionary `/Title`, and why it is empty when it is.

    Returns `(title, error)`. **`except Exception`, not a `pypdf` error type**:
    of the 7 files in 5,007 that raise, only `TIB_mftcc_8.4.4_user_guide.pdf`
    raises `PdfStreamError` -- `TIB_smap_1.0.0_install_guide.pdf` and
    `silver-mobile`'s two guides raise a bare `ValueError` from inside the parser.
    Catching the library's own exception class would let four filenames take a
    whole sync run down.
    """
    try:
        import pypdf

        with path.open("rb") as handle:
            metadata = pypdf.PdfReader(handle).metadata
        title = str((metadata or {}).get("/Title") or "").strip()
    except Exception as exc:  # noqa: BLE001 - see the docstring; a damaged PDF is data
        return "", f"{type(exc).__name__}: {exc}"
    return ("" if is_junk_title(title) else title), ""


def title_from_name(name: str) -> str:
    """The filename stem with `[_.-]+` collapsed to single spaces. Nothing else."""
    return _SEPARATORS.sub(" ", Path(name).stem).strip()


def title_for(routed: RoutedFile) -> tuple[str, str]:
    """§10.5's chain, first hit wins. Returns `(title, error)`.

    `error` is non-empty only when a PDF read raised; the title is still filled in
    from the filename, because a damaged deliverable is published and named rather
    than skipped.
    """
    if routed.kind is not Kind.UNKNOWN:
        return KIND_TITLES[routed.kind], ""
    error = ""
    if routed.path.suffix.lower() == ".pdf":
        title, error = read_pdf_title(routed.path)
        if title:
            return title, error
    return title_from_name(routed.path.name), error


# -- assembly -------------------------------------------------------------------


def group(routed: Iterable[RoutedFile]) -> dict[str, list[RoutedFile]]:
    """Routed files per doc-class, de-duplicated by lower-cased filename.

    The first occurrence wins, and `router.source_folders` yields the root folders
    first, so the root copy is the published one. A doc-class with no files is
    **absent from the mapping rather than present and empty** -- §10.5 expresses
    emptiness by absence, and an `index.md` linking to nothing is a published dead
    end rather than an empty page.
    """
    grouped: dict[str, list[RoutedFile]] = {}
    seen: dict[tuple[str, str], bool] = {}
    for item in routed:
        key = (item.doc_class, item.path.name.lower())
        if key in seen:
            continue
        seen[key] = True
        grouped.setdefault(item.doc_class, []).append(item)
    return {name: grouped[name] for name in DOCUMENT_DOC_CLASSES if name in grouped}


def entries_for(files: Iterable[RoutedFile]) -> tuple[list[DocumentEntry], list[tuple[Path, str]]]:
    """One doc-class's entries, ordered. Also returns the PDFs that would not read.

    Order is **kind rank, then title, then filename** -- the shared rank table in
    `router.Kind`. The filename is the last key so that two files with the same
    canonical title (a product shipping two reminder notices) have a stable order
    rather than the filesystem's.
    """
    entries: list[DocumentEntry] = []
    unreadable: list[tuple[Path, str]] = []
    for item in files:
        title, error = title_for(item)
        if error:
            unreadable.append((item.path, error))
        entries.append(
            DocumentEntry(
                source=item.path,
                name=item.path.name,
                title=title,
                type=item.path.suffix.lstrip(".").lower(),
                bytes=item.path.stat().st_size,
                kind=item.kind,
            )
        )
    entries.sort(key=lambda entry: (entry.kind, entry.title.lower(), entry.name.lower()))
    return entries, unreadable


def index_title(product_name: str, version: str, doc_class: str) -> str:
    """What the doc-class index calls itself: product, version, doc-class."""
    label = DOC_CLASS_LABELS.get(doc_class, doc_class)
    return " ".join(part for part in (product_name.strip(), version.strip(), label) if part)


# -- rendering ------------------------------------------------------------------


def render_index(entries: list[DocumentEntry], title: str, doc_class: str, templates: Path) -> str:
    """`index.md`, frontmatter included.

    Unlike `index.md.j2`, this template writes its own frontmatter: that one is
    body-only because the converter's `_render` heads every page it emits, and no
    converter runs over a folder of PDFs.
    """
    return template(templates, "documents_index.md.j2").render(
        title=title, doc_class=doc_class, entries=entries
    )


def render_toc(entries: list[DocumentEntry], title: str, templates: Path) -> str:
    """`toc.yml`, flat -- these doc-classes have no hierarchy to indent."""
    return template(templates, "documents_toc.yml.j2").render(title=title, entries=entries)
