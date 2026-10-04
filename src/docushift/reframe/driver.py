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

import hashlib
import json
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

import yaml

from docushift import origins
from docushift.catalog import CatalogError, CatalogManager
from docushift.config import ConfigManager
from docushift.models import Product, ProductVersion, SourceEngine
from docushift.reframe import csh as csh_map
from docushift.reframe import manifest, renames, review
from docushift.reframe.audit import audit
from docushift.reframe.packer import (
    Page,
    Topic,
    asset_destination,
    assign,
    carry,
    layout_of,
    override,
    pack,
    project,
    relocate,
    separated,
    shortened,
)
from docushift.reframe.pages import LinkCounts, render, split_frontmatter, title_of, word_count
from docushift.reframe.policy import ReframePolicy, policy_for
from docushift.reframe.review import Flag, branches, inspect
from docushift.reframe.toc import TocEntry, retarget, schema_for
from docushift.reporting.findings import FindingsRun
from docushift.utils import textfile
from docushift.utils.anchors import HEADING
from docushift.utils.longpath import long_path, walk_files
from docushift.utils.slug import version_segment
from docushift.utils.swap import recover, remove, staging_of, swap

# The same function `validate` resolves CSH fragments with, so the audit and the
# gate three stages later cannot disagree about what an anchor is.
from docushift.validation.references import anchors as anchors_in
from docushift.validation.references import mask_code

#: The one engine Reframe runs for (C1). A tuple rather than a bare constant
#: because the question "which engines produce topics small enough to need this?"
#: is an empirical one, and WebWorks is the plausible second answer.
REFRAMABLE_ENGINES: tuple[SourceEngine, ...] = (SourceEngine.FLARE,)


#: Written fresh by this stage, so a copy of the source's version would be stale.
_REGENERATED = frozenset(
    {"toc.yml", "reframe.yml", "redirects.yml", "review-queue.csv", csh_map.CSH_FILE,
     origins.ORIGINS, renames.RENAME_MAP}
)

#: The version-metadata key holding a digest of the `rename-map.csv` this stage
#: last wrote (R9-04). A hand edit changes the file and so the digest, which is
#: what makes the edit a re-merge rather than a no-op.
_RENAME_DIGEST = "reframe_rename_digest"

#: The `convert_build_id` of the converted tree this merge was built from
#: (X3-04). `convert` writes a new one on every build, so a re-convert -- with
#: or without a new package -- makes the merge stale. `sync` compares the same
#: two keys before it publishes a merge.
_MERGED_FROM = "reframe_convert_build"

#: A digest of what shapes the merged tree besides the conversion and the
#: policy (X3-05, X3-07): what `301.yml` is built from, and the publishing
#: host and locale `rename-map.csv` prints its addresses with.
_INPUTS_KEY = "reframe_inputs_key"
#: And a copy of that map's names, outside the tree a swap replaces (X2-02). Read
#: only when `rename-map.csv` is gone, so the file stays the one a writer edits.
_RENAME_PINS = "reframe_rename_pins"


@dataclass(frozen=True)
class _Written:
    """What `_write` actually put on disk, for §6's word-conservation equality."""

    #: Body tokens across every merged page, frontmatter excluded.
    words: int
    #: Tokens the anchors and heading shifts declared they added (`pages.render`).
    scaffolding: int
    #: Per page, the `<a id>` markers actually rendered into it -- section anchors
    #: and the CSH markers that travelled in with the topic bodies alike (20f).
    anchors: dict[PurePosixPath, frozenset[str]] = field(default_factory=dict)
    #: Per page, the identifiers its frontmatter `csh:` key actually lists.
    mirrored: dict[PurePosixPath, frozenset[str]] = field(default_factory=dict)


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
        # `walk_files`, not `rglob` (R9-10), for the reason `_measure_merged`
        # gives: `rglob` omits a file past 260 characters without a word. Here
        # that dropped an asset from the copy and then blamed Stage 6 for the
        # links to it ("present before the merge"), or failed a version over a
        # TOC topic that was on disk all along.
        paths = sorted(relative.as_posix() for relative, _path in walk_files(root))
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
        #: The converted tree's CSH map, or `None` when it has none (20f). Read
        #: here rather than at the write site because the frontmatter mirror and
        #: the retargeted file are two views of it and must not read it twice.
        self.csh = csh_map.load(root)
        self._words: dict[PurePosixPath, int] = {}
        self._headings: dict[PurePosixPath, list[str]] = {}

    def exists(self, relative: PurePosixPath) -> bool:
        return relative in self.files

    def read(self, relative: PurePosixPath) -> str:
        # `long_path`, so a topic the walk can now see can also be opened.
        return long_path(self.root / relative).read_text(encoding="utf-8")

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

    def headings(self, topic: Topic) -> list[str]:
        """Every heading this topic will render, in order. Memoized like `words`.

        What `assign` needs to predict the platform's anchors (Phase 29). The
        *text* is what matters and `shift_headings` never changes it -- only the
        level -- so reading the source body gives the rendered run exactly.

        Fence-masked, for the reason the module docstring gives: a `# comment` in
        a shell sample is not a heading, and treating one as the topic's own H1 is
        the proof-of-concept corruption requirements §7 singles out.

        A body with no H1 gets its TOC title first, because that is precisely what
        `shift_headings` prepends -- the two have to agree or the anchor names a
        heading that is not there.

        `assign` takes index 0 as the topic's own heading. Measured over EMS
        10.5.1: 1,441 of 1,441 topics have an H1 and it is the first heading in
        every one, so the two readings coincide on the whole corpus in hand. A
        body that opened on an `h2` above its `h1` would anchor the topic at that
        `h2` -- wrong, but wrong about a shape no measured topic has.
        """
        if topic.source not in self._headings:
            body = split_frontmatter(self.read(topic.source))[1]
            found = HEADING.findall(mask_code(body))
            texts = [text for _hashes, text in found]
            if not any(len(hashes) == 1 for hashes, _text in found):
                texts.insert(0, topic.title)
            self._headings[topic.source] = texts
        return self._headings[topic.source]


class ReframeOutcome(StrEnum):
    """What happened to one version. Every run reports these five counts."""

    REFRAMED = "reframed"
    # The converted tree, the policy and the approved names in `rename-map.csv`
    # are all unchanged since the last merge, and `--renormalize` was not given.
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
    #: What the merged tree holds once it is built -- one walk, after the swap,
    #: and the two columns Phase 24 records. Not `pages` and not `pages + 5`:
    #: both derivations are wrong for the reason `_measure_merged` gives.
    #: Carried on a `CURRENT` result too, where they are read back from the
    #: catalog rather than measured, so a re-run reports the same funnel.
    reframed_md_files: int = 0
    reframed_files: int = 0
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
    def reframed_md_files(self) -> int:
        """Markdown standing in the merged trees this run measured.

        Summed over every result that carries a measurement, not only over
        `reframed` -- a `current` version is read back from its columns, and its
        tree is as real as one this run built. The same rule
        `ConvertStats.out_files` follows, for the same reason.
        """
        return sum(r.reframed_md_files for r in self.results)

    @property
    def reframed_files(self) -> int:
        return sum(r.reframed_files for r in self.results)

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
        renormalize: bool = False,
    ) -> None:
        self.config = config
        self.catalog = catalog
        self.findings = findings
        #: Ignore `rename-map.csv` and recompute every name. A property of the
        #: invocation rather than of a version, so it rides on the Reframer
        #: rather than being threaded through five signatures that do not care.
        self.renormalize = renormalize
        self.state = catalog.state
        self.reframe_config = config.load_reframe()
        # R1.4. Packing the reference version is the same cost as merging it, and a
        # pinned set asks for it once per sibling -- six times over for EMS. Keyed on
        # (slug, reference version) and holding `None` for a reference that could not
        # be read, so the failure is reported once per product rather than per version.
        self._layouts: dict[tuple[str, str], list[tuple[PurePosixPath, tuple[PurePosixPath, ...]]] | None] = {}

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

        # Before the currency test, for `convert`'s reasons (X2-01, X3-09) -- except
        # that a `.part` with no target beside it is kept: an older tool's
        # interrupted swap left the only copy of the pins in it (X3-02).
        try:
            recover(target, keep_orphan_staging=True)
        except OSError as exc:
            return ReframeResult(slug, number, ReframeOutcome.FAILED,
                                 message=f"{type(exc).__name__}: {exc}")
        # X3-03. A convert killed between its swap and its bookkeeping left a tree
        # its checksums do not describe; merging it would vouch for it.
        if source is None and self._building(slug, number, "convert"):
            return ReframeResult(
                slug, number, ReframeOutcome.FAILED, engine=version.engine,
                message="the converted tree is from a convert that did not finish; "
                        "run `docushift convert` first",
            )

        policy = policy_for(self.reframe_config, slug)
        # X1-02. A standalone folder is not the catalog row's tree, so nothing is
        # read back for it and nothing is recorded: `convert`'s R4-04 guard. It
        # wrote the row's merge state from whatever `--input` named, and `sync`
        # then published the stale `reframed/` tree as current.
        standalone = source is not None
        metadata = {} if standalone else self._metadata(slug, number)
        # Keyed on what produced the input plus what shaped the output. The first
        # alone would leave a tuned `reframe.yaml` looking current over a tree laid
        # out by the old rules, and the boundary rules are expected to be tuned
        # repeatedly -- so that would be the common case, not a corner of it.
        #
        # What produced the input is the *conversion's* build (X3-04, Phase 21's
        # carried item), not the package checksum: `convert --force` wrote that
        # unchanged, so a re-converted tree was not re-merged and the old merge
        # reported current. No recorded build, no currency claim.
        converted_from = metadata.get("convert_build_id", "")
        merged_from = metadata.get(_MERGED_FROM, "")
        policy_current = metadata.get("reframe_policy_key", "") == policy.key
        inputs_key = self._inputs_key(product, version)
        inputs_current = metadata.get(_INPUTS_KEY, "") == inputs_key
        # R9-04. The approved names are an input too. The user guide's workflow is
        # "write a better name into `new_path`; the next run uses it", and with the
        # map outside the key the next run said `current` and used nothing --
        # J's re-merge only worked because it bumped the algorithm. `--renormalize`
        # asks for every name to be recomputed, which a `current` skip cannot do.
        try:
            names_current = (
                not self.renormalize
                and target.is_dir()
                and metadata.get(_RENAME_DIGEST, "") == renames.digest(renames.load(target))
            )
        except renames.Unreadable as exc:
            # X1-06: this version fails, named; it no longer stops the selection.
            return ReframeResult(slug, number, ReframeOutcome.FAILED, engine=version.engine,
                                 message=str(exc))
        # A version still marked as building was interrupted after its swap, so
        # the keys describe some other tree, whatever they say (X3-03).
        if (not force and converted_from and converted_from == merged_from and policy_current
                and inputs_current and names_current
                and not self._building(slug, number, "reframe")):
            current = ReframeResult(
                slug, number, ReframeOutcome.CURRENT, path=target, engine=version.engine
            )
            if self.findings is not None:
                self.findings.point_back("REFRAME_FINDINGS_IN_EARLIER_RUN", slug, number,
                                         metadata.get("reframe_run", ""))
            # Phase 24. Without this the second `reframe` over an unchanged tree
            # reports nothing where the first reported 747 pages, which reads as
            # "the merge produced nothing" rather than "the merge already ran".
            # Measured only when a column is blank -- a version merged before
            # these columns existed, or one whose row was cleared -- so the
            # common case stays a metadata read and not a tree walk.
            if version.reframed_md_files is None or version.reframed_files is None:
                try:
                    current.reframed_md_files, current.reframed_files = self._measure_merged(
                        slug, number, target
                    )
                except CatalogError as exc:
                    # X2-05: `versions.csv` open in Excel fails this row, not the run.
                    return ReframeResult(slug, number, ReframeOutcome.FAILED,
                                         engine=version.engine, message=str(exc))
            else:
                current.reframed_md_files = version.reframed_md_files
                current.reframed_files = version.reframed_files
            # A tree merged before the copy existed gets one now, so a later lost
            # swap finds the names without waiting for a re-merge (X2-02).
            if self.state is not None and not metadata.get(_RENAME_PINS):
                self.state.set_version_metadata(
                    slug, number, _RENAME_PINS, renames.dumps(renames.load(target))
                )
            return current

        try:
            return self._build(product, version, policy, converted, target, converted_from,
                               inputs_key, standalone)
        # `UnicodeDecodeError` too (R9-11): it is a `ValueError`, not an `OSError`,
        # and one undecodable topic or `toc.yml` used to abort the whole
        # selection instead of failing the one version that holds it. A
        # `CatalogError` (X2-05) and an unreadable rename map (X1-06) likewise.
        except (OSError, UnicodeDecodeError, CatalogError, renames.Unreadable) as exc:
            message = f"{type(exc).__name__}: {exc}"
            return ReframeResult(slug, number, ReframeOutcome.FAILED, message=message)

    def _build(
        self,
        product: Product,
        version: ProductVersion,
        policy: ReframePolicy,
        converted: Path,
        target: Path,
        built_from: str,
        inputs_key: str = "",
        standalone: bool = False,
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
        try:
            source = _Source(converted)
        except csh_map.Unreadable as error:
            # Before anything is written, for the reason the TOC check above is:
            # the cheap moment to refuse a merge is the one where there is nothing
            # to roll back.
            self._record("REFRAME_SELF_CHECK_FAILED", slug, number, path=csh_map.CSH_FILE,
                         message=str(error))
            return ReframeResult(
                slug, number, ReframeOutcome.FAILED, engine=version.engine,
                toc_schema=schema_name, message=f"{csh_map.CSH_FILE} does not parse",
            )
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

        packed = self._lay_out(product, version, policy, roots, source)
        if packed is None:
            return ReframeResult(
                slug, number, ReframeOutcome.FAILED, engine=version.engine, topics=topics,
                toc_schema=schema_name,
                message=f"layout pinned to {policy.pin_layout_to}, which cannot be laid out",
            )
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
        placements: dict[int, tuple[Page, str]] = {}
        located = assign(built, source.headings, placements)
        # Folders mirror the TOC (Phase 29), so the repo path and the published
        # URL are the same chain. Before `render`, which resolves every relative
        # link and asset against `page.path`.
        relocate(built, roots)
        # A name a human kept in `rename-map.csv` wins over both the computed
        # name and the computed folder: a published URL must not move because
        # somebody fixed a typo in a title. `--renormalize` is how a writer asks
        # for the names to be recomputed anyway.
        approved = self._approved(slug, number, target, standalone)
        # X2-03. A `new_path` is a write path: refused before the layout sees it
        # unless it names a page inside the tree.
        unsafe = {old: (new, why) for old, new in approved.items()
                  if (why := renames.refusal(new)) is not None}
        if unsafe:
            shown = ", ".join(f"{old} -> {new} ({why})" for old, (new, why) in list(unsafe.items())[:5])
            self._record(
                "RENAME_MAP_REFUSED", slug, number, path=renames.RENAME_MAP, count=len(unsafe),
                message=(
                    f"{len(unsafe)} name(s) in {renames.RENAME_MAP} are not a page path inside "
                    f"the merged tree, so the computed name was kept: {shown}"
                    f"{', ...' if len(unsafe) > 5 else ''}"
                ),
            )
        pinned, refused = override(built, {old: new for old, new in approved.items() if old not in unsafe})
        if pinned:
            self._record(
                "RENAME_MAP_APPLIED", slug, number, count=len(pinned),
                message=(f"{len(pinned)} page name(s) taken from {renames.RENAME_MAP} "
                         f"rather than recomputed"),
            )
        if refused:
            # R9-05. A name somebody chose that silently did nothing looks exactly
            # like one that was applied -- `keep_separate`'s argument, and the
            # same answer: name each one.
            shown = ", ".join(f"{source} -> {wanted}" for source, wanted in list(refused.items())[:5])
            self._record(
                "RENAME_MAP_REFUSED", slug, number, path=renames.RENAME_MAP, count=len(refused),
                message=(
                    f"{len(refused)} name(s) in {renames.RENAME_MAP} name a path another page "
                    f"holds (letter case aside), so the computed name was kept: {shown}"
                    f"{', ...' if len(refused) > 5 else ''}"
                ),
            )
        # X1-07. A pin is keyed on its leading topic's converted path, which a
        # re-convert or a boundary change can retire. Such a row was neither
        # applied nor refused, and the rewritten map erased it, so a hand-chosen
        # URL reverted without a word. It is still dropped -- nothing in the tree
        # carries that topic as a page -- but named, old and new, before it goes.
        leading = {page.topics[0].source for page in built if page.topics}
        unmatched = {old: new for old, new in approved.items() if old not in leading}
        if unmatched:
            shown = ", ".join(f"{old} -> {new}" for old, new in list(unmatched.items())[:5])
            self._record(
                "RENAME_MAP_UNMATCHED", slug, number, path=renames.RENAME_MAP,
                count=len(unmatched),
                message=(
                    f"{len(unmatched)} row(s) in {renames.RENAME_MAP} name a source topic that "
                    f"no longer leads a page, so their names were not used and the rows are "
                    f"dropped from the rewritten map: {shown}{', ...' if len(unmatched) > 5 else ''}"
                ),
            )
        unnavigated = frozenset(page.path for page in carried)
        # Read before anything is written: the queue a writer may have worked (X2-06).
        worked = review.previous(target / "review-queue.csv")

        staging = staging_of(target)
        remove(staging)
        staging.parent.mkdir(parents=True, exist_ok=True)

        # R6, computed before anything is written so the queue and `reframe.yml`
        # are two views of one measurement rather than two passes that could drift.
        ancestors = branches(roots)
        # R9-12: a name taken from `rename-map.csv` is a human's answer to the
        # `shortened` flag, so it is not asked again on every run.
        cut = shortened(built) - pinned
        flagged: dict[PurePosixPath, list[Flag]] = {
            page.path: inspect(
                page, policy.max_words, ancestors,
                shortened=bool(page.topics) and page.topics[0].source in cut,
            )
            for page in built
        }
        queue = review.rows(built, flagged)

        counts = LinkCounts()
        added = self._write(staging, source, built, located, counts)
        self._write_navigation(
            staging, source, roots, built, located, policy, counts, schema_name, flagged,
            queue, self._url_for(product, version), placements, cut, worked,
        )
        self._write_origins(staging, product, version, located, standalone)

        failures = audit(
            built, located, roots,
            words_in=sum(topic.words for page in built for topic in page.topics),
            words_out=added.words, added=added.scaffolding, counts=counts,
            unnavigated=unnavigated, queue=queue,
            csh=csh_map.retarget(source.csh, located) if source.csh else None,
            anchors=added.anchors, mirrored=added.mirrored,
        )
        # Every merged page is one `.md` and nothing else in the tree writes one,
        # so the walk and the counter agree exactly on every version measured
        # (124/124, 128/128). A disagreement means a page write landed somewhere
        # the layout did not intend -- the failure Stage 5's equivalent check
        # exists to catch. **Counted in the staging tree, before the swap**
        # (R9-09): it ran after the swap, reported an error and stamped the tree
        # current anyway, so the next run said `current` and the bad tree stood.
        staged = sum(1 for _relative, path in walk_files(staging) if path.suffix.lower() == ".md")
        if staged != len(built):
            failures.append(
                f"{len(built)} page(s) merged but {staged} Markdown file(s) in the merged "
                f"tree; a page write landed outside the layout"
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
        #
        # Marked as building first, and cleared only once every key below is
        # written (X3-01, X3-03): a run killed in between is rebuilt by the next
        # `reframe` and refused by `sync`, never called `current`.
        if self.state is not None and not standalone:
            self.state.mark_building(slug, number, "reframe")
        swap(staging, target, attempts=8, delay=0.25)
        # The state rows first, then the CSV (X2-05), the order convert settled
        # on in R4-08. The inventory column is the one write Excel can block, and
        # it ran first: its `CatalogError` left the swapped-in tree with no record
        # of what it was built from. Now the rows describe the tree whatever
        # happens to the columns, and the failure is this version's row.
        # Nothing for a standalone folder (X1-02): neither the rows nor the
        # catalog columns describe it.
        if self.state is not None and not standalone:
            self.state.set_version_metadata(slug, number, _MERGED_FROM, built_from)
            self.state.set_version_metadata(slug, number, _INPUTS_KEY, inputs_key)
            self.state.set_version_metadata(slug, number, "reframe_policy_key", policy.key)
            # Read back from the swapped-in tree rather than from `built`, so the
            # digest is of exactly the file the next run will compare (R9-04).
            written = renames.load(target)
            self.state.set_version_metadata(slug, number, _RENAME_DIGEST, renames.digest(written))
            self.state.set_version_metadata(slug, number, _RENAME_PINS, renames.dumps(written))
            # X3-11: the run whose findings describe this tree.
            if self.findings is not None and self.findings.run_id:
                self.state.set_version_metadata(slug, number, "reframe_run", self.findings.run_id)
        merged_md, merged_files = self._measure_merged(slug, number, target, record=not standalone)
        # Cleared only now, with every row and column written (X3-01, X3-03).
        if self.state is not None and not standalone:
            self.state.clear_building(slug, number, "reframe")
        if self.findings is not None:
            self.findings.flush()

        return ReframeResult(
            slug, number, ReframeOutcome.REFRAMED, path=target, engine=version.engine,
            topics=topics, pages=pages, toc_schema=schema_name, queued=len(queue),
            reframed_md_files=merged_md, reframed_files=merged_files,
        )

    # -- measurement -----------------------------------------------------------

    def _measure_merged(
        self, slug: str, version: str, target: Path, record: bool = True
    ) -> tuple[int, int]:
        """One walk of the merged tree, and the two columns it writes (§3.9).

        **Walked, not derived**, and the arithmetic here is wronger than the one
        `converter._measure_output` refuses. `len(built)` is 124 where the tree
        holds 163 files, and the difference is not a constant: `toc.yml`,
        `reframe.yml` and `redirects.yml` are always written, `csh.yml` only for a
        version with a help map, `301.yml` only for a product with a declared
        origin template, `review-queue.csv` always but empty, and the copied
        assets are whatever the pages referenced. Two of those five artifacts are
        conditional on things this stage does not decide.

        Recorded even when the count is unremarkable, because the number that
        matters is not this one -- it is the ratio against `_md_files`, and a
        ratio needs both ends persisted to survive the run that measured it.
        """
        reframed_md = reframed_files = 0
        # `walk_files`, not `rglob`. Since Phase 29 the folders mirror the TOC, so
        # a page seven levels down a Runtime Agent guide is past Windows' 260
        # characters -- and `rglob` reaches each directory through the unprefixed
        # spelling and therefore **omits such a file silently**. It cost an hour
        # here: 118 pages written, 116 counted, and an acceptance check correctly
        # refusing a tree that was in fact complete.
        for _relative, path in walk_files(target):
            reframed_files += 1
            if path.suffix.lower() == ".md":
                reframed_md += 1
        if record:
            self.catalog.record_reframe_inventory(slug, version, reframed_md, reframed_files)
        return reframed_md, reframed_files

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
        mirror = csh_map.by_topic(source.csh) if source.csh else {}
        words = 0
        scaffolding = 0
        anchors: dict[PurePosixPath, frozenset[str]] = {}
        mirrored: dict[PurePosixPath, frozenset[str]] = {}
        for page in built:
            text, added = render(page, source.read, located, existing, counts, mirror)
            # `long_path` since Phase 29: folders mirror the TOC, so a page seven
            # levels down a Runtime Agent guide lands past Windows' 260-character
            # limit and both the `mkdir` and the write fail with a bare
            # FileNotFoundError that names the path and not the reason.
            destination = long_path(staging / page.path)
            # The backstop `renames.refusal` should make unreachable (X2-03), as
            # `safe_unzip` keeps one: `long_path` absolutizes, so a `..` that got
            # this far would be collapsed into a real path outside the tree.
            if long_path(staging) not in destination.parents:
                raise OSError(f"page path {page.path} leaves the merged tree; nothing written")
            destination.parent.mkdir(parents=True, exist_ok=True)
            # LF so the bytes are the same on every platform, which is half of
            # C5; the other half is that everything feeding this is sorted.
            textfile.write_text(destination, text)
            scaffolding += added
            words += word_count(split_frontmatter(text)[1])
            if mirror:
                anchors[page.path] = frozenset(anchors_in(text))
                mirrored[page.path] = frozenset(
                    name for topic in page.topics for name in mirror.get(topic.source, ())
                )
        return _Written(words, scaffolding, anchors, mirrored)

    def _inputs_key(self, product: Product, version: ProductVersion) -> str:
        """A digest of what shapes the merged tree besides the conversion and policy.

        X3-05 / X1-08: what `301.yml` is built from (`origins.fingerprint`, the
        same digest `convert` keys on). X3-07: the publishing host and locale,
        which `rename-map.csv` prints every page's address with. Each changed the
        tree and left the merge `current`.
        """
        publishing = self.config.load_publishing()
        shaping = {
            "origins": origins.fingerprint(
                self.config.load_origin_urls(), product.slug, version.zip_url,
                origins.page_list(self.config.cache_dir, product.slug, version.version),
            ),
            "publish_base_url": str(publishing.get("publish_base_url") or ""),
            "primary_locale": str(publishing.get("primary_locale") or ""),
        }
        payload = json.dumps(shaping, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _url_for(
        self, product: Product, version: ProductVersion
    ) -> Callable[[PurePosixPath], str]:
        """A page path as the address a reader will type, for `rename-map.csv`.

        Through `sync.redirects.published`, not a second formula beside it. The
        served shape -- no repository segment, region-first locale, `.html` --
        is one rule, and the whole point of printing the URL in the rename map
        is that a reviewer can compare it against what the site actually serves.
        Two derivations would make that comparison meaningless exactly when it
        mattered.

        Imported here rather than at module scope: `sync` reaches back into this
        package, so a top-level import makes `import docushift.sync` fail with a
        partially-initialised module depending on which side is imported first.
        """
        from docushift.sync import redirects as redirect_urls

        base = str(self.config.load_publishing().get("publish_base_url") or "")
        locale = str(self.config.load_publishing().get("primary_locale") or "en-us")
        segment = version_segment(version.version)

        def url_of(path: PurePosixPath) -> str:
            return redirect_urls.published(
                base, "", locale, product.slug, "online-help", segment, str(path)
            )

        return url_of

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
        url_of: Callable[[PurePosixPath], str],
        placements: dict[int, tuple[Page, str]],
        cut: set[PurePosixPath],
        worked: list[dict[str, str]] | None = None,
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
            destination = long_path(staging / asset_destination(relative))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(long_path(source.root / relative), destination)

        manifest.write(staging / "toc.yml", manifest.TOC_HEADER,
                       retarget(roots, located, placements))
        manifest.write(
            staging / "reframe.yml",
            manifest.PAGES_HEADER,
            manifest.summary(built, policy, counts, schema, flagged),
        )
        manifest.write(staging / "redirects.yml", manifest.REDIRECTS_HEADER, manifest.redirects(located))
        # Only when the converted tree has one: an empty map in the merged tree
        # would be a file the conversion never produced, which `validate` reads as
        # a promise of context-sensitive help nobody made.
        if source.csh:
            manifest.write(
                staging / csh_map.CSH_FILE,
                csh_map.CSH_HEADER,
                csh_map.retarget(source.csh, located),
            )
        # Always written, even empty: an absent file is indistinguishable from a
        # merge that predates the queue, and a writer checking for pending work
        # should see a header and no rows rather than have to ask why.
        review.write(staging / "review-queue.csv", queue, worked or ())
        renames.write(
            staging / renames.RENAME_MAP,
            renames.rows(built, renames.breadcrumbs(roots), url_of, cut),
        )

    def _write_origins(
        self,
        staging: Path,
        product: Product,
        version: ProductVersion,
        located: dict[PurePosixPath, tuple[Page, str]],
        standalone: bool = False,
    ) -> None:
        """Phase 22's `301.yml`: the live docsite URL of every converted topic.

        Written here rather than in `sync` because of a trap 20d.1 measured. The
        served map has to be assembled after the copy, but a *per-version* file
        written into the published folder after the copy leaves it differing from
        its source, `_identical`'s shallow `filecmp` reports it stale, and **every
        merged version re-copies on every run** with `CURRENT` no longer
        reachable. Written into the staging tree it is copied like any other file
        and the comparison stays true.

        Without `state.db`, or for a standalone `--input` folder, nothing is
        written: the recorded output map is the catalog tree's, not that folder's
        (X1-02 -- the docstring said so and the code wrote one anyway). Otherwise
        the rules -- declared beats derived, derived rows only if the sitemap
        lists them -- are `origins.build`'s, shared with `convert` (Phase 35).
        """
        slug, number = product.slug, version.version
        if self.state is None or standalone:
            return

        moved = {
            str(path): f"{page.path}#{anchor}" for path, (page, anchor) in located.items()
        }
        pages, missing = origins.listing(self.config.cache_dir, slug, number)
        built = origins.build(
            self.config.load_origin_urls(), slug, version.zip_url,
            self.state.get_output_map(slug, number), moved, pages, missing,
        )
        for code, message, count in built.findings:
            self._record(code, slug, number, message=message, count=count)
        if built.rows is not None:
            origins.write(staging / origins.ORIGINS, built.rows)

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

    def _lay_out(
        self,
        product: Product,
        version: ProductVersion,
        policy: ReframePolicy,
        roots: list[TocEntry],
        source: _Source,
    ) -> list[Page] | None:
        """R1.4: the pages of this version, packed on its own or projected onto the pin.

        `None` is the refusal: the pin names a version whose layout cannot be
        computed. Falling back to an unpinned pack would be the worse outcome by
        some distance -- it produces a plausible tree with silently different
        boundaries, and a boundary is the one decision this stage cannot take back.
        """
        if not policy.pin_layout_to or policy.pin_layout_to == version.version:
            return pack(roots, source.words, policy.max_words, policy.keep_separate)
        reference = self._reference_layout(product, policy)
        if reference is None:
            return None
        return project(reference, roots, source.words, policy.max_words, policy.keep_separate)

    def _reference_layout(
        self, product: Product, policy: ReframePolicy
    ) -> list[tuple[PurePosixPath, tuple[PurePosixPath, ...]]] | None:
        """The pinned version's topic->page mapping, packed once and cached.

        Read from the catalog's converted tree even when the caller overrode
        `--input`: the reference is a property of the doc set, not of whichever
        folder this invocation happens to be pointed at.
        """
        number = policy.pin_layout_to
        key = (product.slug, number)
        if key in self._layouts:
            return self._layouts[key]

        layout: list[tuple[PurePosixPath, tuple[PurePosixPath, ...]]] | None = None
        converted = self.config.output_path(product.bu, product.family, product.slug, number)
        if not converted.is_dir():
            reason = f"no converted tree at {converted}; convert {number} first"
        else:
            roots, _ = self._navigation(converted, policy, product.slug, number)
            if roots is None:
                reason = f"no TOC adapter matches {converted / 'toc.yml'}"
            else:
                try:
                    reference = _Source(converted)
                except csh_map.Unreadable as error:
                    reason = str(error)
                else:
                    nodes = {
                        entry.path for root in roots for entry in root.walk()
                        if entry.path is not None
                    }
                    missing = [path for path in nodes if not reference.exists(path)]
                    if missing:
                        reason = f"{len(missing)} TOC path(s) name no file in {number}"
                    else:
                        reason = ""
                        layout = self._reference_pages(roots, reference, policy, nodes)
        if layout is None:
            self._record(
                "REFRAME_PIN_UNAVAILABLE", product.slug, "", path="reframe.yaml",
                message=(
                    f"`pin_layout_to: {number}` names a version whose layout cannot be "
                    f"computed, so no other version can be merged: {reason}"
                ),
            )
        self._layouts[key] = layout
        return layout

    @staticmethod
    def _reference_pages(
        roots: list[TocEntry],
        source: _Source,
        policy: ReframePolicy,
        nodes: set[PurePosixPath],
    ) -> list[tuple[PurePosixPath, tuple[PurePosixPath, ...]]]:
        """The reference version's packed pages, named exactly as its own merge names them.

        `carry` and `assign` are run even though only the packed pages are pinned,
        because the carried pages compete for filenames: leaving them out would let
        the reference report a name its own merge never used.
        """
        packed = pack(roots, source.words, policy.max_words, policy.keep_separate)
        stranded = [path for path in source.topics if path not in nodes]
        carried = carry(stranded, lambda path: title_of(source.read(path), path.stem), source.words)
        assign(packed + carried, source.headings)
        return layout_of(packed)

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

    def _building(self, slug: str, number: str, stage: str) -> bool:
        return self.state is not None and self.state.is_building(slug, number, stage)

    def _approved(
        self, slug: str, number: str, target: Path, standalone: bool = False
    ) -> dict[PurePosixPath, PurePosixPath]:
        """The names a previous merge kept -- and never silently none when it kept some.

        X2-02, X3-02. `rename-map.csv` lives inside the tree a swap replaces, so a
        failed or killed swap took it along, and the next run recomputed every
        name: the published URLs moved and nothing said so. Every merge writes a
        row per page, so a version with a recorded digest had a map. When the
        file is gone, the names come from the copy `state.db` keeps, or from the
        `.part` an older tool's interrupted swap left; either way the run warns.
        """
        if self.renormalize:
            return {}
        if (target / renames.RENAME_MAP).is_file() or standalone:
            return renames.load(target)
        metadata = self._metadata(slug, number)
        if metadata.get(_RENAME_DIGEST, "") in ("", renames.digest({})):
            return {}
        orphan = staging_of(target)
        approved, where = renames.loads(metadata.get(_RENAME_PINS, "")), "the copy state.db keeps"
        if not approved and (orphan / renames.RENAME_MAP).is_file():
            approved, where = renames.load(orphan), f"the unfinished merge in {orphan.name}"
        if approved:
            message = (f"{renames.RENAME_MAP} is missing from the merged tree; "
                       f"{len(approved)} name(s) taken from {where}")
        else:
            message = (f"{renames.RENAME_MAP} is missing from the merged tree and no copy "
                       f"survives, so every page name was recomputed and published URLs may "
                       f"move; restore the file, or accept the new names with --renormalize")
        self._record("RENAME_MAP_MISSING", slug, number, path=renames.RENAME_MAP, message=message)
        return approved

    def _record(self, code: str, slug: str, number: str, path: str = "", message: str = "",
                count: int = 1) -> None:
        if self.findings is not None:
            self.findings.record(code, slug=slug, version=number, path=path, message=message,
                                 count=count)

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
