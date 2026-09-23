"""Stage 6b's driver: the engine gate, the TOC read, and the swap.

Shaped like `converter/driver.py` deliberately -- the same selection, the same
"a failure is a returned outcome, never an exception", the same build-and-swap, the
same five-outcome summary -- because `convert` and `reframe` will be read side by
side and run one after the other.

Four rules the driver holds so the packer never has to:

- **The engine gate lives here, inside the stage** (requirements C2), not only in
  whatever selects the versions. The standalone path is exactly where a
  wrong-doc-set invocation happens, and the caller is not in that path.
- **The input is never written to** (C4). Stage 6a's `output/` tree is read and a
  sibling `reframed/` tree is built, so tuning a boundary rule is a re-run rather
  than a restoration from git.
- **Output is built at `<target>.part/` and swapped**, for the reason Stage 5 does
  it: a re-merge over a live directory leaves the previous pass's pages in place,
  and a boundary that moved would show up as two pages covering one topic.
- **An unrecognised TOC is a failure, not a skip.** A half-parsed tree merges into
  a plausible-looking page count with a branch silently missing.

In Phase 20a no packer is registered, so a Flare version is read, checked and
passed through byte-identical. That is the sub-phase's whole visible behaviour and
it is honest: the spine runs end to end, the gate holds, and nothing is merged yet.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import yaml

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.models import Product, ProductVersion, SourceEngine
from docushift.reframe.policy import ReframePolicy, policy_for
from docushift.reframe.toc import TocEntry, schema_for
from docushift.reporting.findings import FindingsRun
from docushift.utils.swap import remove, swap

#: The one engine Reframe runs for (C1). A tuple rather than a bare constant
#: because the question "which engines produce topics small enough to need this?"
#: is an empirical one, and WebWorks is the plausible second answer.
REFRAMABLE_ENGINES: tuple[SourceEngine, ...] = (SourceEngine.FLARE,)


class ReframeOutcome(StrEnum):
    """What happened to one version. Every run reports these five counts."""

    REFRAMED = "reframed"
    # The converted tree and the policy are both unchanged since the last merge.
    CURRENT = "current"
    # Selected, but its engine does not produce topics this stage merges (C1).
    # Not a failure and not a warning -- the overwhelming majority of the catalog.
    NOT_FLARE = "not-flare"
    # Flare, and eligible, but nothing has been converted yet.
    NO_OUTPUT = "no-output"
    FAILED = "failed"


@dataclass
class ReframeResult:
    """One version's outcome, for the report and for the tests."""

    slug: str
    version: str
    outcome: ReframeOutcome
    path: Path | None = None
    engine: SourceEngine | None = None
    #: Topics read out of the source `toc.yml`. The denominator every acceptance
    #: check in requirements §6 is measured against.
    topics: int = 0
    #: Pages written. Equal to `topics` until the packer lands in 20b.
    pages: int = 0
    #: Which TOC dialect the adapter seam matched, for the report.
    toc_schema: str = ""
    message: str = ""


@dataclass
class ReframeStats:
    results: list[ReframeResult] = field(default_factory=list)

    def count(self, outcome: ReframeOutcome) -> int:
        return sum(1 for r in self.results if r.outcome is outcome)

    @property
    def topics(self) -> int:
        return sum(r.topics for r in self.results)

    @property
    def pages(self) -> int:
        return sum(r.pages for r in self.results)

    @property
    def failures(self) -> list[ReframeResult]:
        return [r for r in self.results if r.outcome is ReframeOutcome.FAILED]

    @property
    def reframed(self) -> list[ReframeResult]:
        return [r for r in self.results if r.outcome is ReframeOutcome.REFRAMED]


class Reframer:
    """Merges a converted Flare tree into fewer, larger pages."""

    def __init__(
        self,
        config: ConfigManager,
        catalog: CatalogManager,
        findings: FindingsRun | None = None,
    ) -> None:
        self.config = config
        self.catalog = catalog
        self.findings = findings
        self.state = catalog.state
        self.reframe_config = config.load_reframe()

    # -- one version ----------------------------------------------------------

    def reframe_one(
        self,
        product: Product,
        version: ProductVersion,
        force: bool = False,
        source: Path | None = None,
        output: Path | None = None,
    ) -> ReframeResult:
        """Merges one version. Never raises.

        `source` and `output` override the catalog's paths, which is what
        `--input`/`--output` are for; everything else about the run is identical, so
        a standalone folder is not a second code path.
        """
        slug, number = product.slug, version.version

        # C2: the gate is the first thing the stage does, before it has looked at a
        # path, and it is checked against the version in hand rather than trusting
        # that the selection already filtered. `--input` is the case that matters.
        if version.engine not in REFRAMABLE_ENGINES:
            return ReframeResult(
                slug, number, ReframeOutcome.NOT_FLARE, engine=version.engine,
                message=f"{version.engine} topics are not merged by this stage",
            )

        converted = source or self.config.output_path(product.bu, product.family, slug, number)
        target = output or self.config.reframed_path(product.bu, product.family, slug, number)

        if not converted.is_dir():
            message = f"no converted tree at {converted}; run `docushift convert` first"
            return ReframeResult(slug, number, ReframeOutcome.NO_OUTPUT, message=message)

        policy = policy_for(self.reframe_config, slug)
        metadata = self._metadata(slug, number)
        # Keyed on what produced the input plus what shaped the output. The first
        # alone would leave a tuned `reframe.yaml` looking current over a tree laid
        # out by the old rules, and the boundary rules are expected to be tuned
        # repeatedly -- so that would be the common case, not a corner of it.
        converted_from = metadata.get("convert_source_checksum", "")
        merged_from = metadata.get("reframe_source_checksum", "")
        policy_current = metadata.get("reframe_policy_key", "") == policy.key
        if not force and converted_from and converted_from == merged_from and policy_current and target.is_dir():
            return ReframeResult(
                slug, number, ReframeOutcome.CURRENT, path=target, engine=version.engine
            )

        try:
            return self._build(product, version, policy, converted, target, converted_from)
        except OSError as exc:  # pragma: no cover - filesystem failure, not logic
            message = f"{type(exc).__name__}: {exc}"
            return ReframeResult(slug, number, ReframeOutcome.FAILED, message=message)

    def _build(
        self,
        product: Product,
        version: ProductVersion,
        policy: ReframePolicy,
        converted: Path,
        target: Path,
        checksum: str,
    ) -> ReframeResult:
        """Reads the navigation, checks the pins, writes the tree, swaps it in."""
        slug, number = product.slug, version.version

        entries, schema_name = self._navigation(converted, policy, slug, number)
        if entries is None:
            return ReframeResult(
                slug, number, ReframeOutcome.FAILED, engine=version.engine,
                message=f"no TOC adapter matches {converted / 'toc.yml'}",
            )

        self._check_pin(product, policy)
        topics = sum(1 for entry in entries if entry.path is not None)

        staging = target.with_name(target.name + ".part")
        remove(staging)
        staging.parent.mkdir(parents=True, exist_ok=True)

        # 20a's passthrough. The packer replaces this call in 20b; what it must not
        # replace is the shape around it -- build into `.part`, swap, then record.
        # `copytree` rather than a rename of the input, because C4 is the rule the
        # rest of this stage's reversibility rests on.
        shutil.copytree(converted, staging)
        pages = sum(1 for _ in staging.rglob("*.md"))

        # Eight attempts over ~9s rather than `swap`'s default five over ~1s. The
        # default is calibrated against `convert`, which writes its files one at a
        # time over minutes; this stage hands the scanner a whole tree in one burst
        # and then immediately asks to rename the directory out from under it. EMS
        # 10.5.1 -- 1,441 files -- failed all five default attempts on the first
        # real run and succeeded on a manual retry a moment later. Widening the
        # budget here rather than in `swap` keeps the other callers' failures fast.
        swap(staging, target, attempts=8, delay=0.25)
        if self.state is not None:
            self.state.set_version_metadata(slug, number, "reframe_source_checksum", checksum)
            self.state.set_version_metadata(slug, number, "reframe_policy_key", policy.key)
        if self.findings is not None:
            self.findings.flush()

        return ReframeResult(
            slug, number, ReframeOutcome.REFRAMED, path=target, engine=version.engine,
            topics=topics, pages=pages, toc_schema=schema_name,
        )

    # -- the pieces -----------------------------------------------------------

    def _navigation(
        self, converted: Path, policy: ReframePolicy, slug: str, number: str
    ) -> tuple[list[TocEntry] | None, str]:
        """Every TOC row of one version, flattened, through the adapter seam.

        Returns `(None, "")` after recording the finding, rather than raising, so a
        doc set with an unreadable TOC is one named row in the report and the rest
        of the selection still runs.
        """
        path = converted / "toc.yml"
        document: object = None
        if path.is_file():
            try:
                document = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                self._record("REFRAME_TOC_SCHEMA_UNKNOWN", slug, number, message=str(exc))
                return None, ""

        schema = schema_for(document, policy.toc_schema)
        if schema is None:
            reason = (
                f"configured schema '{policy.toc_schema}' is not registered"
                if policy.toc_schema else "no registered adapter recognises this shape"
            )
            self._record("REFRAME_TOC_SCHEMA_UNKNOWN", slug, number, path="toc.yml", message=reason)
            return None, ""

        entries = [row for top in schema.parse(document) for row in top.walk()]
        return entries, schema.name

    def _check_pin(self, product: Product, policy: ReframePolicy) -> None:
        """R1.4. A doc set with two eligible versions and no pin drifts, permanently.

        Counted off the catalog rather than off disk: the question is how many
        versions *will* be merged, and the second one not being converted yet is
        precisely when pinning is still cheap to decide. Narrowed to the engines
        this stage merges for the same reason -- five `auto` versions beside one
        Flare version cannot drift apart, because only one of them is ever laid out.
        """
        if policy.pin_layout_to:
            return
        eligible = [
            version
            for _, version in self.catalog.iter_versions(slug=product.slug, eligible_only=True)
            if version.engine in REFRAMABLE_ENGINES
        ]
        if len(eligible) < 2:
            return
        self._record(
            "REFRAME_LAYOUT_UNPINNED", product.slug, "",
            message=(
                f"{len(eligible)} eligible Flare versions and no `pin_layout_to` in "
                f"config/reframe.yaml"
            ),
        )

    def _metadata(self, slug: str, number: str) -> dict[str, str]:
        if self.state is None:
            return {}
        return self.state.get_version_metadata(slug, number)

    def _record(self, code: str, slug: str, number: str, path: str = "", message: str = "") -> None:
        if self.findings is not None:
            self.findings.record(code, slug=slug, version=number, path=path, message=message)

    # -- the selection --------------------------------------------------------

    def reframe_many(
        self,
        pairs: Iterable[tuple[Product, ProductVersion]],
        force: bool = False,
        on_result: Callable[[ReframeResult], None] | None = None,
    ) -> ReframeStats:
        """Runs the selection serially, in `iter_versions` order.

        Serial for the reason conversion is: the work is disk-bound, and two merges
        writing thousands of small files onto one disk contend rather than overlap.
        """
        stats = ReframeStats()
        for product, version in pairs:
            result = self.reframe_one(product, version, force=force)
            stats.results.append(result)
            if on_result is not None:
                on_result(result)
        return stats
