"""What is actually on the shelf -- the walk `validate` runs before it checks anything.

`architecture.md` §6.1 and §6.2 describe the published layout
(`{target}/{tree}/{locale}/{slug}/{doc-class}/{version-dashed}/`) as something
`sync` *writes*. This module reads it back, and the difference is the whole point
of §7.1's boundary: **the catalog is not consulted.** A published tree outlives
the row that produced it -- a product retired last week still has help on the
shelf, and that is exactly when somebody wants to know whether it is intact -- so
the selectors here filter directory names and a target another machine synced is
validated with no `versions.csv` agreement required.

Three shapes the walk has to get right, all of them measured on the sample tree of
2026-09-16 rather than assumed from §6.2:

- **`archives/` has no version segment.** The folder *is* the history rather than
  a version of it, so it is walked as a unit with an empty segment.
- **`.part` is not a version.** A failed sync leaves its staging sibling behind --
  two of them in the sample -- and reporting on a folder the swap refused to
  publish would make a failed `sync` produce `validate` errors that a successful
  re-run silently cures. They come back as residue instead.
- **A doc-class directory nobody recognizes is skipped, not guessed at.** The same
  rule `DOC_CLASSES` states for writing: a stray folder beside `online-help` must
  not acquire meaning by being walked.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from docushift.sync import API_REFERENCES, ARCHIVES, DOC_CLASSES
from docushift.sync.distributor import STAGING_SUFFIX

# Every doc-class a published tree can hold, across both repositories. The docs
# tree's four (`distributor.DOC_CLASSES`) plus the `-resources` sibling's two.
PUBLISHED_DOC_CLASSES: tuple[str, ...] = (*DOC_CLASSES, API_REFERENCES, ARCHIVES)

# The doc-class whose folder is itself the unit: no version segment beneath it.
UNVERSIONED_DOC_CLASSES: frozenset[str] = frozenset({ARCHIVES})


@dataclass(frozen=True)
class VersionFolder:
    """One published unit -- a version folder, or `archives/` itself."""

    path: Path
    tree: str
    locale: str
    slug: str
    doc_class: str
    # The dashed published segment, `10-4-0`. Empty for an unversioned doc-class.
    #
    # Recorded verbatim into the findings `version` column rather than converted
    # back to `10.4.0`: §4.1 is explicit that the dashed form does not round-trip
    # (`10.4.0` and `10-4-0` both dash to the same thing, and so does `10 4 0`),
    # so a `validate` finding names the folder it is about and nothing else.
    segment: str = ""

    @property
    def relative(self) -> Path:
        """`{tree}/{locale}/{slug}/{doc-class}/{segment}` -- what a finding prints."""
        parts = [self.tree, self.locale, self.slug, self.doc_class]
        if self.segment:
            parts.append(self.segment)
        return Path(*parts)

    def rel(self, child: Path) -> str:
        """A file inside this folder, as a POSIX path relative to the target root."""
        return (self.relative / child.relative_to(self.path)).as_posix()


@dataclass
class ProductFolder:
    """One `{tree}/{locale}/{slug}/` directory and everything published under it."""

    path: Path
    tree: str
    locale: str
    slug: str
    versions: list[VersionFolder] = field(default_factory=list)
    # `.part` directories found under this product. Litter from a sync that
    # failed, which may have gone unnoticed -- worth a note, never a check.
    residue: list[Path] = field(default_factory=list)

    @property
    def relative(self) -> Path:
        return Path(self.tree, self.locale, self.slug)

    @property
    def is_resources(self) -> bool:
        """Is this the `-resources` sibling rather than the docs tree?

        Asked by name because the walk has no `ConfigManager`: a target directory
        is validated on its own terms, and `resources_tree_name()` would need the
        product's bu and family, which is a catalog lookup this module refuses.
        """
        return self.tree.endswith("-resources")


def _subdirs(folder: Path) -> Iterator[Path]:
    try:
        children = sorted(folder.iterdir())
    except OSError:  # pragma: no cover - an unreadable directory is the OS's business
        return
    for child in children:
        if child.is_dir():
            yield child


def walk(
    target: Path,
    product: str | None = None,
    version: str | None = None,
    doc_class: str | None = None,
) -> list[ProductFolder]:
    """Every published product under `target`, narrowed by the three selectors.

    `version` matches the **published segment**, so `--version 10-4-0` and
    `--version 10.4.0` both find `10-4-0/`: the dashed form is what is on disk and
    the dotted form is what a human has in hand, and refusing one of them would be
    a trap rather than a rule.

    Ordered -- trees, then locales, then slugs, then doc-classes in `§6.2` order,
    then segments as the filesystem sorts them -- so two runs over one tree produce
    findings in the same order and a diff of two reports is readable.
    """
    wanted_segment = _segment_filter(version)
    found: list[ProductFolder] = []
    for tree in _subdirs(target):
        for locale in _subdirs(tree):
            for slug in _subdirs(locale):
                if product and slug.name != product:
                    continue
                entry = ProductFolder(slug, tree.name, locale.name, slug.name)
                for folder in _subdirs(slug):
                    if folder.name.endswith(STAGING_SUFFIX):
                        entry.residue.append(folder)
                        continue
                    if folder.name not in PUBLISHED_DOC_CLASSES:
                        continue
                    if doc_class and folder.name != doc_class:
                        continue
                    entry.versions.extend(
                        _units(entry, folder, wanted_segment)
                    )
                    entry.residue.extend(
                        child for child in _subdirs(folder)
                        if child.name.endswith(STAGING_SUFFIX)
                    )
                if entry.versions or entry.residue:
                    found.append(entry)
    return found


def _units(
    product: ProductFolder, folder: Path, wanted_segment: str | None
) -> Iterator[VersionFolder]:
    if folder.name in UNVERSIONED_DOC_CLASSES:
        # `archives/` is one unit with no segment, so a `--version` selector has
        # nothing to match and excludes it rather than matching everything.
        if wanted_segment is None:
            yield VersionFolder(folder, product.tree, product.locale, product.slug, folder.name)
        return
    for child in _subdirs(folder):
        if child.name.endswith(STAGING_SUFFIX):
            continue
        if wanted_segment is not None and child.name != wanted_segment:
            continue
        yield VersionFolder(
            child, product.tree, product.locale, product.slug, folder.name, child.name
        )


def _segment_filter(version: str | None) -> str | None:
    """`10.4.0` or `10-4-0` -> `10-4-0`. `None` stays `None`."""
    if not version:
        return None
    from docushift.utils.slug import version_segment

    return version_segment(version) or version


def tree_names(target: Path) -> set[str]:
    """The top-level directory names, which is the set of published repositories.

    Needed by the link checker and nowhere else: a reference whose first raw
    segment is one of these is a host-less published URL (`architecture.md`
    §6.4.2), not a path inside a version folder. Read from disk, because a target
    holding two of the nine trees must not have the other seven inferred into it.
    """
    try:
        return {child.name for child in target.iterdir() if child.is_dir()}
    except OSError:  # pragma: no cover
        return set()
