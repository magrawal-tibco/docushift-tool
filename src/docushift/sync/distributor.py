"""Stage 7's driver: the converted tree, moved into publishing form.

`{target}/{docs-tree}/{locale}/{slug}/online-help/{segment}/`, plus the two
artifacts that live *above* a version folder -- the product's `metadata.yml` and
the doc-class's `version.yml`. Shaped like `DocumentConverter` on purpose: the
same selection, the same "a failure is a returned outcome, never an exception",
the same five-outcome summary, because the four commands are read side by side.

Phase 6b built the spine and placed `online-help`; **6c adds the three document
doc-classes**, which ride on it unchanged -- same staging sibling, same swap, same
five outcomes, same one-directory-deep boundary. The one thing they do not share
is their source: `online-help` comes from `output_path()` and the documents come
from `extract_path()`, because a version that never converted can still ship eight
PDFs. So one version can be `NO_OUTPUT` for `online-help` and `SYNCED` for
`user-guides` in the same run, and that is a fact about the package rather than a
disagreement to reconcile.

**6d adds a second tree.** `api-references/` and `archives/` go to the family's
`-resources` sibling (§6.3), not to a fifth doc-class here, and that is a
repository boundary rather than a folder: `DOC_CLASSES` stays four long and the
two new ones are reached through `resources_dir` instead. They keep the staging
sibling and the swap; what they do not keep is the docs tree's product-level
furniture. There is no `version.yml` beside `api-references/` -- the drop-down is
an AEM page control and these folders are copied Javadoc, not AEM pages -- and
`archives/` has no version segment at all, because the folder *is* the history
rather than a version of it.

Four rules the driver owns:

- **The version folder is swapped, and nothing above it is.** Each version's
  doc-class folder is built in a staging sibling and renamed over the target with
  `utils/swap.py` -- the converter's build-and-swap, for the same virus-scanner
  reason. Scoping the swap to the doc-class instead would delete the thirty-seven
  sibling versions the run did not touch, and take `version.yml` with them.
- **Currency is compared, not recorded.** No fingerprint goes into `state.db`.
  The target is outside this tool's control -- the `version.yml` rule assumes a
  human edits it -- so a stored hash would claim currency for a tree that no
  longer matches. `_identical` compares the two trees instead.
- **The product-level artifacts are written once per product, after its versions**,
  and only where the doc-class folder exists. Writing `metadata.yml` for a product
  whose every version reported "no converted tree" would create an empty product
  folder that publishes nothing.
- **Nothing is written back to `output/`.** Stage 7 reads the converted tree and
  the catalog and writes only under `--target-dir`. A version with no converted
  tree is one of the five outcomes, not an abort: over a partially converted
  corpus, that is the normal state.
"""

import filecmp
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from docushift.apiref import find_api_roots, recorded_roots
from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.converter import navigation
from docushift.models import Product, ProductVersion
from docushift.reporting.findings import FindingsRun
from docushift.sync import apirefs, router
from docushift.sync import archives as archive_index
from docushift.sync import documents as document_index
from docushift.sync import versions as version_file
from docushift.utils.slug import is_numeric_version, slugify, version_segment
from docushift.utils.swap import remove, swap

# The converted doc-class. Named here rather than inlined at four call sites,
# because 6c added three more and the difference between "the doc-class we place"
# and "the doc-class this file is for" started mattering.
ONLINE_HELP = "online-help"

# Every doc-class in the docs tree, in the order a reader meets them. A fixed
# tuple rather than "whatever directories are there": a stray folder somebody
# dropped beside `online-help` must not acquire a `version.yml` and become a
# drop-down. 6d's `-resources` tree is a sibling of this one, not a member.
DOC_CLASSES = (ONLINE_HELP, *router.DOCUMENT_DOC_CLASSES)

# The three files a document doc-class folder gets beside its copied files.
_RENDERED = ("index.md", "toc.yml", "metadata.yml")

# The staging sibling a version folder is built in before the swap. A constant
# rather than four literals because Phase 7b's `validate` has to recognize one: a
# failed run leaves `10-4-0.part` on the shelf, and a linter that mistook it for a
# published version would report findings about a folder the swap deliberately
# refused to publish.
STAGING_SUFFIX = ".part"


class SyncOutcome(StrEnum):
    """What happened to one version. Every run reports these five counts."""

    SYNCED = "synced"
    # The published tree already matches the converted one, file for file.
    CURRENT = "current"
    # Selected and eligible, but `convert` has not produced a tree yet.
    NO_OUTPUT = "no-output"
    # The version string yields no publishable folder name. Named, never guessed
    # at -- the analogue of `convert`'s `ENGINE_UNKNOWN`. No active row is in this
    # state today: `Cloud™` and `(iPaaS)` reshape to `cloud` and `ipaas`, and only
    # a version that is *entirely* punctuation would land here.
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class SyncResult:
    """One version's outcome, for the report and for the tests."""

    slug: str
    version: str
    outcome: SyncOutcome
    # The published folder, `.../online-help/10-4-0/`. Set whenever one was named,
    # including for `CURRENT`, so the report can point at it.
    path: Path | None = None
    segment: str = ""
    files: int = 0
    bytes: int = 0
    message: str = ""
    # Which doc-class this row is about. A run reports one row per (version,
    # doc-class) that had something to say, so a version appears up to four times.
    # Empty means the row is about the version rather than one of its doc-classes
    # -- the extracted tree being gone is not a fact about `user-guides`.
    doc_class: str = ONLINE_HELP


@dataclass
class SyncStats:
    results: list[SyncResult] = field(default_factory=list)
    # Product-level `metadata.yml` files written, and doc-class `version.yml`
    # drop-downs written. Counted apart from the versions, because a scoped run
    # touches one version and still rewrites the whole drop-down.
    products: int = 0
    dropdowns: int = 0
    # `version.yml` files left alone because they would not parse. Named in the
    # report; the file is not touched.
    unparsed: list[str] = field(default_factory=list)

    def count(self, outcome: SyncOutcome) -> int:
        return sum(1 for r in self.results if r.outcome is outcome)

    @property
    def files(self) -> int:
        return sum(r.files for r in self.results)

    @property
    def bytes(self) -> int:
        return sum(r.bytes for r in self.results)

    @property
    def failures(self) -> list[SyncResult]:
        return [r for r in self.results if r.outcome is SyncOutcome.FAILED]

    @property
    def synced(self) -> list[SyncResult]:
        return [r for r in self.results if r.outcome is SyncOutcome.SYNCED]


class WorkspaceDistributor:
    """Copies converted versions into a target workspace and indexes them."""

    def __init__(
        self,
        config: ConfigManager,
        catalog: CatalogManager,
        findings: FindingsRun | None = None,
    ):
        self.config = config
        self.catalog = catalog
        self.findings = findings

    def _record(self, code: str, slug: str, version: str, **fields: Any) -> None:
        if self.findings is not None:
            self.findings.record(code, slug=slug, version=version, **fields)

    # -- paths -----------------------------------------------------------------

    def product_dir(self, product: Product, target: Path) -> Path:
        """`{target}/{docs-tree}/{locale}/{slug}/` -- the product level (§6.1)."""
        tree = self.config.docs_tree_name(product.bu, product.family)
        return target / tree / slugify(self.config.locale) / product.slug

    def doc_class_dir(self, product: Product, target: Path, doc_class: str = ONLINE_HELP) -> Path:
        return self.product_dir(product, target) / doc_class

    def resources_dir(self, product: Product, target: Path) -> Path:
        """`{target}/{resources-tree}/{locale}/{slug}/` -- the sibling tree (§6.3).

        The same shape one level up in a *different* repository, which is why it is
        not `doc_class_dir` with a fifth name. Callers must check
        `publishes_resources()` first: `resources_tree_name` raises for a
        non-primary locale rather than inventing a `loc-…-resources`, since the
        localized tree carries every language and an API reference has none.
        """
        tree = self.config.resources_tree_name(product.bu, product.family)
        return target / tree / slugify(self.config.locale) / product.slug

    # -- one version -----------------------------------------------------------

    def sync_one(
        self,
        product: Product,
        version: ProductVersion,
        target: Path,
        force: bool = False,
    ) -> SyncResult:
        """Publishes one version's converted tree. Never raises."""
        slug, number = product.slug, version.version
        segment = version_segment(number)
        if not segment:
            message = f"version {number!r} yields no publishable folder name"
            self._record("VERSION_NOT_NUMERIC", slug, number, message=message)
            return SyncResult(slug, number, SyncOutcome.SKIPPED, message=message)

        source = self.config.output_path(product.bu, product.family, slug, number)
        if not source.is_dir():
            message = f"no converted tree at {source}; run `docushift convert` first"
            return SyncResult(slug, number, SyncOutcome.NO_OUTPUT, segment=segment, message=message)

        destination = self.doc_class_dir(product, target) / segment
        if not force and destination.is_dir() and _identical(source, destination):
            return SyncResult(slug, number, SyncOutcome.CURRENT, path=destination, segment=segment)

        try:
            files, size = self._place(source, destination)
        except OSError as exc:  # pragma: no cover - filesystem failure, not logic
            message = f"{type(exc).__name__}: {exc}"
            return SyncResult(slug, number, SyncOutcome.FAILED, segment=segment, message=message)

        return SyncResult(
            slug, number, SyncOutcome.SYNCED, path=destination, segment=segment,
            files=files, bytes=size,
        )

    def _place(self, source: Path, destination: Path) -> tuple[int, int]:
        """Copies the tree into a staging sibling and swaps it over the target.

        Wholesale replacement, exactly one directory deep: a topic deleted upstream
        must not survive in the published tree, and `version.yml` one level up must
        not be reached by the replacement that removes it.
        """
        staging = destination.with_name(destination.name + STAGING_SUFFIX)
        remove(staging)
        staging.parent.mkdir(parents=True, exist_ok=True)
        # `copy2` rather than `copy`, so mtime survives the copy -- which is what
        # makes `_identical` able to tell a re-sync from a human's edit.
        shutil.copytree(source, staging, copy_function=shutil.copy2)
        files = [path for path in staging.rglob("*") if path.is_file()]
        size = sum(path.stat().st_size for path in files)
        swap(staging, destination)
        return len(files), size

    # -- one version's documents (6c) ------------------------------------------

    def sync_documents(
        self,
        product: Product,
        version: ProductVersion,
        target: Path,
        force: bool = False,
    ) -> list[SyncResult]:
        """Places the three document doc-classes for one version. Never raises.

        One row per doc-class that had something to say, so a version with PDFs and
        a readme reports two and a version with neither reports none. **The two
        absences are different and are reported differently**: an extracted tree
        that is gone is one `NO_OUTPUT` row naming `docushift extract`, because it
        is recoverable; a tree that is present and routes nothing gets no row,
        because 156 of 1,822 versions are in that state and reporting them would
        put 156 recoverable-looking failures in every full run.
        """
        slug, number = product.slug, version.version
        segment = version_segment(number)
        if not segment:
            # Silent here on purpose. The version string is a property of the
            # version, not of a doc-class, and `sync_one` already names it --
            # reporting it again per doc-class would quadruple one warning.
            return []

        tree = self.config.extract_path(product.bu, product.family, slug, number)
        if not tree.is_dir():
            message = f"no extracted tree at {tree}; run `docushift extract` first"
            return [SyncResult(slug, number, SyncOutcome.NO_OUTPUT, segment=segment,
                               message=message, doc_class="")]

        grouped = document_index.group(router.route_version(tree, version.engine))
        results = []
        for doc_class, files in grouped.items():
            results.append(self._sync_doc_class(product, version, target, doc_class, files, force))
        return results

    def _sync_doc_class(
        self,
        product: Product,
        version: ProductVersion,
        target: Path,
        doc_class: str,
        files: list[router.RoutedFile],
        force: bool,
    ) -> SyncResult:
        slug, number = product.slug, version.version
        segment = version_segment(number)
        destination = self.doc_class_dir(product, target, doc_class) / segment

        if not force and _documents_current(files, destination):
            return SyncResult(slug, number, SyncOutcome.CURRENT, path=destination,
                              segment=segment, doc_class=doc_class)

        entries, unreadable = document_index.entries_for(files)
        for path, error in unreadable:
            self._record(
                "DOCUMENT_UNREADABLE", slug, number,
                message=f"{path.name}: {error}; titled from its filename",
            )
        try:
            count, size = self._place_documents(entries, destination, product, version, doc_class)
        except OSError as exc:  # pragma: no cover - filesystem failure, not logic
            return SyncResult(slug, number, SyncOutcome.FAILED, segment=segment,
                              message=f"{type(exc).__name__}: {exc}", doc_class=doc_class)

        return SyncResult(slug, number, SyncOutcome.SYNCED, path=destination, segment=segment,
                          files=count, bytes=size, doc_class=doc_class)

    def _place_documents(
        self,
        entries: list[document_index.DocumentEntry],
        destination: Path,
        product: Product,
        version: ProductVersion,
        doc_class: str,
    ) -> tuple[int, int]:
        """The copied files and the three rendered ones, staged and swapped.

        The same build-and-swap `_place` uses, and `copy2` for the same reason:
        `_documents_current` compares mtime, and only a copy that preserves it can
        tell a re-sync from a human's edit.
        """
        staging = destination.with_name(destination.name + STAGING_SUFFIX)
        remove(staging)
        staging.mkdir(parents=True, exist_ok=True)
        size = 0
        for entry in entries:
            shutil.copy2(entry.source, staging / entry.name)
            size += entry.bytes

        templates = self.config.aem_templates_dir
        title = document_index.index_title(product.display_name, version.version, doc_class)
        (staging / "index.md").write_text(
            document_index.render_index(entries, title, doc_class, templates), encoding="utf-8"
        )
        (staging / "toc.yml").write_text(
            document_index.render_toc(title, templates), encoding="utf-8"
        )
        (staging / "metadata.yml").write_text(
            navigation.render_metadata([("csg-version", version.version)], templates, "version"),
            encoding="utf-8",
        )
        swap(staging, destination)
        return len(entries), size

    # -- one version's API references (6d) -------------------------------------

    def sync_api_references(
        self,
        product: Product,
        version: ProductVersion,
        target: Path,
        force: bool = False,
    ) -> list[SyncResult]:
        """Copies one version's API trees into the `-resources` sibling. Never raises.

        **Copied verbatim from the extracted tree, never from `output/`.** Javadoc
        and Doxygen are not engine output; converting them turns working HTML into
        broken Markdown, which is why Stage 5 skips them in the first place. 133 of
        the corpus's 165 in-scope roots sit *inside* an engine output root, so this
        copy and that skip are two halves of one rule about who owns a directory.

        At most one row, and none at all for a version with no API tree -- 409 of
        the 422 products a full sync selects are in that state, and a row each
        would bury the 13 that have something to publish.
        """
        slug, number = product.slug, version.version
        if not self.config.publishes_resources():
            return []
        segment = version_segment(number)
        if not segment:
            # `sync_one` has already named the unpublishable version string; saying
            # it again per tree would multiply one warning by the doc-classes.
            return []

        tree = self.config.extract_path(product.bu, product.family, slug, number)
        if not tree.is_dir():
            # Also silent: `sync_documents` raises the one `NO_OUTPUT` row for a
            # missing extracted tree, and that absence is a fact about the version.
            return []

        roots = apirefs.select(tree, self.api_roots(slug, number, tree))
        if not roots:
            return []

        destination = self.resources_dir(product, target) / apirefs.API_REFERENCES / segment
        if not force and apirefs.current(roots, destination):
            return [SyncResult(slug, number, SyncOutcome.CURRENT, path=destination,
                               segment=segment, doc_class=apirefs.API_REFERENCES)]

        try:
            files, size = self._place_api_references(roots, destination, version)
        except OSError as exc:  # pragma: no cover - filesystem failure, not logic
            return [SyncResult(slug, number, SyncOutcome.FAILED, segment=segment,
                               message=f"{type(exc).__name__}: {exc}",
                               doc_class=apirefs.API_REFERENCES)]

        if not self.config.publish_base_url():
            self._record(
                "PUBLISH_BASE_URL_UNSET", slug, number,
                message=f"{len(roots)} API tree(s) published to the -resources tree with no "
                        f"publish_base_url set; links into them stay relative and will not "
                        f"resolve across the repository boundary",
            )

        return [SyncResult(slug, number, SyncOutcome.SYNCED, path=destination, segment=segment,
                           files=files, bytes=size, doc_class=apirefs.API_REFERENCES)]

    def _place_api_references(
        self, roots: list[apirefs.ApiRoot], destination: Path, version: ProductVersion
    ) -> tuple[int, int]:
        """One folder per named root, staged and swapped, plus the version metadata.

        No `index.md` and no `toc.yml`: all 165 in-scope roots ship their own
        `index.html`, and a second entry point competes with the one the generator
        wrote. `metadata.yml` is written anyway because it describes the *version
        folder* rather than the content, and leaving it out would make this the one
        version folder in the layout that carries no version.
        """
        staging = destination.with_name(destination.name + STAGING_SUFFIX)
        remove(staging)
        staging.mkdir(parents=True, exist_ok=True)
        for root in roots:
            shutil.copytree(root.source, staging / root.name, copy_function=shutil.copy2)
        (staging / "metadata.yml").write_text(
            navigation.render_metadata(
                [("csg-version", version.version)], self.config.aem_templates_dir, "version"
            ),
            encoding="utf-8",
        )
        swap(staging, destination)
        return sum(root.files for root in roots), sum(root.bytes for root in roots)

    def api_roots(self, slug: str, version: str, tree: Path) -> list[Path]:
        """Stage 4's recorded API roots, located here only when there is no record.

        `converter/driver.py:_api_roots`, one stage later and with one difference:
        the output roots are read from the record only, never located, because
        Stage 7 has no engine in hand and a missing record here means the version
        never went through `extract` -- in which case there is no output root to
        protect a help tree that was never converted either.
        """
        metadata = self.catalog.state.get_version_metadata(slug, version) if self.catalog.state else {}
        recorded = recorded_roots(metadata, "api_roots", tree)
        if recorded:
            return recorded
        return find_api_roots(tree, recorded_roots(metadata, "output_roots", tree))

    # -- one product's archived history (6d) -----------------------------------

    def sync_archives(self, product: Product, target: Path, force: bool = False) -> SyncResult | None:
        """The product's archived-version index. **No version segment.**

        Per product rather than per version, and built from the *catalog* rather
        than the directory: there are 0 archived ZIPs on disk against the 1,270
        archived rows a full sync reaches, so indexing the disk would publish an
        empty history that reads as a complete one. A product with no archived rows
        gets no folder -- 43% of the in-scope ones, and an empty index is a claim
        that a product has no history rather than that this tool holds none of it.

        Returns one row or `None`. The row's `version` is empty, which is what the
        report uses to tell a product-level artifact from a version's.
        """
        if not self.config.publishes_resources():
            return None
        entries = archive_index.entries_for(
            product, self.config.archive_dir(product.bu, product.family)
        )
        if not entries:
            return None

        templates = self.config.aem_templates_dir
        title = archive_index.index_title(product.display_name)
        index = archive_index.render_index(entries, title, templates)
        destination = self.resources_dir(product, target) / archive_index.ARCHIVES

        if not force and archive_index.current(entries, destination, index):
            return SyncResult(product.slug, "", SyncOutcome.CURRENT, path=destination,
                              doc_class=archive_index.ARCHIVES)
        try:
            size = self._place_archives(entries, destination, product, title, index)
        except OSError as exc:  # pragma: no cover - filesystem failure, not logic
            return SyncResult(product.slug, "", SyncOutcome.FAILED,
                              message=f"{type(exc).__name__}: {exc}",
                              doc_class=archive_index.ARCHIVES)

        return SyncResult(product.slug, "", SyncOutcome.SYNCED, path=destination,
                          files=len(entries), bytes=size, doc_class=archive_index.ARCHIVES)

    def _place_archives(
        self,
        entries: list[archive_index.ArchiveEntry],
        destination: Path,
        product: Product,
        title: str,
        index: str,
    ) -> int:
        """The index, the TOC, the product metadata, and whatever ZIPs are on disk.

        `csg-product` at product level, not `csg-version`: this folder spans every
        version the product ever had, so there is no version for it to carry.
        """
        staging = destination.with_name(destination.name + STAGING_SUFFIX)
        remove(staging)
        staging.mkdir(parents=True, exist_ok=True)
        size = 0
        for entry in entries:
            if entry.source is not None:
                shutil.copy2(entry.source, staging / entry.source.name)
                size += entry.bytes

        templates = self.config.aem_templates_dir
        (staging / "index.md").write_text(index, encoding="utf-8")
        (staging / "toc.yml").write_text(
            archive_index.render_toc(title, templates), encoding="utf-8"
        )
        (staging / "metadata.yml").write_text(
            navigation.render_metadata([("csg-product", product.display_name)],
                                       templates, "product"),
            encoding="utf-8",
        )
        swap(staging, destination)
        return size

    # -- one product -----------------------------------------------------------

    def finish_product(self, product: Product, target: Path, stats: SyncStats) -> None:
        """The artifacts above a version folder, written once the copies are done.

        One `metadata.yml` per product and **one `version.yml` per doc-class the
        product actually has** -- the drop-downs will legitimately disagree, since
        `user-guides` carries versions that shipped no converted help. That is the
        point of the per-doc-class placement rather than a defect to reconcile, and
        6b's assembly rule needs no change to produce it: it already takes
        `present` from the directory listing.

        Skipped entirely when the product has no doc-class folder at all: a product
        whose every version reported `NO_OUTPUT` has published nothing, and a
        product folder holding a `metadata.yml` and no content is a dead entry.
        """
        root = self.product_dir(product, target)
        folders = [(name, root / name) for name in DOC_CLASSES if (root / name).is_dir()]
        if not folders:
            return

        templates = self.config.aem_templates_dir
        (root / "metadata.yml").write_text(
            navigation.render_metadata([("csg-product", product.display_name)], templates, "product"),
            encoding="utf-8",
        )
        stats.products += 1

        catalog_versions = list(product.versions.values())
        everywhere: set[str] = set()
        for _name, folder in folders:
            present = {child.name for child in folder.iterdir() if child.is_dir()}
            everywhere |= present
            self._write_dropdown(folder, present, catalog_versions, templates, stats)

        # Once per product over the union, not once per doc-class. A version in
        # three doc-classes is one non-numeric version string, and naming it three
        # times would make the report's warning count a function of how many PDFs
        # the package happened to ship.
        self._report_rows(product, everywhere)

    def _write_dropdown(
        self,
        folder: Path,
        present: set[str],
        catalog_versions: list[ProductVersion],
        templates: Path,
        stats: SyncStats,
    ) -> None:
        rows = version_file.generated_rows(catalog_versions, present)
        path = folder / "version.yml"
        existing: list[version_file.VersionRow] | None = []
        if path.is_file():
            existing = version_file.parse(path.read_text(encoding="utf-8"))
        if existing is None:
            # Left alone, deliberately. Whatever is in there is the only copy.
            stats.unparsed.append(str(path))
            return

        merged = version_file.merge(
            existing, rows, version_file.owned_paths(present, catalog_versions)
        )
        path.write_text(version_file.render(merged, templates), encoding="utf-8")
        stats.dropdowns += 1

    def _report_rows(self, product: Product, present: set[str]) -> None:
        """The two registered `sync` findings, raised for the first time here.

        Both are scoped to versions that actually reached the drop-down, because
        both are about what a reader will see: a row the run did not publish is
        not in the file and has nothing to report.
        """
        for version in product.versions.values():
            if version.is_archived or version_segment(version.version) not in present:
                continue
            if not is_numeric_version(version.version):
                self._record(
                    "VERSION_NOT_NUMERIC", product.slug, version.version,
                    message=f"{version.version!r} is not N(.N)*; published as "
                            f"{version_segment(version.version)!r} and sorted last",
                )
            if not version_file.release_month(version.release_date):
                self._record(
                    "VERSION_UNDATED", product.slug, version.version,
                    message="no usable release_date; the drop-down title loses its bracket",
                )

    # -- the run ---------------------------------------------------------------

    def sync_many(
        self,
        pairs: Iterable[tuple[Product, ProductVersion]],
        target: Path,
        force: bool = False,
        on_result: Callable[[SyncResult], None] | None = None,
    ) -> SyncStats:
        """Every selected version, then every touched product's artifacts.

        **API references are placed before the docs tree's doc-classes**, so that a
        link crossing into `-resources` can be rewritten against a tree that is
        already on disk rather than one this run intends to write (§6.4).
        """
        stats = SyncStats()
        touched: dict[str, Product] = {}
        for product, version in pairs:
            results = [
                *self.sync_api_references(product, version, target, force=force),
                self.sync_one(product, version, target, force=force),
                *self.sync_documents(product, version, target, force=force),
            ]
            stats.results.extend(results)
            touched[product.slug] = product
            if on_result is not None:
                for result in results:
                    on_result(result)

        for product in touched.values():
            self.finish_product(product, target, stats)
            # After, not before: the archives index is a product-level artifact and
            # belongs with the other two, but it goes to the other tree, so it
            # cannot ride on `finish_product`'s "does this product folder exist"
            # guard -- a product can have archived history and no published help.
            archived = self.sync_archives(product, target, force=force)
            if archived is not None:
                stats.results.append(archived)
                if on_result is not None:
                    on_result(archived)

        if self.findings is not None:
            self.findings.flush()
        return stats


def _identical(source: Path, target: Path) -> bool:
    """Whether the published tree still matches the converted one, file for file.

    Size and mtime, not content: `_place` copies with `copy2`, so a file this tool
    published carries the source's mtime and a file a human edited does not. A
    byte comparison would read both trees in full on every run to answer a
    question the metadata already answers -- and the one case it answers
    differently, an edit that preserved size and mtime, is not a case a filesystem
    produces by accident.
    """
    left = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    right = {path.relative_to(target) for path in target.rglob("*") if path.is_file()}
    if left != right:
        return False
    return all(filecmp.cmp(source / name, target / name, shallow=True) for name in left)


def _documents_current(files: list[router.RoutedFile], destination: Path) -> bool:
    """Whether a document doc-class folder still matches what routing found.

    **Compared before anything is built**, which is the whole reason this is not
    `_identical`. Titling a `user-guides` folder means opening every PDF in it, and
    reading all 5,007 in the corpus takes thirteen minutes; staging first and
    comparing after -- `online-help`'s shape -- would pay that on every run to
    answer a question the file metadata already answers.

    The inference the cheap check rests on: the three rendered files are a pure
    function of the routed filenames and the PDFs' contents, so if every copied
    file is byte-for-byte current by size and mtime and the three exist, they are
    current too. A *template* change is the one thing that escapes it, and
    `--force` is the answer to that, as it is to a changed engine.
    """
    if not destination.is_dir():
        return False
    expected = {entry.path.name for entry in files}
    try:
        published = {child.name for child in destination.iterdir() if child.is_file()}
    except OSError:  # pragma: no cover - unreadable target, treated as not current
        return False
    if published != expected | set(_RENDERED):
        return False
    return all(
        filecmp.cmp(entry.path, destination / entry.path.name, shallow=True) for entry in files
    )
