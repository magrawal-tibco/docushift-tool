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
        if not product.in_scope:
            continue
        result.in_scope += 1
        if version.release_status is ReleaseStatus.RETIRED:
            continue
        result.not_retired += 1
        if not version.convert_eligible:
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
