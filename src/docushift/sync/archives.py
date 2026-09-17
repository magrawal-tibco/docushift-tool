"""Stage 6d's second step: the archived-versions index.

`design.md` §10.6. One `archives/` folder per product in the `-resources` tree,
listing every version the catalog has ever carried -- **no version segment**,
because the folder is the history rather than a version of it.

**Built from the catalog, never from the directory.** Archived ZIPs are pulled on
demand by `docushift archive download`, and there are **0 on disk** today against
1,270 archived rows a full sync reaches. Indexing what is there would publish an
empty history that looks complete; indexing the catalog publishes a complete one
that is honest about what it can hand over. This is `version.yml`'s rule in
reverse and for the reverse reason (`sync/versions.py`): there the directory is a
superset of the truth, here it is a nearly-empty subset.

Three things the 2026-09-15 re-measure of the committed catalog changed, all of
them against the 60-product API sample §10.6 was written from:

- **The date is a day, not a month.** Not one archived row is spelled
  `November 2022`. The 2,100 are 1,785 plain `YYYY-MM-DD`, 309 epoch-millisecond
  strings across 138 products, and 6 empty -- and the days are real: 31 distinct
  day-of-month values, with `-01` at only 3%. `release_month` still renders the
  month, so the two places a date reaches published output agree, but the claim
  that the month is all the data has is no longer true.
- **`zip_url` is already absolute** in 2,086 of the 2,100, and absent in the other
  14. There is no `{base_url}{zipPath}` to compose, so nothing here touches
  `publish_base_url`.
- **Nothing is ever cross-linked to `online-help/`.** 0 archived versions are also
  live -- the catalog keys `Product.versions` by version string, so one version
  being both is unrepresentable -- and 0 archived rows are `convert_eligible`, so
  no archived version is published for a link to point at. The `ARCHIVE_ALSO_LIVE`
  code registered for that link was retired with this phase.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from docushift.models import Product, ProductVersion
from docushift.sync.versions import release_month
from docushift.utils.csvio import natural_version_key
from docushift.utils.slug import is_numeric_version
from docushift.utils.templating import template

ARCHIVES = "archives"


@dataclass(frozen=True)
class ArchiveEntry:
    """One archived version: what it is, when it shipped, and how to get it."""

    version: str
    # `Feb 2026`, or empty where the row carries no usable date. Never synthesized.
    released: str
    # Whether the ZIP is on disk in this target. False for every row in the corpus
    # today; the column exists so a reader is told, rather than given a dead link.
    available: bool
    # The catalog's `zip_url` verbatim, or the published filename when the ZIP was
    # copied in. Empty for the 14 rows that carry neither.
    url: str
    bytes: int = 0
    # Set only when the ZIP was copied into the folder, so the placer knows what to
    # copy and `current` knows what to compare.
    source: Path | None = None

    @property
    def link(self) -> str:
        """The target for a Markdown link: a remote URL untouched, a filename quoted."""
        return self.url if "://" in self.url else quote(self.url)


def entries_for(
    product: Product,
    archive_path: Path | None = None,
    versions: Iterable[ProductVersion] | None = None,
) -> list[ArchiveEntry]:
    """One product's archived rows, newest first.

    **Ordered by version descending, not by date.** The two disagree for 38% of
    products with more than one archived row, not the sampled 28% -- and the
    version is what a reader is looking for. Non-numeric strings sort last, the
    same rule `version.yml` follows, because they are upstream parse artifacts
    rather than versions and putting them first would head the history with one.

    `archive_path` is called per row to locate a downloaded ZIP; passing `None`
    means nothing is on disk, which is the whole corpus's state today.
    """
    rows = [v for v in (versions if versions is not None else product.versions.values())
            if v.is_archived]
    numeric = sorted(
        (v for v in rows if is_numeric_version(v.version)),
        key=lambda v: natural_version_key(v.version),
        reverse=True,
    )
    trailing = sorted(
        (v for v in rows if not is_numeric_version(v.version)), key=lambda v: v.version.lower()
    )

    entries: list[ArchiveEntry] = []
    for version in (*numeric, *trailing):
        local = archive_path / f"{product.slug}-{version.version}.zip" if archive_path else None
        on_disk = local is not None and local.is_file()
        entries.append(
            ArchiveEntry(
                version=version.version,
                released=release_month(version.release_date),
                available=on_disk,
                # The local copy wins when there is one: a reader on the published
                # site should not be sent back to the docsite for a file the
                # publisher is already hosting.
                url=local.name if on_disk and local else (version.zip_url or ""),
                bytes=local.stat().st_size if on_disk and local else 0,
                source=local if on_disk else None,
            )
        )
    return entries


def index_title(product_name: str) -> str:
    """What the archives index calls itself. No version -- the folder is all of them."""
    return f"{product_name.strip()} Archived Versions".strip()


def render_index(entries: list[ArchiveEntry], title: str, templates: Path) -> str:
    """`index.md`, frontmatter included -- nothing converts this folder either."""
    return template(templates, "archives_index.md.j2").render(title=title, entries=entries)


def render_toc(title: str, templates: Path) -> str:
    """`toc.yml`: one item, pointing at the `index.md` beside it.

    The history is a list, but it is `index.md`'s list -- see
    `archives_toc.yml.j2` for why these entries collapse despite being catalog
    rows rather than files. Entries are not a parameter for the same reason as
    `documents.render_toc`.
    """
    return template(templates, "archives_toc.yml.j2").render(title=title)


def current(entries: list[ArchiveEntry], destination: Path, index: str) -> bool:
    """Whether the placed folder already says what this run would say.

    **The rendered `index.md` is compared as text**, which the other doc-classes do
    not need to do. Theirs are a function of the files they copy, so comparing the
    copies settles it; this one is a function of the *catalog*, and 1,270 of the
    corpus's 1,270 archived rows copy no file at all. A version retired since the
    last sync would add a row and change nothing on disk, so a file-set comparison
    would report the folder current forever. The file is a few hundred bytes.
    """
    if not destination.is_dir():
        return False
    expected = {entry.url for entry in entries if entry.source is not None}
    try:
        published = {child.name for child in destination.iterdir() if child.is_file()}
    except OSError:  # pragma: no cover - unreadable target, treated as not current
        return False
    if published != expected | {"index.md", "toc.yml", "metadata.yml"}:
        return False
    try:
        return (destination / "index.md").read_text(encoding="utf-8") == index
    except OSError:  # pragma: no cover - unreadable target, treated as not current
        return False
