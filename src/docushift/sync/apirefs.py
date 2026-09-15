"""Stage 6d's first step: which API trees get published, and under what name.

`design.md` §10.7. Stage 4 records where the API trees are; this decides which of
them is a *distinct artefact* and what to call its folder. Both questions come
from the same measurement of the in-scope corpus -- 165 roots in 49 versions
across 13 products -- and in both the obvious answer is wrong:

- **The leaf name is not the folder name.** `lib` is the commonest leaf in the
  corpus (34 of 165) and it is not a language, it is the library half of a Javadoc
  pair whose other half is `sample`. Leaf names collide inside a single version in
  **16 of 49** versions -- `tps/6.2.0` has four roots called `lib` -- while the
  relative path from the version root collides in **none**. So the name is built
  from the path, with the container segments that carry no information dropped.
- **Not every root is a distinct artefact.** The extracts self-nest: `rtview`'s
  `5.9.1-august-2011` contains itself four times over, `tps/6.0.0` carries
  `api/api/java/lib` beside `api/java/lib`, and `ftl` 7.1.2 ships `c`, `dotnet` and
  `java` both at the version root and again under `html/api-docs/`. **19 of the 165
  are copies**, and publishing them is publishing the same Javadoc five times.

De-duplication runs first and naming second, which is not an implementation
detail: 10 of the 11 name collisions that survive the path rule are *between a
root and its own duplicate*, so de-duplicating first resolves them without a
tie-break. What remains is one version -- `tps/6.0.0`, whose nested copies differ
in size -- and there the whole version falls back to the full path.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from docushift.transforms import links

# Path segments that say where a generator's output was filed, not what it is.
# Dropping them turns `html/api-reference/java` into `java` and
# `doc/html/api/java/lib` into `java-lib`. Every one of these is a container the
# corpus uses for more than one artefact, which is exactly why it cannot name one.
CONTAINER_SEGMENTS = frozenset({
    "doc", "docs", "html", "api", "apis", "api-docs", "api_docs", "apidocs",
    "api-reference", "api_reference", "apireference", "reference",
    # `bpmhelp` is amx-bpm's whole help tree; its three API trees sit inside it.
    "bpmhelp",
})

# The doc-class name in the `-resources` tree. Not one of `DOC_CLASSES`: those are
# the docs tree's, and this one is the reason the second tree exists.
API_REFERENCES = "api-references"


@dataclass(frozen=True)
class ApiRoot:
    """One API tree that will be published, with the folder name it gets."""

    source: Path
    # Relative to the version root, POSIX-separated -- `html/api-reference/java`.
    # Kept after naming because the link rewriter matches on it: a help topic
    # links to where the tree *was*, not to what it will be called.
    relative: PurePosixPath
    name: str
    files: int
    bytes: int


def measure(root: Path) -> tuple[int, int]:
    """File count and byte total for one tree. `(0, 0)` for an unreadable one."""
    files = size = 0
    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
            size += path.stat().st_size
        except OSError:  # pragma: no cover - a file that vanished mid-walk
            continue
        files += 1
    return files, size


def display_name(relative: PurePosixPath) -> str:
    """`html/api-reference/java` -> `java`; `api/java/lib` -> `java-lib`.

    A container is dropped wherever it sits, not only at the front: ems ships its
    .NET tree at `html/api/dotnetdoc/html`, which names itself `dotnetdoc`.

    Falls back to the leaf when *every* segment is a container -- `html/apidocs`
    would otherwise name itself nothing at all, and `apidocs` at least says what
    the packager thought it was.
    """
    parts = [part.lower() for part in relative.parts]
    kept = [part for part in parts if part not in CONTAINER_SEGMENTS]
    return "-".join(kept) if kept else parts[-1]


def full_name(relative: PurePosixPath) -> str:
    """Every segment, joined. Unique across the corpus; readable in nothing."""
    return "-".join(part.lower() for part in relative.parts)


_Entry = tuple[PurePosixPath, Path, int, int]


def _measured(tree: Path, roots: Iterable[Path]) -> list[_Entry]:
    """Every recorded root that is still on disk, measured, shallowest first.

    Roots outside `tree`, and roots that no longer exist, are dropped silently: the
    record can outlive the extract, and a recorded path is not a promise about the
    disk.

    Shallowest first, so the copy a duplicate is dropped in favour of is the one
    nearest the version root -- `html/javadocs` rather than the same tree four
    directories down inside `rtview`'s self-nested extract.
    """
    entries: list[_Entry] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            relative = PurePosixPath(root.relative_to(tree).as_posix())
        except ValueError:  # pragma: no cover - a record from another tree
            continue
        if str(relative) == ".":
            # The whole version is one API tree. Nothing to name it after, and
            # nothing else in the package; published under the leaf of the tree.
            relative = PurePosixPath(tree.name)
        files, size = measure(root)
        entries.append((relative, root, files, size))

    entries.sort(key=lambda item: (len(item[0].parts), str(item[0])))
    return entries


def _deduplicate(entries: Sequence[_Entry]) -> tuple[list[_Entry], dict[Path, Path]]:
    """The distinct trees, and the dropped copies mapped to the one that survived.

    The second half is what `url_map` needs and `select` throws away: a help topic
    that links into a duplicate has to be sent to the folder that was published,
    not to the folder that was not.
    """
    kept: list[_Entry] = []
    survivor: dict[tuple[int, int, str], Path] = {}
    aliases: dict[Path, Path] = {}
    for relative, root, files, size in entries:
        # Size, count and leaf name together. Not content: `rtview`'s duplicate is
        # 8,000 files four levels down, and reading it to prove what its size
        # already says would cost more than publishing it.
        signature = (files, size, relative.name.lower())
        first = survivor.get(signature)
        if first is not None:
            aliases[root] = first
            continue
        survivor[signature] = root
        kept.append((relative, root, files, size))
    return kept, aliases


def _named(kept: Sequence[_Entry]) -> list[ApiRoot]:
    """The surviving trees, each with the folder name it gets."""
    names = [display_name(relative) for relative, *_ in kept]
    if len(set(names)) != len(names):
        # Uniform within the version, not per-root: mixing the two rules would name
        # two siblings by two different schemes and the reader could not tell which
        # `java` was which. One version in the corpus reaches this -- `tps/6.0.0`.
        names = [full_name(relative) for relative, *_ in kept]

    return [
        ApiRoot(source=root, relative=relative, name=name, files=files, bytes=size)
        for name, (relative, root, files, size) in zip(names, kept, strict=True)
    ]


def select(tree: Path, roots: Iterable[Path]) -> list[ApiRoot]:
    """The publishable API trees for one version, de-duplicated and named.

    `roots` is Stage 4's recorded answer, passed in rather than located -- §6.3's
    rule that Stages 4, 5 and 7 read one answer.
    """
    kept, _ = _deduplicate(_measured(tree, roots))
    return _named(kept)


def published_url(base: str, tree_name: str, locale: str, slug: str,
                  segment: str, name: str) -> str:
    """Where a placed API tree lives once it is published.

    One function for the copy's destination and the rewrite's target, so the two
    cannot disagree -- and it composes the tree name from the caller's
    `resources_tree_name()`, so a link cannot point at a repository that was never
    created.

    An empty `base` yields the tree-rooted path with no scheme and no host. That is
    the shipped state and a deliberate choice (6e): the path is the part this tool
    can derive, a link missing only its prefix is fixable by search-and-replace when
    the AEM host is known, and a link that was never emitted is not recoverable at
    all. The path is percent-encoded here and the base is not -- the base is a URL
    the config validated, and the path is folder names this tool invented.
    """
    path = f"{tree_name}/{locale}/{slug}/{API_REFERENCES}/{segment}/{name}"
    encoded = links.encode(path)
    return f"{base.rstrip('/')}/{encoded}" if base else encoded


def url_map(tree: Path, roots: Iterable[Path], base: str, tree_name: str,
            locale: str, slug: str, segment: str) -> dict[Path, str]:
    """Every recorded API root paired with the URL its content is published at.

    What Stage 5 is handed so that conversion can rewrite a cross-boundary link
    without knowing the publishing layout (§10.7). Built through the same
    `_measured`/`_deduplicate`/`_named` path Stage 7's `select` uses, so the folder
    that gets written and the URL that gets emitted come from one de-duplication,
    one naming rule and one collision fallback -- anything less and `tps/6.0.0`,
    whose whole version demotes to dashed names, gets links to folders that were
    never created.

    **The 19 duplicates are keys too**, each mapping to its survivor's URL. A topic
    inside `rtview`'s self-nested extract links to the copy beside it, and that copy
    is exactly the one `select` drops; dropping the link with it would punish the
    topic for the packager's mistake.
    """
    entries = _measured(tree, roots)
    kept, aliases = _deduplicate(entries)
    urls = {
        root.source: published_url(base, tree_name, locale, slug, segment, root.name)
        for root in _named(kept)
    }
    for duplicate, survivor in aliases.items():
        urls[duplicate] = urls[survivor]
    return urls


def current(roots: Sequence[ApiRoot], destination: Path) -> bool:
    """Whether the placed folder still matches the trees `select` found.

    Compared **before staging**, for 6c's reason at ten times the scale: the copy
    is 1.39 GiB across the corpus, and a size-and-count check answers the question
    without reading any of it. Each root's own folder is checked for its file count
    and byte total rather than file by file -- a Javadoc tree is 2,465 files and
    nothing edits one of them by hand.
    """
    if not destination.is_dir():
        return False
    try:
        present = {child.name for child in destination.iterdir() if child.is_dir()}
    except OSError:  # pragma: no cover - unreadable target, treated as not current
        return False
    if present != {root.name for root in roots}:
        return False
    return all(measure(destination / root.name) == (root.files, root.bytes) for root in roots)
