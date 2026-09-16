"""Stage 8's driver: the walk, the three checkers, and the one gate in the tool.

Shaped like `DocumentConverter` and `WorkspaceDistributor` on purpose -- the same
selection, the same "a failure is a returned outcome, never an exception", the
same counts at the end -- because the commands are read side by side. What it does
differently is the thing §7.1 asks of it: **it takes no `CatalogManager`.** The
target is the evidence. A published tree outlives the row that produced it, and a
linter that needed the catalog to agree could not check the one tree somebody most
wants checked.

Two orderings matter and both are deliberate:

- **Findings are flushed per version folder**, inside the same transaction §7.1
  gives every other stage, so a crash on folder 800 keeps the first 799.
- **The external pass runs last, once, over the whole run's deduplicated URL set.**
  A boilerplate support link appears in all 10,190 pages of the sample; checking
  it per folder would put ten thousand requests on somebody's web server to learn
  one fact.

`validate` is the only command that gates (§7.4): it exits 1 if and only if it
recorded at least one `error`, and a selection matching nothing exits 1 for the
same reason every other stage does.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from docushift.reporting.findings import Finding, FindingsRun, Severity
from docushift.sync import API_REFERENCES
from docushift.validation import artifacts, csh, links
from docushift.validation.links import FolderIndex, LinkContext, LinkReport
from docushift.validation.tree import ProductFolder, VersionFolder, tree_names, walk


@dataclass
class FolderResult:
    """What one published folder cost and what it turned up."""

    folder: VersionFolder
    findings: list[Finding] = field(default_factory=list)
    report: LinkReport = field(default_factory=LinkReport)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.ERROR)


@dataclass
class ValidationStats:
    """The run's counts, for the table the command prints."""

    products: int = 0
    folders: int = 0
    files: int = 0
    references: int = 0
    html: int = 0
    absolute: int = 0
    tree_rooted: int = 0
    fragments: int = 0
    anchors_matched: int = 0
    residue: int = 0
    external_checked: int = 0
    # Help identifiers a version lost against its predecessor (§7.6). Summed from
    # the findings' `count`, because the finding is one row per version and the
    # magnitude lives in the column.
    dropped: int = 0
    results: list[FolderResult] = field(default_factory=list)

    @property
    def unmatched_anchors(self) -> int:
        return self.fragments - self.anchors_matched


class Validator:
    """One `validate` run over one target directory."""

    def __init__(self, target: Path, findings: FindingsRun | None = None) -> None:
        self.target = target
        self.findings = findings
        self.context = LinkContext(target=target, trees=tree_names(target))

    # -- one folder ------------------------------------------------------------

    def check_folder(self, folder: VersionFolder) -> FolderResult:
        """The three checkers over one folder, in the order a reader acts in.

        `api-references/` is the exception and the reason the branch is here
        rather than inside each checker: the folders are copied Javadoc, 496 of
        499 of them ship their own frame set, and walking them would dominate the
        run's wall-clock to report defects in somebody else's generator. Their
        `metadata.yml` is still checked, because that file *is* ours (§6.2.1).
        """
        index = FolderIndex(folder.path)
        result = FolderResult(folder)
        if folder.doc_class == API_REFERENCES:
            result.findings.extend(artifacts.check(folder, index))
            return result
        result.report = links.check(folder, self.context, index)
        result.findings.extend(result.report.findings)
        result.findings.extend(artifacts.check(folder, index))
        result.findings.extend(csh.check(folder, index))
        return result

    # -- the run ---------------------------------------------------------------

    def run(
        self,
        product: str | None = None,
        version: str | None = None,
        doc_class: str | None = None,
        on_folder: Callable[[FolderResult], None] | None = None,
        fetch: links.Fetcher | None = None,
        selection: list[ProductFolder] | None = None,
    ) -> ValidationStats:
        """`selection` is the walk already done, when the caller needed it first.

        The CLI has to know whether anything matched before it opens a run -- an
        empty selection exits 1 without writing a row -- so it hands back the list
        rather than making this walk the tree a second time.
        """
        stats = ValidationStats()
        found = selection if selection is not None else walk(
            self.target, product, version, doc_class
        )
        for entry in found:
            stats.products += 1
            self._record(artifacts.check_product(entry))
            self._record(self._dropdowns(entry))
            # §7.6 is a product-level question -- it needs two version folders --
            # so it sits beside the drop-down check rather than inside the
            # per-folder pass. `validate` runs it although it can never fail on
            # it: the gate's report has to be complete, and a warning it cannot
            # gate on still belongs in it.
            regressions = csh.check_regression(entry)
            stats.dropped += sum(finding.count for finding in regressions)
            self._record(regressions)
            self._record(self._residue(entry))
            stats.residue += len(entry.residue)
            for folder in entry.versions:
                result = self.check_folder(folder)
                self._record(result.findings)
                self._absorb(stats, result)
                if on_folder is not None:
                    on_folder(result)
                # Per folder, so a crash keeps everything before it (§7.1).
                if self.findings is not None:
                    self.findings.flush()

        if fetch is not None:
            stats.external_checked = len(self.context.external)
            self._record(links.check_external(self.context.external, fetch))
            if self.findings is not None:
                self.findings.flush()
        return stats

    def selection(
        self,
        product: str | None = None,
        version: str | None = None,
        doc_class: str | None = None,
    ) -> list[ProductFolder]:
        """What a run would walk. `--dry-run`'s answer, and nothing is read."""
        return walk(self.target, product, version, doc_class)

    # -- internals -------------------------------------------------------------

    def _dropdowns(self, entry: ProductFolder) -> list[Finding]:
        """`version.yml` sits above the version folders, so it is checked here.

        Once per doc-class directory that has one, rather than once per version:
        the file describes the set, and a scoped `--version` run still reads the
        whole drop-down because that is the only way "every folder has a row" can
        be answered at all.
        """
        found: list[Finding] = []
        for name in sorted({folder.doc_class for folder in entry.versions}):
            found.extend(artifacts.check_dropdown(entry, entry.path / name))
        return found

    def _residue(self, entry: ProductFolder) -> list[Finding]:
        return [
            Finding(
                "SYNC_RESIDUE",
                slug=entry.slug,
                path=path.relative_to(self.target).as_posix(),
                message="staging folder left by a sync that did not finish",
            )
            for path in entry.residue
        ]

    def _record(self, findings: list[Finding]) -> None:
        if self.findings is None:
            return
        for finding in findings:
            self.findings.record(
                finding.code, finding.slug, finding.version, finding.path,
                finding.message, finding.count,
            )

    @staticmethod
    def _absorb(stats: ValidationStats, result: FolderResult) -> None:
        stats.folders += 1
        stats.results.append(result)
        report = result.report
        stats.files += report.files
        stats.references += report.references
        stats.html += report.html
        stats.absolute += report.absolute
        stats.tree_rooted += report.tree_rooted
        stats.fragments += report.fragments
        stats.anchors_matched += report.anchors_matched
