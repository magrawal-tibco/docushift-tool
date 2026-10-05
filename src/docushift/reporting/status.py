"""Where everything is now -- `architecture.md` §7.1, §7.2.

`status` answers one question from the catalog and `version_state`, and the
boundary §7.1 draws is load-bearing: **this module never reads the `findings`
table.** `status` and `report` were both declared in Phase 1 with overlapping help
text, and left that way they converge -- a status screen grows a "problems"
section, a report grows a progress table, and the tool ends with two commands
answering each other's question differently on the same day.

The funnel's steps nest by construction, because each one is read from what a
stage recorded rather than from the single `status` column (`StateStore.progress`).
There is **no `published` step unless the caller supplies a target directory**:
Phase 6b decided sync currency is compared and never recorded, so the database
genuinely cannot answer it, and a column that guessed would be wrong for exactly
the versions somebody had edited by hand.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from docushift.models import CONVERTIBLE_ENGINES, ReleaseStatus, SourceEngine

if TYPE_CHECKING:  # pragma: no cover - type checkers only
    from docushift.catalog import CatalogManager
    from docushift.config import ConfigManager


@dataclass
class Funnel:
    """One count per pipeline step, over the selected slice of the catalog."""

    catalogued: int = 0
    in_scope: int = 0
    not_retired: int = 0
    eligible: int = 0
    downloaded: int = 0
    extracted: int = 0
    converted: int = 0
    # Only populated with a target directory on disk. `None` means not asked,
    # which is a different answer from 0 and prints as an absent row.
    published: int | None = None
    errors: int = 0

    def rows(self) -> list[tuple[str, int, str]]:
        """`(label, count, source)` in pipeline order, for the table."""
        rows = [
            ("Catalogued", self.catalogued, "versions.csv"),
            ("In scope", self.in_scope, "scope.yaml"),
            ("Not retired", self.not_retired, "eos report"),
            ("Convert eligible", self.eligible, "versions.csv"),
            ("Downloaded", self.downloaded, "state.db"),
            ("Extracted", self.extracted, "state.db"),
            ("Converted", self.converted, "state.db"),
        ]
        if self.published is not None:
            rows.append(("Published", self.published, "target tree"))
        return rows


@dataclass
class Engines:
    """What generator each eligible version is on, and what is still undetermined."""

    counts: dict[str, int] = field(default_factory=dict)
    undetermined: list[str] = field(default_factory=list)
    unconvertible: list[str] = field(default_factory=list)

    def rows(self) -> list[tuple[str, int]]:
        return sorted(self.counts.items(), key=lambda item: (-item[1], item[0]))


# -- the per-version answer: versions.csv's four status columns (Phase 38) ----

# Pipeline order, and the word each stage's failure is reported under.
_STAGES = ("download", "extract", "convert", "reframe")
_FAILED = {"download": "download-failed", "extract": "extract-failed",
           "convert": "convert-failed", "reframe": "merge-failed"}

Events = dict[tuple[str, str], tuple[str, str]]


@dataclass(frozen=True)
class VersionStatus:
    """The four `versions.csv` columns for one version. Dates are ISO days, UTC."""

    status: str
    status_date: str = ""
    sync_status: str = ""
    sync_date: str = ""


@dataclass
class StatusEvidence:
    """Everything `version_status` reads, fetched from `state.db` once per save."""

    progress: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)
    run_dates: dict = field(default_factory=dict)
    content: dict = field(default_factory=dict)

    @classmethod
    def read(cls, state) -> "StatusEvidence":
        return cls(state.progress(), state.stage_events(), state.run_dates(), state.content_kinds())


def gate(product, version) -> str | None:
    """Which gate keeps this version out of the work, outside in (§3.7), or None.

    Shared with `funnel`, so the sheet and `docushift status` count alike.
    """
    if not product.in_scope:
        return "out-of-scope"
    if version.release_status is ReleaseStatus.RETIRED:
        return "retired"
    if not version.convert_eligible:
        return "not-selected"
    return None


def _day(stamp: str | None) -> str:
    return (stamp or "")[:10]


def _built(events: Events, runs: dict[str, str], stage: str) -> str:
    """When the stage last succeeded: its event, else the start of the run that built it."""
    ok = events.get((stage, "ok"))
    return ok[0] if ok else (runs.get(stage) or "")


def _current_failure(events: Events, stage: str) -> str | None:
    """The failure's time when the stage's last attempt failed, else None."""
    failed, ok = events.get((stage, "failed")), events.get((stage, "ok"))
    if failed and (not ok or failed[0] >= ok[0]):
        return failed[0]
    return None


def version_status(product, version, evidence: StatusEvidence) -> VersionStatus:
    """Where one version stands, and when it got there.

    A gate wins. Otherwise a failure at a stage beyond the furthest one that
    succeeded, otherwise that furthest stage. Success is read from what each stage
    left behind (`StateStore.progress`, `_reframed_md_files`), the same evidence as
    the funnel; `stage_event` supplies the dates and the failures.
    """
    key = (product.slug, version.version)
    events: Events = evidence.events.get(key, {})
    runs: dict[str, str] = evidence.run_dates.get(key, {})
    recorded = evidence.progress.get(key) or {}
    topics, documents = evidence.content.get(key, (0, 0))
    # Phase 39: unpacked, nothing the tool converts, and nothing but documents in the
    # package. Not stuck -- there is no HTML help to convert.
    pdf_only = (
        bool(recorded.get("extracted")) and not recorded.get("converted")
        and version.engine not in CONVERTIBLE_ENGINES and not topics and documents > 0
    )
    sync_status, sync_date = _sync(events, runs, pdf_only)

    blocked = gate(product, version)
    if blocked:
        return VersionStatus(blocked, "", sync_status, sync_date)

    if recorded.get("converted") and version.reframed_md_files is not None:
        furthest, status = "reframe", "merged"
    elif recorded.get("converted"):
        furthest, status = "convert", "converted"
    elif recorded.get("extracted"):
        furthest = "extract"
        status = ("extracted" if version.engine in CONVERTIBLE_ENGINES
                  else "pdf-only" if pdf_only else "format-unknown")
    elif recorded.get("downloaded"):
        furthest, status = "download", "downloaded"
    else:
        furthest, status = None, "not-started"

    date = (_built(events, runs, furthest) or recorded.get("updated_at")) if furthest else ""

    beyond = _STAGES[_STAGES.index(furthest) + 1:] if furthest else _STAGES
    failures = [(at, stage) for stage in beyond if (at := _current_failure(events, stage))]
    if failures:
        at, stage = max(failures)
        status, date = _FAILED[stage], at
    elif recorded.get("error") and not any(outcome == "failed" for _, outcome in events):
        # Recorded before `stage_event` existed: `version_state` holds the error but
        # not its stage, so the stage is the one after the furthest evidence.
        legacy = {None: "download", "download": "extract", "extract": "convert"}.get(furthest)
        if legacy and not (legacy == "convert" and status in ("format-unknown", "pdf-only")):
            status, date = _FAILED[legacy], recorded.get("updated_at")

    return VersionStatus(status, _day(date), sync_status, sync_date)


def _sync(events: Events, runs: dict[str, str], pdf_only: bool = False) -> tuple[str, str]:
    """`_sync_status` and `_sync_date`: this tool's own placements, never the target.

    A converted version is placed when its help is (`sync`); a PDF-only one when its
    documents are (`sync-docs`, Phase 39), and is rebuilt by a re-extract rather than
    a re-convert, because that is where its PDFs come from.
    """
    failed_at = _current_failure(events, "sync")
    if failed_at:
        return "sync-failed", _day(failed_at)
    placed = events.get(("sync-docs" if pdf_only else "sync", "ok"))
    if not placed:
        return "", ""
    if pdf_only:
        rebuilt = _built(events, runs, "extract")
    else:
        rebuilt = max(_built(events, runs, "convert"), _built(events, runs, "reframe"))
    return ("out-of-date" if rebuilt > placed[0] else "synced"), _day(placed[0])


def funnel(
    catalog: "CatalogManager",
    bu: str | None = None,
    family: str | None = None,
    published: dict[str, int] | None = None,
) -> Funnel:
    """The pipeline's counts over one slice of the catalog.

    `eligible_only=False`, deliberately: an out-of-scope or retired version is
    absent from the *work* and never from the *books* (§3.10), and the whole point
    of the first four rows is to show what each gate costs.
    """
    result = Funnel()
    progress = catalog.state.progress() if catalog.state is not None else {}

    for product, version in catalog.iter_versions(bu=bu, family=family):
        result.catalogued += 1
        blocked = gate(product, version)
        if blocked == "out-of-scope":
            continue
        result.in_scope += 1
        if blocked == "retired":
            continue
        result.not_retired += 1
        if blocked == "not-selected":
            continue
        result.eligible += 1

        recorded = progress.get((product.slug, version.version))
        if recorded is None:
            continue
        result.downloaded += bool(recorded["downloaded"])
        result.extracted += bool(recorded["extracted"])
        result.converted += bool(recorded["converted"])
        result.errors += bool(recorded["error"])

    if published is not None:
        result.published = sum(published.values())
    return result


def engines(catalog: "CatalogManager", bu: str | None = None, family: str | None = None) -> Engines:
    """Engine resolution over the eligible population, with both gaps named.

    Two lists rather than one, because they are different decisions: `auto` is a
    detector that has not run or has not matched, and a named engine with no
    handler is a scoping call for a human (`design.md` invariant 7). Collapsing
    them into "not converting" is what makes a detector regression invisible.
    """
    result = Engines()
    for product, version in catalog.iter_versions(bu=bu, family=family, eligible_only=True):
        name = str(version.engine)
        result.counts[name] = result.counts.get(name, 0) + 1
        who = f"{product.slug}@{version.version}"
        if version.engine is SourceEngine.AUTO:
            result.undetermined.append(who)
        elif version.engine not in CONVERTIBLE_ENGINES:
            result.unconvertible.append(who)
    return result


def published_counts(
    config: "ConfigManager",
    catalog: "CatalogManager",
    target: Path,
    bu: str | None = None,
    family: str | None = None,
) -> dict[str, int]:
    """Version folders present in the target tree, per product. Counted from disk.

    §7.2's rule made concrete: about the target, the disk is the evidence and the
    database is a memory. This is the same direction 6b's drop-down assembly takes
    (§6.6) -- read the doc-class directory and believe it.
    """
    from docushift.sync import ONLINE_HELP, WorkspaceDistributor

    distributor = WorkspaceDistributor(config, catalog)
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for product, _version in catalog.iter_versions(bu=bu, family=family, eligible_only=True):
        if product.slug in seen:
            continue
        seen.add(product.slug)
        folder = distributor.doc_class_dir(product, target, ONLINE_HELP)
        if not folder.is_dir():
            continue
        placed = sum(1 for child in folder.iterdir() if child.is_dir())
        if placed:
            counts[product.slug] = placed
    return counts
