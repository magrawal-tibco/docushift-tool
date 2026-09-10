"""Unit tests for the CSV-backed additive catalog and its 3-way merge.

The central guarantee under test is the one in docs/architecture.md §3.5: a manual
edit survives a fetch **without the user having flagged it**, because the last
fetch is recorded in `state.db` and any divergence from it is read as a human edit.
"""

from pathlib import Path

import pytest

from docushift.catalog import CatalogError, CatalogManager
from docushift.config import ConfigManager
from docushift.models import (
    EngineSource,
    FamilySource,
    Product,
    ReleaseStatus,
    ReleaseStatusSource,
    ScopeSource,
    SourceEngine,
    ZipSource,
)
from docushift.state import StateStore
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

    product = reloaded.products["tibco-ems"]
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
    catalog.products_path.write_text("slug,product_code,display_name\n", encoding="utf-8-sig", newline="")
    catalog.versions_path.write_text("slug,version\nghost,1.0.0\n", encoding="utf-8-sig", newline="")

    with pytest.raises(CatalogError, match="unknown slug 'ghost'"):
        catalog.load()


def test_booleans_are_read_permissively_and_written_lowercase(catalog: CatalogManager) -> None:
    """Excel writes TRUE/FALSE; the catalog always writes lowercase."""
    catalog.products_path.write_text(
        "slug,product_code,display_name,bu,family,family_source,custom_override\n"
        "tibco-ems,ems,EMS,tibco,messaging,manual,TRUE\n",
        encoding="utf-8-sig",
        newline="",
    )

    assert catalog.load().products["tibco-ems"].custom_override is True

    catalog.save()
    assert read_rows(catalog.products_path)[0]["custom_override"] == "true"


# -- additive merge ----------------------------------------------------------


def test_fetch_adds_new_products(catalog: CatalogManager, sample_product: Product) -> None:
    stats = _fetch(catalog, sample_product)

    assert (stats.products_added, stats.versions_added) == (1, 2)


def test_fetch_is_additive_for_new_versions(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    incoming = make_product("tibco-ems", product_code="ems", family="messaging")
    incoming.versions = {
        "10.5.0": make_version("tibco-ems", "10.5.0"),
        "10.4.0": make_version("tibco-ems", "10.4.0"),
        "8.6.0": make_version("tibco-ems", "8.6.0", is_archived=True, convert_eligible=False),
    }
    stats = catalog.merge_fetch_results([incoming])

    assert stats.versions_added == 1
    assert set(catalog.get_product("tibco-ems").versions) == {"10.4.0", "8.6.0", "10.5.0"}


def test_archived_versions_default_to_ineligible(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    archived = _reload(catalog).get_version("tibco-ems", "8.6.0")

    assert (archived.is_archived, archived.convert_eligible) == (True, False)


# -- deletion safety ---------------------------------------------------------


def test_disappearing_version_aborts_the_fetch(catalog: CatalogManager, sample_product: Product) -> None:
    """Excel reading '1.10' as '1.1' must be reported, not silently applied."""
    _fetch(catalog, sample_product)

    shrunk = make_product("tibco-ems", product_code="ems", family="messaging")
    shrunk.versions = {"10.4.0": make_version("tibco-ems", "10.4.0")}

    with pytest.raises(CatalogError, match="8.6.0"):
        catalog.merge_fetch_results([shrunk])


def test_allow_deletes_permits_the_removal(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    shrunk = make_product("tibco-ems", product_code="ems", family="messaging")
    shrunk.versions = {"10.4.0": make_version("tibco-ems", "10.4.0")}
    catalog.merge_fetch_results([shrunk], allow_deletes=True)

    assert set(catalog.get_product("tibco-ems").versions) == {"10.4.0"}
    assert catalog.state.get_version_snapshot("tibco-ems", "8.6.0") is None


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
    catalog.set_conversion_eligibility("tibco-ems", "8.6.0", True)

    catalog.merge_fetch_results([sample_product])

    assert catalog.get_version("tibco-ems", "8.6.0").convert_eligible is True


def test_untouched_fields_still_take_upstream_changes(catalog: CatalogManager, sample_product: Product) -> None:
    """Preserving edits must not mean freezing everything else."""
    _fetch(catalog, sample_product)

    renamed = make_product(
        "tibco-ems", product_code="ems", display_name="TIBCO EMS (renamed upstream)", family="messaging"
    )
    renamed.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([renamed])

    assert catalog.get_product("tibco-ems").display_name == "TIBCO EMS (renamed upstream)"


def test_edited_field_is_preserved_while_its_sibling_updates(
    catalog: CatalogManager, sample_product: Product
) -> None:
    _fetch(catalog, sample_product)
    catalog.get_product("tibco-ems").display_name = "My Preferred Name"
    catalog.save()

    upstream = make_product("tibco-ems", product_code="ems-new", display_name="Upstream Name", family="messaging")
    upstream.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([upstream])

    product = catalog.get_product("tibco-ems")
    assert product.display_name == "My Preferred Name"
    assert product.product_code == "ems-new"


def test_manual_family_is_never_overwritten(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_product_field("tibco-ems", "family", "integration")

    upstream = make_product(
        "tibco-ems", product_code="ems", family="analytics", family_source=FamilySource.DOCSITE_CATEGORY
    )
    upstream.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([upstream])

    product = catalog.get_product("tibco-ems")
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
    catalog.set_product_field("tibco-ems", "custom_override", "true")

    upstream = make_product("new-slug", product_code="ems", display_name="Upstream", bu="ibi", family="webfocus")
    upstream.versions = dict(sample_product.versions)
    catalog.merge_fetch_results([upstream])

    product = catalog.get_product("tibco-ems")
    assert (product.display_name, product.slug, product.bu) == (
        "TIBCO Enterprise Message Service™",
        "tibco-ems",
        "tibco",
    )


def test_custom_override_pins_a_version_row(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_version_field("tibco-ems", "10.4.0", "custom_override", "true")
    catalog.set_version_field("tibco-ems", "10.4.0", "zip_url", "https://internal/mirror.zip")

    upstream = make_product("tibco-ems", product_code="ems", family="messaging")
    upstream.versions = {
        "10.4.0": make_version("tibco-ems", "10.4.0", zip_url="https://docs.tibco.com/upstream.zip"),
        "8.6.0": make_version("tibco-ems", "8.6.0", is_archived=True, convert_eligible=False),
    }
    catalog.merge_fetch_results([upstream])

    assert catalog.get_version("tibco-ems", "10.4.0").zip_url == "https://internal/mirror.zip"


def test_without_a_snapshot_existing_values_are_kept(
    stateless_catalog: CatalogManager, sample_product: Product
) -> None:
    """With no merge base, the conservative reading is that the CSV value is the user's."""
    stateless_catalog.merge_fetch_results([sample_product])

    renamed = make_product("tibco-ems", product_code="ems", display_name="Upstream Rename", family="messaging")
    renamed.versions = dict(sample_product.versions)
    stateless_catalog.merge_fetch_results([renamed])

    assert stateless_catalog.get_product("tibco-ems").display_name == "TIBCO Enterprise Message Service™"


def test_dry_run_writes_nothing(catalog: CatalogManager, sample_product: Product) -> None:
    catalog.merge_fetch_results([sample_product], dry_run=True)

    assert not catalog.products_path.exists()
    assert catalog.state.get_product_snapshot("tibco-ems") is None


# -- engine handling ---------------------------------------------------------


def test_new_versions_default_to_auto_never_flare(catalog: CatalogManager, sample_product: Product) -> None:
    """A wrong engine default is silently destructive; `auto` is skipped instead."""
    _fetch(catalog, sample_product)

    version = catalog.get_version("tibco-ems", "10.4.0")

    assert (version.engine, version.engine_source) == (SourceEngine.AUTO, EngineSource.AUTO)


def test_detected_engine_is_written_back(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    assert catalog.record_detected_engine("tibco-ems", "10.4.0", SourceEngine.FLARE) is True

    version = _reload(catalog).get_version("tibco-ems", "10.4.0")
    assert (version.engine, version.engine_source) == (SourceEngine.FLARE, EngineSource.DETECTED)


def test_detection_never_overrides_a_manual_engine(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_version_field("tibco-ems", "8.6.0", "engine", "webworks")

    assert catalog.record_detected_engine("tibco-ems", "8.6.0", SourceEngine.FLARE) is False
    assert catalog.get_version("tibco-ems", "8.6.0").engine == SourceEngine.WEBWORKS


def test_a_fetch_does_not_reset_a_detected_engine(catalog: CatalogManager, sample_product: Product) -> None:
    """Discovery does not own the engine columns, so it must not touch them."""
    _fetch(catalog, sample_product)
    catalog.record_detected_engine("tibco-ems", "10.4.0", SourceEngine.FLARE)

    catalog.merge_fetch_results([sample_product])

    assert catalog.get_version("tibco-ems", "10.4.0").engine == SourceEngine.FLARE


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


def test_an_unconvertible_engine_survives_a_round_trip(catalog: CatalogManager, sample_product: Product) -> None:
    """The point of naming R help in the enum: it has to reach the sheet to be reviewed.

    Before the unconvertible engines existed, `load()` coerced anything it did not
    recognise back to `auto` -- which is exactly the value that means "we have no
    idea", so a correct detection became indistinguishable from a failed one.
    """
    _fetch(catalog, sample_product)

    assert catalog.record_detected_engine("tibco-ems", "10.4.0", SourceEngine.R_HELP) is True

    row = next(r for r in read_rows(catalog.versions_path) if r["version"] == "10.4.0")
    assert row["engine"] == "r-help"
    assert _reload(catalog).get_version("tibco-ems", "10.4.0").engine == SourceEngine.R_HELP


@pytest.mark.parametrize("engine", sorted(e.value for e in SourceEngine))
def test_every_engine_value_round_trips_through_the_csv(
    catalog: CatalogManager, sample_product: Product, engine: str
) -> None:
    _fetch(catalog, sample_product)

    catalog.set_version_field("tibco-ems", "10.4.0", "engine", engine)

    assert _reload(catalog).get_version("tibco-ems", "10.4.0").engine == SourceEngine(engine)


# -- edits, filtering, reporting ---------------------------------------------


def test_setting_family_pins_provenance_to_manual(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    catalog.set_product_field("tibco-ems", "family", "Integration")

    product = catalog.get_product("tibco-ems")
    assert (product.family, product.family_source) == ("integration", FamilySource.MANUAL)


def test_setting_an_unknown_field_is_rejected(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    with pytest.raises(CatalogError, match="not a settable"):
        catalog.set_product_field("tibco-ems", "nonsense", "x")


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
    assert len(catalog.iter_versions(slug="tibco-ems", version="10.4.0")) == 1


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


# -- product scope: the outermost gate (architecture.md §3.10) ---------------

# The 16 public products whose slug contains `spotfire` and which are **in scope**:
# the eight-product Data Science line, the four Statistica products, and four
# others. A substring rule would sweep every one of them, which is why matching is
# an exact dict hit. Taken from the live A-to-Z index, 2026-09-09.
IN_SCOPE_SPOTFIRE_SLUGS = (
    "spotfire-application",
    "spotfire-data-science-author",
    "spotfire-data-science-for-life-science-author",
    "spotfire-data-science-for-life-science-operations",
    "spotfire-data-science-operations",
    "spotfire-data-science-workbench",
    "spotfire-data-streams",
    "spotfire-liveview-web-enterprise-edition",
    "spotfire-statistica",
    "spotfire-statistica-all-servers",
    "spotfire-statistica-estore-edition",
    "spotfire-statistica-integration",
    "spotfire-statistics-services",
    "tibco-data-science-for-tibco-spotfire-analyst",
    "tibco-data-science-service-for-tibco-spotfire",
    "tibco-spotfire-data-science-package-for-notebooks",
)

# The three in-scope products a substring `ebx` rule would drop. ebXML is an
# unrelated B2B standard; the catalog product is built *on* EBX but is its own.
IN_SCOPE_EBX_SLUGS = (
    "tibco-businessconnect-ebxml-protocol",
    "tibco-businessconnect-container-edition-ebxml-protocol",
    "tibco-product-and-service-catalog-powered-by-tibco-ebx",
)


def _scoped(project_root: Path, state: StateStore, *slugs: str) -> CatalogManager:
    """A catalog manager whose `config/scope.yaml` excludes exactly `slugs`.

    Built fresh each call rather than reused, because `ConfigManager` caches the
    parsed YAML -- rewriting the file mid-test would otherwise change nothing.
    """
    body = "out_of_scope:\n" + "".join(f'  - slug: {slug}\n    reason: "test"\n' for slug in slugs)
    (project_root / "config" / "scope.yaml").write_text(body, encoding="utf-8")
    return CatalogManager(
        project_root / "config" / "products.csv",
        project_root / "config" / "versions.csv",
        state,
        ConfigManager(root_dir=project_root),
    )


def test_a_listed_slug_is_excluded_on_arrival(project_root: Path, state: StateStore) -> None:
    """A product first discovered after the rule was written is never converted once."""
    catalog = _scoped(project_root, state, "tibco-ebx")

    stats = _fetch(catalog, make_product("tibco-ebx", product_code="ebx"))

    product = catalog.get_product("tibco-ebx")
    assert (product.in_scope, product.scope_source) == (False, ScopeSource.SCOPE_RULE)
    assert stats.products_out_of_scope == 1


def test_scope_matches_the_exact_slug_never_a_substring(project_root: Path, state: StateStore) -> None:
    """The regression this whole mechanism is shaped around -- §3.10's failure table."""
    catalog = _scoped(project_root, state, "tibco-ebx", "spotfire")
    look_alikes = IN_SCOPE_EBX_SLUGS + IN_SCOPE_SPOTFIRE_SLUGS

    _fetch(
        catalog,
        make_product("tibco-ebx", product_code="ebx"),
        make_product("spotfire"),
        *(make_product(slug, product_code=f"p{i}") for i, slug in enumerate(look_alikes)),
    )

    excluded = {p.product_code for p in catalog.load().products.values() if not p.in_scope}
    assert excluded == {"ebx", "spotfire"}
    assert len(look_alikes) == 19


def test_scope_round_trips_through_the_csv(project_root: Path, state: StateStore) -> None:
    catalog = _scoped(project_root, state, "tibco-ebx")
    _fetch(catalog, make_product("tibco-ebx", product_code="ebx"))

    reloaded = _reload(catalog).get_product("tibco-ebx")

    assert (reloaded.in_scope, reloaded.scope_source) == (False, ScopeSource.SCOPE_RULE)


def test_a_blank_in_scope_cell_reads_as_in_scope(catalog: CatalogManager, sample_product: Product) -> None:
    """A hand-made row must never be excluded from every stage by an empty cell."""
    _fetch(catalog, sample_product)
    text = catalog.products_path.read_text(encoding="utf-8-sig").replace(",true,default,", ",,,")
    catalog.products_path.write_text(text, encoding="utf-8-sig", newline="")

    product = _reload(catalog).get_product("tibco-ems")

    assert (product.in_scope, product.scope_source) == (True, ScopeSource.DEFAULT)


def test_a_manual_scope_decision_survives_a_fetch_that_would_exclude(
    project_root: Path, state: StateStore
) -> None:
    """`manual` short-circuits ahead of the rule file, or readmission would not stick."""
    catalog = _scoped(project_root, state, "tibco-ebx")
    _fetch(catalog, make_product("tibco-ebx", product_code="ebx"))
    catalog.set_product_field("tibco-ebx", "in_scope", "true")

    _fetch(_scoped(project_root, state, "tibco-ebx"), make_product("tibco-ebx", product_code="ebx"))

    product = _scoped(project_root, state, "tibco-ebx").get_product("tibco-ebx")
    assert (product.in_scope, product.scope_source) == (True, ScopeSource.MANUAL)


def test_a_manual_exclusion_survives_a_fetch_with_no_matching_rule(
    project_root: Path, state: StateStore
) -> None:
    catalog = _scoped(project_root, state)
    _fetch(catalog, make_product("tibco-ems", product_code="ems"))
    catalog.set_product_field("tibco-ems", "in_scope", "false")

    _fetch(_scoped(project_root, state), make_product("tibco-ems", product_code="ems"))

    product = _scoped(project_root, state).get_product("tibco-ems")
    assert (product.in_scope, product.scope_source) == (False, ScopeSource.MANUAL)


def test_removing_a_slug_from_the_yaml_restores_the_product(project_root: Path, state: StateStore) -> None:
    """Step 3 actively resets, so the rule file is removable in fact and not just in name."""
    _fetch(_scoped(project_root, state, "tibco-ebx"), make_product("tibco-ebx", product_code="ebx"))

    _fetch(_scoped(project_root, state), make_product("tibco-ebx", product_code="ebx"))

    product = _scoped(project_root, state).get_product("tibco-ebx")
    assert (product.in_scope, product.scope_source) == (True, ScopeSource.DEFAULT)


def test_a_rule_matching_no_product_is_reported(project_root: Path, state: StateStore) -> None:
    """The rename detector: a rule that quietly matches nothing stops excluding anything."""
    catalog = _scoped(project_root, state, "tibco-ebx", "spotfire-renamed-upstream")

    stats = _fetch(catalog, make_product("tibco-ebx", product_code="ebx"))

    assert stats.scope_rules_unmatched == ["spotfire-renamed-upstream"]
    assert any("spotfire-renamed-upstream" in note and "match no product" in note for note in catalog.warnings())


def test_unmatched_rules_are_reported_as_one_aggregated_note(project_root: Path, state: StateStore) -> None:
    """Sixty near-identical warnings would bury the ones that matter."""
    catalog = _scoped(project_root, state, *(f"gone-{i}" for i in range(20)))
    _fetch(catalog, make_product("tibco-ems", product_code="ems"))

    notes = [note for note in catalog.warnings() if "scope.yaml" in note]

    assert len(notes) == 1
    assert "20 of 20" in notes[0] and "..." in notes[0]


def test_an_excluded_product_is_still_fully_catalogued(project_root: Path, state: StateStore) -> None:
    """Excluded is not absent: it stays on the books, it is just never worked on."""
    catalog = _scoped(project_root, state, "tibco-ebx")
    ebx = make_product("tibco-ebx", product_code="ebx")
    ebx.versions = {v: make_version("tibco-ebx", v) for v in ("6.2.0", "6.1.0", "5.9.0")}

    _fetch(catalog, ebx)

    assert set(_reload(catalog).get_product("tibco-ebx").versions) == {"6.2.0", "6.1.0", "5.9.0"}
    assert len(catalog.iter_versions(slug="tibco-ebx")) == 3


def test_eligible_only_skips_an_out_of_scope_product_whole(project_root: Path, state: StateStore) -> None:
    catalog = _scoped(project_root, state, "tibco-ebx")
    ebx = make_product("tibco-ebx", product_code="ebx")
    ebx.versions = {"6.2.0": make_version("ebx", "6.2.0", convert_eligible=True)}
    ems = make_product("tibco-ems", product_code="ems")
    ems.versions = {"10.4.0": make_version("ems", "10.4.0", convert_eligible=True)}
    _fetch(catalog, ebx, ems)

    assert len(catalog.iter_versions()) == 2
    assert [p.product_code for p, _ in catalog.iter_versions(eligible_only=True)] == ["ems"]


def test_a_batch_tag_on_an_out_of_scope_product_warns(project_root: Path, state: StateStore) -> None:
    """The row reads as scheduled and will never run, so the exclusion has to be named."""
    catalog = _scoped(project_root, state, "tibco-ebx")
    ebx = make_product("tibco-ebx", product_code="ebx")
    ebx.versions = {"6.2.0": make_version("ebx", "6.2.0")}
    _fetch(catalog, ebx)
    catalog.set_version_field("tibco-ebx", "6.2.0", "convert_batch", "poc-1")

    notes = catalog.warnings()

    assert any("poc-1" in note and "config/scope.yaml" in note for note in notes)


def test_a_batch_tag_under_a_manual_exclusion_names_the_csv_not_the_yaml(
    project_root: Path, state: StateStore
) -> None:
    catalog = _scoped(project_root, state)
    ems = make_product("tibco-ems", product_code="ems")
    ems.versions = {"10.4.0": make_version("ems", "10.4.0")}
    _fetch(catalog, ems)
    catalog.set_product_field("tibco-ems", "in_scope", "false")
    catalog.set_version_field("tibco-ems", "10.4.0", "convert_batch", "poc-1")

    notes = catalog.warnings()

    assert any("poc-1" in note and "manual in_scope=false" in note for note in notes)


def test_triage_summary_counts_scope(project_root: Path, state: StateStore) -> None:
    catalog = _scoped(project_root, state, "tibco-ebx")
    _fetch(catalog, make_product("tibco-ebx", product_code="ebx"), make_product("tibco-ems", product_code="ems"))
    catalog.set_product_field("tibco-ems", "in_scope", "false")

    summary = catalog.triage_summary()

    # Reported as slugs, which is what identifies a product now that the code does not.
    assert summary["out_of_scope"] == ["tibco-ebx", "tibco-ems"]
    assert summary["scope_counts"] == {"manual": 1, "scope_rule": 1, "default": 0}


def test_a_catalog_with_no_config_excludes_nothing(catalog: CatalogManager, sample_product: Product) -> None:
    """The scope file is optional; a manager built without a ConfigManager has no rules."""
    stats = _fetch(catalog, sample_product)

    assert stats.products_out_of_scope == 0
    assert catalog.get_product("tibco-ems").in_scope is True


# -- end-of-support retirement: the second gate (architecture.md §3.11) ------


def _eos(
    project_root: Path,
    state: StateStore,
    rows: tuple[tuple[str, str, str, str], ...] = (),
    aliases: str = "",
    out_of_scope: tuple[str, ...] = (),
) -> CatalogManager:
    """A catalog manager over an end-of-support report carrying exactly `rows`.

    Each row is `(report name, version, status, retirement date)` in the report's
    own `MM-DD-YYYY` spelling. Built fresh each call for the same reason `_scoped`
    is: `ConfigManager` caches both files, so rewriting one mid-test would
    otherwise change nothing -- which is exactly the shape of the re-apply tests
    below.
    """
    report = project_root / "config" / "eos" / "report.csv"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "Product Name,Version,Release Status,Retirement Date,Last Updated On,\n"
        + "".join(f"{name},{version},{status},{date},01-05-2025,\n" for name, version, status, date in rows),
        encoding="utf-8-sig",
    )
    (project_root / "config" / "eos.yaml").write_text(f"report: eos/report.csv\n{aliases}", encoding="utf-8")
    body = "out_of_scope:\n" + "".join(f'  - slug: {slug}\n    reason: "test"\n' for slug in out_of_scope)
    (project_root / "config" / "scope.yaml").write_text(body, encoding="utf-8")
    return CatalogManager(
        project_root / "config" / "products.csv",
        project_root / "config" / "versions.csv",
        state,
        ConfigManager(root_dir=project_root),
    )


def _ems(*versions: str) -> Product:
    """One product whose every version is active and convert-eligible."""
    return make_product(
        "tibco-ems",
        product_code="ems",
        versions={v: make_version("tibco-ems", v, zip_url=f"https://x/{v}.zip") for v in versions},
    )


RETIRED_8_6 = (("TIBCO EMS", "8.6.0", "Retired", "12-31-2024"),)


def test_a_retired_version_is_excluded_from_the_work(project_root: Path, state: StateStore) -> None:
    catalog = _eos(project_root, state, RETIRED_8_6)

    _fetch(catalog, _ems("10.4.0", "8.6.0"))

    assert [v.version for _, v in catalog.iter_versions(eligible_only=True)] == ["10.4.0"]


def test_a_retired_version_is_never_absent_from_the_books(project_root: Path, state: StateStore) -> None:
    """Reporting and inventory callers still see it -- §3.10's rule, applied to §3.11."""
    catalog = _eos(project_root, state, RETIRED_8_6)

    _fetch(catalog, _ems("10.4.0", "8.6.0"))

    assert [v.version for _, v in catalog.iter_versions()] == ["10.4.0", "8.6.0"]


def test_only_retired_gates_conversion(project_root: Path, state: StateStore) -> None:
    """`Retirement Announced` names a version that is supported *today*.

    Treating it as retired would drop 94 eligible versions whose retirement dates
    are a year or more out -- versions the pipeline exists to convert.
    """
    catalog = _eos(
        project_root,
        state,
        (
            ("TIBCO EMS", "8.6.0", "Retired", "12-31-2024"),
            ("TIBCO EMS", "9.1.0", "Retirement Announced", "12-31-2027"),
            ("TIBCO EMS", "10.4.0", "GA", "12-31-2030"),
        ),
    )

    _fetch(catalog, _ems("10.4.0", "9.1.0", "8.6.0", "11.0.0"))

    # 11.0.0 has no row at all: absence is silence, not a verdict.
    assert [v.version for _, v in catalog.iter_versions(eligible_only=True)] == ["11.0.0", "10.4.0", "9.1.0"]


def test_a_version_missing_from_a_covered_product_stays_eligible(
    project_root: Path, state: StateStore
) -> None:
    """The report covers `TIBCO EMS` but says nothing about 10.4.0. That is not a retirement."""
    catalog = _eos(project_root, state, RETIRED_8_6)

    _fetch(catalog, _ems("10.4.0", "8.6.0"))

    version = catalog.get_version("tibco-ems", "10.4.0")
    assert version.release_status is ReleaseStatus.UNKNOWN
    assert version.release_status_source is ReleaseStatusSource.UNKNOWN
    assert version.convert_eligible is True


def test_a_product_absent_from_the_report_is_untouched(project_root: Path, state: StateStore) -> None:
    """2,004 of the catalog's 2,506 unknown versions are unknown for exactly this reason."""
    catalog = _eos(project_root, state, RETIRED_8_6)

    _fetch(catalog, make_product("tibco-ebx", versions={"6.2.0": make_version("tibco-ebx", "6.2.0")}))

    assert catalog.get_version("tibco-ebx", "6.2.0").release_status is ReleaseStatus.UNKNOWN
    assert len(catalog.iter_versions(eligible_only=True)) == 1


def test_the_verdict_and_its_date_round_trip_through_the_csv(project_root: Path, state: StateStore) -> None:
    catalog = _eos(project_root, state, RETIRED_8_6)
    _fetch(catalog, _ems("8.6.0"))

    row = read_rows(catalog.versions_path)[0]
    assert row["release_status"] == "retired"
    assert row["retirement_date"] == "2024-12-31"
    assert row["release_status_source"] == "eos_report"

    reloaded = _reload(catalog).get_version("tibco-ems", "8.6.0")
    assert reloaded.release_status is ReleaseStatus.RETIRED
    # Re-read verbatim: running the ISO value back through the permissive date
    # parser is what would turn it into something else on the second round trip.
    assert reloaded.retirement_date == "2024-12-31"


def test_a_version_discovered_after_the_report_landed_is_retired_on_arrival(
    project_root: Path, state: StateStore
) -> None:
    """The §3.10 argument, restated for retirement: policy written as a cleared flag decays.

    A fetch defaults a newly discovered version to `convert_eligible=true`, so a
    retirement applied once and never re-checked would be undone by the next crawl.
    """
    catalog = _eos(project_root, state, RETIRED_8_6)
    _fetch(catalog, _ems("10.4.0"))

    _fetch(_eos(project_root, state, RETIRED_8_6), _ems("10.4.0", "8.6.0"))

    assert _eos(project_root, state, RETIRED_8_6).get_version("tibco-ems", "8.6.0").release_status is (
        ReleaseStatus.RETIRED
    )


def test_a_manual_verdict_survives_a_fetch(project_root: Path, state: StateStore) -> None:
    """The escape hatch: a retired version being converted anyway must stay converted."""
    catalog = _eos(project_root, state, RETIRED_8_6)
    _fetch(catalog, _ems("8.6.0"))
    catalog.set_version_field("tibco-ems", "8.6.0", "release_status", "ga")

    _fetch(_eos(project_root, state, RETIRED_8_6), _ems("8.6.0"))

    version = _eos(project_root, state, RETIRED_8_6).get_version("tibco-ems", "8.6.0")
    assert (version.release_status, version.release_status_source) == (
        ReleaseStatus.GA,
        ReleaseStatusSource.MANUAL,
    )


def test_a_manual_retirement_also_pins_to_manual(project_root: Path, state: StateStore) -> None:
    """The other direction: retiring by hand a version the report has not reached."""
    catalog = _eos(project_root, state)
    _fetch(catalog, _ems("8.6.0"))

    catalog.set_version_field("tibco-ems", "8.6.0", "release_status", "retired")

    version = _reload(catalog).get_version("tibco-ems", "8.6.0")
    assert version.release_status_source is ReleaseStatusSource.MANUAL
    assert catalog.iter_versions(eligible_only=True) == []


def test_removing_an_alias_restores_the_version(project_root: Path, state: StateStore) -> None:
    """Step 3 of the resolution actively resets, so a correction really does take effect."""
    alias = 'aliases:\n  - report_name: "EMS Classic"\n    slug: tibco-ems\n'
    rows = (("EMS Classic", "8.6.0", "Retired", "12-31-2024"),)
    _fetch(_eos(project_root, state, rows, aliases=alias), _ems("8.6.0"))

    _fetch(_eos(project_root, state, rows), _ems("8.6.0"))

    version = _eos(project_root, state, rows).get_version("tibco-ems", "8.6.0")
    assert version.release_status is ReleaseStatus.UNKNOWN
    assert version.retirement_date is None
    assert version.release_status_source is ReleaseStatusSource.UNKNOWN


def test_a_dropped_report_row_restores_the_version(project_root: Path, state: StateStore) -> None:
    """A corrected report is the common case; it must not need a hand-edit to land."""
    _fetch(_eos(project_root, state, RETIRED_8_6), _ems("8.6.0"))

    _fetch(_eos(project_root, state), _ems("8.6.0"))

    assert _eos(project_root, state).get_version("tibco-ems", "8.6.0").release_status is ReleaseStatus.UNKNOWN


def test_apply_eos_re_resolves_without_a_crawl(project_root: Path, state: StateStore) -> None:
    """A new report should cost a CSV swap, not an hour of walking the docsite."""
    _fetch(_eos(project_root, state), _ems("10.4.0", "8.6.0"))

    stats = _eos(project_root, state, RETIRED_8_6).apply_eos()

    assert stats.versions_retired == 1
    assert _eos(project_root, state, RETIRED_8_6).get_version("tibco-ems", "8.6.0").release_status is (
        ReleaseStatus.RETIRED
    )


def test_a_product_left_with_nothing_convertible_is_named(project_root: Path, state: StateStore) -> None:
    """Never a count: a product with no convertible version publishes no docs at all."""
    catalog = _eos(
        project_root,
        state,
        (("TIBCO EMS", "10.4.0", "Retired", "12-31-2024"), ("TIBCO EMS", "8.6.0", "Retired", "12-31-2024")),
    )

    stats = _fetch(catalog, _ems("10.4.0", "8.6.0"))

    assert stats.versions_retired == 2
    assert stats.products_fully_retired == ["tibco-ems"]


def test_a_partly_retired_product_is_not_reported_as_emptied(project_root: Path, state: StateStore) -> None:
    catalog = _eos(project_root, state, RETIRED_8_6)

    stats = _fetch(catalog, _ems("10.4.0", "8.6.0"))

    assert (stats.versions_retired, stats.products_fully_retired) == (1, [])


def test_retirement_is_measured_over_the_convertible_population(
    project_root: Path, state: StateStore
) -> None:
    """An out-of-scope product's retirements cost the run nothing, so they are not counted.

    Counted over the whole catalog the figure is four times larger and almost
    entirely restates the archive flag -- alarming, and meaningless.
    """
    catalog = _eos(project_root, state, RETIRED_8_6, out_of_scope=("tibco-ems",))

    stats = _fetch(catalog, _ems("10.4.0", "8.6.0"))

    assert (stats.versions_retired, stats.products_fully_retired) == (0, [])


def test_an_ineligible_retired_version_is_not_counted_twice(project_root: Path, state: StateStore) -> None:
    """It was already excluded; retirement changes nothing about this row."""
    catalog = _eos(project_root, state, RETIRED_8_6)
    product = _ems("10.4.0")
    product.versions["8.6.0"] = make_version("tibco-ems", "8.6.0", is_archived=True, convert_eligible=False)

    stats = _fetch(catalog, product)

    assert stats.versions_retired == 0


def test_a_batch_tag_on_a_retired_version_warns(project_root: Path, state: StateStore) -> None:
    """The row reads as scheduled and will never run, so the reason has to be named."""
    catalog = _eos(project_root, state, RETIRED_8_6)
    _fetch(catalog, _ems("8.6.0"))

    catalog.set_version_field("tibco-ems", "8.6.0", "convert_batch", "poc-1")

    notes = catalog.warnings()
    assert any("poc-1" in note and "the end-of-support report" in note for note in notes)


def test_a_manually_retired_version_in_a_batch_names_the_hand_edit(
    project_root: Path, state: StateStore
) -> None:
    """The two are undone differently, so the warning must not conflate them."""
    catalog = _eos(project_root, state)
    _fetch(catalog, _ems("8.6.0"))
    catalog.set_version_field("tibco-ems", "8.6.0", "release_status", "retired")

    catalog.set_version_field("tibco-ems", "8.6.0", "convert_batch", "poc-1")

    assert any("a manual release_status=retired" in note for note in catalog.warnings())


def test_a_stale_alias_warns(project_root: Path, state: StateStore) -> None:
    """Support renaming a product silently stops the alias retiring anything."""
    catalog = _eos(
        project_root,
        state,
        RETIRED_8_6,
        aliases='aliases:\n  - report_name: "Renamed Upstream"\n    slug: tibco-ebx\n',
    )
    _fetch(catalog, _ems("8.6.0"))

    notes = [note for note in catalog.warnings() if "eos.yaml" in note]
    assert len(notes) == 1
    assert "Renamed Upstream" in notes[0]


def test_an_unknown_release_status_is_rejected(project_root: Path, state: StateStore) -> None:
    catalog = _eos(project_root, state)
    _fetch(catalog, _ems("8.6.0"))

    with pytest.raises(ValueError):
        catalog.set_version_field("tibco-ems", "8.6.0", "release_status", "end-of-life")


def test_eos_coverage_counts_products_the_report_reaches(project_root: Path, state: StateStore) -> None:
    """Reported so 'nothing retired' reads as coverage rather than as a clean bill."""
    catalog = _eos(project_root, state, RETIRED_8_6)
    _fetch(catalog, _ems("8.6.0"), make_product("tibco-ebx", versions={"6.2.0": make_version("tibco-ebx", "6.2.0")}))

    assert catalog.eos_coverage() == (1, 2)


def test_triage_summary_counts_release_status(project_root: Path, state: StateStore) -> None:
    catalog = _eos(
        project_root,
        state,
        (("TIBCO EMS", "8.6.0", "Retired", "12-31-2024"), ("TIBCO EMS", "9.1.0", "GA", "12-31-2030")),
    )
    _fetch(catalog, _ems("10.4.0", "9.1.0", "8.6.0"))

    summary = catalog.triage_summary()

    assert summary["release_status_counts"] == {
        "retired": 1,
        "retirement-announced": 0,
        "ga": 1,
        "unknown": 1,
    }
    assert summary["versions_retired"] == 1


def test_a_catalog_with_no_config_retires_nothing(catalog: CatalogManager, sample_product: Product) -> None:
    """The report is optional; a manager built without a ConfigManager has none."""
    stats = _fetch(catalog, sample_product)

    assert (stats.versions_retired, stats.products_fully_retired) == (0, [])
    assert catalog.get_version("tibco-ems", "10.4.0").release_status is ReleaseStatus.UNKNOWN


def test_the_shipped_report_retires_the_measured_set(repo_root: Path) -> None:
    """A guard on the real three files: products.csv, versions.csv and eos.yaml.

    The figures are what the 2026-09-10 report costs the *convertible* population,
    and they are asserted exactly rather than as a floor: a report swap that moves
    them is a decision to look at, not something to discover after a conversion run.
    """
    manager = CatalogManager(
        repo_root / "config" / "products.csv",
        repo_root / "config" / "versions.csv",
        config=ConfigManager(root_dir=repo_root),
    )

    summary = manager.triage_summary()

    assert summary["versions_retired"] == 128
    assert len(summary["products_fully_retired"]) == 11
    assert manager.eos_coverage() == (251, 634)


def test_the_shipped_report_never_retires_a_look_alike(repo_root: Path) -> None:
    """`Spotfire Analytics` shares 0 of 7 versions with `tibco-analytics` -- see eos.yaml.

    The one rejected alias that would have been actively wrong. Asserted here as
    well as in test_config, because the config test only proves the mapping is
    absent while this proves no version of the product was retired by it.
    """
    report = ConfigManager(root_dir=repo_root).load_eos()

    assert report.entries.get("tibco-analytics") is None


# -- the catalog key: slug, not product_code (architecture.md §3.1) ----------

# Every `product_code` the 2026-09-09 crawl of all 634 products found on more than
# one product, with the slugs carrying it. Enumerated rather than sampled because
# each pair is a distinct way the old code-keyed catalog silently lost a product:
# a rebrand that kept the old code (`tibco-clarity` / `-enterprise-edition`), an
# edition split (`bwpluginedi-healthcare`), a renamed product whose code outlived
# the name (`fsi`), and one -- `stat-sts` -- that straddles the scope boundary.
SHARED_CODES = {
    "business-studio-analyst-edition": (
        "tibco-business-studio-analyst-edition",
        "tibco-business-studio-for-analysts",
    ),
    "bwpluginedi-healthcare": (
        "tibco-activematrix-businessworks-plug-in-for-edi",
        "tibco-activematrix-businessworks-plug-in-for-edi-healthcare-edition",
    ),
    "clarity-dt": ("tibco-clarity", "tibco-clarity-enterprise-edition"),
    "fsi": ("tibco-fulfillment-subscriber-inventory", "tibco-product-and-service-inventory-2-1-0"),
    "loglmi": ("tibco-loglogic", "tibco-loglogic-log-management-intelligence"),
    "sfire-cloud": ("tibco-cloud-spotfire-14-6-0", "tibco-cloud-spotfire-14-6-2"),
    "sfire-dscpn": (
        "tibco-data-science-package-for-notebooks",
        "tibco-spotfire-data-science-package-for-notebooks",
    ),
    "spotfire": ("spotfire", "tibco-spotfire-general", "tibco-spotfire-professional"),
    "stat-ext": ("spotfire-statistica-integration", "tibco-data-science-for-tibco-spotfire-analyst"),
    "stat-sts": ("spotfire-service-for-statistica", "tibco-data-science-service-for-tibco-spotfire"),
}


@pytest.mark.parametrize(("code", "slugs"), sorted(SHARED_CODES.items()))
def test_products_sharing_a_code_round_trip_as_separate_rows(
    catalog: CatalogManager, code: str, slugs: tuple[str, ...]
) -> None:
    """Twenty-one real products share ten codes; none of them may collapse into one row.

    Keyed on `product_code` this wrote `len(slugs)` rows and read back one, so the
    losing products lost every column the user had edited and every version they had.
    """
    incoming = []
    for index, slug in enumerate(slugs):
        product = make_product(slug, product_code=code, display_name=slug.upper())
        product.versions[f"{index + 1}.0.0"] = make_version(slug, f"{index + 1}.0.0")
        incoming.append(product)

    _fetch(catalog, *incoming)

    reloaded = _reload(catalog).load()
    assert sorted(s for s in reloaded.products if reloaded.products[s].product_code == code) == sorted(slugs)
    # Each keeps its own versions rather than inheriting whichever row was written last.
    for index, slug in enumerate(slugs):
        assert set(reloaded.products[slug].versions) == {f"{index + 1}.0.0"}


def test_the_one_scope_mixed_collision_is_decided_per_product_not_per_code(
    project_root: Path, state: StateStore
) -> None:
    """`stat-sts` by name: the collision that made this re-key urgent rather than tidy.

    Both products carry `product_code=stat-sts`, but only `spotfire-service-for-statistica`
    is listed in `scope.yaml`. Keyed on the code, whichever of the two merged second
    overwrote the other's `in_scope`, so *merge order* -- effectively the docsite's A-to-Z
    ordering -- decided whether four excluded versions got converted.
    """
    excluded = "spotfire-service-for-statistica"
    included = "tibco-data-science-service-for-tibco-spotfire"
    manager = _scoped(project_root, state, excluded)

    stats = _fetch(
        manager,
        make_product(included, product_code="stat-sts"),
        make_product(excluded, product_code="stat-sts"),
    )

    assert stats.products_out_of_scope == 1
    reloaded = _reload(manager)
    assert reloaded.get_product(excluded).in_scope is False
    assert reloaded.get_product(included).in_scope is True


def test_the_scope_verdict_does_not_depend_on_merge_order(project_root: Path, state: StateStore) -> None:
    """The same fetch with the two `stat-sts` products swapped must reach the same catalog."""
    excluded = "spotfire-service-for-statistica"
    included = "tibco-data-science-service-for-tibco-spotfire"
    manager = _scoped(project_root, state, excluded)

    _fetch(manager, make_product(excluded, product_code="stat-sts"), make_product(included, product_code="stat-sts"))

    reloaded = _reload(manager)
    assert reloaded.get_product(excluded).in_scope is False
    assert reloaded.get_product(included).in_scope is True


def test_a_duplicate_slug_is_a_validation_error(catalog: CatalogManager) -> None:
    """Only a hand-edit can produce one, and `load()` has already dropped a row by then.

    Reported rather than raised, so the sheet still opens -- but reported loudly, because
    a `save()` on the collapsed catalog would write the loss back over the file.
    """
    catalog.products_path.write_text(
        "slug,product_code,display_name\n"
        "tibco-ems,ems,TIBCO EMS\n"
        "tibco-ems,ems,TIBCO EMS (copy)\n",
        encoding="utf-8",
    )
    catalog.versions_path.write_text("slug,version\n", encoding="utf-8")

    problems = catalog.validate()

    assert any("more than one row with slug 'tibco-ems'" in problem for problem in problems)


def test_a_product_code_shared_by_two_products_is_not_silently_resolved(catalog: CatalogManager) -> None:
    """`--product stat-sts` must ask rather than pick, and must say what to pick from."""
    _fetch(
        catalog,
        make_product("spotfire-service-for-statistica", product_code="stat-sts"),
        make_product("tibco-data-science-service-for-tibco-spotfire", product_code="stat-sts"),
    )

    with pytest.raises(CatalogError) as excinfo:
        catalog.resolve_slug("stat-sts")

    message = str(excinfo.value)
    assert "spotfire-service-for-statistica" in message
    assert "tibco-data-science-service-for-tibco-spotfire" in message


def test_an_unambiguous_product_code_still_resolves(catalog: CatalogManager, sample_product: Product) -> None:
    """The short code stays typeable: nobody should have to write out the slug for `ems`."""
    _fetch(catalog, sample_product)

    assert catalog.resolve_slug("ems") == "tibco-ems"
    assert catalog.resolve_slug("tibco-ems") == "tibco-ems"
    # Unknown selectors pass through, so `--product <slug>` works before the first fetch.
    assert catalog.resolve_slug("never-heard-of-it") == "never-heard-of-it"


def test_the_full_discovery_dump_merges_and_re_merges_cleanly(
    catalog: CatalogManager, discovered_products: list[Product]
) -> None:
    """The regression this phase exists for, at full scale: 634 products, twice.

    The bug surfaced as a second `catalog fetch --all` aborting with blocked deletions
    against a catalog the *first* fetch had just written -- because the code-keyed rows
    had collapsed, so the versions of every losing product were missing on re-read and
    read as upstream removals. Re-merging the identical dump must be a no-op.
    """
    first = _fetch(catalog, *discovered_products)

    assert first.products_added == 634
    assert first.deletions_blocked == []

    second = _reload(catalog).merge_fetch_results(discovered_products)

    assert second.deletions_blocked == []
    assert second.products_added == 0
    assert second.versions_added == 0


# -- convert_batch: run scheduling, orthogonal to eligibility ----------------


def test_convert_batch_round_trips_through_the_csv(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    catalog.set_version_field("tibco-ems", "10.4.0", "convert_batch", "poc-1")

    assert read_rows(catalog.versions_path)[0]["convert_batch"] == "poc-1"
    assert _reload(catalog).get_version("tibco-ems", "10.4.0").convert_batch == "poc-1"


def test_convert_batch_is_normalized_to_lowercase(catalog: CatalogManager, sample_product: Product) -> None:
    """`POC-1` and `poc-1 ` must select the same rows as `poc-1`."""
    _fetch(catalog, sample_product)

    catalog.set_version_field("tibco-ems", "10.4.0", "convert_batch", "  POC-1 ")

    assert catalog.get_version("tibco-ems", "10.4.0").convert_batch == "poc-1"
    assert len(catalog.iter_versions(batch="POC-1")) == 1


def test_a_batch_tag_survives_a_refetch(catalog: CatalogManager, sample_product: Product) -> None:
    """Discovery has nothing to say about scheduling, so it must never clear the column."""
    _fetch(catalog, sample_product)
    catalog.set_version_field("tibco-ems", "10.4.0", "convert_batch", "wave-2")

    _fetch(_reload(catalog), sample_product)

    assert _reload(catalog).get_version("tibco-ems", "10.4.0").convert_batch == "wave-2"


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
    catalog.set_version_field("tibco-ems", "8.6.0", "convert_batch", "poc-1")

    assert len(catalog.iter_versions(batch="poc-1")) == 1
    assert catalog.iter_versions(batch="poc-1", eligible_only=True) == []


def test_batches_counts_only_scheduled_versions(catalog: CatalogManager, sample_product: Product) -> None:
    ebx = make_product("ebx", family="data_management")
    ebx.versions = {"6.2.0": make_version("ebx", "6.2.0")}
    _fetch(catalog, sample_product, ebx)
    catalog.set_version_field("tibco-ems", "10.4.0", "convert_batch", "poc-1")
    catalog.set_version_field("ebx", "6.2.0", "convert_batch", "poc-1")

    assert catalog.batches() == {"poc-1": 2}


def test_batches_is_empty_when_nothing_is_scheduled(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    assert catalog.batches() == {}


# -- warnings: accepted, but worth saying out loud ---------------------------


def test_scheduled_but_ineligible_version_warns(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)
    catalog.set_version_field("tibco-ems", "8.6.0", "convert_batch", "poc-1")

    notes = catalog.warnings()

    assert any("convert_eligible=false" in note and "8.6.0" in note for note in notes)


def test_an_identified_but_unconvertible_engine_warns(catalog: CatalogManager, sample_product: Product) -> None:
    """A named engine makes the row *look* settled, so the missing handler has to be said."""
    _fetch(catalog, sample_product)
    catalog.record_detected_engine("tibco-ems", "10.4.0", SourceEngine.R_HELP)

    notes = catalog.warnings()

    assert any("r-help" in note and "no Stage 5 handler" in note for note in notes)


def test_a_convertible_engine_produces_no_handler_warning(
    catalog: CatalogManager, sample_product: Product
) -> None:
    _fetch(catalog, sample_product)
    catalog.record_detected_engine("tibco-ems", "10.4.0", SourceEngine.FLARE)

    assert not any("no Stage 5 handler" in note for note in catalog.warnings())


def test_auto_is_not_reported_as_an_unconvertible_engine(
    catalog: CatalogManager, sample_product: Product
) -> None:
    """`auto` is also unconvertible, but it means "undetected" -- a different report line."""
    _fetch(catalog, sample_product)

    assert not any("no Stage 5 handler" in note for note in catalog.warnings())


def test_an_ineligible_unconvertible_engine_stays_quiet(
    catalog: CatalogManager, sample_product: Product
) -> None:
    """Out of scope already: the warning would name nothing the user can act on."""
    _fetch(catalog, sample_product)
    catalog.record_detected_engine("tibco-ems", "8.6.0", SourceEngine.MKDOCS)

    assert not any("no Stage 5 handler" in note for note in catalog.warnings())


def test_an_undeclared_family_warns_but_does_not_fail(taxonomy_config, catalog: CatalogManager) -> None:
    """A family typed straight into products.csv is accepted; the folder is auto-registered."""
    catalog.config = taxonomy_config
    product = make_product("newthing", family="streaming_analytics")
    product.versions = {"1.0.0": make_version("newthing", "1.0.0", zip_url="https://x/z.zip")}
    _fetch(catalog, product)

    assert catalog.validate() == []
    notes = catalog.warnings()
    assert any("streaming_analytics" in note for note in notes)
    # The BU's `repo_slug` applies even though the family has none of its own.
    assert any("families/en-us-tib-streaming-analytics" in note for note in notes)


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


# -- zip_source: where the package came from ---------------------------------


def test_zip_source_defaults_to_auto_and_round_trips(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    assert read_rows(catalog.versions_path)[0]["zip_source"] == "auto"

    catalog.set_version_field("tibco-ems", "10.4.0", "zip_source", "manual")

    assert read_rows(catalog.versions_path)[0]["zip_source"] == "manual"
    assert _reload(catalog).get_version("tibco-ems", "10.4.0").zip_source is ZipSource.MANUAL


def test_a_manual_package_is_exempt_from_the_missing_zip_url_check(catalog: CatalogManager) -> None:
    """The package is already at the canonical path, so there is no URL to be missing."""
    product = make_product("ems")
    product.versions = {"1.0.0": make_version("ems", "1.0.0", convert_eligible=True)}
    _fetch(catalog, product)
    catalog.set_version_field("ems", "1.0.0", "zip_source", "manual")

    assert catalog.validate() == []


def test_a_manual_package_with_a_discovered_url_warns_without_blocking(
    catalog: CatalogManager, sample_product: Product
) -> None:
    """Discovery has since found an endpoint, so the hand-supplied ZIP may be redundant."""
    _fetch(catalog, sample_product)
    catalog.set_version_field("tibco-ems", "10.4.0", "zip_source", "manual")

    assert catalog.validate() == []
    assert any("--zip-source auto" in note for note in catalog.warnings())


def test_a_refetch_never_clears_zip_source(catalog: CatalogManager, sample_product: Product) -> None:
    """It records a human's supply decision; discovery has no opinion to contribute."""
    _fetch(catalog, sample_product)
    catalog.set_version_field("tibco-ems", "10.4.0", "zip_source", "manual")

    _fetch(_reload(catalog), sample_product)

    assert _reload(catalog).get_version("tibco-ems", "10.4.0").zip_source is ZipSource.MANUAL


def test_a_refetch_still_updates_zip_url_on_a_manual_row(catalog: CatalogManager) -> None:
    """zip_url stays merged so 'discovery now has a URL' remains a computable warning."""
    product = make_product("ems")
    product.versions = {"1.0.0": make_version("ems", "1.0.0")}
    _fetch(catalog, product)
    catalog.set_version_field("ems", "1.0.0", "zip_source", "manual")

    found = make_product("ems")
    found.versions = {"1.0.0": make_version("ems", "1.0.0", zip_url="https://docs.tibco.com/found.zip")}
    _fetch(_reload(catalog), found)

    updated = _reload(catalog).get_version("ems", "1.0.0")
    assert updated.zip_url == "https://docs.tibco.com/found.zip"
    assert updated.zip_source is ZipSource.MANUAL


def test_an_unknown_zip_source_is_rejected(catalog: CatalogManager, sample_product: Product) -> None:
    _fetch(catalog, sample_product)

    with pytest.raises(ValueError):
        catalog.set_version_field("tibco-ems", "10.4.0", "zip_source", "somewhere-else")


# -- Stage 4 extraction inventory (architecture.md §3.9) ---------------------


def _extracted(catalog: CatalogManager) -> None:
    """Puts one product in the catalog and records an inventory against it."""
    _fetch(catalog, make_product("ems", versions={"10.4.0": make_version("ems", "10.4.0")}))
    catalog.record_extract_inventory("ems", "10.4.0", csh_sources=2, csh_names=358, api_files=4310, doc_files=19776)


def test_inventory_is_blank_until_the_version_is_extracted(catalog: CatalogManager) -> None:
    """Blank and zero are different answers: nothing has opened this package yet."""
    _fetch(catalog, make_product("ems", versions={"10.4.0": make_version("ems", "10.4.0")}))

    version = _reload(catalog).get_version("ems", "10.4.0")

    assert version.has_csh is None
    assert version.csh_names is None
    assert version.api_files is None
    assert version.doc_files is None
    row = read_rows(catalog.versions_path)[0]
    assert row["_has_csh"] == ""
    assert row["_doc_files"] == ""


def test_recorded_inventory_round_trips(catalog: CatalogManager) -> None:
    _extracted(catalog)

    version = _reload(catalog).get_version("ems", "10.4.0")

    assert version.has_csh is True
    assert version.csh_names == 358
    assert version.has_api_ref is True
    assert version.api_files == 4310
    assert version.doc_files == 19776


def test_measured_zero_survives_as_zero_not_blank(catalog: CatalogManager) -> None:
    """`0` means Stage 4 looked and found none -- it must not degrade to 'never ran'."""
    _fetch(catalog, make_product("ebx", versions={"6.2.0": make_version("ebx", "6.2.0")}))
    catalog.record_extract_inventory("ebx", "6.2.0", csh_sources=0, csh_names=0, api_files=0, doc_files=8104)

    version = _reload(catalog).get_version("ebx", "6.2.0")

    assert version.has_csh is False
    assert version.csh_names == 0
    assert version.has_api_ref is False
    assert version.api_files == 0


def test_a_csh_source_that_parses_to_nothing_is_a_distinct_state(catalog: CatalogManager) -> None:
    """The empty `<CatapultAliasFile />` case -- 28% of the corpus (architecture.md §5.3.1)."""
    _fetch(catalog, make_product("ebx", versions={"6.2.0": make_version("ebx", "6.2.0")}))
    catalog.record_extract_inventory("ebx", "6.2.0", csh_sources=3, csh_names=0, api_files=0, doc_files=8104)

    version = _reload(catalog).get_version("ebx", "6.2.0")

    assert version.has_csh is True
    assert version.csh_names == 0
    # A source that yields nothing is a measurement, not an inconsistency.
    assert catalog.warnings() == []


def test_a_fetch_never_touches_the_inventory(catalog: CatalogManager) -> None:
    """Discovery has never opened the package, so it has nothing true to say (§3.5)."""
    _extracted(catalog)

    _fetch(catalog, make_product("ems", versions={"10.4.0": make_version("ems", "10.4.0")}))

    version = _reload(catalog).get_version("ems", "10.4.0")
    assert version.csh_names == 358
    assert version.api_files == 4310
    assert version.doc_files == 19776


def test_inventory_survives_a_spreadsheet_round_trip(catalog: CatalogManager) -> None:
    _extracted(catalog)
    before = catalog.versions_path.read_bytes()

    _reload(catalog).save()

    assert catalog.versions_path.read_bytes() == before


def test_clearing_the_inventory_restores_never_extracted(catalog: CatalogManager) -> None:
    _extracted(catalog)

    assert catalog.clear_extract_inventory("ems", "10.4.0") is True

    version = _reload(catalog).get_version("ems", "10.4.0")
    assert version.has_csh is None
    assert version.doc_files is None


def test_recording_against_an_unknown_version_reports_failure(catalog: CatalogManager) -> None:
    assert catalog.record_extract_inventory("nope", "1.0", 0, 0, 0, 0) is False


def test_a_hand_edited_boolean_that_contradicts_its_count_warns(catalog: CatalogManager) -> None:
    """The tool writes both from one measurement, so this shape is only ever a hand-edit."""
    _extracted(catalog)
    catalog.get_version("ems", "10.4.0").has_api_ref = False
    catalog.save()

    notes = _reload(catalog).warnings()

    assert any("_has_api_ref=false but _api_files=4310" in note for note in notes)
    # Advisory only -- the next extract overwrites both, so it must never become a
    # blocking problem. (Other, unrelated problems may legitimately be present.)
    assert not any("_has_api_ref" in problem for problem in _reload(catalog).validate())
