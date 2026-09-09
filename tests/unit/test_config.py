"""Unit tests for ConfigManager path resolution, YAML loading, and taxonomy rules.

`resolve_product_info` is rule-driven rather than product-driven: per-product
bu/family assignment lives in config/products.csv, so the taxonomy only declares
which families exist and how to guess one. See docs/architecture.md §3.3.
"""

from pathlib import Path

import pytest

from docushift.config import ConfigManager
from docushift.models import FamilySource

RULES_YAML = (
    "business_units:\n"
    "  tibco:\n"
    "    name: TIBCO\n"
    "    families:\n"
    "      messaging: {name: Messaging}\n"
    "      general: {name: General}\n"
    "  ibi:\n"
    "    name: ibi\n"
    "    families:\n"
    "      webfocus: {name: WebFOCUS}\n"
    "rules:\n"
    '  - match: ["ems", "enterprise message service"]\n'
    "    bu: tibco\n"
    "    family: messaging\n"
    '  - match: ["webfocus"]\n'
    "    bu: ibi\n"
    "    family: webfocus\n"
)


def test_creates_working_directories(project_root: Path) -> None:
    ConfigManager(root_dir=project_root)

    assert (project_root / "cache").is_dir()
    assert (project_root / "families").is_dir()
    assert (project_root / "output").is_dir()


def test_family_workspace_paths(config: ConfigManager, project_root: Path) -> None:
    families = project_root / "families" / "en-us-tibco-data-management"

    assert config.family_folder_name("tibco", "data_management") == "en-us-tibco-data-management"
    assert config.family_dir("tibco", "data_management") == families
    assert config.downloads_dir("tibco", "data_management") == families / "downloads"
    assert config.extracted_dir("tibco", "data_management") == families / "extracted"
    assert config.archive_dir("tibco", "data_management") == families / "archive"


def test_download_and_extract_paths_are_keyed_by_the_catalog(config: ConfigManager) -> None:
    """Both paths derive from `product_code` + `version`, so state.db can round-trip them."""
    family = config.family_dir("tibco", "messaging")

    assert config.download_path("tibco", "messaging", "ems", "10.4.0") == family / "downloads" / "ems-10.4.0.zip"
    # Dots survive in the working tree; dots-to-dashes is a Stage 6 output concern.
    assert config.extract_path("tibco", "messaging", "ems", "10.4.0") == family / "extracted" / "ems" / "10.4.0"


def test_locale_prefix_is_configurable(project_root: Path) -> None:
    cfg = ConfigManager(root_dir=project_root, locale="fr-fr")

    assert cfg.family_folder_name("tibco", "messaging") == "fr-fr-tibco-messaging"


def test_family_folders_are_not_precreated(config: ConfigManager, project_root: Path) -> None:
    assert not config.family_dir("tibco", "messaging").exists()


def test_resolved_paths(config: ConfigManager, project_root: Path) -> None:
    assert config.taxonomy_path == project_root / "config" / "taxonomy.yaml"
    assert config.docsite_path == project_root / "config" / "docsite.yaml"
    assert config.aem_templates_dir == project_root / "config" / "aem_templates"
    assert config.state_db_path == project_root / "cache" / "state.db"


def test_catalog_paths_are_the_csv_pair(config: ConfigManager, project_root: Path) -> None:
    """The JSON catalog was retired in Phase 2 in favour of two CSVs."""
    assert config.products_path == project_root / "config" / "products.csv"
    assert config.versions_path == project_root / "config" / "versions.csv"
    assert not hasattr(config, "catalog_path")


def test_missing_taxonomy_yields_empty_structure(config: ConfigManager) -> None:
    assert config.load_taxonomy() == {"business_units": {}, "rules": []}


def test_missing_docsite_yields_empty_dict(config: ConfigManager) -> None:
    assert config.load_docsite() == {}


def test_taxonomy_is_cached(config: ConfigManager) -> None:
    config.taxonomy_path.write_text('business_units:\n  tibco:\n    name: "TIBCO"\n', encoding="utf-8")
    first = config.load_taxonomy()

    config.taxonomy_path.write_text("business_units: {}\n", encoding="utf-8")

    assert config.load_taxonomy() is first


def test_docsite_loads_endpoints(config: ConfigManager) -> None:
    config.docsite_path.write_text(
        'base_url: "https://docs.tibco.com"\nendpoints:\n  a_to_z: "/api/a_to_z"\n',
        encoding="utf-8",
    )

    assert config.load_docsite()["endpoints"]["a_to_z"] == "/api/a_to_z"


def test_families_are_listed_per_business_unit(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert set(config.families("tibco")) == {"messaging", "general"}
    assert set(config.families("ibi")) == {"webfocus"}
    assert config.families("nonexistent") == {}


def test_is_known_family_is_scoped_to_its_business_unit(config: ConfigManager) -> None:
    """`webfocus` is a real family, but not under `tibco`."""
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert config.is_known_family("ibi", "webfocus") is True
    assert config.is_known_family("tibco", "webfocus") is False


def test_resolve_product_info_matches_a_rule_by_product_code(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    info = config.resolve_product_info("ems", "TIBCO Enterprise Message Service")

    assert info["bu"] == "tibco"
    assert info["family"] == "messaging"
    assert info["family_source"] is FamilySource.TAXONOMY_RULE
    assert info["display_name"] == "TIBCO Enterprise Message Service"


def test_resolve_product_info_matches_a_rule_by_display_name_substring(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    info = config.resolve_product_info("wf-client", "ibi WebFOCUS Client")

    assert (info["bu"], info["family"]) == ("ibi", "webfocus")


def test_resolve_product_info_is_case_insensitive(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert config.resolve_product_info("EMS", "EMS")["family"] == "messaging"


def test_unmatched_products_are_unclassified_not_guessed(config: ConfigManager) -> None:
    """Flagging a product for triage beats inventing a family for it."""
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    info = config.resolve_product_info("unknown-thing", "Some Unlisted Product")

    assert (info["bu"], info["family"]) == ("tibco", "general")
    assert info["family_source"] is FamilySource.UNCLASSIFIED


def test_resolve_product_info_never_returns_an_engine(config: ConfigManager) -> None:
    """Engine is a per-version property detected from the package, not a rule output."""
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert "engine" not in config.resolve_product_info("ems", "EMS")


# -- scope.yaml (architecture.md §3.10) --------------------------------------


def test_missing_scope_yields_no_exclusions(config: ConfigManager) -> None:
    """A fresh checkout with no scope.yaml excludes nothing, rather than erroring."""
    assert config.load_scope() == {}


def test_scope_loads_slug_to_reason(config: ConfigManager) -> None:
    config.scope_path.write_text(
        "out_of_scope:\n"
        '  - slug: ebx\n    display_name: "TIBCO EBX"\n    reason: "EBX is out of scope"\n'
        "  - slug: spotfire\n    reason: \"Spotfire is out of scope\"\n",
        encoding="utf-8",
    )

    assert config.load_scope() == {"ebx": "EBX is out of scope", "spotfire": "Spotfire is out of scope"}


def test_scope_accepts_a_bare_slug_with_no_reason(config: ConfigManager) -> None:
    config.scope_path.write_text("out_of_scope:\n  - ebx\n  - Spotfire-Server\n", encoding="utf-8")

    assert config.load_scope() == {"ebx": "", "spotfire-server": ""}


def test_duplicate_scope_slug_is_an_error(config: ConfigManager) -> None:
    """Two entries for one product means two reasons, one of them about to vanish."""
    config.scope_path.write_text(
        'out_of_scope:\n  - slug: ebx\n    reason: "first"\n  - slug: ebx\n    reason: "second"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate out_of_scope slug 'ebx'"):
        config.load_scope()


def test_shipped_scope_lists_the_ebx_and_spotfire_products(repo_root: Path) -> None:
    """A guard on the real config/scope.yaml, verified against the A-to-Z index."""
    rules = ConfigManager(root_dir=repo_root).load_scope()

    assert len(rules) == 61
    for slug in ("tibco-ebx", "spotfire", "spotfire-server", "spotfire-desktop", "tibco-spotfire-for-apple-ipad"):
        assert slug in rules
    # The look-alikes the exact-slug rule exists to protect -- see §3.10.
    for slug in ("tibco-businessconnect-ebxml-protocol", "spotfire-data-streams", "spotfire-statistics-services"):
        assert slug not in rules


def test_shipped_taxonomy_rules_classify_known_products(repo_root: Path) -> None:
    """A guard on the real config/taxonomy.yaml, not a synthetic one."""
    cfg = ConfigManager(root_dir=repo_root)

    assert cfg.resolve_product_info("ems", "TIBCO Enterprise Message Service")["family"] == "messaging"
    assert cfg.resolve_product_info("spotfire", "TIBCO Spotfire")["family"] == "analytics"
    assert cfg.resolve_product_info("webfocus", "ibi WebFOCUS")["bu"] == "ibi"
    assert cfg.resolve_product_info("ebx", "TIBCO EBX")["family"] == "data_management"
