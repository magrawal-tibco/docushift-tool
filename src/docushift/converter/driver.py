"""Stage 5's driver: selection, dispatch, the write, and the swap.

Implements `design.md` §6.4 steps 4-7 and §9.3-§9.5 at the stage level, and knows
nothing about any engine. Shaped like `PackageDownloader` and `PackageExtractor`
on purpose -- the same selection, the same "a failure is a returned outcome, never
an exception", the same five-outcome summary -- because the three commands are
read side by side.

Four rules, all of them things the driver does so that no engine has to:

- **Dispatch is on the registered handler**, never on membership of
  `CONVERTIBLE_ENGINES` (`engines/base.py`). `auto`, an unconvertible generator and
  a convertible one with no handler written yet are one path and one finding:
  `ENGINE_UNKNOWN`, skipped rather than guessed (invariant 7).
- **Output is built at `<output>.part/` and swapped**, the rule 4b-1 established
  for extraction, for the reason it established it: a re-convert over a live
  directory leaves the previous run's topics in place, so a guide dropped upstream
  survives in the output forever. Not atomic on Windows -- build, remove, rename.
- **CSH identifiers reach the topic's first and only write** (§9.5). They are read
  before conversion begins, because parsing a 24 KB alias file is cheap and a
  read-modify-write pass over the whole output tree is not.
- **The asset copier is the driver's**, handed to the engine per unit. The engine
  resolves while it emits, which is invariant 13; the engine does not decide where
  a file lands, which would make the destination exist in two places.

In Phase 5a no engine is registered, so every selected version reports
`ENGINE_UNKNOWN` and nothing is written. That is the sub-phase's whole visible
behaviour and it is honest: the spine runs end to end and the register says so.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.engines.base import ConversionContext, Document, Unit, engine_for
from docushift.engines.csh import CshFormat, CshSource, csh_format_of, read_csh_source
from docushift.models import ConversionStatus, Product, ProductVersion, SourceEngine
from docushift.reporting.findings import FindingsRun
from docushift.transforms import csh as csh_transform
from docushift.transforms.assets import AssetCopier, Counts
from docushift.utils.swap import remove, swap


class ConvertOutcome(StrEnum):
    """What happened to one version. Every run reports these five counts."""

    CONVERTED = "converted"
    # The extracted tree has not changed since it was converted.
    CURRENT = "current"
    # Selected and eligible, but nothing has been extracted yet.
    NO_TREE = "no-tree"
    # `auto`, or a named engine with no registered handler. Skipped, never guessed.
    ENGINE_UNKNOWN = "engine-unknown"
    FAILED = "failed"


@dataclass
class ConvertResult:
    """One version's outcome, for the report and for the tests."""

    slug: str
    version: str
    outcome: ConvertOutcome
    path: Path | None = None
    engine: SourceEngine = SourceEngine.AUTO
    units: int = 0
    documents: int = 0
    assets: int = 0
    message: str = ""
    # Asset counts summed over the version's units. Per-root detail stays in the
    # findings, which name the root.
    counts: Counts = field(default_factory=Counts)
    # What §9.3 resolved, or None when the version has no CSH at all.
    csh: csh_transform.CshMap | None = None
    skipped: dict[str, int] = field(default_factory=dict)


@dataclass
class ConvertStats:
    results: list[ConvertResult] = field(default_factory=list)

    def count(self, outcome: ConvertOutcome) -> int:
        return sum(1 for r in self.results if r.outcome is outcome)

    @property
    def documents(self) -> int:
        return sum(r.documents for r in self.results)

    @property
    def assets(self) -> int:
        return sum(r.assets for r in self.results)

    @property
    def failures(self) -> list[ConvertResult]:
        return [r for r in self.results if r.outcome is ConvertOutcome.FAILED]

    @property
    def converted(self) -> list[ConvertResult]:
        return [r for r in self.results if r.outcome is ConvertOutcome.CONVERTED]


class DocumentConverter:
    """Converts extracted trees into `output/<family>/<slug>/<version>/`."""

    def __init__(
        self,
        config: ConfigManager,
        catalog: CatalogManager,
        findings: FindingsRun | None = None,
    ):
        self.config = config
        self.catalog = catalog
        self.findings = findings

    # -- state -----------------------------------------------------------------

    @property
    def state(self) -> Any:
        return self.catalog.state

    def _metadata(self, slug: str, version: str) -> dict[str, str]:
        if self.state is None:
            return {}
        return self.state.get_version_metadata(slug, version) or {}

    def _record(self, code: str, slug: str, version: str, **fields: Any) -> None:
        if self.findings is not None:
            self.findings.record(code, slug=slug, version=version, **fields)

    # -- one version -----------------------------------------------------------

    def convert_one(
        self,
        product: Product,
        version: ProductVersion,
        force: bool = False,
        tree: Path | None = None,
        output: Path | None = None,
    ) -> ConvertResult:
        """Converts one version. Never raises.

        `tree` and `output` override the catalog's paths, which is what
        `--input`/`--output` are for; everything else about the run is identical,
        so a standalone folder is not a second code path.
        """
        slug, number = product.slug, version.version
        source = tree or self.config.extract_path(product.bu, product.family, slug, number)
        target = output or self.config.output_path(product.bu, product.family, slug, number)

        if not source.is_dir():
            message = f"no extracted tree at {source}; run `docushift extract` first"
            return ConvertResult(slug, number, ConvertOutcome.NO_TREE, message=message)

        handler_cls = engine_for(version.engine)
        if handler_cls is None:
            # One branch for three conditions, on purpose. `auto` is a detector
            # bug, an unconvertible generator is a scoping decision and an
            # unwritten handler is a to-do -- but the *action here* is identical
            # in all three, and inventing three outcomes would suggest otherwise.
            reason = (
                "engine undetected (`auto`)" if version.engine is SourceEngine.AUTO
                else f"no converter registered for {version.engine}"
            )
            self._record("ENGINE_UNKNOWN", slug, number, message=reason)
            return ConvertResult(
                slug, number, ConvertOutcome.ENGINE_UNKNOWN, engine=version.engine, message=reason
            )

        checksum = self._metadata(slug, number).get("extract_zip_checksum", "")
        converted_from = self._metadata(slug, number).get("convert_source_checksum", "")
        # Keyed on the *package's* checksum, the value 4b-1 already records, rather
        # than on a hash of thousands of Markdown files: the input is one file and
        # the output is the thing whose freshness is in question.
        if not force and checksum and checksum == converted_from and target.is_dir():
            return ConvertResult(
                slug, number, ConvertOutcome.CURRENT, path=target, engine=version.engine
            )

        try:
            return self._build(product, version, handler_cls(), source, target, checksum)
        except OSError as exc:  # pragma: no cover - filesystem failure, not logic
            message = f"{type(exc).__name__}: {exc}"
            if self.state is not None:
                self.state.set_version_state(
                    slug, number, status=ConversionStatus.ERROR, error=message
                )
            return ConvertResult(slug, number, ConvertOutcome.FAILED, message=message)

    def _build(
        self,
        product: Product,
        version: ProductVersion,
        handler: Any,
        tree: Path,
        target: Path,
        checksum: str,
    ) -> ConvertResult:
        """Converts every unit into a staging directory, then swaps it into place."""
        slug, number = product.slug, version.version
        staging = target.with_name(target.name + ".part")
        remove(staging)
        staging.mkdir(parents=True, exist_ok=True)

        sources = self._csh_sources(slug, number, tree)
        owned = csh_transform.identifiers_by_source(sources)

        context = ConversionContext(
            tree=tree,
            output=staging,
            engine=version.engine,
            slug=slug,
            version=number,
            api_roots=self._recorded_paths(slug, number, "api_roots", tree),
            output_roots=self._recorded_paths(slug, number, "output_roots", tree),
            findings=self.findings,
        )

        result = ConvertResult(
            slug, number, ConvertOutcome.CONVERTED, path=target, engine=version.engine
        )
        output_rows: list[tuple[str, str, str]] = []

        for root in handler.units(context):
            unit_name = _relative(tree, root)
            copier = AssetCopier(root, version.engine, staging / unit_name if unit_name else staging)
            context.assets = copier
            unit = handler.convert_unit(context, root)
            self._write_unit(context, unit, owned, output_rows, staging)
            result.assets += copier.copy()
            self._report_assets(context, unit_name, copier)
            _merge(result.counts, copier.counts)
            for reason, count in unit.skipped.items():
                result.skipped[reason] = result.skipped.get(reason, 0) + count
            result.units += 1
            result.documents += len(unit.documents)
        context.assets = None

        # Resolution runs against what this run *just produced*, from the rows in
        # hand rather than from the table -- the table is written below, and a
        # read-back would resolve against the previous run on a re-convert.
        mapping = {source: output for source, output, _unit in output_rows}
        result.csh = csh_transform.resolve(sources, mapping)
        self._report_csh(context, result.csh)
        csh_transform.write(staging / "csh.yml", result.csh.entries)

        swap(staging, target)

        if self.state is not None:
            self.state.record_output_map(slug, number, output_rows)
            self.state.set_version_state(
                slug, number, status=ConversionStatus.CONVERTED, error=None
            )
            # Written only after the swap, so an interrupted run cannot leave a
            # checksum claiming an output tree that was never completed.
            if checksum:
                self.state.set_version_metadata(slug, number, "convert_source_checksum", checksum)
        if self.findings is not None:
            self.findings.flush()
        return result

    # -- writing ---------------------------------------------------------------

    def _write_unit(
        self,
        context: ConversionContext,
        unit: Unit,
        owned: dict[str, list[str]],
        output_rows: list[tuple[str, str, str]],
        staging: Path,
    ) -> None:
        """Writes one unit's documents, each in a single pass (§9.5)."""
        for document in unit.documents:
            source = _relative(context.tree, document.source)
            relative = PurePosixPath(unit.name) / document.relative if unit.name else document.relative
            if not document.csh:
                document.csh = owned.get(source, [])
            path = staging / Path(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render(document), encoding="utf-8")
            output_rows.append((source, str(relative), unit.name))

    # -- reporting -------------------------------------------------------------

    def _report_assets(self, context: ConversionContext, unit: str, copier: AssetCopier) -> None:
        """§6.4 steps 5 and 7, as findings rather than as terminal scrollback."""
        for segment, count in sorted(copier.counts.dangling_by_segment.items()):
            context.record(
                "REFERENCE_UNRESOLVED",
                path=f"{unit}/{segment}" if unit else segment,
                message=f"{count} reference(s) resolved to nothing",
                count=count,
            )
        orphans = copier.orphans()
        if orphans:
            # A note, aggregated: 54.6% of Flare's images are orphans by the
            # authoring tool's design, and a row per file would be 300,000 rows
            # saying something normal.
            context.record(
                "ASSET_ORPHANED",
                path=unit,
                message=f"{len(orphans)} unreferenced file(s), {copier.counts.orphan_bytes} bytes",
                count=len(orphans),
            )

    def _report_csh(self, context: ConversionContext, resolved: csh_transform.CshMap) -> None:
        """§9.4's `unresolved` and the ambiguity list, relocated to the register.

        This is the whole remaining record of both: the flat `csh.yml` has nowhere
        to put them, and invariant 10 says an absence is reported rather than
        faked. Losing these lines would turn a broken Help button into silence.
        """
        for entry in resolved.unresolved:
            context.record(
                "CSH_UNRESOLVED",
                path=entry.doc_set,
                message=f"{entry.identifier} -> {entry.link} matched no produced topic",
            )
        for entry in resolved.ambiguous:
            context.record(
                "CSH_AMBIGUOUS",
                path=entry.chosen,
                message=f"{entry.identifier} also resolved to {', '.join(entry.dropped)}",
            )

    # -- inputs ----------------------------------------------------------------

    def _recorded_paths(self, slug: str, version: str, key: str, tree: Path) -> list[Path]:
        """Reads back a newline-joined path list Stage 4 wrote. Never re-walks.

        §6.3 is explicit that Stages 4, 5 and 7 read one recorded answer. A second
        walk here could disagree with the counts already in `versions.csv`, and it
        would disagree silently.
        """
        raw = self._metadata(slug, version).get(key, "")
        return [tree / line for line in raw.splitlines() if line.strip()]

    def _csh_sources(self, slug: str, version: str, tree: Path) -> list[CshSource]:
        """The version's help maps, re-read from disk at the paths Stage 4 recorded.

        Re-read rather than re-located: `state.db` holds each source's path, format
        and **doc-set**, and the doc-set is the one part that cannot be recovered
        from the file itself. Entries are not stored -- 11,054 rows of Flare alias
        for one product would be a copy of a file we already have.

        Falls back to locating them when there is no record, which is the
        `--input` case: a standalone folder never went through `extract`.
        """
        rows = self.state.get_csh_sources(slug, version) if self.state is not None else []
        located: list[tuple[Path, CshFormat, str]] = []
        for row in rows:
            path = tree / Path(row["path"])
            try:
                fmt = CshFormat(row["format"])
            except ValueError:  # pragma: no cover - a format the enum lost
                continue
            located.append((path, fmt, row["doc_set"] or ""))
        if not located:
            located = [
                (path, fmt, _doc_set_of(tree, path))
                for path, fmt in _find_csh(tree)
            ]

        sources = []
        for path, fmt, doc_set in sorted(located, key=lambda item: str(item[0])):
            if not path.is_file():
                continue
            source = read_csh_source(path, fmt)
            source.path = path.relative_to(tree)
            source.doc_set = doc_set
            sources.append(source)
        return sources

    # -- a run -----------------------------------------------------------------

    def convert_many(
        self,
        pairs: Iterable[tuple[Product, ProductVersion]],
        force: bool = False,
        on_result: Callable[[ConvertResult], None] | None = None,
    ) -> ConvertStats:
        """Runs the selection serially, in `iter_versions` order.

        Serial for the reason extraction is: the work is disk-bound, and two
        conversions writing thousands of small files onto one disk contend rather
        than overlap.
        """
        stats = ConvertStats()
        for product, version in pairs:
            result = self.convert_one(product, version, force=force)
            stats.results.append(result)
            if on_result is not None:
                on_result(result)
        return stats


def _render(document: Document) -> str:
    """One Markdown file: frontmatter, then the body.

    Frontmatter is emitted only when there is something to say. An empty `---`
    block is noise in every renderer, and a `csh: []` would claim a page is a help
    target with no identifiers rather than not a help target.
    """
    lines: list[str] = []
    if document.title:
        lines.append(f"title: {csh_transform.quote(document.title)}")
    for key in sorted(document.frontmatter):
        lines.append(f"{key}: {_scalar(document.frontmatter[key])}")
    if document.csh:
        lines.append(f"csh: {csh_transform.frontmatter_value(document.csh)}")
    body = document.body.rstrip("\n")
    if not lines:
        return body + "\n"
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body + "\n"


def _scalar(value: Any) -> str:
    """A frontmatter value. Strings are quoted; bools and numbers are not."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(csh_transform.quote(str(item)) for item in value) + "]"
    return csh_transform.quote(str(value))


def _relative(tree: Path, path: Path) -> str:
    try:
        return path.relative_to(tree).as_posix()
    except ValueError:  # pragma: no cover - an engine returning a path outside the tree
        return path.name


def _merge(total: Counts, part: Counts) -> None:
    for name in ("resolved", "skin", "escaped", "dangling", "external",
                 "case_mismatch", "orphan_files", "orphan_bytes"):
        setattr(total, name, getattr(total, name) + getattr(part, name))
    for segment, count in part.dangling_by_segment.items():
        total.dangling_by_segment[segment] = total.dangling_by_segment.get(segment, 0) + count


def _find_csh(tree: Path) -> list[tuple[Path, CshFormat]]:
    """Locates help maps in a tree nobody has inventoried. `--input` only."""
    found = []
    for path in tree.rglob("*"):
        if not path.is_file():
            continue
        fmt = csh_format_of(path)
        if fmt is not None:
            found.append((path, fmt))
    return found


def _doc_set_of(tree: Path, path: Path) -> str:
    """The book directory of a located source: `<book>/Data/Alias.xml` -> `<book>`.

    Only reached in the `--input` case. WebWorks sits one level deeper than the
    other two, which `extractor/inventory.py` handles the same way and for the
    same reason.
    """
    depth = 3 if csh_format_of(path) is CshFormat.WEBWORKS_TOPICS else 2
    book = path.parents[depth - 1]
    return _relative(tree, book) if book != tree else ""
