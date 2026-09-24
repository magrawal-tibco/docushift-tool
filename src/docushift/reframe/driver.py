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

A fifth rule arrives with the packer in 20b: **the acceptance checks run before the
swap, not after it.** Requirements §6 asks the stage to self-validate and fail, and
§1 explains why it has to be here rather than in a test -- the merge is a one-way
door, so the run that built a tree is the last cheap moment to reject it. A failing
audit removes the staging tree and leaves the previous merge, if any, untouched.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

import yaml

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.models import Product, ProductVersion, SourceEngine
from docushift.reframe import manifest, review
from docushift.reframe.audit import audit
from docushift.reframe.packer import Page, assign, carry, pack, separated
from docushift.reframe.pages import LinkCounts, render, split_frontmatter, title_of, word_count
from docushift.reframe.policy import ReframePolicy, policy_for
from docushift.reframe.review import Flag, branches, inspect
from docushift.reframe.toc import TocEntry, retarget, schema_for
from docushift.reporting.findings import FindingsRun
from docushift.utils.swap import remove, swap

#: The one engine Reframe runs for (C1). A tuple rather than a bare constant
#: because the question "which engines produce topics small enough to need this?"
#: is an empirical one, and WebWorks is the plausible second answer.
REFRAMABLE_ENGINES: tuple[SourceEngine, ...] = (SourceEngine.FLARE,)


#: Written fresh by this stage, so a copy of the source's version would be stale.
_REGENERATED = frozenset({"toc.yml", "reframe.yml", "redirects.yml", "review-queue.csv"})


@dataclass(frozen=True)
class _Written:
    """What `_write` actually put on disk, for §6's word-conservation equality."""

    #: Body tokens across every merged page, frontmatter excluded.
    words: int
    #: Tokens the anchors and heading shifts declared they added (`pages.render`).
    scaffolding: int


class _Source:
    """A read-only view of the converted tree, with one word count per topic.

    A class rather than a pair of closures because the word count is asked for
    twice -- once to choose boundaries and once to check conservation -- and the
    two must be the same number by construction rather than by two call sites
    agreeing. It also holds the file inventory that separates R4's *unresolvable*
    target from a genuinely orphaned one.

    Nothing here writes, which is C4 held at the level of the type.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        paths = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
        self.files = frozenset(PurePosixPath(p) for p in paths)
        #: Everything copied through untouched: not a topic, and not the navigation
        #: or sidecars this stage regenerates from scratch.
        self.assets = tuple(
            PurePosixPath(p)
            for p in paths
            if not p.lower().endswith(".md") and p not in _REGENERATED
        )
        #: Every Markdown topic on disk, whether or not the TOC knows about it.
        self.topics = tuple(PurePosixPath(p) for p in paths if p.lower().endswith(".md"))
        self._words: dict[PurePosixPath, int] = {}

    def exists(self, relative: PurePosixPath) -> bool:
        return relative in self.files

    def read(self, relative: PurePosixPath) -> str:
        return (self.root / relative).read_text(encoding="utf-8")

    def words(self, relative: PurePosixPath) -> int:
        """Body tokens, frontmatter excluded. Memoized; never swallows a read error.

        The POC returned 0 on `OSError` here and then opened the same path
        unguarded in its write pass (requirements §10). The driver checks every TOC
        path exists before calling this, so a failure now is a real filesystem
        fault and belongs in the stage's `except OSError`, not in a zero.
        """
        if relative not in self._words:
            self._words[relative] = word_count(split_frontmatter(self.read(relative))[1])
        return self._words[relative]


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
    #: Merged pages written. The ratio against `topics` is the stage's whole point.
    pages: int = 0
    #: Which TOC dialect the adapter seam matched, for the report.
    toc_schema: str = ""
    #: Pages R6 put in front of a writer. Surfaced because the count is the thing
    #: a human acts on, and it should not need a file opened to be discovered.
    queued: int = 0
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
    def queued(self) -> int:
        return sum(r.queued for r in self.results)

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
        """Reads the navigation, packs, writes the tree, audits it, swaps it in."""
        slug, number = product.slug, version.version

        roots, schema_name = self._navigation(converted, policy, slug, number)
        if roots is None:
            return ReframeResult(
                slug, number, ReframeOutcome.FAILED, engine=version.engine,
                message=f"no TOC adapter matches {converted / 'toc.yml'}",
            )

        self._check_pin(product, policy)
        source = _Source(converted)
        nodes = [entry for root in roots for entry in root.walk() if entry.path is not None]
        topics = len(nodes)

        # Requirements §10's third POC defect, refused at the only point it can be:
        # there, a TOC entry naming a missing file sized as zero words, packed
        # silently, and then crashed the write pass -- after the previous output had
        # already been deleted. Here it is a named failure before anything is built.
        missing = [str(entry.path) for entry in nodes if not source.exists(entry.path)]
        if missing:
            shown = ", ".join(missing[:5]) + (", ..." if len(missing) > 5 else "")
            self._record("REFRAME_SELF_CHECK_FAILED", slug, number, path="toc.yml",
                         message=f"{len(missing)} TOC path(s) name no file: {shown}")
            return ReframeResult(
                slug, number, ReframeOutcome.FAILED, engine=version.engine, topics=topics,
                toc_schema=schema_name, message=f"{len(missing)} TOC path(s) name no file",
            )

        # 20e. Reported per version, not per product: `keep_separate` is written
        # once against the pinned layout, and a path that is right for 10.5.1 and
        # absent from 10.4.0 is exactly the drift worth naming.
        unmatched = [
            path for path in policy.keep_separate
            if not any(separated(topic, [path]) for topic in source.topics)
        ]
        if unmatched:
            self._record(
                "REFRAME_KEEP_SEPARATE_UNMATCHED", slug, number, path="reframe.yaml",
                message=(
                    f"{len(unmatched)} keep_separate path(s) match no topic here, so the "
                    f"merge they were meant to undo still happened: {', '.join(unmatched[:5])}"
                    f"{', ...' if len(unmatched) > 5 else ''}"
                ),
            )

        packed = pack(roots, source.words, policy.max_words, policy.keep_separate)
        # Topics the navigation never listed. Stage 7 publishes them today, so
        # dropping them would delete live content; `packer.carry` explains the call.
        stranded = [
            path for path in source.topics if path not in {entry.path for entry in nodes}
        ]
        if stranded:
            shown = ", ".join(str(path) for path in stranded[:5])
            self._record(
                "REFRAME_TOPIC_UNTOCKED", slug, number,
                message=(
                    f"{len(stranded)} topic(s) absent from toc.yml, carried through as "
                    f"single-topic pages: {shown}{', ...' if len(stranded) > 5 else ''}"
                ),
            )
        carried = carry(
            stranded,
            lambda path: title_of(source.read(path), path.stem),
            source.words,
        )
        built = packed + carried
        located = assign(built)
        unnavigated = frozenset(page.path for page in carried)

        staging = target.with_name(target.name + ".part")
        remove(staging)
        staging.parent.mkdir(parents=True, exist_ok=True)

        # R6, computed before anything is written so the queue and `reframe.yml`
        # are two views of one measurement rather than two passes that could drift.
        ancestors = branches(roots)
        flagged: dict[PurePosixPath, list[Flag]] = {
            page.path: inspect(page, policy.max_words, ancestors) for page in built
        }
        queue = review.rows(built, flagged)

        counts = LinkCounts()
        added = self._write(staging, source, built, located, counts)
        self._write_navigation(
            staging, source, roots, built, located, policy, counts, schema_name, flagged, queue
        )

        failures = audit(
            built, located, roots,
            words_in=sum(topic.words for page in built for topic in page.topics),
            words_out=added.words, added=added.scaffolding, counts=counts,
            unnavigated=unnavigated, queue=queue,
        )
        if failures:
            # Nothing is swapped. Requirements §6: "fail the stage if any check
            # fails" -- and the staging tree is removed rather than left for
            # inspection, because a half-trusted merged tree beside a good one is
            # exactly the thing a later run would pick up by mistake.
            for failure in failures:
                self._record("REFRAME_SELF_CHECK_FAILED", slug, number, message=failure)
            remove(staging)
            return ReframeResult(
                slug, number, ReframeOutcome.FAILED, engine=version.engine, topics=topics,
                pages=len(built), toc_schema=schema_name,
                message=f"{len(failures)} acceptance check(s) failed: {failures[0]}",
            )

        if queue:
            breakdown = ", ".join(f"{name} {count}" for name, count in review.tally(flagged).items())
            self._record(
                "REFRAME_REVIEW_QUEUED", slug, number, path="review-queue.csv",
                message=(
                    f"{len(queue)} of {len(built)} page(s) need an editorial decision "
                    f"(flags across all pages: {breakdown})"
                ),
            )

        if counts.unresolved:
            self._record(
                "REFRAME_LINK_UNRESOLVED", slug, number,
                message=(
                    f"{counts.unresolved} relative reference(s) point outside the converted "
                    f"tree; present before the merge and left exactly as written"
                ),
            )

        pages = len(built)

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
            topics=topics, pages=pages, toc_schema=schema_name, queued=len(queue),
        )

    # -- writing --------------------------------------------------------------

    def _write(
        self,
        staging: Path,
        source: _Source,
        built: list[Page],
        located: dict[PurePosixPath, tuple[Page, str]],
        counts: LinkCounts,
    ) -> _Written:
        """Renders every page into the staging tree. Returns the word accounting."""
        existing = source.files
        words = 0
        scaffolding = 0
        for page in built:
            text, added = render(page, source.read, located, existing, counts)
            destination = staging / page.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            # `newline=""` so the bytes are the same on every platform, which is
            # half of C5; the other half is that everything feeding this is sorted.
            destination.write_text(text, encoding="utf-8", newline="")
            scaffolding += added
            words += word_count(split_frontmatter(text)[1])
        return _Written(words, scaffolding)

    def _write_navigation(
        self,
        staging: Path,
        source: _Source,
        roots: list[TocEntry],
        built: list[Page],
        located: dict[PurePosixPath, tuple[Page, str]],
        policy: ReframePolicy,
        counts: LinkCounts,
        schema: str,
        flagged: dict[PurePosixPath, list[Flag]],
        queue: list[dict[str, str]],
    ) -> None:
        """Copies the assets through, then writes `toc.yml` and the three sidecars.

        Assets are **everything that is not a topic** rather than an allowlist of
        directory names. The POC hardcoded two (`Resources`, `users-guide/images`)
        and silently repathed every reference to anything else into a link with no
        file behind it -- counted as a success, because the asset branch never
        checked. This corpus has three asset directories under two conventions and
        another set will have others, so the rule has to be structural.
        """
        for relative in source.assets:
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source.root / relative, destination)

        manifest.write(staging / "toc.yml", manifest.TOC_HEADER, retarget(roots, located))
        manifest.write(
            staging / "reframe.yml",
            manifest.PAGES_HEADER,
            manifest.summary(built, policy, counts, schema, flagged),
        )
        manifest.write(staging / "redirects.yml", manifest.REDIRECTS_HEADER, manifest.redirects(located))
        # Always written, even empty: an absent file is indistinguishable from a
        # merge that predates the queue, and a writer checking for pending work
        # should see a header and no rows rather than have to ask why.
        review.write(staging / "review-queue.csv", queue)

    # -- the pieces -----------------------------------------------------------

    def _navigation(
        self, converted: Path, policy: ReframePolicy, slug: str, number: str
    ) -> tuple[list[TocEntry] | None, str]:
        """The top-level TOC rows of one version, as a tree, through the adapter seam.

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

        # The tree, not a flattened list: R1's packing is defined on subtrees, and
        # flattening here would have thrown away the only thing it needs.
        return schema.parse(document), schema.name

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
