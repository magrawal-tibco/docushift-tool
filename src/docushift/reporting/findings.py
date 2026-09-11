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
    Code("METADATA_MISMATCH", Severity.WARNING, Stage.SYNC,
         "SuiteHelp publication-title / release-date disagreeing with the catalog",
         "planning.md Phase 6 contract"),
    Code("ARCHIVE_ALSO_LIVE", Severity.NOTE, Stage.SYNC,
         "Archived version that is also live, cross-linked", "architecture.md §6.2.3"),
    Code("LINK_BROKEN", Severity.ERROR, Stage.VALIDATE,
         "Relative link resolving to nothing", "design.md §8.4"),
    Code("CSH_IDENTIFIER_DROPPED", Severity.WARNING, Stage.VALIDATE,
         "Present in the prior version, absent here", "planning.md §7.6"),
)

# Codes the built code paths can actually emit. Named rather than inferred, so the
# reachability test reports a shrinking list of debts instead of asserting
# something already true. 5b adds the nine the Flare engine raises, which is what
# closes Stage 5's side of the register: every remaining unreachable code belongs
# to `sync` or `validate`, neither of which is written.
REACHABLE_IN_PHASE_5A = frozenset(
    {"ENGINE_UNKNOWN", "REFERENCE_UNRESOLVED", "ASSET_ORPHANED", "CSH_UNRESOLVED",
     "CSH_AMBIGUOUS", "DOCSET_SKIPPED"}
)
REACHABLE_IN_PHASE_5B = REACHABLE_IN_PHASE_5A | {
    "NAV_NODE_DROPPED", "OUTPUT_ROOT_MISSING", "CONTENT_MISSING", "TOC_ORPHAN",
    "TOPIC_LINK_DANGLING", "ALERT_LABEL_UNMAPPED", "LANDING_PAGE_EMPTY",
    "TAIL_PAGE_MISSING", "LOCALIZED_TREE_SKIPPED",
}


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
