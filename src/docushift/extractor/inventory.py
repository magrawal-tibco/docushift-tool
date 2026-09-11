"""Stage 4, second half: one walk of the extracted tree, and everything it measures.

Implements `design.md` §6.1 steps 4-5, §6.2, §6.3's predicate half and §6.4
steps 1-2. **One walk**, because §6.3 and §6.4 both insist on it: the API
partition, the asset categories and the destinations describe one moment or they
describe nothing. A second traversal would let the two disagree about a tree
somebody was writing to, and the disagreement would be silent.

What the walk does *not* do is parse. It collects the CSH sources' paths and
`inventory_tree` reads them afterwards, off that list -- a parse is not a
traversal, and interleaving them would make the walk's cost depend on how much
help a product happens to ship.

Three rules the walk is built on, all from §6.3:

- **Directories are not counted**, only files.
- **Symlinks are not followed.** A documentation ZIP has no legitimate reason to
  contain one, and §6.1 step 2 already refuses members that escape the target.
- **A partial walk writes nothing.** An unreadable directory mid-descent sets
  `partial`, and the caller leaves the five columns blank: a footprint measured
  over part of a tree is a wrong number rather than a small one.
"""

import os
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from docushift.apiref import has_api_marker, looks_like_api_name
from docushift.engines.csh import CshFormat, CshSource, csh_format_of, read_csh_source
from docushift.engines.roots import owning_root
from docushift.models import SourceEngine


class AssetCategory(StrEnum):
    """What kind of file this is. Every file lands in exactly one.

    `topic` is here so the inventory *sums to the file count* -- an invariant
    worth having, and the reason the table can be read as an account of the whole
    package rather than of the part somebody remembered to classify. §6.4 names
    the other seven.
    """

    TOPIC = "topic"
    IMAGE = "image"
    MEDIA = "media"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    SOURCE_FORMAT = "source-format"
    SKIN = "skin"
    OTHER = "other"


class Destination(StrEnum):
    """Which part of the pipeline claims the file (§5.5.2)."""

    API_REFERENCE = "api-reference"
    OUTPUT_ROOT = "output-root"
    DOCUMENT_ROUTER = "document-router"
    UNCLAIMED = "unclaimed"


# Nothing is filtered by an allow-list -- the corpus holds 100 extensions and
# each is counted somewhere. These sets decide *which* bucket, never *whether*.
_TOPIC = frozenset({".htm", ".html", ".xhtml"})
_IMAGE = frozenset({
    # GIF and JPG are 36.2% of the corpus's images and were missing from the
    # list this replaces; GIF is the dominant format in the whole of WebWorks.
    ".png", ".gif", ".jpg", ".jpeg", ".svg", ".bmp", ".ico", ".tif", ".tiff", ".webp",
})
_MEDIA = frozenset({
    ".mp4", ".m4v", ".mov", ".avi", ".wmv", ".webm", ".ogg", ".ogv", ".mp3", ".wav", ".swf",
})
_DOCUMENT = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".csv", ".txt", ".rtf", ".odt", ".ods", ".ipynb",
})
_ARCHIVE = frozenset({".zip", ".jar", ".tar", ".gz", ".tgz", ".bz2", ".7z", ".rar", ".war", ".ear"})
# Visio and draw.io originals shipped beside their exported PNG (§5.1.9). 1,785
# files that no topic references, and a category rather than an asset so that
# they are visible without ever being mistaken for something to copy.
_SOURCE_FORMAT = frozenset({".vsd", ".vsdx", ".drawio", ".psd", ".ai", ".fm", ".indd", ".eps"})

# Skin is a *location*, not an extension: a `.gif` in `Skins/` is chrome, and
# that branch takes 48.7% of DITA and 76.2% of WebWorks reference traffic
# (`architecture.md` §5.5.4). Prefixes are relative to the output root and are
# matched as **whole segments, never as substrings** -- the same rule §6.3.1
# Finding 2 imposes on API paths, and the predecessor breaks in both places.
_SKIN_PREFIXES: dict[SourceEngine, tuple[tuple[str, ...], ...]] = {
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
}

# §10.4's document router owns whole deliverables rather than assets: the PDFs
# and readmes a package ships beside its help output. 9,133 of the corpus's
# 10,800 PDFs are here, and only 10 are inside an engine output root.
_ROUTER_DIRS = frozenset({"pdf", "doc"})


@dataclass
class Bucket:
    files: int = 0
    bytes: int = 0

    def add(self, size: int) -> None:
        self.files += 1
        self.bytes += size


@dataclass
class Inventory:
    """Everything the one walk measured, before any of it is written down."""

    api_roots: list[Path] = field(default_factory=list)
    api_files: int = 0
    doc_files: int = 0
    csh_sources: list[CshSource] = field(default_factory=list)
    # Distinct identifiers across every source, byte-exact and case-sensitive
    # (§9.1), deduplicated version-wide to match how §9.3's resolver merges them.
    csh_names: set[str] = field(default_factory=set)
    buckets: dict[tuple[str, AssetCategory, Destination], Bucket] = field(default_factory=dict)
    # Top path segment -> what fell through there. §5.5.2's 62,525-file residue.
    unclaimed: dict[str, Bucket] = field(default_factory=dict)
    # Directories whose *name* looks like an API reference but which carry no
    # marker. Reported, never classified: their files stay in `doc_files`.
    triage: list[tuple[str, int]] = field(default_factory=list)
    # An unreadable directory. The caller writes no columns when this is set.
    partial: bool = False

    @property
    def total_files(self) -> int:
        return self.api_files + self.doc_files

    @property
    def readable_csh_sources(self) -> int:
        """Sources located, unreadable ones included -- `_has_csh` counts finding a file.

        `architecture.md` §5.4.4: a source that was located but could not be
        parsed still sets `_has_csh`, with the failure counted and named. "Help we
        could not read" and "no help" are different facts.
        """
        return len(self.csh_sources)

    def rows(self) -> list[tuple[str, str, str, int, int]]:
        """`asset_inventory` rows, in a stable order."""
        return [
            (root, str(category), str(destination), bucket.files, bucket.bytes)
            for (root, category, destination), bucket in sorted(
                self.buckets.items(), key=lambda item: (item[0][0], str(item[0][1]), str(item[0][2]))
            )
        ]

    def csh_rows(self) -> list[tuple[str, str, str, int, str]]:
        return [
            (
                source.path.as_posix(),
                source.doc_set,
                str(source.fmt),
                source.count,
                str(source.status),
            )
            for source in self.csh_sources
        ]


def _category(name: str) -> AssetCategory:
    suffix = os.path.splitext(name)[1].lower()
    if suffix in _TOPIC:
        return AssetCategory.TOPIC
    if suffix in _IMAGE:
        return AssetCategory.IMAGE
    if suffix in _MEDIA:
        return AssetCategory.MEDIA
    if suffix in _DOCUMENT:
        return AssetCategory.DOCUMENT
    if suffix in _ARCHIVE:
        return AssetCategory.ARCHIVE
    if suffix in _SOURCE_FORMAT:
        return AssetCategory.SOURCE_FORMAT
    return AssetCategory.OTHER


def _is_skin(relative: tuple[str, ...], engine: SourceEngine) -> bool:
    """Is this path, relative to its output root, inside the engine's chrome?"""
    folded = tuple(part.lower() for part in relative)
    return any(folded[: len(prefix)] == prefix for prefix in _SKIN_PREFIXES.get(engine, ()))


def inventory_tree(
    tree: Path, engine: SourceEngine, output_roots: list[Path]
) -> Inventory:
    """Walks `tree` once and measures it. Never raises.

    `output_roots` comes from `engines.roots.find_output_roots`, which 4b-1
    already ran and recorded -- passed in rather than re-derived so that the
    inventory and the extract report cannot describe two different sets of roots.
    """
    result = Inventory()
    # Direct file count per directory, so a triage candidate's total can be
    # summed by prefix afterwards without a second traversal.
    direct: dict[Path, int] = defaultdict(int)
    candidates: list[Path] = []
    csh_paths: list[tuple[Path, CshFormat]] = []

    # (directory, the API root it sits under, if any)
    stack: list[tuple[Path, Path | None]] = [(tree, None)]
    while stack:
        current, api_root = stack.pop()
        if api_root is None and has_api_marker(current):
            # Outermost match wins and the descent stops testing: a Javadoc tree
            # inside a Doxygen tree is one artefact (§6.3.1 Finding 4).
            api_root = current
            result.api_roots.append(current)
        try:
            entries = list(os.scandir(current))
        except OSError:
            result.partial = True
            continue
        for entry in entries:
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if api_root is None and looks_like_api_name(entry.name):
                        candidates.append(path)
                    stack.append((path, api_root))
                    continue
                size = entry.stat(follow_symlinks=False).st_size
            except OSError:
                result.partial = True
                continue
            direct[current] += 1
            _count_file(result, tree, path, size, engine, output_roots, api_root)
            fmt = csh_format_of(path)
            if fmt is not None:
                csh_paths.append((path, fmt))

    result.api_roots.sort(key=lambda path: (len(path.parts), str(path)))
    result.triage = _triage(tree, candidates, direct, result.api_roots)
    _read_csh(result, tree, csh_paths, output_roots)
    return result


def _count_file(
    result: Inventory,
    tree: Path,
    path: Path,
    size: int,
    engine: SourceEngine,
    output_roots: list[Path],
    api_root: Path | None,
) -> None:
    """Partitions one file, and buckets it by root, category and destination."""
    relative = path.relative_to(tree)
    if api_root is not None:
        result.api_files += 1
        # API-reference trees sit *inside* an output root as often as beside one,
        # so this branch is tested first: a file counted in both destinations
        # would double the totals.
        _bucket(result, _rel(tree, api_root), _category(path.name), Destination.API_REFERENCE, size)
        return

    result.doc_files += 1
    root = owning_root(path, output_roots)
    if root is not None:
        inside = path.relative_to(root).parts
        category = AssetCategory.SKIN if _is_skin(inside, engine) else _category(path.name)
        _bucket(result, _rel(tree, root), category, Destination.OUTPUT_ROOT, size)
        return

    if relative.parts[0].lower() in _ROUTER_DIRS:
        _bucket(result, "", _category(path.name), Destination.DOCUMENT_ROUTER, size)
        return

    _bucket(result, "", _category(path.name), Destination.UNCLAIMED, size)
    segment = relative.parts[0] if len(relative.parts) > 1 else "."
    result.unclaimed.setdefault(segment, Bucket()).add(size)


def _bucket(
    result: Inventory, root: str, category: AssetCategory, destination: Destination, size: int
) -> None:
    result.buckets.setdefault((root, category, destination), Bucket()).add(size)


def _rel(tree: Path, path: Path) -> str:
    return "" if path == tree else path.relative_to(tree).as_posix()


def _triage(
    tree: Path, candidates: list[Path], direct: dict[Path, int], api_roots: list[Path]
) -> list[tuple[str, int]]:
    """API-ish names carrying no marker, with how many files sit beneath each.

    A report line and nothing more. The files stay in `_doc_files` until a human
    says otherwise -- which is the only thing standing between the tool and
    `api-exchange-gateway/`, a product name with 15,677 files of documentation.
    """
    lines = []
    for candidate in sorted(candidates, key=lambda p: (len(p.parts), str(p))):
        if any(candidate == root or root in candidate.parents for root in api_roots):
            continue
        beneath = sum(
            count for directory, count in direct.items()
            if directory == candidate or candidate in directory.parents
        )
        lines.append((_rel(tree, candidate), beneath))
    return lines


def _book_of(path: Path, fmt: CshFormat) -> Path:
    """The book or doc-set directory a source belongs to, from its own layout.

    Only used where no output root claims the source -- the 5 partial trees and
    1 stray of `architecture.md` §5.4.1. WebWorks is two levels deeper than the
    other two (`<book>/wwhdata/common/topics.js`), so the depth is per format
    rather than a constant.
    """
    if fmt is CshFormat.WEBWORKS_TOPICS:
        return path.parent.parent.parent
    return path.parent.parent


def _read_csh(
    result: Inventory, tree: Path, located: list[tuple[Path, CshFormat]], output_roots: list[Path]
) -> None:
    """Reads what the walk found. Empty and unparseable are counted, never raised."""
    for path, fmt in sorted(located, key=lambda item: str(item[0])):
        source = read_csh_source(path, fmt)
        # The doc-set is the output root that owns the source; where none does --
        # the 5 partial trees and 1 stray of §5.4.1 -- the source's own
        # grandparent stands in, which is the book directory in every observed
        # layout (`<book>/Data/Alias.xml`, `<book>/wwhdata/common/topics.js`).
        root = owning_root(path, output_roots)
        source.doc_set = _rel(tree, root) if root is not None else _rel(tree, _book_of(path, fmt))
        source.path = path.relative_to(tree)
        result.csh_sources.append(source)
        result.csh_names.update(entry.identifier for entry in source.entries)
