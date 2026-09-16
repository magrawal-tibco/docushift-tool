"""The findings register: every deferred "report line" in the design, given a code.

Implements `docs/planning.md` §7.1, §7.2 and §7.5. Three rules carry the whole
design, and each of them is a rule about where a decision is *not* made:

- **`code` is the contract; `message` is prose.** Tests assert on codes, so a
  message can be reworded freely and an obligation that existed only as an English
  sentence becomes an enumerable thing.
- **Severity belongs to the code, not to the call site.** It is fixed once, in
  `REGISTRY` below. Two call sites reporting one condition at two severities would
  make the exit code depend on which of them fired.
- **Errors and warnings get a row each; notes are aggregated with a `count`.** You
  act on an error individually and only need the magnitude of a note -- and a
  per-file note would write hundreds of thousands of rows for `ASSET_ORPHANED`
  alone, which is 54.6% of Flare's images by design of the authoring tool.

The module is deliberately small and knows nothing about any stage. It was owed at
the start of Phase 4 (§7.7) and arrived in Phase 5a; the cost of that slip is
recorded in §7.7 rather than tidied away.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from docushift.state import StateStore


class Severity(StrEnum):
    """`planning.md` §7.2. Only `validate` gates, and only on `ERROR`."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


class Stage(StrEnum):
    """Which command discovers the condition. Not which one reports it."""

    CATALOG = "catalog"
    DOWNLOAD = "download"
    EXTRACT = "extract"
    CONVERT = "convert"
    SYNC = "sync"
    VALIDATE = "validate"


@dataclass(frozen=True)
class Code:
    """One row of the §7.5 register."""

    code: str
    severity: Severity
    stage: Stage
    obligation: str
    # Where the promise was made. Kept so `report --explain` can cite the spec
    # rather than paraphrase it.
    specified_in: str


def _codes(*rows: Code) -> dict[str, Code]:
    registry: dict[str, Code] = {}
    for row in rows:
        if row.code in registry:  # pragma: no cover - a typo caught at import time
            raise ValueError(f"Duplicate finding code: {row.code}")
        registry[row.code] = row
    return registry


# The §7.5 register, in full, on the first commit that has a table to put it in.
# All twenty rows are here although Phase 5a can only reach three of them: the
# register is the deliverable, and a half-populated one cannot be audited. The
# test that asserts "every emitted code is registered and every registered code is
# reachable" names the unreachable ones rather than failing, so this stays a
# visible to-do list instead of a silent one.
REGISTRY: dict[str, Code] = _codes(
    Code("SCOPE_RULE_UNMATCHED", Severity.WARNING, Stage.CATALOG,
         "A scope.yaml rule matching no product", "design.md §8.2.5"),
    Code("EOS_ALIAS_STALE", Severity.WARNING, Stage.CATALOG,
         "An alias naming a product the active report lacks", "design.md §8.2"),
    Code("EOS_PRODUCT_EMPTIED", Severity.WARNING, Stage.CATALOG,
         "Retirement left a product with nothing to convert", "planning.md Phase 3.7"),
    Code("BATCH_NOT_ELIGIBLE", Severity.WARNING, Stage.CATALOG,
         "Tagged into a batch but not eligible", "design.md §8.2.2"),
    Code("CSH_SOURCE_EMPTY", Severity.NOTE, Stage.EXTRACT,
         "CSH source present but empty -- no csh.yml written", "architecture.md §5.4.2"),
    Code("CSH_SOURCE_UNPARSED", Severity.WARNING, Stage.EXTRACT,
         "Source located but failed to parse; _has_csh still set", "design.md §6.2"),
    Code("ENGINE_UNKNOWN", Severity.WARNING, Stage.CONVERT,
         "auto, or a named engine with no handler -- skipped, not guessed",
         "design.md invariant 7"),
    Code("DOCSET_SKIPPED", Severity.WARNING, Stage.CONVERT,
         "A file-named doc-set reaching the engine guard", "architecture.md §5.2"),
    Code("NAV_NODE_DROPPED", Severity.NOTE, Stage.CONVERT,
         "A navigation node with no page and no children -- DITA's lof/lot/ix, "
         "Flare's childless headless node and its same-page child",
         "planning.md Phase 5"),
    Code("OUTPUT_ROOT_MISSING", Severity.WARNING, Stage.CONVERT,
         "Engine detected and no unit of work found -- a partial output",
         "architecture.md §5.1.1"),
    Code("CONTENT_MISSING", Severity.WARNING, Stage.CONVERT,
         "A topic with no content container -- not converted, never guessed at",
         "architecture.md §5.1.6"),
    Code("TOC_ORPHAN", Severity.NOTE, Stage.CONVERT,
         "Converted topics in no TOC entry, filed under Unfiled -- 14.1% for Flare",
         "architecture.md §5.1.4"),
    Code("TOPIC_LINK_DANGLING", Severity.NOTE, Stage.CONVERT,
         "A cross-reference to a topic this run did not produce; text kept, link dropped",
         "architecture.md §5.1.3"),
    Code("ALERT_LABEL_UNMAPPED", Severity.WARNING, Stage.CONVERT,
         "An admonition label outside the five GitHub renders; rendered as NOTE",
         "transforms/callouts.py"),
    Code("LANDING_PAGE_EMPTY", Severity.NOTE, Stage.CONVERT,
         "A landing page with nothing past its hero -- a stub was generated",
         "architecture.md §5.1.5"),
    Code("TAIL_PAGE_MISSING", Severity.WARNING, Stage.CONVERT,
         "No support or no legal page in the TOC -- nothing is synthesized",
         "architecture.md §5.1.5"),
    Code("LOCALIZED_TREE_SKIPPED", Severity.NOTE, Stage.CONVERT,
         "A localized subtree inside an English unit, not converted",
         "architecture.md §5.1.9"),
    Code("ASSET_ORPHANED", Severity.NOTE, Stage.CONVERT,
         "Unreferenced asset -- 54.6% is normal for Flare", "architecture.md §5.5.7"),
    Code("REFERENCE_UNRESOLVED", Severity.ERROR, Stage.CONVERT,
         "A reference producing neither link nor copy", "design.md invariant 13"),
    Code("CSH_UNRESOLVED", Severity.WARNING, Stage.CONVERT,
         "Identifier matched no produced topic", "planning.md Phase 6 contract"),
    Code("CSH_AMBIGUOUS", Severity.NOTE, Stage.CONVERT,
         "Identifier claimed by 2+ doc-sets; first ordered doc-set wins",
         "planning.md Phase 6 contract"),
    Code("DOC_REFERENCE_MISSING", Severity.WARNING, Stage.SYNC,
         "Escape pointing at a document the ZIP never shipped", "architecture.md §5.5.8"),
    Code("VERSION_NOT_NUMERIC", Severity.WARNING, Stage.SYNC,
         "Non-numeric version string sorted last in version.yml",
         "planning.md Phase 6 contract"),
    Code("VERSION_UNDATED", Severity.NOTE, Stage.SYNC,
         "Active version with no release_date; title loses its bracket",
         "planning.md Phase 6 contract"),
    # CONVERT rather than SYNC, corrected in 6a: the homepage figures live in
    # `Unit.metadata`, which exists only while the engine's unit is in hand, so
    # conversion is the stage that *discovers* the disagreement even though the
    # keys it used to feed belong to sync's `metadata.yml`.
    Code("METADATA_MISMATCH", Severity.WARNING, Stage.CONVERT,
         "SuiteHelp release-version / release-date disagreeing with the catalog",
         "planning.md Phase 6 contract"),
    # 6c's one new code, and the only one this phase needed. A note rather than a
    # warning: the file is published and titled from its filename, so nothing is
    # lost -- but a damaged deliverable that nobody names is shipped silently. It
    # earns a code by being rare: 7 of the corpus's 5,007 PDFs, in 4 filenames. A
    # *blank* `/Title` is deliberately not reported at all; 27.9% of the corpus is
    # blank, and a note firing 1,396 times describes the corpus, not a defect.
    Code("DOCUMENT_UNREADABLE", Severity.NOTE, Stage.SYNC,
         "PDF whose Info dictionary would not parse; titled from its filename",
         "design.md §10.5"),
    # 6d's one new code, and the first one whose condition is a *configuration*
    # rather than a document. Raised once per product that places an api-reference
    # tree while `publish_base_url` is empty: the copy is published, but the help
    # topics that point into it keep relative links that cannot span two
    # repositories. A warning rather than an error because empty is the shipped,
    # supported state -- the AEM host is not known yet -- and rather than a note
    # because it is a human decision pending, not a property of the corpus.
    Code("PUBLISH_BASE_URL_UNSET", Severity.WARNING, Stage.SYNC,
         "api-references placed with no publish_base_url; cross-tree links have no host",
         "architecture.md §6.4"),
    # 6e's one new code, and a note for the reason 6c's is: nobody acts on one
    # rewritten link and everybody wants the magnitude. Notes aggregate into a
    # single row with a count (§7.1), which is the shape this needs -- because the
    # failure it guards against is silent. A version with an API tree and **zero**
    # rewritten links is either a product whose help genuinely never references its
    # API (8 of the 49 in-scope versions) or a predicate that stopped matching, and
    # a count of 0 is the only thing that tells those apart.
    Code("API_LINK_REWRITTEN", Severity.NOTE, Stage.CONVERT,
         "Link into an api-reference tree pointed at its published -resources URL",
         "design.md §10.7"),
    Code("LINK_BROKEN", Severity.ERROR, Stage.VALIDATE,
         "Relative link resolving to nothing", "design.md §8.4"),
    Code("CSH_IDENTIFIER_DROPPED", Severity.WARNING, Stage.VALIDATE,
         "Present in the prior version, absent here", "planning.md §7.6"),
)

# The register's remaining debt, stated as the *complement* of what is written.
#
# Through Phase 6e this was an eight-deep chain of `REACHABLE_IN_PHASE_*` unions,
# one per sub-phase, each naming what its predecessor could reach plus what it
# added. That shape had two faults. It grew a constant per phase while answering
# one question, and it was asserted as a **subset** -- so a code that quietly
# started being emitted never showed up, and the list could only ever overstate
# the debt. Phase 7a replaces the chain with one frozenset asserted **equal**: a
# code that starts firing fails the test until it is removed from here, and a code
# that stops firing fails it until it is added back.
#
# Three left, and all three belong to commands that are not written: `LINK_BROKEN`
# and `CSH_IDENTIFIER_DROPPED` to `validate` (Phase 7b), `DOC_REFERENCE_MISSING`
# to the document router's escape check (Phase 7c). Before 7a there were nine,
# four of them in stages -- `catalog fetch`, `catalog eos`, `extract` -- that
# computed their findings, printed them, and opened no run to record them in.
#
# The count was briefly believed to be twenty, and how that happened is the reason
# the companion test scans for a quoted literal rather than for a call: the earlier
# count came from grepping `record("CODE"`, which misses every continuation-line
# and every variable call site. The scan that replaces it proves a code is
# *written*, not that it fires -- which is a real limit, and why this set is
# curated by hand rather than derived.
NOT_YET_EMITTED = frozenset(
    {"LINK_BROKEN", "CSH_IDENTIFIER_DROPPED", "DOC_REFERENCE_MISSING"}
)


class UnregisteredCode(KeyError):
    """Raised at the call site, which is the only place that can fix it.

    The one condition in this module that *is* an exception rather than a finding:
    an unregistered code is a programming error, and reporting it as a finding
    would need a code of its own.
    """


@dataclass
class Finding:
    """One row, before it reaches `state.db`."""

    code: str
    slug: str = ""
    version: str = ""
    path: str = ""
    message: str = ""
    count: int = 1

    @property
    def registered(self) -> Code:
        return REGISTRY[self.code]

    @property
    def severity(self) -> Severity:
        return self.registered.severity

    @property
    def stage(self) -> Stage:
        return self.registered.stage

    def row(self) -> tuple[str, str, str, str, str, str, str, int]:
        """The tuple `StateStore.record_findings` takes."""
        return (
            str(self.stage), str(self.severity), self.code,
            self.slug, self.version, self.path, self.message, self.count,
        )


@dataclass
class FindingsRun:
    """Buffers findings for one command run and flushes them to `state.db`.

    Buffered rather than written straight through, because §7.1 requires findings
    to land inside the stage's existing transaction: the caller flushes once per
    version, so a crash on version 200 keeps the first 199 and loses only the
    partial one. A run with no store buffers and never flushes, which is what lets
    a `--dry-run` and a unit test exercise the same code path.
    """

    command: str
    batch: str = ""
    store: "StateStore | None" = None
    run_id: int = 0
    pending: list[Finding] = field(default_factory=list)
    # Notes are folded on the way in, so the buffer cannot grow to one row per
    # orphaned image. Keyed on the aggregation identity, not on the message.
    _notes: dict[tuple[str, str, str], Finding] = field(default_factory=dict)
    recorded: list[Finding] = field(default_factory=list)

    def start(self) -> "FindingsRun":
        if self.store is not None and not self.run_id:
            self.run_id = self.store.start_run(self.command, self.batch)
        return self

    def record(
        self,
        code: str,
        slug: str = "",
        version: str = "",
        path: str = "",
        message: str = "",
        count: int = 1,
    ) -> Finding:
        """Records one finding. Severity comes from the registry, never from here."""
        if code not in REGISTRY:
            raise UnregisteredCode(
                f"{code} is not in the §7.5 register; add it to REGISTRY with a severity"
            )
        finding = Finding(code, slug, version, path, message, count)
        if finding.severity is Severity.NOTE:
            key = (code, slug, version)
            existing = self._notes.get(key)
            if existing is not None:
                existing.count += count
                # The first message stands. A note's prose describes the class of
                # thing, and the count is what the reader acts on.
                return existing
            self._notes[key] = finding
        self.pending.append(finding)
        return finding

    def flush(self) -> None:
        """Writes the buffer. Called by the stage, inside its own transaction."""
        if not self.pending:
            return
        if self.store is not None and self.run_id:
            self.store.record_findings(self.run_id, [f.row() for f in self.pending])
        self.recorded.extend(self.pending)
        self.pending.clear()
        self._notes.clear()

    def finish(self, exit_code: int = 0) -> None:
        self.flush()
        if self.store is not None and self.run_id:
            self.store.finish_run(self.run_id, exit_code)

    # -- reading back ---------------------------------------------------------

    @property
    def all(self) -> list[Finding]:
        """Everything recorded this run, flushed or not, in record order."""
        return [*self.recorded, *self.pending]

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.all if f.severity is severity]

    def counts(self) -> dict[Severity, int]:
        """Rows per severity -- notes counted as rows, not as occurrences.

        The magnitude of a note lives in its `count` column; what a summary line
        needs is how many distinct things were noted.
        """
        tally = {severity: 0 for severity in Severity}
        for finding in self.all:
            tally[finding.severity] += 1
        return tally

    def summary(self) -> str:
        """One line for the end of a run report. Empty when there is nothing to say."""
        tally = self.counts()
        parts = [
            f"{tally[severity]} {severity}{'s' if tally[severity] != 1 else ''}"
            for severity in Severity if tally[severity]
        ]
        return ", ".join(parts)

    def __iter__(self) -> Iterator[Finding]:
        return iter(self.all)


def unreachable_codes(emitted: Iterable[str]) -> list[str]:
    """Registered codes that no supplied code path reaches. For the §7.5 test."""
    return sorted(set(REGISTRY) - set(emitted))
