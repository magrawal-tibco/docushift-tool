"""End-to-end smoke tests over a fresh project root.

The full multi-product conversion suite arrives with Phase 5; for now this asserts
that a clean checkout bootstraps its working directories and that the shipped
config files load through the real ConfigManager.
"""

from pathlib import Path

from click.testing import CliRunner

from docushift.cli import main
from docushift.config import ConfigManager


def test_fresh_root_bootstraps_working_directories(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["--root", str(tmp_path), "doctor"])

    assert result.exit_code == 0
    assert (tmp_path / "cache").is_dir()
    assert (tmp_path / "families").is_dir()
    assert (tmp_path / "output").is_dir()
    # Per-family folders are created by the downloader, not up front: an empty
    # workspace must not look like a migration that has already started.
    assert list((tmp_path / "families").iterdir()) == []


def test_shipped_config_loads_through_config_manager(repo_root: Path) -> None:
    cfg = ConfigManager(root_dir=repo_root)

    taxonomy = cfg.load_taxonomy()
    docsite = cfg.load_docsite()

    assert "tibco" in taxonomy["business_units"]
    assert docsite["endpoints"]["product"] == "/api/products/{slug}"
    assert cfg.aem_templates_dir.is_dir()
