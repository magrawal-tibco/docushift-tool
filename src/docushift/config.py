"""Configuration and taxonomy manager for DocuShift.

Also the single owner of the **families workspace** path contract
(docs/architecture.md §4): every downloaded ZIP and extracted tree lives under
`families/{locale}-{bu}-{family}/`. Deriving those paths in one place is what lets
Stage 3, Stage 4, and Stage 5 agree on where a package is without passing paths
between them -- `state.db` records the resolved path per version, but the layout
itself is computed here.
"""

import os
from pathlib import Path
from typing import Any

import yaml

from docushift.models import FamilySource
from docushift.utils.slug import family_folder

# Every folder name is locale-prefixed because the predecessor `html-to-md` project
# publishes `fr-fr` and `ja-jp` trees alongside `en-us`. Nothing in the pipeline is
# multi-locale yet; the prefix reserves the shape so adding one is not a rename of
# every folder on disk.
DEFAULT_LOCALE = "en-us"


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
