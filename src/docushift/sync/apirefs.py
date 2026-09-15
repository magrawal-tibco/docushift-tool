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


def select(tree: Path, roots: Iterable[Path]) -> list[ApiRoot]:
    """The publishable API trees for one version, de-duplicated and named.

    `roots` is Stage 4's recorded answer, passed in rather than located -- §6.3's
    rule that Stages 4, 5 and 7 read one answer. Roots outside `tree`, and roots
    that no longer exist, are dropped silently: the record can outlive the extract,
    and a recorded path is not a promise about the disk.

    Shallowest first, so the copy a duplicate is dropped in favour of is the one
    nearest the version root -- `html/javadocs` rather than the same tree four
    directories down inside `rtview`'s self-nested extract.
    """
    entries: list[tuple[PurePosixPath, Path, int, int]] = []
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

    kept: list[tuple[PurePosixPath, Path, int, int]] = []
    seen: set[tuple[int, int, str]] = set()
    for relative, root, files, size in entries:
        # Size, count and leaf name together. Not content: `rtview`'s duplicate is
        # 8,000 files four levels down, and reading it to prove what its size
        # already says would cost more than publishing it.
        signature = (files, size, relative.name.lower())
        if signature in seen:
            continue
        seen.add(signature)
        kept.append((relative, root, files, size))

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


def published_url(base: str, tree_name: str, locale: str, slug: str,
                  segment: str, name: str) -> str:
    """Where a placed API tree lives once it is published.

    One function for the copy's destination and the rewrite's target, so the two
    cannot disagree -- and it composes the tree name from the caller's
    `resources_tree_name()`, so a link cannot point at a repository that was never
    created.
    """
    path = f"{tree_name}/{locale}/{slug}/{API_REFERENCES}/{segment}/{name}"
    return f"{base.rstrip('/')}/{path}" if base else path


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
