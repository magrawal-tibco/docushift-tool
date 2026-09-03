"""Configuration and Taxonomy Manager for DocuShift."""

import os
from pathlib import Path
from typing import Any

import yaml

from docushift.models import SourceEngine


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
        self.catalog_path = self.config_dir / "catalog.json"
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
            self._taxonomy_cache = {"business_units": {}}
            return self._taxonomy_cache

        with open(self.taxonomy_path, encoding="utf-8") as f:
            self._taxonomy_cache = yaml.safe_load(f) or {"business_units": {}}
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

    def resolve_product_info(self, product_code: str, product_name: str = "") -> dict[str, Any]:
        """
        Resolves BU, Product Family, and Engine based on taxonomy mappings
        or intelligent heuristics.
        """
        taxonomy = self.load_taxonomy()
        bus = taxonomy.get("business_units", {})

        code_lower = product_code.lower().strip()
        name_lower = product_name.lower().strip()

        # 1. Exact match in taxonomy
        for bu_key, bu_data in bus.items():
            families = bu_data.get("families", {})
            for fam_key, fam_data in families.items():
                products = fam_data.get("products", {})
                if code_lower in products:
                    prod_info = products[code_lower]
                    return {
                        "bu": bu_key,
                        "family": fam_key,
                        "engine": SourceEngine(prod_info.get("engine", "flare")),
                        "display_name": prod_info.get("name", product_name)
                    }

        # 2. Heuristic inference for IBI products
        ibi_keywords = ("ibi", "webfocus", "omni", "iway")
        if any(kw in name_lower for kw in ibi_keywords) or code_lower.startswith("ibi"):
            fam = "webfocus" if "webfocus" in name_lower else "data_management"
            return {
                "bu": "ibi",
                "family": fam,
                "engine": SourceEngine.FLARE,
                "display_name": product_name
            }

        # 3. Default fallback to TIBCO
        return {
            "bu": "tibco",
            "family": "general",
            "engine": SourceEngine.FLARE,
            "display_name": product_name
        }
