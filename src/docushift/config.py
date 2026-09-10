"""Configuration and taxonomy manager for DocuShift.

Also the single owner of the **families workspace** path contract
(docs/architecture.md §4): every downloaded ZIP and extracted tree lives under
`families/{locale}-{bu}-{family}/`. Deriving those paths in one place is what lets
Stage 3, Stage 4, and Stage 5 agree on where a package is without passing paths
between them -- `state.db` records the resolved path per version, but the layout
itself is computed here.
"""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from docushift.models import FamilySource, ReleaseStatus
from docushift.utils.slug import family_folder, slugify

# Every folder name is locale-prefixed because the predecessor `html-to-md` project
# publishes `fr-fr` and `ja-jp` trees alongside `en-us`. Nothing in the pipeline is
# multi-locale yet; the prefix reserves the shape so adding one is not a rename of
# every folder on disk.
DEFAULT_LOCALE = "en-us"

# The end-of-support report writes `12-31-2025`, and it is unambiguously
# month-first: field one never exceeds 12 across all 5,948 rows while field two
# reaches 31 in 5,134 of them. Parsed with one explicit format rather than through
# `csvio.normalize_date`, whose permissive list tries `%d-%m-%Y` and would read
# `03-04-2021` as 3 April instead of 4 March -- silently, and only for the third of
# rows where both fields are 12 or under.
_EOS_DATE_FORMAT = "%m-%d-%Y"

# The report's `Release Status` spellings, mapped to the enum. Anything else is a
# new value from support and is reported rather than guessed at.
_EOS_STATUS_TOKENS = {
    "retired": ReleaseStatus.RETIRED,
    "retirement announced": ReleaseStatus.RETIREMENT_ANNOUNCED,
    "ga": ReleaseStatus.GA,
}


@dataclass
class EosReport:
    """The active end-of-support report, resolved against `config/eos.yaml`.

    `entries` is keyed by the **slug the report name resolves to**, so a caller
    joins it with a dict hit on `product.slug` and never runs a name match of its
    own. Names that already slugify to a catalog slug resolve to themselves; the
    rest resolve only through a reviewed alias.

    Note the keys are *candidate* slugs: this class has no catalog to check them
    against, and 277 of the report's 528 names name products the catalog does not
    carry at all. An entry for an unknown slug is simply never looked up.
    """
    entries: dict[str, dict[str, tuple[ReleaseStatus, str]]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    # Every product name the report carries a usable row for. Deliberately not
    # paired with a "resolved" set: slugifying a name always yields *something*, so
    # a count computed here would read 528 of 528 whatever the catalog holds. How
    # many of these name a real product is a question only the catalog can answer,
    # and `CatalogManager.eos_coverage()` answers it.
    report_names: set[str] = field(default_factory=set)
    # Statuses the report used that this tool has no enum value for.
    unknown_statuses: list[str] = field(default_factory=list)

    @property
    def unmatched_aliases(self) -> list[str]:
        """Aliases naming a product the active report does not mention.

        The rename detector, and the exact analogue of `unmatched_scope_rules()`:
        the day support renames a product in the report is the day that alias
        stops retiring anything, and silence is indistinguishable from success.
        """
        return sorted(name for name in self.aliases if name not in self.report_names)

    def status_for(self, slug: str, version: str) -> tuple[ReleaseStatus, str] | None:
        """The report's verdict on one version, or `None` if it carries no row.

        Version matching is **exact string equality**, deliberately. Of the 456
        versions whose product the report covers but whose own number it does not
        carry, trailing-`.0` coercion would resolve exactly one -- in exchange for
        reintroducing the `1.10` -> `1.1` hazard the CSV layer exists to prevent.
        """
        return self.entries.get(slug, {}).get(version)


def _parse_eos_date(value: object) -> str:
    """Reads the report's `MM-DD-YYYY` date as ISO, passing anything else through.

    Deliberately not `csvio.normalize_date` -- see `_EOS_DATE_FORMAT`. A value that
    does not match is returned verbatim rather than dropped: the date is
    documentation on the row, and a format change from support should be visible
    in the sheet, not silently blanked.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.strptime(text, _EOS_DATE_FORMAT).date().isoformat()
    except ValueError:
        return text


class ConfigManager:
    """Manages project paths, taxonomy definitions, and configuration files."""

    def __init__(self, root_dir: Path | None = None, locale: str = DEFAULT_LOCALE):
        self.root_dir = root_dir or Path(os.getcwd())
        self.locale = locale
        self.config_dir = self.root_dir / "config"
        self.cache_dir = self.root_dir / "cache"
        self.families_dir = self.root_dir / "families"
        self.output_dir = self.root_dir / "output"
        self.taxonomy_path = self.config_dir / "taxonomy.yaml"
        self.docsite_path = self.config_dir / "docsite.yaml"
        self.scope_path = self.config_dir / "scope.yaml"
        self.eos_path = self.config_dir / "eos.yaml"
        self.aem_templates_dir = self.config_dir / "aem_templates"
        self.products_path = self.config_dir / "products.csv"
        self.versions_path = self.config_dir / "versions.csv"
        self.state_db_path = self.cache_dir / "state.db"

        # Ensure directories exist. Per-family subfolders are created on demand by
        # the downloader, not up front -- pre-creating a folder for all ~12 declared
        # families would make an empty workspace look like a started migration.
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.families_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._taxonomy_cache: dict[str, Any] | None = None
        self._docsite_cache: dict[str, Any] | None = None
        self._scope_cache: dict[str, str] | None = None
        self._eos_cache: EosReport | None = None

    # -- families workspace layout -------------------------------------------

    def family_folder_name(self, bu: str, family: str) -> str:
        """The folder name for one family, e.g. `en-us-tibco-data-management`."""
        return family_folder(self.locale, bu, family)

    def family_dir(self, bu: str, family: str) -> Path:
        """`families/en-us-<bu>-<family>/` -- the root of one family's working set."""
        return self.families_dir / self.family_folder_name(bu, family)

    def downloads_dir(self, bu: str, family: str) -> Path:
        """Where a family's ZIPs land. Split from `extracted/` so that clearing
        every ZIP after a successful extract is one `rmtree`, not a glob."""
        return self.family_dir(bu, family) / "downloads"

    def extracted_dir(self, bu: str, family: str) -> Path:
        """Where a family's unpacked packages land."""
        return self.family_dir(bu, family) / "extracted"

    def archive_dir(self, bu: str, family: str) -> Path:
        """Where `docushift archive download` puts on-demand archived-version ZIPs.

        Deliberately outside `downloads/`, which the pipeline treats as its own
        working set: an archived ZIP pulled for reference must not look to Stage 4
        like a package awaiting extraction.
        """
        return self.family_dir(bu, family) / "archive"

    def download_path(self, bu: str, family: str, slug: str, version: str) -> Path:
        """The ZIP path for one version: `.../downloads/<slug>-<version>.zip`.

        Named from the catalog key rather than from the remote filename, because the
        docsite's own names collide across versions and are not derivable in reverse.

        The key is the slug, not `product_code`, because the code is not unique:
        nine of the ten shared codes are shared by products in the *same* family, so
        a code-named ZIP would land two different products' packages on top of each
        other in one directory.
        """
        return self.downloads_dir(bu, family) / f"{slug}-{version}.zip"

    def extract_path(self, bu: str, family: str, slug: str, version: str) -> Path:
        """The extracted tree for one version: `.../extracted/<slug>/<version>/`.

        The version keeps its dots here. `html-to-md` writes `6-2-3` in *published*
        paths, but this is a working directory keyed by the catalog, and a dotted
        segment round-trips back to a `versions.csv` key unambiguously where a
        dashed one does not (`6-2-3` could be `6.2.3` or `6-2.3`). The dots-to-dashes
        conversion belongs at Stage 6, where the AEM output path is built.
        """
        return self.extracted_dir(bu, family) / slug / version

    def load_taxonomy(self) -> dict[str, Any]:
        """Loads and caches taxonomy rules from taxonomy.yaml."""
        if self._taxonomy_cache is not None:
            return self._taxonomy_cache

        if not self.taxonomy_path.exists():
            self._taxonomy_cache = {"business_units": {}, "rules": []}
            return self._taxonomy_cache

        with open(self.taxonomy_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        loaded.setdefault("business_units", {})
        loaded.setdefault("rules", [])
        self._taxonomy_cache = loaded
        return self._taxonomy_cache

    def load_docsite(self) -> dict[str, Any]:
        """Loads and caches docsite discovery endpoints from docsite.yaml."""
        if self._docsite_cache is not None:
            return self._docsite_cache

        if not self.docsite_path.exists():
            self._docsite_cache = {}
            return self._docsite_cache

        with open(self.docsite_path, encoding="utf-8") as f:
            self._docsite_cache = yaml.safe_load(f) or {}
        return self._docsite_cache

    def load_scope(self) -> dict[str, str]:
        """Loads `scope.yaml` as `{docsite_slug: reason}` -- docs/architecture.md §3.10.

        The returned mapping is looked up by **exact slug** at merge time. It is a
        dict rather than a list precisely so no caller can be tempted into a
        substring test: `ebx` matches `tibco-businessconnect-ebxml-protocol`, and
        `spotfire` matches sixteen products that are in scope.

        A missing file yields an empty mapping -- no exclusions -- rather than an
        error, so a fresh checkout works. A **duplicate slug raises**: two entries
        for one product mean two different reasons were recorded and one is about
        to be silently discarded, which is the sort of thing this file exists to
        make visible.
        """
        if self._scope_cache is not None:
            return self._scope_cache

        rules: dict[str, str] = {}
        if not self.scope_path.exists():
            self._scope_cache = rules
            return rules

        with open(self.scope_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}

        for entry in loaded.get("out_of_scope") or []:
            # A bare string is accepted as a slug with no reason: the list is
            # hand-edited, and rejecting the terser form would be pedantry.
            if isinstance(entry, str):
                slug, reason = entry.strip().lower(), ""
            else:
                slug = str(entry.get("slug", "")).strip().lower()
                reason = str(entry.get("reason", "")).strip()
            if not slug:
                continue
            if slug in rules:
                raise ValueError(f"{self.scope_path}: duplicate out_of_scope slug '{slug}'")
            rules[slug] = reason

        self._scope_cache = rules
        return rules

    def load_eos(self) -> EosReport:
        """Loads `eos.yaml` and the report it names -- docs/architecture.md §3.11.

        Two files, because they have two different authors. The CSV is support's,
        arrives periodically and is never hand-edited; the YAML is ours, and holds
        the one thing the CSV cannot supply -- how its product *names* map to
        catalog *slugs*, given that it carries no slug and no code.

        A missing `eos.yaml` yields an empty report -- no retirements -- rather
        than an error, so a fresh checkout works. Everything else raises, on the
        same reasoning `load_scope()` uses: a duplicate alias, an alias with no
        slug, or a `report:` naming a file that is not there are all cases where
        continuing would quietly retire the wrong set of rows.
        """
        if self._eos_cache is not None:
            return self._eos_cache

        report = EosReport()
        if not self.eos_path.exists():
            self._eos_cache = report
            return report

        with open(self.eos_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}

        for entry in loaded.get("aliases") or []:
            name = str(entry.get("report_name", "")).strip()
            slug = str(entry.get("slug", "")).strip().lower()
            if not name:
                continue
            if not slug:
                raise ValueError(f"{self.eos_path}: alias '{name}' has no slug")
            if name in report.aliases:
                raise ValueError(f"{self.eos_path}: duplicate alias report_name '{name}'")
            report.aliases[name] = slug

        report_ref = str(loaded.get("report", "")).strip()
        if not report_ref:
            self._eos_cache = report
            return report

        report_path = self.config_dir / report_ref
        if not report_path.exists():
            raise ValueError(f"{self.eos_path}: report '{report_ref}' not found at {report_path}")

        self._read_eos_report(report_path, report)
        self._eos_cache = report
        return report

    def _read_eos_report(self, path: Path, report: EosReport) -> None:
        """Parses the support CSV into `report`, keyed by resolved slug.

        Read with `utf-8-sig`: the report ships a BOM, and its header line ends in
        a trailing comma, which `DictReader` renders as a `None` key. Both are
        support's format rather than damage, so neither is worth complaining
        about -- the named columns are read and the rest ignored.

        The report is self-consistent (0 conflicting statuses over 5,948 rows), so
        a repeated `(name, version)` is a harmless duplicate and last-wins is safe.
        A *conflict* is not: two report names resolving to one slug and disagreeing
        about a version means an alias is wrong, and picking one silently is how
        that stays invisible.
        """
        seen_unknown: set[str] = set()
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("Product Name") or "").strip()
                version = (row.get("Version") or "").strip()
                if not name or not version:
                    continue
                report.report_names.add(name)

                token = (row.get("Release Status") or "").strip().lower()
                status = _EOS_STATUS_TOKENS.get(token)
                if status is None:
                    if token and token not in seen_unknown:
                        seen_unknown.add(token)
                        report.unknown_statuses.append(token)
                    continue

                # An alias wins over the slugified name, so a reviewed decision can
                # correct a name that happens to slugify onto the wrong product.
                slug = report.aliases.get(name) or slugify(name)
                if not slug:
                    continue

                retired_on = _parse_eos_date(row.get("Retirement Date"))
                existing = report.entries.setdefault(slug, {}).get(version)
                if existing is not None and existing[0] is not status:
                    raise ValueError(
                        f"{path.name}: '{name}' and another report name both resolve to slug '{slug}' "
                        f"and disagree about version {version} ({existing[0]} vs {status}). "
                        f"Fix the alias in {self.eos_path.name}."
                    )
                report.entries[slug][version] = (status, retired_on)

    def families(self, bu: str) -> dict[str, Any]:
        """The family definitions declared for one business unit."""
        return self.load_taxonomy()["business_units"].get(bu, {}).get("families", {})

    def is_known_family(self, bu: str, family: str) -> bool:
        return family in self.families(bu)

    def resolve_product_info(self, product_code: str, product_name: str = "") -> dict[str, Any]:
        """Infers `bu` and `family` for a product from the taxonomy keyword rules.

        Returns `family_source` alongside them so the caller can record provenance.
        Anything matching no rule comes back `unclassified` for manual triage --
        deliberately, since most products carry no docsite category and guessing a
        family is worse than flagging one for review.

        Never returns an engine: the source toolchain is a per-version property
        detected from the package, not something a product-level rule can assert.
        """
        code_lower = product_code.lower().strip()
        name_lower = product_name.lower().strip()

        for rule in self.load_taxonomy()["rules"]:
            tokens = [str(t).lower().strip() for t in rule.get("match", [])]
            if any(token == code_lower or (token and name_lower and token in name_lower) for token in tokens):
                return {
                    "bu": str(rule.get("bu", "tibco")).lower(),
                    "family": str(rule.get("family", "general")).lower(),
                    "family_source": FamilySource.TAXONOMY_RULE,
                    "display_name": product_name or product_code,
                }

        return {
            "bu": "tibco",
            "family": "general",
            "family_source": FamilySource.UNCLASSIFIED,
            "display_name": product_name or product_code,
        }
