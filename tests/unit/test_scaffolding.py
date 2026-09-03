"""Layout guards: the package modules and shipped config files must actually exist.

These exist because a missing subpackage or a broken console-script entrypoint is
silent -- the previous state of the repo had `pytest` exit green on zero tests and
`[project.scripts]` point at a `cli` module that did not exist.
"""

import importlib
from pathlib import Path

import pytest
import yaml

SUBPACKAGES = [
    "docushift.discovery",
    "docushift.downloader",
    "docushift.extractor",
    "docushift.engines",
    "docushift.transforms",
    "docushift.aem",
    "docushift.sync",
    "docushift.reporting",
    "docushift.utils",
]

CORE_MODULES = [
    "docushift.models",
    "docushift.config",
    "docushift.catalog",
    "docushift.state",
    "docushift.cli",
    "docushift.utils.csvio",
]


@pytest.mark.parametrize("module_name", SUBPACKAGES)
def test_subpackage_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_core_modules_import(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


def test_console_script_entrypoint_resolves() -> None:
    """`docushift = "docushift.cli:main"` in pyproject.toml must be callable."""
    from docushift.cli import main

    assert callable(main)


def test_docsite_config_declares_verified_endpoints(repo_root: Path) -> None:
    docsite = yaml.safe_load((repo_root / "config" / "docsite.yaml").read_text(encoding="utf-8"))

    assert docsite["base_url"] == "https://docs.tibco.com"
    endpoints = docsite["endpoints"]
    for key in ("a_to_z", "product", "product_archive", "product_list_by_suites", "bu_category_products"):
        assert endpoints[key].startswith("/api/")

    # Archived versions must never be convert-eligible by default.
    assert docsite["defaults"]["archived_convert_eligible"] is False
    assert docsite["defaults"]["active_convert_eligible"] is True
    # Engine is detected after extraction, never guessed at discovery time.
    assert docsite["defaults"]["engine"] == "auto"


def test_taxonomy_declares_families_and_rules_but_no_products(repo_root: Path) -> None:
    """Per-product assignment moved to products.csv in Phase 2."""
    taxonomy = yaml.safe_load((repo_root / "config" / "taxonomy.yaml").read_text(encoding="utf-8"))

    assert set(taxonomy["business_units"]) == {"tibco", "ibi"}
    for bu in taxonomy["business_units"].values():
        assert bu["families"]
        assert "products" not in bu
        assert "default_engine" not in bu

    assert taxonomy["rules"], "the taxonomy must ship keyword rules for family inference"


def test_every_taxonomy_rule_targets_a_declared_family(repo_root: Path) -> None:
    """A rule pointing at a family that does not exist would classify into nothing."""
    taxonomy = yaml.safe_load((repo_root / "config" / "taxonomy.yaml").read_text(encoding="utf-8"))

    for rule in taxonomy["rules"]:
        assert rule["match"], f"rule {rule} has no match tokens"
        assert "engine" not in rule
        families = taxonomy["business_units"][rule["bu"]]["families"]
        assert rule["family"] in families, f"{rule['bu']}/{rule['family']} is not a declared family"


def test_aem_templates_present(repo_root: Path) -> None:
    templates_dir = repo_root / "config" / "aem_templates"
    for name in ("toc.yml.j2", "nav.yml.j2", "meta.yml.j2", "index.md.j2"):
        assert (templates_dir / name).is_file()


def test_gitignore_covers_generated_artifacts(repo_root: Path) -> None:
    """ConfigManager creates output/ unconditionally, and state.db is a build artifact."""
    ignored = {
        line.strip()
        for line in (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert {"cache/", "output/", "*.db", ".venv/", "__pycache__/"} <= ignored
