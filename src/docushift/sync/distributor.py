"""Stage 7's driver: the converted tree, moved into publishing form.

`{target}/{docs-tree}/{locale}/{slug}/online-help/{segment}/`, plus the two
artifacts that live *above* a version folder -- the product's `metadata.yml` and
the doc-class's `version.yml`. Shaped like `DocumentConverter` on purpose: the
same selection, the same "a failure is a returned outcome, never an exception",
the same five-outcome summary, because the four commands are read side by side.

Phase 6b places **`online-help` only**. The other three doc-classes need 6c's
document router, and the spine has to be provable before four doc-classes ride
on it.

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

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.converter import navigation
from docushift.models import Product, ProductVersion
from docushift.reporting.findings import FindingsRun
from docushift.sync import versions as version_file
from docushift.utils.slug import is_numeric_version, slugify, version_segment
from docushift.utils.swap import remove, swap

# The one doc-class 6b places. Named here rather than inlined at four call sites,
# because 6c adds three more and the difference between "the doc-class we place"
# and "the doc-class this file is for" is about to start mattering.
ONLINE_HELP = "online-help"


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
        staging = destination.with_name(destination.name + ".part")
        remove(staging)
        staging.parent.mkdir(parents=True, exist_ok=True)
        # `copy2` rather than `copy`, so mtime survives the copy -- which is what
        # makes `_identical` able to tell a re-sync from a human's edit.
        shutil.copytree(source, staging, copy_function=shutil.copy2)
        files = [path for path in staging.rglob("*") if path.is_file()]
        size = sum(path.stat().st_size for path in files)
        swap(staging, destination)
        return len(files), size

    # -- one product -----------------------------------------------------------

    def finish_product(self, product: Product, target: Path, stats: SyncStats) -> None:
        """The two artifacts above a version folder, written once the copies are done.

        Skipped entirely when the doc-class folder does not exist: a product whose
        every version reported `NO_OUTPUT` has published nothing, and a product
        folder holding a `metadata.yml` and no content is a dead entry in AEM.
        """
        doc_class = self.doc_class_dir(product, target)
        if not doc_class.is_dir():
            return

        templates = self.config.aem_templates_dir
        (doc_class.parent / "metadata.yml").write_text(
            navigation.render_metadata([("csg-product", product.display_name)], templates, "product"),
            encoding="utf-8",
        )
        stats.products += 1

        present = {child.name for child in doc_class.iterdir() if child.is_dir()}
        catalog_versions = list(product.versions.values())
        rows = version_file.generated_rows(catalog_versions, present)
        self._report_rows(product, present)

        path = doc_class / "version.yml"
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
        """Every selected version, then every touched product's two artifacts."""
        stats = SyncStats()
        touched: dict[str, Product] = {}
        for product, version in pairs:
            result = self.sync_one(product, version, target, force=force)
            stats.results.append(result)
            touched[product.slug] = product
            if on_result is not None:
                on_result(result)

        for product in touched.values():
            self.finish_product(product, target, stats)

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
