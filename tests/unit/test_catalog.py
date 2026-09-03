"""Unit tests for the additive CatalogManager.

These cover the current JSON-backed, flag-based implementation. Phase 2 replaces
the store with `products.csv` / `versions.csv` and the protection mechanism with a
snapshot-based 3-way merge; the *behavioural* assertions here (additive merge,
archived versions stay ineligible, manual edits survive a fetch) carry over.
"""

from pathlib import Path

from docushift.catalog import CatalogManager
from docushift.models import Product, ProductVersion


def test_load_missing_file_returns_empty_catalog(catalog: CatalogManager) -> None:
    loaded = catalog.load()

    assert loaded.products == {}
    assert loaded.last_updated is not None


def test_save_then_reload_round_trips(catalog: CatalogManager, sample_product: Product, project_root: Path) -> None:
    catalog.upsert_product(sample_product)
    catalog.save()

    reloaded = CatalogManager(project_root / "config" / "catalog.json").load()

    assert set(reloaded.products) == {"ems"}
    assert reloaded.products["ems"].display_name == "TIBCO Enterprise Message Service™"
    assert set(reloaded.products["ems"].versions) == {"10.4.0", "8.6.0"}


def test_corrupt_catalog_falls_back_to_empty(catalog: CatalogManager) -> None:
    catalog.catalog_path.write_text("{ not json", encoding="utf-8")

    assert catalog.load().products == {}


def test_fetch_adds_new_products(catalog: CatalogManager, sample_product: Product) -> None:
    stats = catalog.smart_merge_fetch_results([sample_product])

    assert stats["products_added"] == 1
    assert stats["versions_added"] == 2
    assert catalog.get_product("ems") is not None


def test_fetch_is_additive_for_new_versions(catalog: CatalogManager, sample_product: Product) -> None:
    catalog.smart_merge_fetch_results([sample_product])

    incoming = Product(
        product_code="ems",
        display_name="TIBCO Enterprise Message Service™",
        versions={"10.5.0": ProductVersion(version="10.5.0", is_archived=False)},
    )
    stats = catalog.smart_merge_fetch_results([incoming])

    assert stats["products_added"] == 0
    assert stats["versions_added"] == 1
    # The pre-existing versions must survive a fetch that no longer mentions them.
    assert set(catalog.get_product("ems").versions) == {"10.4.0", "8.6.0", "10.5.0"}


def test_archived_versions_are_not_convert_eligible(catalog: CatalogManager, sample_product: Product) -> None:
    catalog.smart_merge_fetch_results([sample_product])

    archived = catalog.get_version("ems", "8.6.0")

    assert archived.is_archived is True
    assert archived.convert_eligible is False


def test_manual_eligibility_toggle_survives_refetch(catalog: CatalogManager, sample_product: Product) -> None:
    catalog.smart_merge_fetch_results([sample_product])
    assert catalog.set_conversion_eligibility("ems", "8.6.0", True) is True

    # Discovery re-reports the archived version with its default ineligibility.
    refetch = Product(
        product_code="ems",
        display_name="TIBCO Enterprise Message Service™",
        versions={"8.6.0": ProductVersion(version="8.6.0", is_archived=True, convert_eligible=False)},
    )
    catalog.smart_merge_fetch_results([refetch])

    assert catalog.get_version("ems", "8.6.0").convert_eligible is True


def test_custom_override_pins_product_classification(catalog: CatalogManager, sample_product: Product) -> None:
    sample_product.custom_override = True
    sample_product.family = "messaging"
    catalog.smart_merge_fetch_results([sample_product])

    refetch = Product(product_code="ems", display_name="Renamed By Docsite", bu="ibi", family="general")
    catalog.smart_merge_fetch_results([refetch])

    product = catalog.get_product("ems")
    assert product.display_name == "TIBCO Enterprise Message Service™"
    assert product.family == "messaging"


def test_set_conversion_eligibility_on_unknown_version(catalog: CatalogManager) -> None:
    assert catalog.set_conversion_eligibility("nope", "1.0.0", True) is False
