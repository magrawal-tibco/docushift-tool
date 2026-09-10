"""Stage 4, first half: unpacking a package and identifying what is in it.

Implements `docs/design.md` §6.1 steps 1-3 and §7. The selection is the
download's, so an archived or ineligible version is never unpacked; the path is
never accepted from a caller but derived by `ConfigManager`, the same invariant
that lets Stage 5 find a tree without being told where it is.

Shaped like `PackageDownloader` on purpose -- same selection, same "a failure is
a returned outcome, never an exception", same five-count summary -- because the
two commands are read side by side and a reader who knows one should not have to
learn the other. It differs in one respect and deliberately: **extraction is
serial.** The download pool exists because HTTP transfers overlap; two 900 MB
unzips onto one disk contend rather than overlap, and the second one arrives no
sooner for having been started early.
"""

import shutil
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.downloader import sha256_of
from docushift.engines.detector import Detection, detect_version
from docushift.engines.roots import find_output_roots
from docushift.extractor.safe_unzip import UnsafeArchiveError, safe_extract
from docushift.models import ConversionStatus, EngineSource, Product, ProductVersion, SourceEngine


class ExtractOutcome(StrEnum):
    """What happened to one version. Every run reports these five counts."""

    EXTRACTED = "extracted"
    # The ZIP's checksum matches the one the current tree was built from.
    CURRENT = "current"
    # Eligible, but there is no package at the canonical path yet.
    NO_PACKAGE = "no-package"
    # The archive tried to write outside its target directory. Counted apart from
    # `failed` because it is a statement about the package, not about this run:
    # a retry will not fix it and somebody needs to look at the ZIP.
    REFUSED = "refused"
    FAILED = "failed"


@dataclass
class ExtractResult:
    """One version's outcome, for the report and for the tests."""

    slug: str
    version: str
    outcome: ExtractOutcome
    path: Path | None = None
    files: int = 0
    engine: SourceEngine = SourceEngine.AUTO
    # False when the catalog kept a `manual` engine in preference to this answer.
    engine_written: bool = False
    roots: int = 0
    message: str = ""


@dataclass
class Identified:
    """What §7 concluded about one tree, and what the catalog did with it."""

    detection: Detection
    # The engine conversion will use: the detector's, unless a manual pin outranks it.
    engine: SourceEngine
    roots: list[Path]
    # False when nothing was written -- a manual pin, or a tree that stayed `auto`.
    written: bool


@dataclass
class ExtractStats:
    """Run totals, in the order the summary table prints them."""

    results: list[ExtractResult] = field(default_factory=list)

    def count(self, outcome: ExtractOutcome) -> int:
        return sum(1 for r in self.results if r.outcome is outcome)

    @property
    def files_written(self) -> int:
        return sum(r.files for r in self.results if r.outcome is ExtractOutcome.EXTRACTED)

    @property
    def failures(self) -> list[ExtractResult]:
        return [
            r for r in self.results
            if r.outcome in (ExtractOutcome.FAILED, ExtractOutcome.REFUSED)
        ]

    def engine_tally(self) -> dict[SourceEngine, int]:
        """Engine histogram over the versions this run actually looked at."""
        tally: dict[SourceEngine, int] = {}
        for result in self.results:
            if result.outcome in (ExtractOutcome.EXTRACTED, ExtractOutcome.CURRENT):
                tally[result.engine] = tally.get(result.engine, 0) + 1
        return dict(sorted(tally.items(), key=lambda item: (-item[1], str(item[0]))))


class PackageExtractor:
    """Unpacks packages into `families/<family>/extracted/<slug>/<version>/`."""

    def __init__(self, config: ConfigManager, catalog: CatalogManager):
        self.config = config
        self.catalog = catalog

    # -- state ---------------------------------------------------------------

    def _record(self, slug: str, version: str, **fields: Any) -> None:
        if self.catalog.state is not None:
            self.catalog.state.set_version_state(slug, version, **fields)

    def _metadata(self, slug: str, version: str) -> dict[str, str]:
        if self.catalog.state is None:
            return {}
        return self.catalog.state.get_version_metadata(slug, version) or {}

    def _set_metadata(self, slug: str, version: str, key: str, value: Any) -> None:
        if self.catalog.state is not None:
            self.catalog.state.set_version_metadata(slug, version, key, value)

    # -- one version ----------------------------------------------------------

    def extract_one(
        self, product: Product, version: ProductVersion, force: bool = False
    ) -> ExtractResult:
        """`design.md` §6.1 steps 1-3, then §7. Never raises."""
        slug, number = product.slug, version.version
        source = self.config.download_path(product.bu, product.family, slug, number)
        target = self.config.extract_path(product.bu, product.family, slug, number)

        if not source.is_file():
            message = f"no package at {source}; run `docushift download` first"
            return ExtractResult(slug, number, ExtractOutcome.NO_PACKAGE, message=message)

        checksum = sha256_of(source)
        recorded = self._metadata(slug, number)
        # A ZIP that has not changed since the tree was built is a no-op, which is
        # what makes re-running `extract` over a settled batch cheap. Keyed on the
        # *package's* checksum rather than the tree's: the tree is thousands of
        # files and hashing it would cost more than re-extracting.
        if not force and target.is_dir() and recorded.get("extract_zip_checksum") == checksum:
            return ExtractResult(
                slug, number, ExtractOutcome.CURRENT, path=target,
                engine=version.engine, engine_written=version.engine_source is not EngineSource.AUTO,
            )

        # Unpack beside the destination and swap, never over it. A re-extract onto
        # a live directory leaves the *previous* package's files in place, so a
        # guide deleted upstream survives forever and converts. The swap is not
        # atomic on Windows -- build, remove, rename -- so an interrupted run can
        # leave a `.part` directory; the next run removes it before it starts.
        staging = target.with_name(target.name + ".part")
        try:
            if staging.exists():
                shutil.rmtree(staging)
            files = safe_extract(source, staging)
        except UnsafeArchiveError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            self._record(slug, number, status=ConversionStatus.ERROR, error=str(exc))
            return ExtractResult(slug, number, ExtractOutcome.REFUSED, message=str(exc))
        except (OSError, zipfile.BadZipFile) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            message = f"{type(exc).__name__}: {exc}"
            self._record(slug, number, status=ConversionStatus.ERROR, error=message)
            return ExtractResult(slug, number, ExtractOutcome.FAILED, message=message)

        try:
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(target)
        except OSError as exc:
            message = f"{type(exc).__name__}: {exc}"
            self._record(slug, number, status=ConversionStatus.ERROR, error=message)
            return ExtractResult(slug, number, ExtractOutcome.FAILED, message=message)

        self._record(
            slug, number,
            status=ConversionStatus.EXTRACTED, extract_path=str(target), error=None,
        )
        # Written only after the tree is in place, so an interrupted extract
        # cannot leave a checksum claiming a directory that was never built.
        self._set_metadata(slug, number, "extract_zip_checksum", checksum)

        identified = self.identify(product, version, target)
        return ExtractResult(
            slug, number, ExtractOutcome.EXTRACTED, path=target, files=files,
            engine=identified.engine,
            engine_written=identified.written,
            roots=len(identified.roots),
        )

    # -- identification (design.md §7) -----------------------------------------

    def identify(self, product: Product, version: ProductVersion, tree: Path) -> "Identified":
        """Detects the engine and records it, the folder map and the output roots.

        Returns more than the engine, because the caller reports on evidence the
        catalog has no column for -- which pass decided, whether the content
        sample was exhausted, and whether a manual pin kept the answer out.
        """
        slug, number = product.slug, version.version
        detection = detect_version(tree)
        # A pinned engine outranks the detector (§7.3 step 3), so the *effective*
        # engine -- the one conversion will use, and the one the roots are located
        # for -- is the catalog's, not this run's.
        manual = version.engine_source is EngineSource.MANUAL
        engine = version.engine if manual else detection.engine

        # §7.3 step 4: recorded regardless of whether it is unanimous. Finding out
        # that it was not is the reason the map exists.
        if self.catalog.state is not None:
            for folder, folder_engine in detection.folders.items():
                self.catalog.state.record_engine_folder(slug, number, folder, str(folder_engine))

        if detection.generator_raw:
            # `other` on its own is unactionable; the string is what a human
            # triages a new generator from.
            self._set_metadata(slug, number, "engine_generator_raw", detection.generator_raw)

        roots = find_output_roots(tree, engine)
        if roots:
            self._set_metadata(
                slug, number, "output_roots",
                "\n".join(str(root.relative_to(tree)) for root in roots),
            )

        # §7.3 steps 1 and 3: never guess, and never override a manual value.
        # `record_detected_engine` enforces the second; refusing to write `auto`
        # here enforces the first, and also keeps a detection failure from
        # clearing an engine an earlier run got right.
        written = False
        if not manual and detection.engine is not SourceEngine.AUTO:
            written = self.catalog.record_detected_engine(slug, number, detection.engine)
        return Identified(detection=detection, engine=engine, roots=roots, written=written)

    # -- a run ----------------------------------------------------------------

    def extract_many(
        self,
        pairs: Iterable[tuple[Product, ProductVersion]],
        force: bool = False,
        on_result: Callable[[ExtractResult], None] | None = None,
    ) -> ExtractStats:
        """Runs the selection in `iter_versions` order, serially (see the module docstring)."""
        stats = ExtractStats()
        for product, version in pairs:
            result = self.extract_one(product, version, force=force)
            stats.results.append(result)
            if on_result is not None:
                on_result(result)
        return stats
