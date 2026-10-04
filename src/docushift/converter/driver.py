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
  survives in the output forever. The old tree is renamed aside, never deleted
  first (X2-01), so a locked file fails the run and leaves the tree whole.
- **CSH identifiers reach the topic's first and only write** (§9.5). They are read
  before conversion begins, because parsing a 24 KB alias file is cheap and a
  read-modify-write pass over the whole output tree is not -- and since Phase 34
  (R4-05) they are *resolved* before the first topic is written too, so a topic's
  frontmatter carries exactly what `csh.yml` sends to it.
- **The asset copier is the driver's**, handed to the engine per unit. The engine
  resolves while it emits, which is invariant 13; the engine does not decide where
  a file lands, which would make the destination exist in two places.

In Phase 5a no engine is registered, so every selected version reports
`ENGINE_UNKNOWN` and nothing is written. That is the sub-phase's whole visible
behaviour and it is honest: the spine runs end to end and the register says so.
"""

import hashlib
import json
import re
import traceback
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

from docushift import origins
from docushift.apiref import find_api_roots, recorded_roots
from docushift.catalog import CatalogError, CatalogManager
from docushift.config import ConfigManager
from docushift.converter import navigation
from docushift.engines.base import ConversionContext, Document, Unit, engine_for
from docushift.engines.csh import CshFormat, CshSource, csh_format_of, read_csh_source
from docushift.engines.roots import (
    find_output_roots,
    foreign_roots,
    is_output_root,
    owning_root,
    subtree_names,
)
from docushift.extractor import content_root
from docushift.models import ConversionStatus, Product, ProductVersion, SourceEngine
from docushift.reporting.findings import FindingsRun

# Stage 5 importing Stage 7's module is the point, not a layering slip: §6.4
# guarantees the folder sync writes and the URL conversion emits come out of one
# function, and two copies of the naming rule is exactly the failure it forbids.
from docushift.sync import apirefs
from docushift.transforms import csh as csh_transform
from docushift.transforms import fragments, links
from docushift.transforms.assets import AssetCopier, Counts
from docushift.utils import textfile
from docushift.utils.csvio import release_year
from docushift.utils.longpath import long_path, walk_files
from docushift.utils.slug import slugify, version_segment
from docushift.utils.swap import recover, remove, swap

#: A `toc.yml` row's destination. The file is generated from one Jinja template
#: with a stable shape, so a value-level rewrite is safe and -- unlike re-emitting
#: the YAML -- leaves every other byte alone, which is what keeps a re-convert
#: diffable. The key is `url` since Phase 36; it must follow the template's, or
#: this rewrites nothing and says nothing.
_TOC_PATH = re.compile(r'url:[ \t]*"([^"\n]*)"')

#: The converter's output, versioned (X3-06). Bumped by any commit that changes
#: what a converted tree holds -- an engine fix, a transform, a template rule --
#: so `convert --all` rebuilds every tree rather than reporting it `current`
#: over output the old code wrote. `reframe/policy.py:_ALGORITHM` is the same
#: hole closed for the merge; before this, a converter fix reached a tree only
#: through a `--force` somebody remembered.
#:
#: 1 = the first versioned key (X3-04 to X3-08, 2026-10-05).
_CONVERTER_VERSION = 1

#: The `config/aem_templates/` files the converter renders (X3-07). Named, not
#: the whole folder: `sync`'s own templates must not re-convert every tree.
_TEMPLATES = ("index.md.j2", "metadata.yml.j2", "toc.yml.j2")


def _fragment_key(fragment: str) -> str:
    """A `#fragment` as `fragments.marker_targets` keys it: decoded, lower-cased.

    A link emits its fragment percent-encoded (`links.emit`), a marker holds the
    name as written; comparing the two raw missed every target whose name has a
    space in it (Phase 34, R8-08).
    """
    return unquote(fragment).lower()


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
    # Pages Stage 6a wrote that no source file produced: the container pages and,
    # where no unit reports a landing page, the version index. Counted apart from
    # `documents`, which is what the engines converted -- a run that reports 3,625
    # documents converted 3,625 topics.
    generated: int = 0
    nav_nodes: int = 0
    assets: int = 0
    # What the output tree holds once it is built -- one walk, after the swap.
    # Not `documents + generated` and not `assets + 3`: both derivations are
    # wrong in ways the walk is not (see `_measure_output`).
    md_files: int = 0
    out_files: int = 0
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
    def out_files(self) -> int:
        """Files standing in the output trees this run measured.

        Summed over every result that carries a measurement, not only over
        `converted`: a `current` version whose columns were blank is walked and
        filled, and its tree is as real as one this run built.
        """
        return sum(r.out_files for r in self.results)

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

    def _building(self, slug: str, version: str, stage: str) -> bool:
        return self.state is not None and self.state.is_building(slug, version, stage)

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

        Except in what it may read back (Phase 34, R4-04). Stage 4's record --
        output roots, API roots, CSH paths, the package checksum -- describes the
        catalog's extracted tree, and joined to another folder every path missed:
        the run reported `converted` with 0 topics. A standalone folder is located
        from scratch and never `current`.
        """
        slug, number = product.slug, version.version
        standalone = tree is not None
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

        # Before the currency test: a `current` run sweeps a killed build's `.part`
        # (X3-09), and a tree a kill left at `.old` is back before it is judged.
        try:
            recover(target)
        except OSError as exc:
            return self._failed(slug, number, version.engine, _describe(exc))
        # X3-01. An extract that did not finish leaves its mark, and the tree under
        # it may be half the old package and half the new. Converting it reported
        # `converted` with a whole book missing, and once `extract` re-unpacked the
        # same package the damaged output read as `current` for good.
        if not standalone and self._building(slug, number, "extract"):
            return self._failed(
                slug, number, version.engine,
                "the extracted tree is from an extract that did not finish; "
                "run `docushift extract` first",
            )

        metadata = self._metadata(slug, number)
        checksum = metadata.get("extract_zip_checksum", "")
        converted_from = metadata.get("convert_source_checksum", "")
        # Keyed on the *package's* checksum, the value 4b-1 already records, rather
        # than on a hash of thousands of Markdown files: the input is one file and
        # the output is the thing whose freshness is in question.
        #
        # 6e adds a second key, and only for the versions that have one. The package
        # does not change when `publishing.yaml` does, so filling in
        # `publish_base_url` would otherwise leave every converted tree reporting
        # CURRENT with host-less API links baked in -- a silent partial success, the
        # shape §7.5 exists to catch. Versions with no API tree record an empty
        # prefix and are never invalidated by it, which keeps a host being set from
        # reconverting 1,822 versions to change the output of 41.
        recorded_prefix = metadata.get("convert_api_prefix", "")
        prefix_current = not recorded_prefix or recorded_prefix == self._api_prefix(product, number)
        # And the engine (Phase 34, R4-03). `engine_source=manual` is §3.4's remedy
        # for a misdetected engine, and the package does not change when the
        # catalog does -- so a correction reported `current` and kept the wrong
        # engine's tree. Blank for a tree converted before the key existed, which
        # is read as matching, as a blank prefix is.
        recorded_engine = metadata.get("convert_engine", "")
        engine_current = not recorded_engine or recorded_engine == str(version.engine)
        # And everything else that shapes the tree without being in the package
        # (X3-05, X3-06, X3-07): the converter's own version, the display name,
        # the templates and what `301.yml` is built from. **Blank is a mismatch**
        # here, unlike the two keys above: the code-version half exists to
        # invalidate trees, and one built before the key existed is one of them.
        inputs_key = self._inputs_key(product, version)
        inputs_current = metadata.get("convert_inputs_key", "") == inputs_key
        # A version still marked as building was interrupted between its swap and
        # its bookkeeping, so the keys describe some other tree (X3-03), whatever
        # they say.
        if (not force and not standalone and checksum and checksum == converted_from
                and prefix_current and engine_current and inputs_current and target.is_dir()
                and not self._building(slug, number, "convert")):
            current = ConvertResult(
                slug, number, ConvertOutcome.CURRENT, path=target, engine=version.engine
            )
            if self.findings is not None:
                self.findings.point_back("CONVERT_FINDINGS_IN_EARLIER_RUN", slug, number,
                                         metadata.get("convert_run", ""))
            # An unchanged conversion is a no-op *unless* nobody has counted it.
            # This is 4b-1's rule for `extract`, and Phase 12 is what happens
            # without it: a version converted before the output columns existed
            # would report `current` on every future run and stay blank for good.
            # A directory walk against a conversion is free.
            if version.md_files is None or version.out_files is None:
                try:
                    current.md_files, current.out_files = self._measure_output(slug, number, target)
                except CatalogError as exc:
                    # X2-05: outside `_build`'s `try`, so `versions.csv` open in
                    # Excel stopped the selection. The tree is untouched and its
                    # state rows stand; only this row's columns are unwritten.
                    return ConvertResult(slug, number, ConvertOutcome.FAILED,
                                         engine=version.engine, message=str(exc))
            return current

        try:
            result = self._build(
                product, version, handler_cls(), source, target, checksum, standalone,
                inputs_key,
            )
        except Exception as exc:  # noqa: BLE001 - a failure is an outcome (R4-07)
            # Not only `OSError`. "Never raises" was a convention nothing enforced:
            # an engine's `ValueError` or `RecursionError` on one page stopped every
            # remaining version, skipped `findings.finish()` and left
            # `<version>.part` on disk. Extraction learned the same in R3-08.
            remove(target.with_name(target.name + ".part"))
            return self._failed(slug, number, version.engine, _describe(exc))
        if not checksum and not standalone and result.outcome is ConvertOutcome.CONVERTED:
            # X3-08. Correct, but rebuilt on every run under a plain `converted`
            # line: `extract --measure-only` and a failed post-swap extract leave
            # no package checksum, and without one nothing can be called current.
            result.message = ("no package checksum recorded, so this version is rebuilt on "
                              "every run; `docushift extract --force` records one")
        return result

    def _failed(
        self, slug: str, number: str, engine: SourceEngine, message: str
    ) -> ConvertResult:
        """`failed`, recorded in `version_state`, with whatever findings the run held."""
        if self.state is not None:
            self.state.set_version_state(slug, number, status=ConversionStatus.ERROR, error=message)
        if self.findings is not None:
            self.findings.flush()
        return ConvertResult(slug, number, ConvertOutcome.FAILED, engine=engine, message=message)

    def _build(
        self,
        product: Product,
        version: ProductVersion,
        handler: Any,
        tree: Path,
        target: Path,
        checksum: str,
        standalone: bool = False,
        inputs_key: str = "",
    ) -> ConvertResult:
        """Converts every unit into a staging directory, then swaps it into place."""
        slug, number = product.slug, version.version
        staging = target.with_name(target.name + ".part")
        remove(staging)
        staging.mkdir(parents=True, exist_ok=True)

        sources = self._csh_sources(slug, number, tree, standalone)

        # Read before the context is built, because `_api_roots` needs them: an api
        # root that is also an output root is the output root's (6d).
        output_roots = [] if standalone else self._recorded_paths(slug, number, "output_roots", tree)
        if standalone or not all(is_output_root(root, version.engine) for root in output_roots):
            # Stage 4 located these for the engine the version had then, and an
            # unchanged package never re-identifies (R4-03): a hand-corrected
            # engine was handed the old engine's roots. Every recorded root passes
            # its engine's rule by construction, so one that fails was recorded
            # for another engine, and the roots are located again for this one.
            output_roots = find_output_roots(tree, version.engine)
        api_roots = self._api_roots(slug, number, tree, output_roots, standalone)
        context = ConversionContext(
            tree=tree,
            output=staging,
            engine=version.engine,
            slug=slug,
            version=number,
            product_name=product.display_name,
            api_roots=api_roots,
            api_urls=self._api_urls(product, number, tree, api_roots),
            output_roots=output_roots,
            locale=self.config.locale,
            findings=self.findings,
        )

        result = ConvertResult(
            slug, number, ConvertOutcome.CONVERTED, path=target, engine=version.engine
        )
        output_rows: list[tuple[str, str, str]] = []
        units: list[Unit] = []

        # Materialized before the first unit converts, because a unit's subtree
        # name is a property of how many units the version has (§5.1.3): a lone
        # output root publishes at the version root, and that cannot be known
        # while the list is still a generator.
        work = list(handler.units(context))
        context.subtrees = subtree_names(tree, work, version.engine)
        self._exclude_foreign(context, work)
        # A root located and deliberately not converted (a localized build,
        # R5-01, or another engine's unit, R4-02) publishes no topic, so its help
        # identifiers have nothing to resolve to; resolving them anyway reports
        # each one as CSH_UNRESOLVED.
        sources = [source for source in sources if not _excluded(tree, source, context, work)]

        for root in work:
            unit_name = context.subtree_name(root)
            copier = AssetCopier(root, version.engine, staging / unit_name if unit_name else staging)
            context.assets = copier
            unit = handler.convert_unit(context, root)
            result.assets += copier.copy()
            self._report_assets(context, unit_name, copier)
            _merge(result.counts, copier.counts)
            for reason, count in unit.skipped.items():
                result.skipped[reason] = result.skipped.get(reason, 0) + count
            result.units += 1
            result.documents += len(unit.documents)
            units.append(unit)
        context.assets = None
        self._report_api_links(context)
        self._report_flattened_links(context)
        self._report_unrendered(context)
        self._report_repairs(context)

        if not result.documents:
            # Phase 34 (R4-06). No unit, or units with nothing in them -- a
            # re-extract that lost `Data/HelpSystem.xml`, say -- was `converted`,
            # and the swap replaced the last good tree with an empty one under a
            # green CLI line. The engine's warning says why; this keeps the tree.
            remove(staging)
            return self._failed(
                slug, number, version.engine,
                f"nothing converted ({result.units} unit(s), 0 documents); "
                f"the previous output is kept",
            )

        # Resolution runs against what this run *just produced*, from the rows in
        # hand rather than from the table -- the table is written below, and a
        # read-back would resolve against the previous run on a re-convert.
        #
        # And before any topic is written (Phase 34, R4-05). Frontmatter used to
        # come from the link inside the identifier's own doc-set, read before
        # conversion, while `csh.yml` resolves through §9.3 steps 4-5: an
        # identifier the version-wide fallback rescued reached no page, and the
        # loser of an ambiguity kept it while `csh.yml` pointed elsewhere --
        # against §9.6's "every identifier in frontmatter is in csh.yml, and vice
        # versa". Every output path is known once the units are converted, so the
        # frontmatter is now read off the resolved map, still in the first write.
        for unit in units:
            for document in unit.documents:
                output_rows.append(
                    (_relative(tree, document.source), str(_output_path(unit, document)), unit.name)
                )
        mapping = {source: output for source, output, _unit in output_rows}
        result.csh = csh_transform.resolve(sources, mapping)
        owned: dict[str, list[str]] = {}
        for identifier, destination in result.csh.entries.items():
            owned.setdefault(destination.partition("#")[0], []).append(identifier)
        for unit in units:
            self._write_unit(unit, {path: sorted(ids) for path, ids in owned.items()}, staging)

        # Stage 6a, and it runs here rather than in a later command because the
        # node list exists only while the units are in hand and the pages it
        # generates have to reach the staging tree before the swap.
        self._synthesize(context, units, staging, product, version, result)

        # The help map is written after the fragment pass, which retargets its
        # anchors as it does every link's (Phase 34, R8-04). Written before, it
        # kept the marker names the platform ignores, and every Help button in an
        # unmerged tree opened the top of its page.
        self._report_csh(context, result.csh)
        self._retarget_fragments(context, staging, result.csh.entries)
        csh_transform.write(staging / "csh.yml", result.csh.entries)
        self._write_origins(staging, product, version, mapping)

        # Marked before the swap and cleared only once every row and column below
        # is written (X3-01, X3-03): a run killed in between is rebuilt by the next
        # `convert` and refused by `reframe` and `sync`, never called `current`.
        if self.state is not None and not standalone:
            self.state.mark_building(slug, number, "convert")
        swap(staging, target)

        # The state rows first, then the CSV (Phase 34, R4-08). The CSV write is
        # the one a human can block -- Excel holding `versions.csv` -- and it ran
        # first, so a failure there left the new tree beside the previous build's
        # `output_map`, which Reframe reads, and the previous checksum. The rows
        # describe the tree now published whatever happens to the columns.
        if self.state is not None:
            self.state.record_output_map(slug, number, output_rows)
            self.state.set_version_state(
                slug, number, status=ConversionStatus.CONVERTED, error=None
            )
            # Written only after the swap, so an interrupted run cannot leave a
            # checksum claiming an output tree that was never completed.
            if checksum:
                self.state.set_version_metadata(slug, number, "convert_source_checksum", checksum)
            self.state.set_version_metadata(
                slug, number, "convert_api_prefix",
                self._api_prefix(product, number) if context.api_urls else "",
            )
            self.state.set_version_metadata(slug, number, "convert_engine", str(version.engine))
            self.state.set_version_metadata(slug, number, "convert_inputs_key", inputs_key)
            # X3-04. The converted tree's identity, new on every build, which is
            # what `reframe` and `sync` key a merge on. The package checksum they
            # used is unchanged by `convert --force`, so a re-converted tree was
            # merged by nothing and the old merge reported current.
            self.state.set_version_metadata(slug, number, "convert_build_id", uuid.uuid4().hex)
            # X3-11. The run whose findings describe this tree, for the note a
            # `current` re-run records in place of them.
            if self.findings is not None and self.findings.run_id:
                self.state.set_version_metadata(slug, number, "convert_run", self.findings.run_id)

        # After the swap rather than over the staging directory, so the columns
        # describe the tree that is actually published from. A swap that failed
        # raised above and wrote nothing, which is the blank-not-zero rule.
        result.md_files, result.out_files = self._measure_output(slug, number, target)
        if self.state is not None and not standalone:
            self.state.clear_building(slug, number, "convert")
        self._report_output_count(context, result)
        if self.findings is not None:
            self.findings.flush()
        return result

    # -- measurement -------------------------------------------------------------

    def _write_origins(
        self, staging: Path, product: Product, version: ProductVersion, mapping: dict[str, str]
    ) -> None:
        """Phase 35: `301.yml` in the converted tree, which `sync` publishes for
        every product that does not publish merged.

        Into staging, before the swap, for the reason Reframe's is: written into
        the published folder after the copy it would make `sync`'s shallow
        `filecmp` see every version as stale on every run (20d.1). Nothing has
        moved yet, so every `to` is the topic's own output path. Skipped without
        `state.db` -- the standalone `--input` path -- as Reframe skips it.
        """
        if self.state is None:
            return
        slug, number = product.slug, version.version
        pages, missing = origins.listing(self.config.cache_dir, slug, number)
        built = origins.build(
            self.config.load_origin_urls(), slug, version.zip_url, mapping, {}, pages, missing,
        )
        for code, message, count in built.findings:
            self._record(code, slug, number, message=message, count=count)
        if built.rows is not None:
            origins.write(staging / origins.ORIGINS, built.rows)

    def _measure_output(self, slug: str, version: str, target: Path) -> tuple[int, int]:
        """One walk of the output tree, and the two columns it writes (§3.9).

        **Walked, not derived.** The arithmetic that looks equivalent --
        `documents + generated` for the Markdown, plus `assets`, plus the root
        artifacts -- is wrong at the last term on every version measured so far:
        `csh.yml` is written only for a non-empty map (`transforms/csh.write`), so
        a version whose help map yields no identifiers has **two** root artifacts
        and not three, and that is the majority case rather than the edge one. A
        constant that is already false is not a constant, and the walk costs a
        directory traversal against a conversion.

        `_api_files` has no counterpart here because it needs none: the converter
        skips API-reference trees and Stage 7 copies them verbatim into
        `-resources` (§10.6), so the same count stands at both ends of the
        pipeline. What this measures is the Markdown half -- the thing that
        actually changed shape.
        """
        md_files = out_files = 0
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            out_files += 1
            if path.suffix.lower() == ".md":
                md_files += 1
        self.catalog.record_convert_inventory(slug, version, md_files, out_files)
        return md_files, out_files

    # -- writing ---------------------------------------------------------------

    def _write_unit(self, unit: Unit, owned: dict[str, list[str]], staging: Path) -> None:
        """Writes one unit's documents, each in a single pass (§9.5).

        `owned` is keyed on the version-relative output path: the identifiers
        `csh.yml` resolves to that page, and no others (R4-05).
        """
        for document in unit.documents:
            relative = _output_path(unit, document)
            if not document.csh:
                document.csh = owned.get(str(relative), [])
            path = staging / Path(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            textfile.write_text(path, _render(document))

    def _synthesize(
        self,
        context: ConversionContext,
        units: list[Unit],
        staging: Path,
        product: Product,
        version: ProductVersion,
        result: ConvertResult,
    ) -> None:
        """Stage 6a: the version's `toc.yml`, its generated pages and `metadata.yml`.

        Inside the build and before the swap. The generated pages are written the
        same way a converted topic is -- `_render` gives them the same frontmatter
        rules -- and they are deliberately absent from `output_rows`: the §9.3 map
        is keyed on the source file, and these have none.
        """
        templates = self.config.aem_templates_dir
        synthesis = navigation.synthesize(context, units, templates)
        for document in synthesis.documents:
            path = staging / Path(*document.relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            textfile.write_text(path, _render(document))

        title = f"{product.display_name} {version.version}".strip()
        textfile.write_text(
            staging / "toc.yml", navigation.render_toc(synthesis.nodes, templates, title)
        )
        # Version level, so `csg-version` and nothing else -- `csg-product` belongs
        # to the product folder, which only the distributor (6b) creates. Dotted,
        # as the product names it; the dashed form is the publishing boundary's.
        textfile.write_text(
            staging / "metadata.yml",
            navigation.render_metadata([("csg-version", version.version)], templates, "version"),
        )

        result.generated = synthesis.generated
        result.nav_nodes = sum(1 for node in synthesis.nodes for _ in node.walk())
        self._report_metadata(context, units, version)

    # -- reporting -------------------------------------------------------------

    def _exclude_foreign(self, context: ConversionContext, work: list[Path]) -> None:
        """Names every unit of work a second convertible engine owns (Phase 34, R4-02).

        A version is converted by one engine. BusinessConnect 7.4.0 detects as
        Flare, and the 83-page WebWorks book inside its Flare root was fed to the
        Flare converter page by page -- about 80 `CONTENT_MISSING` lines that read
        as a Flare markup defect -- while a book outside every Flare root was never
        looked at. Converting both engines in one version is deferred; until then
        each such root is one `ENGINE_ROOT_UNCONVERTED` line naming the engine,
        and the root joins `excluded_roots` so this engine skips its files.

        Not reported: a root inside an API tree, which Stage 7 copies verbatim,
        and a root inside one already left out (a localized build).
        """
        for other, root in foreign_roots(context.tree, context.engine):
            if root in work or any(
                excluded == root or excluded in root.parents
                for excluded in (*context.api_roots, *context.excluded_roots)
            ):
                continue
            context.excluded_roots.append(root)
            context.record(
                "ENGINE_ROOT_UNCONVERTED", path=_relative(context.tree, root),
                message=f"{other} unit of work in a version converted as {context.engine}; "
                        f"not converted (one engine per version)",
            )

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

    def _report_metadata(
        self, context: ConversionContext, units: list[Unit], version: ProductVersion
    ) -> None:
        """What the source says about itself, against what the catalog says (§5.2.7).

        SuiteHelp's `GUID-*-homepage.html` is the only source that states its own
        version and date, in all 314 doc-sets that ship one. Since AEM fixed
        `metadata.yml` at the `csg-*` keys, those three fields stopped being a
        metadata source and became this check -- and it has to happen here, during
        conversion, because `Unit.metadata` dies with the run.

        **`publication-title` is not compared**, deliberately. It names the
        *publication*, and a version ships up to 11 of them; equality with the
        catalog's one product display name would be false for almost every
        doc-set, and a warning that fires on almost everything is read as noise.
        The date is compared by year, because the homepage writes `March 2021`
        where the catalog writes a day, and normalizing further would be inventing
        precision neither side has.
        """
        for unit in units:
            declared = unit.metadata.get("release-version", "").strip()
            if declared and declared != version.version.strip():
                context.record(
                    "METADATA_MISMATCH", path=unit.name,
                    message=f"homepage release-version {declared!r} != catalog {version.version!r}",
                )
            date = release_year(unit.metadata.get("release-date", ""))
            catalog_date = release_year(version.release_date)
            if date and catalog_date and date != catalog_date:
                context.record(
                    "METADATA_MISMATCH", path=unit.name,
                    message=f"homepage release-date {date} != catalog {catalog_date}",
                )

    def _report_api_links(self, context: ConversionContext) -> None:
        """One note per version for the whole cross-boundary rewrite (6e).

        Once, with a count, rather than once per link: nobody acts on a single
        rewritten link and everybody wants the magnitude. It matters because the
        failure here is silent -- a version with an API tree and **zero** rewritten
        links is either a product whose help genuinely never references its API (8
        of the 49 in-scope versions) or a predicate that stopped matching, and
        without the count those two are indistinguishable.
        """
        if not context.api_urls:
            return
        context.record(
            "API_LINK_REWRITTEN",
            message=f"{context.api_links} link(s) rewritten to the -resources tree "
                    f"across {len(context.api_urls)} API tree(s)",
            count=context.api_links,
        )

    def _report_flattened_links(self, context: ConversionContext) -> None:
        """One note per version for the links a code fence could not hold (Phase 8).

        The inline half of the code-span swallow is fixed -- a link inside
        `<code>` now reaches `link()` and is emitted. A `<pre>` is not, because GFM
        has no syntax that puts a link inside a fence, and emitting the block as
        HTML instead would cost every reader a copy-pasteable code block to recover
        a type cross-reference. That is a decision rather than an oversight, and
        this is what makes it a number somebody can argue with.
        """
        if not context.flattened_links:
            return
        context.record(
            "CODE_LINK_FLATTENED",
            message=f"{context.flattened_links} link(s) inside a code block kept "
                    f"their words and lost their target",
            count=context.flattened_links,
        )

    def _report_unrendered(self, context: ConversionContext) -> None:
        """One note per version for the media the walk had no Markdown for (R8-13).

        Named by tag, because the tag is the decision somebody would argue with:
        a version full of `<iframe>`s wants a construct, a stray `<svg>` does not.
        """
        if not context.unrendered:
            return
        total = sum(context.unrendered.values())
        tags = ", ".join(f"{name} {count}" for name, count in sorted(context.unrendered.items()))
        context.record(
            "ELEMENT_UNRENDERED",
            message=f"{total} embedded element(s) with no Markdown form ({tags}); an absolute "
                    f"URL became a link, anything else kept only its fallback text",
            count=total,
        )

    def _retarget_fragments(
        self, context: ConversionContext, staging: Path, help_map: dict[str, str] | None = None
    ) -> None:
        """Points every `#fragment` at a heading rather than at an inert marker.

        **A whole-tree pass, after every document is written and before the
        swap**, because a fragment names a heading in *another* file and the
        converter emits one document at a time: at render time the target may
        not exist yet. The same reason `csh` resolution runs here.

        Measured before this existed: of Streaming 11.2.1's 5,670 internal
        fragment links, 5,670 pointed at an `<a id>` marker and **none** at a
        heading -- so every one of them landed at the top of a page. Across the
        published trees it was roughly 50,000.

        A fragment this cannot place is left exactly as written and counted. The
        two reasons it cannot are a target document with no headings at all, and
        a fragment naming no marker in it; inventing an anchor for either would
        replace a link that fails visibly with one that fails quietly elsewhere.

        A fragment is looked up decoded (R8-08). Links emit it percent-encoded
        and markers hold the name as written, so `#tibdg%20proxy%20shed` missed
        `<a id="tibdg proxy shed">` and was counted here as having no heading:
        53 of the 201 encoded fragments in the published trees.

        `help_map`, the resolved `csh.yml` entries, is retargeted in place.
        """
        targets: dict[PurePosixPath, dict[str, str]] = {}
        bodies: dict[PurePosixPath, str] = {}
        for path in sorted(staging.rglob("*.md")):
            relative = PurePosixPath(path.relative_to(staging).as_posix())
            bodies[relative] = path.read_text(encoding="utf-8")
            targets[relative] = fragments.marker_targets(bodies[relative])

        rewritten = unplaced = 0
        for relative, body in bodies.items():
            def anchor_for(raw: str, fragment: str, here: PurePosixPath = relative) -> str | None:
                nonlocal unplaced
                reference = links.classify(raw)
                if reference.kind is links.ReferenceKind.ABSOLUTE:
                    return None
                target = here if not raw else links.resolve(here.parent, reference.path)
                found = targets.get(PurePosixPath(target))
                if found is None:
                    return None
                placed = found.get(_fragment_key(fragment))
                if placed is None:
                    unplaced += 1
                return placed

            updated, count = fragments.retarget(body, anchor_for)
            if count:
                rewritten += count
                textfile.write_text(staging / Path(*relative.parts), updated)

        # **And the navigation, which is where most of them are.** Measured on
        # the first run of this pass: 18,047 of 18,112 surviving broken
        # fragments came from `toc.yml` and only 65 from page bodies. A TOC node
        # for a same-page section carries `url: "foo.md#anchor"`, and that
        # anchor is a marker like any other. Rewriting the value in place rather
        # than re-emitting the YAML keeps the file byte-stable everywhere else,
        # which is what makes a re-convert diffable.
        toc = staging / "toc.yml"
        if toc.is_file():
            text = toc.read_text(encoding="utf-8")
            moved = 0

            def replace(match: re.Match[str]) -> str:
                nonlocal moved, unplaced
                path, separator, fragment = match.group(1).partition("#")
                if not separator or not fragment:
                    return match.group(0)
                found = targets.get(PurePosixPath(path))
                placed = found.get(_fragment_key(fragment)) if found is not None else None
                if placed is None:
                    unplaced += 1
                    return match.group(0)
                moved += 1
                return f'url: "{path}#{placed}"'

            updated = _TOC_PATH.sub(replace, text)
            if moved:
                rewritten += moved
                textfile.write_text(toc, updated)

        # **And the help map**, rewritten in place before the caller writes it
        # (Phase 34, R8-04). Its anchor is the source's marker name, so a Help
        # button pointed at the inert marker and opened the top of the page: 345
        # entries in all 7 TRA versions, which publish unmerged. Reframe already
        # retargets the map for merged trees (`reframe/csh.py`); this is the same
        # repair for the trees that never reach it, with the same lookup as a
        # link's and the same count for what it cannot place.
        entries = help_map if help_map is not None else {}
        for identifier, value in list(entries.items()):
            path, separator, fragment = value.partition("#")
            if not separator or not fragment:
                continue
            found = targets.get(PurePosixPath(path))
            placed = found.get(_fragment_key(fragment)) if found is not None else None
            if placed is None:
                unplaced += 1
                continue
            rewritten += 1
            entries[identifier] = f"{path}#{placed}"

        if rewritten:
            context.record(
                "FRAGMENT_RETARGETED",
                message=f"{rewritten} cross-reference(s) pointed at a heading instead of an "
                        f"inert anchor marker the platform does not honour",
                count=rewritten,
            )
        if unplaced:
            context.record(
                "FRAGMENT_UNPLACEABLE",
                message=f"{unplaced} cross-reference(s) name no anchor marker with a heading "
                        f"behind it in their target; left as written and will not resolve",
                count=unplaced,
            )

    def _report_repairs(self, context: ConversionContext) -> None:
        """One note each for Phase 27's two structural repairs to the source.

        Both are rewrites of what the author wrote, applied to every page silently
        and correctly, which is exactly the shape of change that is impossible to
        audit a year later unless somebody counted it at the time.
        """
        if context.renumbered_headings:
            context.record(
                "HEADING_LEVEL_NORMALIZED",
                message=f"{context.renumbered_headings} heading(s) renumbered to close "
                        f"a level the source skipped",
                count=context.renumbered_headings,
            )
        if context.recovered_terms:
            context.record(
                "DEFINITION_TERM_RECOVERED",
                message=f"{context.recovered_terms} definition term(s) recovered from "
                        f"class-named markup and published as terms",
                count=context.recovered_terms,
            )

    def _report_output_count(self, context: ConversionContext, result: ConvertResult) -> None:
        """The engines' document count against the files on disk (Phase 13).

        Every document and every generated page is one `write_text` to a path the
        engine chose, so the two numbers agree unless **two writes resolved to one
        path** -- in which case the second silently replaced the first and the
        version publishes with a topic missing. That is not hypothetical: 7b found
        `navigation._free` comparing a generated container page's path
        case-sensitively, and three versions had already shipped that way.

        Only a shortfall is reported. A surplus means a file in the tree that no
        document produced, which is what `csh.yml`, `toc.yml` and `metadata.yml`
        are -- they are `.yml`, so they cannot reach this count at all, and any
        other surplus is a stray the orphan sweep is the right reader for.
        """
        expected = result.documents + result.generated
        if result.md_files >= expected:
            return
        context.record(
            "OUTPUT_COUNT_MISMATCH",
            message=f"{expected} document(s) converted but {result.md_files} Markdown file(s) "
                    f"on disk; {expected - result.md_files} write(s) landed on another",
            count=expected - result.md_files,
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

        The reading itself moved to `apiref.recorded_roots` in 6d, when Stage 7
        needed the same answer: §6.3 says the three stages share one record, and
        two functions parsing it is the first step towards two records.
        """
        return recorded_roots(self._metadata(slug, version), key, tree)

    def _api_roots(
        self, slug: str, version: str, tree: Path, output_roots: list[Path],
        standalone: bool = False,
    ) -> list[Path]:
        """Stage 4's recorded API roots, located here only when there is no record.

        §6.3's rule -- Stages 4, 5 and 7 share one recorded answer -- is intact,
        because this never *re*-walks a tree that has an answer: a recorded empty
        list and a located empty list come from the same predicate and cannot
        disagree. The fallback is for `--input`, a standalone folder that never
        went through `extract`, and it is the same fallback `_csh_sources` makes
        one line below for the same reason.

        It is not cosmetic. A DocBook package's `apidocs/dotnet` tree is 1,466
        pages whose generator is in no marker list, so without the fallback they
        are skipped as merely "not DocBook" instead of named as the API reference
        they are -- the difference between a report line that explains 1,466 files
        and one that shrugs at them.
        """
        recorded = [] if standalone else self._recorded_paths(slug, version, "api_roots", tree)
        return recorded or find_api_roots(tree, output_roots)

    def _inputs_key(self, product: Product, version: ProductVersion) -> str:
        """A digest of what shapes the converted tree besides the package (X3-05/06/07).

        The converter's version, the display name (it titles the version's
        `toc.yml` and index), the templates the converter renders, and what
        `301.yml` is built from -- each changed the output and left the stage
        `current`. Read fresh per version: a template is three small files and
        the page list one cached leaf, against a conversion.
        """
        slug, number = product.slug, version.version
        templates = hashlib.sha256()
        for name in _TEMPLATES:
            path = self.config.aem_templates_dir / name
            templates.update(name.encode("utf-8") + b"\0")
            templates.update(path.read_bytes() if path.is_file() else b"")
        shaping = {
            "converter": _CONVERTER_VERSION,
            "display_name": product.display_name,
            "templates": templates.hexdigest()[:16],
            "origins": origins.fingerprint(
                self.config.load_origin_urls(), slug, version.zip_url,
                origins.page_list(self.config.cache_dir, slug, number),
            ),
        }
        payload = json.dumps(shaping, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _api_prefix(self, product: Product, version: str) -> str:
        """The publishing coordinates every one of this version's API URLs shares.

        The currency key, and nothing else reads it -- the URLs themselves are
        composed per root by `apirefs.url_map`. Empty whenever no URL could be
        emitted at all, so that "no API tree" and "no `-resources` tree for this
        locale" record the same absence as a version that simply has none.
        """
        segment = version_segment(version)
        if not segment or not self.config.publishes_resources():
            return ""
        tree_name = self.config.resources_tree_name(product.bu, product.family)
        return apirefs.published_url(
            self.config.publish_base_url(), tree_name,
            slugify(self.config.locale), product.slug, segment, "",
        )

    def _content_tree(self, product: Product, version: str, tree: Path) -> Path:
        """Where content starts inside the extracted tree (Phase 15b).

        Used for one thing only -- the base API-reference folders are named from.
        The engines locate content by scanning rather than by path, so a wrapper
        directory has never troubled them, and moving their root on no evidence
        would be a change to four converters to fix a defect in neither.
        """
        metadata = self.catalog.state.get_version_metadata(
            product.slug, version
        ) if self.catalog.state else {}
        return content_root.of(tree, metadata.get(content_root.METADATA_KEY))

    def _api_urls(
        self, product: Product, version: str, tree: Path, api_roots: list[Path]
    ) -> dict[Path, str]:
        """Where each of this version's API trees will be published (6e).

        Conversion is *told* this rather than deriving it, which is what keeps
        §10.7's rationale true: the engines still do not know the publishing layout.
        Skipped entirely when there are no API roots, because `url_map` measures the
        trees it is given and there is nothing to measure.
        """
        if not api_roots or not self._api_prefix(product, version):
            return {}
        # The *naming* base, not the tree: `url_map` and Stage 7's `select` run
        # through one `_measured`, so the URL emitted here and the folder written
        # there must be derived from the same root or they disagree by a wrapper
        # directory's name (Phase 15b).
        return apirefs.url_map(
            self._content_tree(product, version, tree), api_roots,
            self.config.publish_base_url(),
            self.config.resources_tree_name(product.bu, product.family),
            slugify(self.config.locale), product.slug, version_segment(version),
        )

    def _csh_sources(
        self, slug: str, version: str, tree: Path, standalone: bool = False
    ) -> list[CshSource]:
        """The version's help maps, re-read from disk at the paths Stage 4 recorded.

        Re-read rather than re-located: `state.db` holds each source's path, format
        and **doc-set**, and the doc-set is the one part that cannot be recovered
        from the file itself. Entries are not stored -- 11,054 rows of Flare alias
        for one product would be a copy of a file we already have.

        Falls back to locating them when there is no record, and always for a
        standalone `--input` folder, whose layout the record does not describe.
        """
        rows = (
            self.state.get_csh_sources(slug, version)
            if self.state is not None and not standalone else []
        )
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
            # `long_path` (X2-08): a help map past 260 characters is on disk.
            if not long_path(path).is_file():
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


def _describe(exc: BaseException) -> str:
    """`ValueError: message (flare.py:812)` -- the type, the text, the innermost frame."""
    frames = traceback.extract_tb(exc.__traceback__)
    where = f" ({Path(frames[-1].filename).name}:{frames[-1].lineno})" if frames else ""
    return f"{type(exc).__name__}: {exc}{where}"


def _output_path(unit: Unit, document: Document) -> PurePosixPath:
    """A document's path in the version's output: its unit's subtree, then its own."""
    return PurePosixPath(unit.name) / document.relative if unit.name else document.relative


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


def _excluded(tree: Path, source: CshSource, context: ConversionContext, work: list[Path]) -> bool:
    """Is this help map inside a root the version left out, and in no unit below it?

    Judged by the file's path and not its recorded doc-set: the doc-set is the
    innermost root *of the version's engine*, so a WebWorks `topics.js` inside a
    Flare root is recorded against the Flare root.
    """
    owner = owning_root(tree / source.path, [*work, *context.excluded_roots])
    return owner is not None and owner in context.excluded_roots


def _find_csh(tree: Path) -> list[tuple[Path, CshFormat]]:
    """Locates help maps in a tree nobody has inventoried. `--input` only.

    `walk_files`, not `rglob` (X2-08), which drops a file past 260 characters.
    """
    found = []
    for relative, _absolute in walk_files(tree):
        path = tree / relative
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
