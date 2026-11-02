"""The old site's TOC, per engine, as a tree keyed by published page (Phase 58, step 8).

Each reader takes the engine's own *raw* TOC reader -- never the engine's navigation
builder, which already drops and folds nodes -- and resolves every entry to its
source file, then to the published page through the caller's `key_of` (the
`output_map`, then the merge's `redirects.yml`). A bookmark entry is placed with
the caller's `bookmark`, which reads the published page's markers.

Every reader returns an `OldToc`: the tree, the `(source, title)` rows whose page
was never converted, and the parts it could not read at all, each named.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from docushift.engines import dita, docbook, flare_toc
from docushift.engines.webworks import GENERATED_LIST_STEMS
from docushift.engines.webworks_toc import read_books, read_files, read_return
from docushift.engines.webworks_toc import read_toc as read_webworks_toc
from docushift.models import SourceEngine
from docushift.transforms import links, markdown
from docushift.utils.longpath import long_path
from docushift.verify.toc import Node, root

KeyOf = Callable[[str], str]
Bookmark = Callable[[str, str], str]


@dataclass
class OldToc:
    tree: Node
    unconverted: list[tuple[str, str]] = field(default_factory=list)
    #: A part of the version whose old TOC could not be read, and why.
    unchecked: list[str] = field(default_factory=list)


def _relative(path: Path, extracted: Path) -> str:
    text = path.relative_to(extracted).as_posix()
    return "" if text == "." else text


def _join(base: str, relative: str) -> str:
    return posixpath.normpath(f"{base}/{relative}" if base else relative)


def _read(path: Path) -> str | None:
    try:
        return long_path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None


def _soup(path: Path):
    text = _read(path) if path.is_file() else None
    return markdown.parse(text) if text is not None else None


def _wrap(units: list[tuple[str, list[Node]]]) -> Node:
    """One unit's nodes are the version's; several become one heading each, as
    `converter/navigation._assemble` lays them out."""
    if len(units) == 1:
        return root(units[0][1])
    return root([Node(title, None, nodes) for title, nodes in units])


# -- Flare ---------------------------------------------------------------------


def flare(roots: list[Path], extracted: Path, outmap: dict[str, str], key_of: KeyOf,
          bookmark: Bookmark) -> OldToc:
    """Every Flare root's TOC as one tree. A `.flprj` insertion point is a merge
    marker, not a page (Phase 51), and is left out."""
    result = OldToc(root([]))

    def build(nodes, base: str) -> list[Node]:
        out: list[Node] = []
        for node in nodes:
            if node.entry.project:
                continue
            key = None
            if node.entry.path:
                source = f"{base}/{node.entry.path}" if base else node.entry.path
                if source in outmap:
                    key = bookmark(key_of(source), node.entry.anchor)
                else:
                    result.unconverted.append((source, node.entry.label))
            out.append(Node(node.entry.label, key, build(node.children, base)))
        return out

    top: list[Node] = []
    for root_dir in roots:
        manifest = flare_toc.read_manifest(root_dir)
        name = manifest.toc if manifest and manifest.toc else ""
        files = [root_dir / name] if name else flare_toc.tree_files(root_dir)[:1]
        for file in files:
            toc = flare_toc.read_toc(file)
            top.extend(build(toc.nodes, _relative(root_dir, extracted)))
    result.tree = root(top)
    return result


# -- DITA (SDL SuiteHelp) ------------------------------------------------------


def dita_sets(roots: list[Path], extracted: Path, outmap: dict[str, str], key_of: KeyOf,
              bookmark: Bookmark) -> OldToc:
    """Each doc-set's `suitehelp_topic_list.html` (else `toc_crawler.html`).

    An href names a topic by GUID. A `_unique_N` republished copy is never
    converted; it resolves to its original by the topic identifier, which is how
    the engine pairs them (`dita._deduplicate`), so its TOC position is not an
    unconverted topic.
    """
    result = OldToc(root([]))
    units = [unit for unit in (_DitaSet(root_dir, extracted, outmap, key_of, result).read()
                               for root_dir in roots) if unit is not None]
    if units:
        result.tree = _wrap(units)
    return result


class _DitaSet:
    def __init__(self, root_dir: Path, extracted: Path, outmap: dict[str, str], key_of: KeyOf,
                 result: OldToc) -> None:
        self.root_dir, self.extracted, self.key_of, self.result = root_dir, extracted, key_of, result
        self.base = _relative(root_dir, extracted)
        self.prefix = f"{self.base}/" if self.base else ""
        self.by_stem = {PurePosixPath(source).stem.lower(): source for source in outmap
                        if source.startswith(self.prefix) and "/" not in source[len(self.prefix):]}
        self.identities: dict[str, str] | None = None

    def read(self) -> tuple[str, list[Node]] | None:
        if not self.by_stem:
            self.result.unchecked.append(f"{self.base or '.'}: no topic of this doc-set was converted")
            return None
        entries: list = []
        for name in dita.TOC_SOURCES:
            if (self.root_dir / name).is_file():
                entries = dita.read_toc(self.root_dir / name)
                if entries:
                    break
        if not entries:
            self.result.unchecked.append(f"{self.base or '.'}: no SuiteHelp TOC file")
            return None
        return _publication_title(self.root_dir), self.build(entries)

    def build(self, items) -> list[Node]:
        out: list[Node] = []
        for item in items:
            key = None
            if item.href:
                source, converted = self.resolve(item.href)
                if source is not None and converted:
                    key = self.key_of(source)
                elif source is not None:
                    self.result.unconverted.append((source, item.label))
            out.append(Node(item.label, key, self.build(item.children)))
        return out

    def resolve(self, href: str) -> tuple[str | None, bool]:
        """(source, converted). None for an href naming no file of the doc-set."""
        page = href.partition("#")[0]
        guid = dita._guid_of(page)
        if guid is None:
            return None, False
        if guid in self.by_stem:
            return self.by_stem[guid], True
        name = PurePosixPath(page).name
        path = self.root_dir / name
        text = _read(path) if path.is_file() else None
        if text is None:
            return None, False
        if self.identities is None:
            self.identities = {}
            for source in self.by_stem.values():
                body = _read(self.extracted / source)
                if body is not None:
                    self.identities.setdefault(dita._profile(self.extracted / source, body).guid, source)
        original = self.identities.get(dita._profile(path, text).guid)
        return (original, True) if original else (f"{self.prefix}{name}", False)


def _publication_title(root_dir: Path) -> str:
    """The doc-set's label in a multi-unit `toc.yml`: its homepage's publication title."""
    for path in sorted(root_dir.iterdir()):
        if path.is_file() and dita.HOMEPAGE_MARKER in path.name.lower():
            text = _read(path)
            if text is not None:
                metadata: dict[str, str] = {}
                dita._read_metadata(text, metadata)
                return metadata.get("publication-title", "")
    return ""


# -- WebWorks ------------------------------------------------------------------


def webworks_books(roots: list[Path], extracted: Path, outmap: dict[str, str], key_of: KeyOf,
                   bookmark: Bookmark) -> OldToc:
    """Each book's `toc.js`, its entries naming `files.js` by position.

    Matched to `output_map` without regard to case, as the engine keys its books.
    A stripped book (no `files.js`) had no navigation on the old site: it is named
    as unchecked, never passed in silence.
    """
    result = OldToc(root([]))
    lower = {source.lower(): source for source in outmap}
    units = [unit for unit in (_Book(book, extracted, lower, key_of, bookmark, result).read()
                               for book in _books_in_order(roots, extracted)) if unit is not None]
    if units:
        result.tree = _wrap(units)
    return result


class _Book:
    def __init__(self, book: Path, extracted: Path, lower: dict[str, str], key_of: KeyOf,
                 bookmark: Bookmark, result: OldToc) -> None:
        self.book, self.extracted, self.lower = book, extracted, lower
        self.key_of, self.bookmark, self.result = key_of, bookmark, result
        self.base = _relative(book, extracted)
        self.files: list = []

    def read(self) -> tuple[str, list[Node]] | None:
        name = self.base or "."
        prefix = f"{self.base}/".lower() if self.base else ""
        if not any(source.startswith(prefix) for source in self.lower):
            self.result.unchecked.append(f"{name}: no topic of this book was converted")
            return None
        runtime = self.book / "wwhdata"
        files_js = runtime / "common" / "files.js"
        if not files_js.is_file():
            self.result.unchecked.append(f"{name}: stripped book, no navigation on the old site")
            return None
        self.files = read_files(files_js)
        entries = read_webworks_toc(runtime / "js" / "toc.js")
        if not entries:
            self.result.unchecked.append(f"{name}: no toc.js entries")
            return None
        return read_return(runtime / "common" / "title.js"), self.build(entries)

    def build(self, items) -> list[Node]:
        out: list[Node] = []
        for item in items:
            key = None
            if item.index is not None and 0 <= item.index < len(self.files):
                wanted = _join(self.base, self.files[item.index].href)
                source = self.lower.get(wanted.lower())
                if source is not None:
                    key = self.bookmark(self.key_of(source), item.anchor)
                elif _generated_list(wanted):
                    pass  # `lof`/`lot`/`ix`: never converted, by the engine's own rule
                elif (self.extracted / wanted).is_file():
                    self.result.unconverted.append((wanted, item.label))
            out.append(Node(item.label, key, self.build(item.children)))
        return out


def _generated_list(path: str) -> bool:
    """A list of figures, tables or index entries, which WebWorks never converts.

    Matched as the engine matches it (`webworks._skip_reason`): the stem, folded,
    with the generator's numbering (`lof.2.htm`, `LOF.htm`) read off first.
    """
    stem = PurePosixPath(path).name.lower().split(".", 1)[0]
    return stem in GENERATED_LIST_STEMS


def _books_in_order(roots: list[Path], extracted: Path) -> list[Path]:
    """Books grouped by collection in `books.xml` order, the rest after, as the
    engine orders them (`webworks._order`)."""
    known = set(roots)
    claimed: list[Path] = []
    for candidate in sorted({book.parent for book in roots} | {extracted}):
        collection = read_books(candidate / "wwhelp" / "books.xml")
        if collection is None:
            continue
        for reference in collection.books:
            book = candidate / Path(*PurePosixPath(reference.directory).parts)
            if book in known and book not in claimed:
                claimed.append(book)
    return claimed + sorted(book for book in roots if book not in claimed)


# -- DocBook -------------------------------------------------------------------


def docbook_guides(roots: list[Path], extracted: Path, outmap: dict[str, str], key_of: KeyOf,
                   bookmark: Bookmark) -> OldToc:
    """The menu's guides in order, each with its book page's `div.toc`, then each
    listed page's own `div.toc` to the engine's depth, first sighting only.

    Guides the menu does not name follow alphabetically, as the engine orders
    them. Pages the engine adds from the link graph, or as unfiled, are in
    `toc.yml` and not here; the comparison walks old -> new only. The engine
    converts one DocBook root; any other is a duplicate it skipped.
    """
    result = OldToc(root([]))
    for root_dir in roots:
        reader = _DocBookRoot(root_dir, extracted, outmap, key_of, bookmark, result)
        if reader.pages:
            result.tree = root(reader.guides())
            break
    return result


class _DocBookRoot:
    def __init__(self, root_dir: Path, extracted: Path, outmap: dict[str, str], key_of: KeyOf,
                 bookmark: Bookmark, result: OldToc) -> None:
        self.root_dir, self.key_of, self.bookmark, self.result = root_dir, key_of, bookmark, result
        self.base = _relative(root_dir, extracted)
        prefix = f"{self.base}/" if self.base else ""
        self.lower = {source.lower(): source for source in outmap}
        self.pages = sorted(PurePosixPath(source[len(prefix):]) for source in outmap if source.startswith(prefix))
        self.filed: set[str] = set()

    def guides(self) -> list[Node]:
        index = _soup(self.root_dir / "index.html")
        menu = docbook.read_menu(index, PurePosixPath()) if index is not None else []
        ordered: list[tuple[str, PurePosixPath]] = []
        seen: set[str] = set()
        for label, relative in menu:
            guide = relative.parts[0] if len(relative.parts) > 1 else ""
            if guide in seen or (guide == "" and str(relative) == "index.html"):
                continue
            seen.add(guide)
            ordered.append((label, relative))
        for guide in sorted({page.parts[0] for page in self.pages if len(page.parts) > 1} - seen):
            ordered.append(("", PurePosixPath(guide, "index.html")))

        top: list[Node] = []
        for label, book in ordered:
            source = self.source_of(book)
            if source is None:
                continue
            self.filed.add(source)
            children = self.build(self.entries_of(book), book, 0)
            top.append(Node(label or _title(self.root_dir / Path(*book.parts)), self.key_of(source), children))
        return top

    def source_of(self, relative: PurePosixPath) -> str | None:
        return self.lower.get(_join(self.base, str(relative)).lower())

    def entries_of(self, page: PurePosixPath) -> list:
        soup = _soup(self.root_dir / Path(*page.parts))
        container = soup.find(id=docbook.CONTENT_ID) if soup is not None else None
        listing = container.find("div", class_="toc") if container is not None else None
        return docbook.read_toc(listing) if listing is not None else []

    def build(self, items, page: PurePosixPath, depth: int) -> list[Node]:
        """The entries as the old site listed them, parent before its children.

        `filed` holds every page and `page#section` already placed. A part page's
        own `div.toc` repeats the slice its book already listed, so an entry
        placed before is left out, and only a page's first placement opens its own
        `div.toc`, to the engine's depth.
        """
        out: list[Node] = []
        for item in items:
            reference = links.classify(item.href) if item.href else None
            target = None
            if reference is not None and reference.path and links.is_topic(reference.path):
                target = links.resolve(page.parent, reference.path)
            elif reference is not None and item.href.startswith("#"):
                target = page
            source = self.source_of(target) if target is not None else None
            if source is None:
                if target is not None and (self.root_dir / Path(*target.parts)).is_file():
                    self.result.unconverted.append((_join(self.base, str(target)), item.label))
                children = self.build(item.children, page, depth)
                if children or not item.href:
                    out.append(Node(item.label, None, children))
                continue
            place = f"{source}#{reference.fragment}" if reference.fragment else source
            if place in self.filed:
                children = self.build(item.children, page, depth)
                if children:
                    out.append(Node(item.label, None, children))
                continue
            self.filed.add(place)
            node = Node(item.label, self.bookmark(self.key_of(source), reference.fragment))
            node.children = self.build(item.children, page, depth)
            if not reference.fragment and depth < docbook.TOC_DEPTH:
                node.children.extend(self.build(self.entries_of(target), target, depth + 1))
            out.append(node)
        return out


def _title(path: Path) -> str:
    soup = _soup(path)
    title = soup.find("title") if soup is not None else None
    return " ".join(title.get_text(" ").split()) if title is not None else ""


#: The reader for each engine whose roots `find_output_roots` locates. Flare is
#: read from its `HelpSystem.xml` roots by the driver, as before.
READERS = {
    SourceEngine.DITA: dita_sets,
    SourceEngine.WEBWORKS: webworks_books,
    SourceEngine.DOCBOOK: docbook_guides,
}
