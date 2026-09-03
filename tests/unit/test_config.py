"""Unit tests for ConfigManager path resolution and YAML loading."""

from pathlib import Path

from docushift.config import ConfigManager


def test_creates_working_directories(project_root: Path) -> None:
    ConfigManager(root_dir=project_root)

    assert (project_root / "cache" / "downloads").is_dir()
    assert (project_root / "cache" / "extracted").is_dir()
    assert (project_root / "output").is_dir()


def test_resolved_paths(config: ConfigManager, project_root: Path) -> None:
    assert config.taxonomy_path == project_root / "config" / "taxonomy.yaml"
    assert config.docsite_path == project_root / "config" / "docsite.yaml"
    assert config.aem_templates_dir == project_root / "config" / "aem_templates"
    assert config.state_db_path == project_root / "cache" / "state.db"


def test_missing_taxonomy_yields_empty_structure(config: ConfigManager) -> None:
    assert config.load_taxonomy() == {"business_units": {}}


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


def test_resolve_product_info_matches_taxonomy(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(
        "business_units:\n"
        "  tibco:\n"
        "    families:\n"
        "      messaging:\n"
        "        products:\n"
        "          ems:\n"
        '            name: "TIBCO Enterprise Message Service"\n',
        encoding="utf-8",
    )

    info = config.resolve_product_info("ems", "EMS")

    assert info["bu"] == "tibco"
    assert info["family"] == "messaging"
    assert info["display_name"] == "TIBCO Enterprise Message Service"


def test_resolve_product_info_infers_ibi(config: ConfigManager) -> None:
    info = config.resolve_product_info("webfocus", "ibi WebFOCUS")

    assert info["bu"] == "ibi"
    assert info["family"] == "webfocus"


def test_resolve_product_info_falls_back_to_tibco_general(config: ConfigManager) -> None:
    info = config.resolve_product_info("unknown-thing", "Some Unlisted Product")

    assert info["bu"] == "tibco"
    assert info["family"] == "general"
