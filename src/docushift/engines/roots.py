"""Where an engine's output roots are, inside an extracted tree.

`design.md` §7.1 is explicit that this is a **separate step from engine
detection**: the engine answers "which converter", once per version, while the
roots answer "which units of work", and one version commonly has several. It
lives in `engines/` rather than `extractor/` because it is engine-specific
knowledge -- Phase 5's converters locate their work with the same function that
Phase 4b's extract reports with. One function, one answer, two callers.

Roots are found **by content, never by a configured path**. Measured against the
`html-to-md` cache (`architecture.md` §5.1.1, §5.1.3, §5.3.2, §5.6.3):

- Flare: a directory holding `Data/HelpSystem.xml`. 51 of 595 versions ship more
  than one, and 153 roots nest inside another, so the walk descends rather than
  stopping at the first match.
- DITA (SDL): a directory holding a `GUID-*.html`, at no fixed depth.
- WebWorks: the parent of a `wwhdata/` directory -- 195 of 195, zero either way.
- DocBook: a directory holding a DocBook-marked page whose stylesheet link
  resolves **inside that directory**. "Holds a DocBook page" alone is not enough:
  a `str` version ships eight top-level directories that duplicate a guide already
  under `html/`, byte for byte, and they link `../css/sbhelp.css` -- outside
  themselves, and absent. The link test selects exactly `html` in 10 of 10
  versions and rejects all 42 duplicates.

`SKIN_PREFIXES` lives here for the same reason the roots do: it is per-engine
layout knowledge with two stage-level callers. Stage 4 categorises a file as
`skin`, Stage 5 drops a reference to one -- and those have to be the same answer,
or a file is chrome in the inventory and an asset in the copy set.
"""

import re
from pathlib import Path

from docushift.engines.detector import GUID_HTML_NAME
from docushift.models import SourceEngine

# The string DocBook XSL writes into the head of every page it generates. It is
# also what `detect_tree` decides on, so detection and root-finding agree by
# construction rather than by coincidence (`architecture.md` §5.6.2).
DOCBOOK_MARKER = b"DocBook XSL Stylesheets"

# Enough to cover the head of any generated page; the marker sits in the first
# comment. Reading whole files here would mean reading a 200 MB tree to answer a
# question about directories.
_HEAD_BYTES = 6000

_STYLESHEET_HREF = re.compile(rb"""href\s*=\s*["']([^"']+\.css)["']""", re.IGNORECASE)

# How many of a directory's own pages the DocBook root test reads before giving
# up. A directory of 2,400 javadoc files answers "no" from its first few as
# surely as from all of them, and the DocBook directories are homogeneous.
_ROOT_PROBE_LIMIT = 25

# Skin is a *location*, not an extension: a `.gif` in `Skins/` is chrome. This
# branch takes 48.7% of DITA and 76.2% of WebWorks reference traffic
# (`architecture.md` §5.5.4), so it is the main path rather than an edge case.
# Prefixes are relative to the output root and are matched as **whole segments,
# never as substrings** -- the same rule §6.3.1 Finding 2 imposes on API paths,
# and the predecessor breaks it in both places.
SKIN_PREFIXES: dict[SourceEngine, tuple[tuple[str, ...], ...]] = {
    SourceEngine.FLARE: (
        ("skins",),
        ("resources", "scripts"),
        ("resources", "stylesheets"),
        ("resources", "masterpages"),
        ("resources", "templateextensions"),
        ("data",),
    ),
    SourceEngine.DITA: (("static",), ("fonts",)),
    SourceEngine.WEBWORKS: (("wwhdata",), ("wwhelp",), ("tpl",)),
    SourceEngine.DOCBOOK: (("css",),),
}


def is_skin_path(relative: tuple[str, ...], engine: SourceEngine) -> bool:
    """Is this path, relative to its output root, inside the engine's chrome?"""
    folded = tuple(part.lower() for part in relative)
    return any(folded[: len(prefix)] == prefix for prefix in SKIN_PREFIXES.get(engine, ()))


def _walk_dirs(tree: Path):
    """Every directory in `tree`, `tree` itself included, unreadable ones skipped."""
    stack = [tree]
    while stack:
        current = stack.pop()
        yield current
        try:
            stack.extend(child for child in current.iterdir() if child.is_dir())
        except OSError:
            continue


def _is_flare_root(directory: Path) -> bool:
    return (directory / "Data" / "HelpSystem.xml").is_file()


def _is_dita_root(directory: Path) -> bool:
    try:
        return any(GUID_HTML_NAME.match(child.name.lower()) for child in directory.iterdir() if child.is_file())
    except OSError:
        return False


def _is_webworks_root(directory: Path) -> bool:
    return (directory / "wwhdata").is_dir()


def is_docbook_page(path: Path) -> bool:
    """Did DocBook XSL generate this file? The head carries the answer.

    One package holds four generators -- DocBook, javadoc, Doxygen and Doxia
    (`architecture.md` §5.6.1) -- so "is an `.html` under the root" is not the
    question. This is, and it is exact.
    """
    try:
        with path.open("rb") as handle:
            return DOCBOOK_MARKER in handle.read(_HEAD_BYTES)
    except OSError:
        return False


def _html_files(directory: Path) -> list[Path]:
    """The directory's own HTML files, `index.html` first, then sorted."""
    try:
        files = [
            child
            for child in directory.iterdir()
            if child.is_file() and child.suffix.lower() in (".html", ".htm")
        ]
    except OSError:
        return []
    return sorted(files, key=lambda path: (path.name.lower() != "index.html", path.name.lower()))


def _links_stylesheet_within(page: Path, directory: Path) -> bool:
    """Does `page` link a stylesheet that resolves to a file inside `directory`?"""
    try:
        with page.open("rb") as handle:
            head = handle.read(_HEAD_BYTES)
    except OSError:
        return False
    for match in _STYLESHEET_HREF.finditer(head):
        href = match.group(1).decode("utf-8", "replace").strip()
        if not href or "://" in href or href.startswith(("/", "#")):
            continue
        target = Path(page.parent, href)
        try:
            resolved = target.resolve()
            inside = resolved.is_relative_to(directory.resolve())
        except (OSError, ValueError):
            continue
        if inside and resolved.is_file():
            return True
    return False


def _is_docbook_root(directory: Path) -> bool:
    for page in _html_files(directory)[:_ROOT_PROBE_LIMIT]:
        if is_docbook_page(page) and _links_stylesheet_within(page, directory):
            return True
    return False


_RULES = {
    SourceEngine.FLARE: _is_flare_root,
    SourceEngine.DITA: _is_dita_root,
    SourceEngine.WEBWORKS: _is_webworks_root,
    SourceEngine.DOCBOOK: _is_docbook_root,
}


def find_output_roots(tree: Path, engine: SourceEngine) -> list[Path]:
    """The output roots of `tree` for `engine`, sorted shallowest first.

    An **empty list means no rule applies** -- either the engine has none (no
    unconvertible engine does) or the markers are absent from a tree that detected
    on content. Callers treat that as "the version tree is the single unit of
    work"; what they must not do is treat it as "there is nothing here", which is
    a different fact and one this function never reports.

    Roots are returned even when one nests inside another, because that is the
    measured shape of the corpus rather than a defect. `owning_root` resolves
    which of them owns a given file.
    """
    rule = _RULES.get(engine)
    if rule is None:
        return []
    roots = [directory for directory in _walk_dirs(tree) if rule(directory)]
    # Sorted by depth then by path: deterministic, and the shallowest root first
    # is the order a human reads a bundle in.
    return sorted(roots, key=lambda path: (len(path.parts), str(path)))


def owning_root(path: Path, roots: list[Path]) -> Path | None:
    """Which root owns `path`. **The innermost one** (`architecture.md` §5.1.3).

    153 Flare roots nest inside another, and a file under a nested root belongs to
    that root and not to its container -- getting this backwards silently
    attributes a sub-guide's topics to its parent guide.
    """
    best: Path | None = None
    for root in roots:
        contains = path == root or root in path.parents
        if contains and (best is None or len(root.parts) > len(best.parts)):
            best = root
    return best
