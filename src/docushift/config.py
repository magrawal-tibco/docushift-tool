"""Configuration and taxonomy manager for DocuShift.

Also the single owner of the **families workspace** path contract
(docs/architecture.md §4): every downloaded ZIP and extracted tree lives under
`families/{locale}-{bu}-{family}/`. Deriving those paths in one place is what lets
Stage 3, Stage 4, and Stage 5 agree on where a package is without passing paths
between them -- `state.db` records the resolved path per version, but the layout
itself is computed here.
"""

import csv
import io
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from docushift.models import FamilySource, MigrateDecision, ReleaseStatus

# X2-04: every file a human edits is read UTF-8 first and Windows-1252 second,
# the code page Excel's and Notepad's default save writes here.
from docushift.utils.csvio import read_text
from docushift.utils.slug import (
    docs_tree_name,
    family_workspace_folder,
    is_primary_locale,
    resources_tree_name,
    slugify,
)

# Every folder name is locale-prefixed because the predecessor `html-to-md` project
# publishes `fr-fr` and `ja-jp` trees alongside `en-us`. Nothing in the pipeline is
# multi-locale yet; the prefix reserves the shape so adding one is not a rename of
# every folder on disk.
#
# Language-region, and used verbatim: there is no locale mapping table anywhere in
# the tool. Its only content would be the value the caller already has, and it
# would have to be maintained for every locale the docsite might one day serve. If
# the docsite's own codes turn out to differ from the publishing platform's, that
# mapping belongs at the discovery boundary where the codes are read.
DEFAULT_LOCALE = "en-us"

# The publishing tokens, duplicated from `config/publishing.yaml` so a missing or
# partial file falls back to the documented names rather than failing a run that
# has not reached publishing yet. Same cache-and-default pattern as `load_docsite`.
PUBLISHING_DEFAULTS: dict[str, str] = {
    "docs_suffix": "userdocs",
    "resources_suffix": "resources",
    "localized_prefix": "loc",
    "primary_locale": DEFAULT_LOCALE,
    # The AEM host, for the one link that cannot be relative: a help topic pointing
    # into the `-resources` tree crosses a repository boundary. **Empty is the
    # shipped value and a supported state** -- the host is not known yet, and 409 of
    # the 422 products a full sync selects have no api-reference tree to link into.
    # `sync` leaves those links relative and reports it once per product; it does
    # not fail, and it does not invent a URL. Deployment configuration, not design.
    "publish_base_url": "",
}

# Stage 6b's editorial policy, duplicated from `config/reframe.yaml` for the reason
# above and one more: these are the values the reference baseline was measured at.
#
# `max_words` is a **cap, not a target** (requirements R1.2). Subtree cohesion picks
# the boundary; the cap only refuses a join that would cross it, and never splits a
# source topic to respect it. Measured over EMS 10.5.1's 1,441 topics: 2000 gives 171
# pages, 3000 gives 113, 4000 gives 92, 6000 gives 60. 3000 is shipped because it is
# the value the proof-of-concept's published baseline was taken at, so a regression
# in the packer shows up as a page-count diff against a number somebody has read.
#
# `min_words` is deliberately absent. The POC declared it and never used it, and the
# maintenance retarget drops it rather than wiring it up: a short page whose subtree
# is genuinely short is the correct answer, not a defect to pack away. Removing it is
# what moves the count from the POC's 106 to 113.
#
# **Every field of `reframe.policy.ReframePolicy`, not just the two that shape the
# baseline**, because `load_reframe` passes a `defaults:` key through only if it is
# named here. With two names, the shipped file's own `publish: false` and
# `keep_separate: []` never arrived, and a default `publish: true` was dropped with
# no message (Phase 34, R1-06). Values equal the dataclass's; a test keeps the key
# sets equal, since importing the policy here would be an import cycle.
REFRAME_DEFAULTS: dict[str, Any] = {
    "max_words": 3000,
    "toc_schema": "",
    "pin_layout_to": "",
    "publish": False,
    "keep_separate": (),
}

# A publishing suffix must be one lowercase token. A hyphen makes the family/suffix
# boundary unparseable (`...-messaging-user-docs` -- where does the family end?) and
# an empty value silently turns a tree name back into the bare workspace name.
_SUFFIX_TOKEN = re.compile(r"^[a-z0-9]+$")

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


_MIGRATE_DECISION_TOKENS = {
    "migrate": MigrateDecision.MIGRATE,
    "do not migrate": MigrateDecision.DO_NOT_MIGRATE,
    "do_not_migrate": MigrateDecision.DO_NOT_MIGRATE,
}


@dataclass
class MigrationSheet:
    """The active docsite-migration export, resolved against `docsite-migration.yaml`.

    `entries` is keyed by the **slug recovered from the row's `doc_url`**, so a
    caller joins it with a dict hit on `product.slug` and never runs a match of its
    own. This is a stronger join than `EosReport`'s: that class has only a display
    name to slugify, while this sheet ships the canonical docsite URL, so the key
    is read off the row rather than reconstructed from prose.

    The keys are still *candidate* slugs -- this class has no catalog to check them
    against, and 104 of them name products the catalog does not carry. `unmatched`
    is what makes that visible: `CatalogManager.apply_migrate_decisions` reports
    every one of them rather than letting 410 rows evaporate.
    """
    entries: dict[str, dict[str, MigrateDecision]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    # Every sheet slug carrying at least one usable row, with its row count and how
    # many of those rows say `migrate`. Kept for all slugs, not just unmatched ones:
    # which of them name a real product is a question only the catalog can answer,
    # and `apply_migrate_decisions` answers it.
    slug_rows: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Decision tokens the sheet used that this tool has no enum value for.
    unknown_decisions: list[str] = field(default_factory=list)

    @property
    def unmatched_aliases(self) -> list[str]:
        """Aliases naming a sheet slug the active export does not carry.

        The rename detector, and the exact analogue of `EosReport.unmatched_aliases`:
        the day the export starts spelling a product the catalog's way is the day
        that alias stops moving anything, and silence is indistinguishable from
        success.
        """
        return sorted(name for name in self.aliases if name not in self.slug_rows)

    def decision_for(self, slug: str, version: str) -> MigrateDecision | None:
        """The sheet's verdict on one version, or `None` if it carries no row.

        Version matching is **exact string equality**, for the reason
        `EosReport.status_for` gives: the versions come from the same docsite the
        catalog was crawled from, so a coercion could only ever paper over a real
        mismatch while reintroducing the `1.10` -> `1.1` hazard.
        """
        return self.entries.get(slug, {}).get(version)


def _sheet_slug(doc_url: str, version: str) -> str:
    """The catalog slug a sheet row names, read off its `doc_url`.

    Every row's URL is `https://docs.tibco.com/products/{slug}-{dashed version}`,
    so the slug is the path after `/products/` with that suffix removed. The suffix
    is required to match before it is stripped -- a URL shaped differently is
    returned whole and will simply fail the equality test against `products.csv`,
    which is the correct outcome for a row nobody has reviewed. Guessing at a
    partial strip is how a verdict lands on the wrong product.
    """
    path = doc_url.strip().rstrip("/").rsplit("/products/", 1)[-1]
    suffix = "-" + version.replace(".", "-")
    return path[: -len(suffix)] if suffix != "-" and path.endswith(suffix) else path


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
        self.reframed_dir = self.root_dir / "reframed"
        self.taxonomy_path = self.config_dir / "taxonomy.yaml"
        self.docsite_path = self.config_dir / "docsite.yaml"
        self.scope_path = self.config_dir / "scope.yaml"
        self.eos_path = self.config_dir / "eos.yaml"
        self.docsite_migration_path = self.config_dir / "docsite-migration.yaml"
        self.publishing_path = self.config_dir / "publishing.yaml"
        self.reframe_path = self.config_dir / "reframe.yaml"
        self.origin_urls_path = self.config_dir / "origin-urls.yaml"
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
        self._migration_cache: MigrationSheet | None = None
        self._publishing_cache: dict[str, str] | None = None
        self._reframe_cache: dict[str, Any] | None = None
        self._origin_urls_cache: dict[str, dict[str, Any]] | None = None

    # -- publishing tokens ----------------------------------------------------

    def repo_slug(self, bu: str, family: str | None = None) -> str:
        """The short publishing token for a business unit, or for one of its families.

        Resolution goes through the taxonomy but never *requires* it: a family typed
        straight into products.csv is auto-registered rather than rejected (§4.2), and
        an auto-registered family still has to name a folder. Absent a `repo_slug` the
        slugified key is the token, which is what every family currently uses.
        """
        units = self.load_taxonomy()["business_units"]
        unit = units.get(bu) or {}
        if family is None:
            return str(unit.get("repo_slug") or "").strip().lower() or slugify(bu)
        declared = self.families(bu).get(family) or {}
        return str(declared.get("repo_slug") or "").strip().lower() or slugify(family)

    # -- families workspace layout -------------------------------------------

    def family_workspace_name(self, bu: str, family: str) -> str:
        """The local folder name for one family, e.g. `en-us-tib-data-management`.

        Deliberately *not* a repository name any more. One family now publishes into
        two or three trees, so there is no single repo name for the workspace to
        mirror; `sync` composes the destination name from `docs_tree_name` instead.
        """
        return family_workspace_folder(self.locale, self.repo_slug(bu), self.repo_slug(bu, family))

    def docs_tree_name(self, bu: str, family: str) -> str:
        """The docs repository for one family, e.g. `en-us-tib-messaging-userdocs`."""
        publishing = self.load_publishing()
        return docs_tree_name(
            self.locale,
            self.repo_slug(bu),
            self.repo_slug(bu, family),
            suffix=publishing["docs_suffix"],
            localized_prefix=publishing["localized_prefix"],
            primary_locale=publishing["primary_locale"],
        )

    def resources_tree_name(self, bu: str, family: str) -> str:
        """The resources sibling. Raises for a non-primary locale -- English only."""
        publishing = self.load_publishing()
        return resources_tree_name(
            self.locale,
            self.repo_slug(bu),
            self.repo_slug(bu, family),
            docs_suffix=publishing["docs_suffix"],
            resources_suffix=publishing["resources_suffix"],
            primary_locale=publishing["primary_locale"],
        )

    def publishes_resources(self) -> bool:
        """Whether this run's locale gets a `-resources` tree at all."""
        return is_primary_locale(self.locale, self.load_publishing()["primary_locale"])

    def publish_base_url(self) -> str:
        """The AEM host, without a trailing slash. Empty means "not configured yet".

        Empty is a supported state, not an error: `sync` leaves the cross-tree links
        relative and reports it, because the alternative -- failing the run -- would
        make `sync --all` unrunnable over 422 products for a value that changes the
        output of 13.
        """
        return self.load_publishing()["publish_base_url"].rstrip("/")

    def family_dir(self, bu: str, family: str) -> Path:
        """`families/en-us-<bu>-<family>/` -- the root of one family's working set."""
        return self.families_dir / self.family_workspace_name(bu, family)

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

    def archive_path(self, bu: str, family: str, slug: str, version: str) -> Path:
        """The ZIP path for one archived version: `.../archive/<slug>-<version>.zip`.

        The same filename as `download_path` under a different parent, which is the
        whole design: an archived package pulled for reference is named and found
        exactly like a pipeline one, but sits outside the working set so `extract`
        never mistakes it for a package awaiting conversion (§4.3).
        """
        return self.archive_dir(bu, family) / f"{slug}-{version}.zip"

    def extract_path(self, bu: str, family: str, slug: str, version: str) -> Path:
        """The extracted tree for one version: `.../extracted/<slug>/<version>/`.

        The version keeps its dots here. `html-to-md` writes `6-2-3` in *published*
        paths, but this is a working directory keyed by the catalog, and a dotted
        segment round-trips back to a `versions.csv` key unambiguously where a
        dashed one does not (`6-2-3` could be `6.2.3` or `6-2.3`). The dots-to-dashes
        conversion belongs at Stage 6, where the AEM output path is built.
        """
        return self.extracted_dir(bu, family) / slug / version

    def output_path(self, bu: str, family: str, slug: str, version: str) -> Path:
        """The converted Markdown for one version: `output/<family>/<slug>/<version>/`.

        Under `output/` rather than beside `extracted/` because these two trees have
        different lifetimes: the extracted tree is disposable working state, and the
        Markdown is what Stage 6 shapes and Stage 7 lays out. `--clean` reaching one
        must not reach the other.

        The version keeps its dots, for the reason `extract_path` gives: this is a
        working path keyed by the catalog, and the dots-to-dashes conversion belongs
        at Stage 6 where the AEM path is built. A method rather than a join at the
        call site, because Stages 5, 6 and 7 all need the same answer.
        """
        return self.output_dir / self.family_workspace_name(bu, family) / slug / version

    def reframed_path(self, bu: str, family: str, slug: str, version: str) -> Path:
        """The merged Markdown for one version: `reframed/<family>/<slug>/<version>/`.

        A sibling tree rather than a rewrite of `output/`, because Reframe must never
        write to its input (requirements C4). Two things follow from that. The merge
        stays re-runnable -- boundary rules get tuned repeatedly and each pass needs a
        clean `output/` to start from, which is the whole iterate-and-eyeball loop the
        integration plan §3 is protecting. And the irreversibility the plan calls its
        first risk becomes reversible right up until publication: a bad boundary is
        one `reframe --force` away from gone, where an in-place merge would have taken
        the converted topics with it.

        `reframed/` is created on demand, not in `__init__`, for the reason the family
        folders are: an empty directory in a workspace with no Flare set in scope reads
        as a started migration.
        """
        return self.reframed_dir / self.family_workspace_name(bu, family) / slug / version

    def load_taxonomy(self) -> dict[str, Any]:
        """Loads and caches taxonomy rules from taxonomy.yaml."""
        if self._taxonomy_cache is not None:
            return self._taxonomy_cache

        if not self.taxonomy_path.exists():
            self._taxonomy_cache = {"business_units": {}, "rules": []}
            return self._taxonomy_cache

        loaded = yaml.safe_load(read_text(self.taxonomy_path)) or {}
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

        self._docsite_cache = yaml.safe_load(read_text(self.docsite_path)) or {}
        return self._docsite_cache

    def load_publishing(self) -> dict[str, str]:
        """Loads and caches the publishing tokens from `publishing.yaml`.

        A missing or partial file falls back to `PUBLISHING_DEFAULTS` key by key,
        rather than erroring: nothing publishes until Stage 7, and a fresh checkout
        must still be able to compute a workspace folder name. The values are not
        validated here -- `catalog validate` reports a malformed suffix, so a bad
        token surfaces once with an explanation instead of raising from whichever
        accessor happened to touch it first.
        """
        if self._publishing_cache is not None:
            return self._publishing_cache

        loaded: dict[str, Any] = {}
        if self.publishing_path.exists():
            loaded = yaml.safe_load(read_text(self.publishing_path)) or {}

        resolved = dict(PUBLISHING_DEFAULTS)
        for key in PUBLISHING_DEFAULTS:
            value = str(loaded.get(key, "") or "").strip()
            if value:
                resolved[key] = value
        self._publishing_cache = resolved
        return resolved

    def load_reframe(self) -> dict[str, Any]:
        """Loads `reframe.yaml` -- the editorial policy Stage 6b merges topics by.

        Two blocks: `defaults`, and `products` keyed by slug. Resolution is
        default-then-override per key, which `reframe.policy_for` does; this method
        only reads and shapes, so a caller that wants to print the file gets the file.

        A missing file yields the built-in defaults rather than an error. That is the
        deliberate choice `load_scope` makes and `load_publishing` makes, and it is
        load-bearing here for a different reason: the defaults are what the reference
        corpus was measured at, so a fresh checkout reproduces the baseline in
        requirements §6 without first being configured into it.
        """
        if self._reframe_cache is not None:
            return self._reframe_cache

        loaded: dict[str, Any] = {}
        if self.reframe_path.exists():
            loaded = yaml.safe_load(read_text(self.reframe_path)) or {}

        defaults = dict(REFRAME_DEFAULTS)
        defaults.update(
            {k: v for k, v in (loaded.get("defaults") or {}).items() if k in REFRAME_DEFAULTS}
        )
        self._reframe_cache = {"defaults": defaults, "products": loaded.get("products") or {}}
        return self._reframe_cache

    def load_origin_urls(self) -> dict[str, dict[str, Any]]:
        """Loads `origin-urls.yaml` as `{slug: {template, drop_segments}}`.

        **A missing file yields `{}`, and an absent product is not an error** --
        the opposite default from `load_reframe`, and deliberately so. Reframe's
        defaults are a measured baseline that a fresh checkout should reproduce;
        there is no such thing as a default origin URL, because the answer is a
        fact about how one product's package happens to be laid out on the
        docsite. The four layouts in the file's own header are the evidence. A
        guess here is a 301 to a page that never existed, so the only safe
        default is to decline.

        Rows are shaped but not validated against the catalog: this method reads
        files, and whether a slug names a real product is `origins.template_for`'s
        question, asked where the row is in hand.
        """
        if self._origin_urls_cache is not None:
            return self._origin_urls_cache

        loaded: dict[str, Any] = {}
        if self.origin_urls_path.exists():
            loaded = yaml.safe_load(read_text(self.origin_urls_path)) or {}

        products = loaded.get("products") or {}
        self._origin_urls_cache = {
            slug: dict(entry) for slug, entry in products.items() if isinstance(entry, dict)
        }
        return self._origin_urls_cache

    def publishing_problems(self) -> list[str]:
        """Naming problems that would publish two things into one repository.

        Reported rather than raised, and reported alongside the catalog's own
        problems, because they share a consequence: a run that continues past one of
        these writes into a destination nobody meant, and does so silently.
        """
        problems: list[str] = []
        publishing = self.load_publishing()

        for key in ("docs_suffix", "resources_suffix"):
            value = publishing[key]
            if not _SUFFIX_TOKEN.match(value):
                problems.append(
                    f"config/publishing.yaml: {key} '{value}' is not a single lowercase token. "
                    f"Every other segment of a tree name is hyphen-separated, so a hyphen here makes "
                    f"the family/suffix boundary unparseable."
                )

        # Empty is fine and is the shipped value; a *set* value that is not a URL is
        # not, because it is silently concatenated into every cross-tree link.
        base = publishing["publish_base_url"]
        if base and not base.lower().startswith(("http://", "https://")):
            problems.append(
                f"config/publishing.yaml: publish_base_url '{base}' is not an absolute URL. "
                f"It is prefixed to every link that crosses from the docs tree into "
                f"-resources, so a relative value publishes links that resolve nowhere."
            )

        for bu in sorted(self.load_taxonomy()["business_units"]):
            seen: dict[str, str] = {}
            for family in sorted(self.families(bu)):
                token = self.repo_slug(bu, family)
                if token in seen:
                    problems.append(
                        f"config/taxonomy.yaml: families '{seen[token]}' and '{family}' in bu '{bu}' both "
                        f"resolve to repo_slug '{token}', so both would publish into one repository. "
                        f"Give one of them its own repo_slug."
                    )
                    continue
                seen[token] = family
        return problems

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

        loaded = yaml.safe_load(read_text(self.scope_path)) or {}

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

        loaded = yaml.safe_load(read_text(self.eos_path)) or {}

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
        with io.StringIO(read_text(path), newline="") as handle:
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

    def load_docsite_migration(self) -> MigrationSheet:
        """Loads `docsite-migration.yaml` and the export it names -- §3.12.

        Two files with two authors, exactly as `load_eos()` has: the CSV is the
        docsite inventory's, arrives periodically and is never hand-edited; the
        YAML is ours, and holds the one thing the CSV cannot supply -- how its
        slugs map to catalog slugs where somebody has since renamed a product.

        A missing YAML yields an empty sheet -- every version `unknown` -- rather
        than an error, so a fresh checkout works. Everything else raises, for
        `load_scope()`'s reason: a duplicate alias, an alias with no slug, a
        `sheet:` naming a file that is not there, or a `decision_column` the export
        does not carry are all cases where continuing would quietly write the wrong
        verdict onto a few thousand rows.
        """
        if self._migration_cache is not None:
            return self._migration_cache

        sheet = MigrationSheet()
        if not self.docsite_migration_path.exists():
            self._migration_cache = sheet
            return sheet

        loaded = yaml.safe_load(read_text(self.docsite_migration_path)) or {}

        for entry in loaded.get("aliases") or []:
            name = str(entry.get("sheet_slug", "")).strip().lower()
            slug = str(entry.get("slug", "")).strip().lower()
            if not name:
                continue
            if not slug:
                raise ValueError(f"{self.docsite_migration_path}: alias '{name}' has no slug")
            if name in sheet.aliases:
                raise ValueError(f"{self.docsite_migration_path}: duplicate alias sheet_slug '{name}'")
            sheet.aliases[name] = slug

        sheet_ref = str(loaded.get("sheet", "")).strip()
        if not sheet_ref:
            self._migration_cache = sheet
            return sheet

        sheet_path = self.config_dir / sheet_ref
        if not sheet_path.exists():
            raise ValueError(f"{self.docsite_migration_path}: sheet '{sheet_ref}' not found at {sheet_path}")

        column = str(loaded.get("decision_column", "")).strip()
        if not column:
            raise ValueError(f"{self.docsite_migration_path}: no decision_column named")

        self._read_migration_sheet(sheet_path, column, sheet)
        self._migration_cache = sheet
        return sheet

    def _read_migration_sheet(self, path: Path, column: str, sheet: MigrationSheet) -> None:
        """Parses the docsite export into `sheet`, keyed by resolved slug.

        Read with `utf-8-sig`: the export ships a BOM, as the eos report does.

        A repeated `(slug, version)` agreeing with itself is a harmless duplicate
        and last-wins is safe. A *conflict* is not: two sheet slugs resolving to one
        catalog slug and disagreeing about a version means an alias is wrong, and
        picking one silently is how that stays invisible -- the same rule
        `_read_eos_report` enforces, for the same reason.
        """
        seen_unknown: set[str] = set()
        with io.StringIO(read_text(path), newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or column not in reader.fieldnames:
                raise ValueError(
                    f"{path.name}: no '{column}' column. "
                    f"Fix decision_column in {self.docsite_migration_path.name}."
                )
            for row in reader:
                version = (row.get("version") or "").strip()
                doc_url = (row.get("doc_url") or "").strip()
                if not version or not doc_url:
                    continue

                token = (row.get(column) or "").strip().lower()
                decision = _MIGRATE_DECISION_TOKENS.get(token)
                if decision is None:
                    if token and token not in seen_unknown:
                        seen_unknown.add(token)
                        sheet.unknown_decisions.append(token)
                    continue

                raw = _sheet_slug(doc_url, version)
                if not raw:
                    continue
                count, migrating = sheet.slug_rows.get(raw, (0, 0))
                sheet.slug_rows[raw] = (count + 1, migrating + (decision is MigrateDecision.MIGRATE))

                # An alias wins over the URL's own slug, so a reviewed decision can
                # correct a product the docsite has since renamed.
                slug = sheet.aliases.get(raw, raw)
                existing = sheet.entries.setdefault(slug, {}).get(version)
                if existing is not None and existing is not decision:
                    raise ValueError(
                        f"{path.name}: '{raw}' and another sheet slug both resolve to slug '{slug}' "
                        f"and disagree about version {version} ({existing} vs {decision}). "
                        f"Fix the alias in {self.docsite_migration_path.name}."
                    )
                sheet.entries[slug][version] = decision

    def families(self, bu: str) -> dict[str, Any]:
        """The family definitions declared for one business unit."""
        return self.load_taxonomy()["business_units"].get(bu, {}).get("families", {})

    def is_known_family(self, bu: str, family: str) -> bool:
        return family in self.families(bu)

    def resolve_product_info(self, product_code: str, product_name: str = "") -> dict[str, Any]:
        """Infers `bu` for a product from the taxonomy keyword rules. Never a family.

        **A family is a human's call -- Phase 32.** The rules once returned one too,
        and the mechanism was retired after it twice assigned by coincidence rather
        than by meaning: a bare `webfocus` token claimed all seven products of a
        line that wanted five families, and a `container edition` token would have
        pulled sixteen TIBCO products into an ibi family. Both were caught by
        counting matches by hand, which is the triage the classifier existed to
        save. So every product now comes back `unclassified` and waits for
        `catalog set --product <slug> --family <key>`.

        `bu` is still inferred, and the asymmetry is deliberate. The no-match
        fallback is `tibco`; without rules every new ibi, Spotfire and DataSynapse
        product would file under TIBCO, and `bu` is the first segment of both the
        workspace path and the publishing repository. A wrong repository is worse
        than an unset family, and the brand-level signal is the half that has never
        been wrong -- `webfocus` really is ibi.

        The matched rule's `family:` key is returned as `family_rule_hint` for the
        triage view: it is what the rule *would* have guessed, carried as advice to
        a human and never written to the catalog.

        Never returns an engine: the source toolchain is a per-version property
        detected from the package, not something a product-level rule can assert.
        """
        code_lower = product_code.lower().strip()
        name_lower = product_name.lower().strip()

        info: dict[str, Any] = {
            "bu": "tibco",
            "family": "general",
            "family_source": FamilySource.UNCLASSIFIED,
            "display_name": product_name or product_code,
            "family_rule_hint": "",
        }

        for rule in self.load_taxonomy()["rules"]:
            tokens = [str(t).lower().strip() for t in rule.get("match", [])]
            if any(token == code_lower or (token and name_lower and token in name_lower) for token in tokens):
                info["bu"] = str(rule.get("bu", "tibco")).lower()
                info["family_rule_hint"] = str(rule.get("family", "")).lower()
                break

        return info
