"""Configuration and taxonomy manager for DocuShift."""

import os
from pathlib import Path
from typing import Any

import yaml

from docushift.models import FamilySource


class ConfigManager:
    """Manages project paths, taxonomy definitions, and configuration files."""

    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or Path(os.getcwd())
        self.config_dir = self.root_dir / "config"
        self.cache_dir = self.root_dir / "cache"
        self.output_dir = self.root_dir / "output"
        self.taxonomy_path = self.config_dir / "taxonomy.yaml"
        self.docsite_path = self.config_dir / "docsite.yaml"
        self.aem_templates_dir = self.config_dir / "aem_templates"
        self.products_path = self.config_dir / "products.csv"
        self.versions_path = self.config_dir / "versions.csv"
        self.state_db_path = self.cache_dir / "state.db"

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "downloads").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "extracted").mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._taxonomy_cache: dict[str, Any] | None = None
        self._docsite_cache: dict[str, Any] | None = None

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
