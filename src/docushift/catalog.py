"""Additive Catalog Manager for DocuShift."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from docushift.models import Catalog, Product, ProductVersion, SourceEngine


class CatalogManager:
    """
    Manages the master Additive Product Catalog (config/catalog.json).
    Implements 3-way smart merge logic to protect manual user overrides
    while seamlessly incorporating newly discovered products and versions.
    """

    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path
        self._catalog: Optional[Catalog] = None

    def load(self) -> Catalog:
        """Loads catalog from disk or initializes a new one if not present."""
        if self._catalog is not None:
            return self._catalog

        if not self.catalog_path.exists():
            self._catalog = Catalog(last_updated=datetime.now(timezone.utc).isoformat())
            return self._catalog

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._catalog = Catalog.model_validate(data)
        except Exception as e:
            # Fallback to empty catalog on corruption or error
            self._catalog = Catalog(last_updated=datetime.now(timezone.utc).isoformat())
        return self._catalog

    def save(self) -> None:
        """Saves current catalog to disk with clean indentation."""
        if self._catalog is None:
            return

        self._catalog.last_updated = datetime.now(timezone.utc).isoformat()
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.catalog_path, "w", encoding="utf-8") as f:
            json.dump(self._catalog.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    def get_product(self, product_code: str) -> Optional[Product]:
        """Gets a product by its code."""
        catalog = self.load()
        return catalog.products.get(product_code)

    def get_version(self, product_code: str, version: str) -> Optional[ProductVersion]:
        """Gets a specific product version."""
        product = self.get_product(product_code)
        if product:
            return product.versions.get(version)
        return None

    def upsert_product(self, product: Product) -> Product:
        """
        Smart upsert for a product:
        If product already exists and has custom_override == True, preserve manual fields.
        """
        catalog = self.load()
        existing = catalog.products.get(product.product_code)

        if existing is None:
            catalog.products[product.product_code] = product
            return product

        if existing.custom_override:
            # Preserve user overrides for top-level product attributes
            product.display_name = existing.display_name
            product.bu = existing.bu
            product.family = existing.family
            product.engine = existing.engine
            product.custom_override = True

        # Merge versions
        for ver_key, ver_data in product.versions.items():
            existing_ver = existing.versions.get(ver_key)
            if existing_ver is not None:
                if existing_ver.custom_override:
                    # Preserve manual version overrides (e.g. custom zip url, convert_eligible toggle)
                    ver_data.convert_eligible = existing_ver.convert_eligible
                    ver_data.zip_url = existing_ver.zip_url or ver_data.zip_url
                    ver_data.custom_override = True
            existing.versions[ver_key] = ver_data

        return existing

    def smart_merge_fetch_results(self, discovered_products: List[Product]) -> Dict[str, int]:
        """
        Merges a list of freshly discovered products from docsite discovery into catalog.
        Returns statistics: {'products_added': int, 'products_updated': int, 'versions_added': int}
        """
        catalog = self.load()
        stats = {"products_added": 0, "products_updated": 0, "versions_added": 0}

        for new_prod in discovered_products:
            code = new_prod.product_code
            if code not in catalog.products:
                catalog.products[code] = new_prod
                stats["products_added"] += 1
                stats["versions_added"] += len(new_prod.versions)
            else:
                existing_prod = catalog.products[code]
                stats["products_updated"] += 1

                # Update product details if not overridden
                if not existing_prod.custom_override:
                    existing_prod.display_name = new_prod.display_name
                    existing_prod.slug = new_prod.slug or existing_prod.slug
                    existing_prod.docsite_id = new_prod.docsite_id or existing_prod.docsite_id
                    if new_prod.bu != "tibco":  # If new discovery found specific BU
                        existing_prod.bu = new_prod.bu
                    if new_prod.family != "general":
                        existing_prod.family = new_prod.family

                # Merge versions additively
                for ver_key, new_ver in new_prod.versions.items():
                    if ver_key not in existing_prod.versions:
                        existing_prod.versions[ver_key] = new_ver
                        stats["versions_added"] += 1
                    else:
                        existing_ver = existing_prod.versions[ver_key]
                        if not existing_ver.custom_override:
                            existing_ver.title = new_ver.title or existing_ver.title
                            existing_ver.zip_url = new_ver.zip_url or existing_ver.zip_url
                            existing_ver.release_date = new_ver.release_date or existing_ver.release_date
                            existing_ver.folder_path = new_ver.folder_path or existing_ver.folder_path
                            existing_ver.is_archived = new_ver.is_archived

        self.save()
        return stats

    def set_conversion_eligibility(self, product_code: str, version: str, eligible: bool) -> bool:
        """Enables or disables conversion for a specific product version."""
        v = self.get_version(product_code, version)
        if v:
            v.convert_eligible = eligible
            v.custom_override = True
            self.save()
            return True
        return False
