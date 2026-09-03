"""Unit tests for the CSV-backed additive catalog and its 3-way merge.

The central guarantee under test is the one in docs/architecture.md §3.5: a manual
edit survives a fetch **without the user having flagged it**, because the last
fetch is recorded in `state.db` and any divergence from it is read as a human edit.
"""

from pathlib import Path

import pytest

from docushift.catalog import CatalogError, CatalogManager
from docushift.models import EngineSource, FamilySource, Product, SourceEngine
from docushift.utils.csvio import read_rows
from tests.conftest import make_product, make_version


def _fetch(catalog: CatalogManager, *products: Product):
    return catalog.merge_fetch_results(list(products))


def _reload(catalog: CatalogManager) -> CatalogManager:
    """A fresh manager over the same files, to prove state survived the write."""
    return CatalogManager(catalog.products_path, catalog.versions_path, catalog.state)


# -- load / save -------------------------------------------------------------


def test_missing_files_yield_an_empty_catalog(catalog: CatalogManager) -> None:
    assert catalog.load().products == {}


def test_save_then_reload_round_trips(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    reloaded = _reload(catalog).load()

    product = reloaded.products["ems"]
    assert product.display_name == "TIBCO Enterprise Message Service™"
    assert product.family == "messaging"
    assert set(product.versions) == {"10.4.0", "8.6.0"}


def test_rewrite_produces_no_diff_churn(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    before = (catalog.products_path.read_bytes(), catalog.versions_path.read_bytes())

    _reload(catalog).save()

    assert (catalog.products_path.read_bytes(), catalog.versions_path.read_bytes()) == before


def test_versions_are_written_in_natural_descending_order(catalog: CatalogManager) -> None:
    product = make_product("ems")
    for version in ("9.1.0", "10.4.0", "8.6.0"):
        product.versions[version] = make_version("ems", version)
    _fetch(catalog, product)

    written = [row["version"] for row in read_rows(catalog.versions_path)]

    assert written == ["10.4.0", "9.1.0", "8.6.0"]


def test_products_are_sorted_by_bu_family_code(catalog: CatalogManager) -> None:
    _fetch(
        catalog,
        make_product("zeta", bu="tibco", family="messaging"),
        make_product("alpha", bu="ibi", family="webfocus"),
        make_product("beta", bu="tibco", family="analytics"),
    )

    written = [row["product_code"] for row in read_rows(catalog.products_path)]

    assert written == ["alpha", "beta", "zeta"]


def test_denormalized_columns_are_regenerated_from_products(catalog: CatalogManager) -> None:
    """`_bu` / `_family` exist so the sheet can be filtered without a VLOOKUP."""
    product = make_product("ems", bu="tibco", family="messaging")
    product.versions["10.4.0"] = make_version("ems", "10.4.0")
    _fetch(catalog, product)

    row = read_rows(catalog.versions_path)[0]

    assert (row["_bu"], row["_family"]) == ("tibco", "messaging")


def test_edits_to_denormalized_columns_are_ignored(catalog: CatalogManager) -> None:
    product = make_product("ems", bu="tibco", family="messaging")
    product.versions["10.4.0"] = make_version("ems", "10.4.0")
    _fetch(catalog, product)

    text = catalog.versions_path.read_text(encoding="utf-8-sig").replace("tibco,messaging", "ibi,webfocus")
    catalog.versions_path.write_text(text, encoding="utf-8-sig", newline="")
    _reload(catalog).save()

    row = read_rows(catalog.versions_path)[0]
    assert (row["_bu"], row["_family"]) == ("tibco", "messaging")


def test_orphaned_version_row_is_an_error_not_a_silent_product(catalog: CatalogManager) -> None:
    catalog.products_path.write_text("product_code,display_name\n", encoding="utf-8-sig", newline="")
    catalog.versions_path.write_text(
        "product_code,version\nghost,1.0.0\n", encoding="utf-8-sig", newline=""
    )

    with pytest.raises(CatalogError, match="unknown product_code 'ghost'"):
        catalog.load()


def test_booleans_are_read_permissively_and_written_lowercase(catalog: CatalogManager) -> None:
    """Excel writes TRUE/FALSE; the catalog always writes lowercase."""
    catalog.products_path.write_text(
        "product_code,display_name,bu,family,family_source,slug,custom_override\n"
        "ems,EMS,tibco,messaging,manual,tibco-ems,TRUE\n",
        encoding="utf-8-sig",
        newline="",
    )

    assert catalog.load().products["ems"].custom_override is True

    catalog.save()
    assert read_rows(catalog.products_path)[0]["custom_override"] == "true"


# -- additive merge ----------------------------------------------------------


def test_fetch_adds_new_products(catalog: CatalogManager, sample_product: Product) -> None:
    stats = _fetch(catalog, sample_product)

    assert (stats.products_added, stats.versions_added) == (1, 2)


def test_fetch_is_additive_for_new_versions(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    incoming = make_product("ems", family="messaging")
    incoming.versions = {
        "10.5.0": make_version("ems", "10.5.0"),
        "10.4.0": make_version("ems", "10.4.0"),
        "8.6.0": make_version("ems", "8.6.0", is_archived=True, convert_eligible=False),
    }
    stats = catalog.merge_fetch_results([incoming])

    assert stats.versions_added == 1
    assert set(catalog.get_product("ems").versions) == {"10.4.0", "8.6.0", "10.5.0"}


def test_archived_versions_default_to_ineligible(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    archived = _reload(catalog).get_version("ems", "8.6.0")

    assert (archived.is_archived, archived.convert_eligible) == (True, False)


# -- deletion safety ---------------------------------------------------------


def test_disappearing_version_aborts_the_fetch(catalog: CatalogManager, sample_product: Product) -> None:
    """Excel reading '1.10' as '1.1' must be reported, not silently applied."""
    _fetch(catalog, sample_product)

    shrunk = make_product("ems", family="messaging")
    shrunk.versions = {"10.4.0": make_version("ems", "10.4.0")}

    with pytest.raises(CatalogError, match="8.6.0"):
        catalog.merge_fetch_results([shrunk])


def test_allow_deletes_permits_the_removal(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    shrunk = make_product("ems", family="messaging")
    shrunk.versions = {"10.4.0": make_version("ems", "10.4.0")}
    catalog.merge_fetch_results([shrunk], allow_deletes=True)

    assert set(catalog.get_product("ems").versions) == {"10.4.0"}
    assert catalog.state.get_version_snapshot("ems", "8.6.0") is None


def test_deletion_check_is_scoped_to_fetched_products(catalog: CatalogManager) -> None:
    """A single-product fetch must never threaten another product's rows."""
    ems = make_product("ems")
    ems.versions = {"10.4.0": make_version("ems", "10.4.0")}
    ebx = make_product("ebx")
    ebx.versions = {"6.2.0": make_version("ebx", "6.2.0")}
    _fetch(catalog, ems, ebx)

    catalog.merge_fetch_results([ems])

    assert set(catalog.get_product("ebx").versions) == {"6.2.0"}


# -- 3-way merge: unflagged manual edits survive ------------------------------


def test_manual_eligibility_toggle_survives_refetch(catalog: CatalogManager, sample_product: Product) -> None:
    """The headline guarantee -- no custom_override was set here."""
    _fetch(catalog, sample_product)
    catalog.set_conversion_eligibility("ems", "8.6.0", True)

    catalog.merge_fetch_results([sample_product])

    assert catalog.get_version("ems", "8.6.0").convert_eligible is True


def test_untouched_fields_still_take_upstream_changes(catalog: CatalogManager, sample_product: Product) -> None:
    """Preserving edits must not mean freezing everything else."""
    _fetch(catalog, sample_product)

    renamed = make_product("ems", display_name="TIBCO EMS (renamed upstream)", family="messaging")
    renamed.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([renamed])

    assert catalog.get_product("ems").display_name == "TIBCO EMS (renamed upstream)"


def test_edited_field_is_preserved_while_its_sibling_updates(
    catalog: CatalogManager, sample_product: Product
) -> None:
    _fetch(catalog, sample_product)
    catalog.get_product("ems").display_name = "My Preferred Name"
    catalog.save()

    upstream = make_product("ems", display_name="Upstream Name", slug="tibco-ems-new", family="messaging")
    upstream.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([upstream])

    product = catalog.get_product("ems")
    assert product.display_name == "My Preferred Name"
    assert product.slug == "tibco-ems-new"


def test_manual_family_is_never_overwritten(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_product_field("ems", "family", "integration")

    upstream = make_product("ems", family="analytics", family_source=FamilySource.DOCSITE_CATEGORY)
    upstream.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([upstream])

    product = catalog.get_product("ems")
    assert (product.family, product.family_source) == ("integration", FamilySource.MANUAL)


def test_lower_confidence_family_source_cannot_downgrade(catalog: CatalogManager) -> None:
    """A docsite category must not overwrite a taxonomy-rule assignment."""
    rule_based = make_product("ems", family="messaging", family_source=FamilySource.TAXONOMY_RULE)
    _fetch(catalog, rule_based)

    catalog.merge_fetch_results([make_product("ems", family="general", family_source=FamilySource.DOCSITE_CATEGORY)])

    assert catalog.get_product("ems").family == "messaging"


def test_docsite_category_can_promote_an_unclassified_product(catalog: CatalogManager) -> None:
    _fetch(catalog, make_product("mystery", family="general", family_source=FamilySource.UNCLASSIFIED))

    catalog.merge_fetch_results(
        [make_product("mystery", family="analytics", family_source=FamilySource.DOCSITE_CATEGORY)]
    )

    product = catalog.get_product("mystery")
    assert (product.family, product.family_source) == ("analytics", FamilySource.DOCSITE_CATEGORY)


def test_custom_override_pins_the_whole_product_row(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_product_field("ems", "custom_override", "true")

    upstream = make_product("ems", display_name="Upstream", slug="new-slug", bu="ibi", family="webfocus")
    upstream.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([upstream])

    product = catalog.get_product("ems")
    assert (product.display_name, product.slug, product.bu) == (
        "TIBCO Enterprise Message Service™",
        "tibco-ems",
        "tibco",
    )


def test_custom_override_pins_a_version_row(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_version_field("ems", "10.4.0", "custom_override", "true")
    catalog.set_version_field("ems", "10.4.0", "zip_url", "https://internal/mirror.zip")

    upstream = make_product("ems", family="messaging")
    upstream.versions = {
        "10.4.0": make_version("ems", "10.4.0", zip_url="https://docs.tibco.com/upstream.zip"),
        "8.6.0": make_version("ems", "8.6.0", is_archived=True, convert_eligible=False),
    }
    catalog.merge_fetch_results([upstream])

    assert catalog.get_version("ems", "10.4.0").zip_url == "https://internal/mirror.zip"


def test_without_a_snapshot_existing_values_are_kept(
    stateless_catalog: CatalogManager, sample_product: Product
) -> None:
    """With no merge base, the conservative reading is that the CSV value is the user's."""
    stateless_catalog.merge_fetch_results([sample_product])

    renamed = make_product("ems", display_name="Upstream Rename", family="messaging")
    renamed.versions = dict(sample_product.versions)
    stateless_catalog.merge_fetch_results([renamed])

    assert stateless_catalog.get_product("ems").display_name == "TIBCO Enterprise Message Service™"


def test_dry_run_writes_nothing(catalog: CatalogManager, sample_product: Product) -> None:
    catalog.merge_fetch_results([sample_product], dry_run=True)

    assert not catalog.products_path.exists()
    assert catalog.state.get_product_snapshot("ems") is None


# -- engine handling ---------------------------------------------------------


def test_new_versions_default_to_auto_never_flare(catalog: CatalogManager, sample_product: Product) -> None:
    """A wrong engine default is silently destructive; `auto` is skipped instead."""
    _fetch(catalog, sample_product)

    version = catalog.get_version("ems", "10.4.0")

    assert (version.engine, version.engine_source) == (SourceEngine.AUTO, EngineSource.AUTO)


def test_detected_engine_is_written_back(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    assert catalog.record_detected_engine("ems", "10.4.0", SourceEngine.FLARE) is True

    version = _reload(catalog).get_version("ems", "10.4.0")
    assert (version.engine, version.engine_source) == (SourceEngine.FLARE, EngineSource.DETECTED)


def test_detection_never_overrides_a_manual_engine(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_version_field("ems", "8.6.0", "engine", "webworks")

    assert catalog.record_detected_engine("ems", "8.6.0", SourceEngine.FLARE) is False
    assert catalog.get_version("ems", "8.6.0").engine == SourceEngine.WEBWORKS


def test_a_fetch_does_not_reset_a_detected_engine(catalog: CatalogManager, sample_product: Product) -> None:
    """Discovery does not own the engine columns, so it must not touch them."""
    _fetch(catalog, sample_product)
    catalog.record_detected_engine("ems", "10.4.0", SourceEngine.FLARE)

    catalog.merge_fetch_results([sample_product])

    assert catalog.get_version("ems", "10.4.0").engine == SourceEngine.FLARE


def test_engine_varies_across_one_products_versions(catalog: CatalogManager) -> None:
    """The reason engine is per-version: one product's history spans generators."""
    product = make_product("ems", family="messaging")
    for version in ("10.4.0", "10.2.1", "8.6.0"):
        product.versions[version] = make_version("ems", version)
    _fetch(catalog, product)

    catalog.record_detected_engine("ems", "10.4.0", SourceEngine.FLARE)
    catalog.record_detected_engine("ems", "8.6.0", SourceEngine.WEBWORKS)

    reloaded = _reload(catalog)
    assert reloaded.get_version("ems", "10.4.0").engine == SourceEngine.FLARE
    assert reloaded.get_version("ems", "8.6.0").engine == SourceEngine.WEBWORKS
    assert reloaded.get_version("ems", "10.2.1").engine == SourceEngine.AUTO


# -- edits, filtering, reporting ---------------------------------------------


def test_setting_family_pins_provenance_to_manual(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    catalog.set_product_field("ems", "family", "Integration")

    product = catalog.get_product("ems")
    assert (product.family, product.family_source) == ("integration", FamilySource.MANUAL)


def test_setting_an_unknown_field_is_rejected(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    with pytest.raises(CatalogError, match="not a settable"):
        catalog.set_product_field("ems", "nonsense", "x")


def test_edits_to_absent_rows_report_failure(catalog: CatalogManager) -> None:
    assert catalog.set_conversion_eligibility("nope", "1.0.0", True) is False
    assert catalog.set_product_field("nope", "family", "messaging") is False
    assert catalog.set_version_field("nope", "1.0.0", "zip_url", "x") is False


def test_iter_versions_filters(catalog: CatalogManager, sample_product: Product) -> None:
    ebx = make_product("ebx", bu="tibco", family="data_management")
    ebx.versions = {"6.2.0": make_version("ebx", "6.2.0")}
    _fetch(catalog, sample_product, ebx)

    assert len(catalog.iter_versions()) == 3
    assert len(catalog.iter_versions(family="messaging")) == 2
    assert len(catalog.iter_versions(eligible_only=True)) == 2
    assert len(catalog.iter_versions(product_code="ems", version="10.4.0")) == 1


def test_triage_summary_counts_provenance(catalog: CatalogManager) -> None:
    _fetch(
        catalog,
        make_product("a", family_source=FamilySource.UNCLASSIFIED),
        make_product("b", family_source=FamilySource.UNCLASSIFIED),
        make_product("c", family="messaging", family_source=FamilySource.TAXONOMY_RULE),
    )

    summary = catalog.triage_summary()

    assert summary["total"] == 3
    assert summary["counts"]["unclassified"] == 2
    assert summary["unclassified"] == ["a", "b"]


def test_validate_flags_a_version_key_lost_to_excel(catalog: CatalogManager) -> None:
    product = make_product("ems")
    product.versions = {"1.10": make_version("ems", "1.10", zip_url="https://x/z.zip")}
    _fetch(catalog, product)

    # Excel reads 1.10 as the number 1.1 and saves it back that way.
    text = catalog.versions_path.read_text(encoding="utf-8-sig").replace("1.10", "1.1")
    catalog.versions_path.write_text(text, encoding="utf-8-sig", newline="")

    problems = _reload(catalog).validate()

    assert any("1.10" in problem for problem in problems)


def test_validate_flags_eligible_versions_with_no_zip(catalog: CatalogManager) -> None:
    product = make_product("ems")
    product.versions = {"1.0.0": make_version("ems", "1.0.0", convert_eligible=True)}
    _fetch(catalog, product)

    assert any("no zip_url" in problem for problem in catalog.validate())


def test_catalog_json_is_retired(repo_root: Path) -> None:
    assert not (repo_root / "config" / "catalog.json").exists()


# -- convert_batch: run scheduling, orthogonal to eligibility ----------------


def test_convert_batch_round_trips_through_the_csv(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    catalog.set_version_field("ems", "10.4.0", "convert_batch", "poc-1")

    assert read_rows(catalog.versions_path)[0]["convert_batch"] == "poc-1"
    assert _reload(catalog).get_version("ems", "10.4.0").convert_batch == "poc-1"


def test_convert_batch_is_normalized_to_lowercase(catalog: CatalogManager, sample_product: Product) -> None:
    """`POC-1` and `poc-1 ` must select the same rows as `poc-1`."""
    _fetch(catalog, sample_product)

    catalog.set_version_field("ems", "10.4.0", "convert_batch", "  POC-1 ")

    assert catalog.get_version("ems", "10.4.0").convert_batch == "poc-1"
    assert len(catalog.iter_versions(batch="POC-1")) == 1


def test_a_batch_tag_survives_a_refetch(catalog: CatalogManager, sample_product: Product) -> None:
    """Discovery has nothing to say about scheduling, so it must never clear the column."""
    _fetch(catalog, sample_product)
    catalog.set_version_field("ems", "10.4.0", "convert_batch", "wave-2")

    _fetch(_reload(catalog), sample_product)

    assert _reload(catalog).get_version("ems", "10.4.0").convert_batch == "wave-2"


def test_batch_selection_is_opt_in(catalog: CatalogManager, sample_product: Product) -> None:
    """The POC case: tagging one row must not require touching any other."""
    ebx = make_product("ebx", family="data_management")
    ebx.versions = {"6.2.0": make_version("ebx", "6.2.0"), "6.1.0": make_version("ebx", "6.1.0")}
    _fetch(catalog, sample_product, ebx)
    catalog.set_version_field("ebx", "6.2.0", "convert_batch", "poc-1")

    assert len(catalog.iter_versions()) == 4
    assert [v.version for _, v in catalog.iter_versions(batch="poc-1")] == ["6.2.0"]
    # Every other row is untouched -- still eligible, just not scheduled.
    assert len(catalog.iter_versions(eligible_only=True)) == 3


def test_eligibility_is_the_hard_gate_over_the_batch(catalog: CatalogManager, sample_product: Product) -> None:
    """An archived version tagged into a batch is still excluded from the run."""
    _fetch(catalog, sample_product)
    catalog.set_version_field("ems", "8.6.0", "convert_batch", "poc-1")

    assert len(catalog.iter_versions(batch="poc-1")) == 1
    assert catalog.iter_versions(batch="poc-1", eligible_only=True) == []


def test_batches_counts_only_scheduled_versions(catalog: CatalogManager, sample_product: Product) -> None:
    ebx = make_product("ebx", family="data_management")
    ebx.versions = {"6.2.0": make_version("ebx", "6.2.0")}
    _fetch(catalog, sample_product, ebx)
    catalog.set_version_field("ems", "10.4.0", "convert_batch", "poc-1")
    catalog.set_version_field("ebx", "6.2.0", "convert_batch", "poc-1")

    assert catalog.batches() == {"poc-1": 2}


def test_batches_is_empty_when_nothing_is_scheduled(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    assert catalog.batches() == {}


# -- warnings: accepted, but worth saying out loud ---------------------------


def test_scheduled_but_ineligible_version_warns(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_version_field("ems", "8.6.0", "convert_batch", "poc-1")

    notes = catalog.warnings()

    assert any("convert_eligible=false" in note and "8.6.0" in note for note in notes)


def test_an_undeclared_family_warns_but_does_not_fail(taxonomy_config, catalog: CatalogManager) -> None:
    """A family typed straight into products.csv is accepted; the folder is auto-registered."""
    catalog.config = taxonomy_config
    product = make_product("newthing", family="streaming_analytics")
    product.versions = {"1.0.0": make_version("newthing", "1.0.0", zip_url="https://x/z.zip")}
    _fetch(catalog, product)

    assert catalog.validate() == []
    notes = catalog.warnings()
    assert any("streaming_analytics" in note for note in notes)
    assert any("families/en-us-tibco-streaming-analytics" in note for note in notes)


def test_a_declared_family_produces_no_warning(
    taxonomy_config, catalog: CatalogManager, sample_product: Product
) -> None:
    catalog.config = taxonomy_config
    _fetch(catalog, sample_product)

    assert catalog.warnings() == []


def test_warnings_are_inert_without_a_config(catalog: CatalogManager) -> None:
    """Family checking is optional; nothing should blow up when taxonomy is unavailable."""
    product = make_product("newthing", family="whatever")
    product.versions = {"1.0.0": make_version("newthing", "1.0.0", zip_url="https://x/z.zip")}
    _fetch(catalog, product)

    assert catalog.warnings() == []
