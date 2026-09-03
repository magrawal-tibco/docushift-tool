"""Shared pytest fixtures for the DocuShift suite."""

from pathlib import Path

import pytest

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.models import Product, ProductVersion

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    """The real repository root, for asserting on shipped config files."""
    return REPO_ROOT


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """An isolated project root with a config/ directory, safe to write to."""
    (tmp_path / "config").mkdir()
    return tmp_path


@pytest.fixture
def config(project_root: Path) -> ConfigManager:
    """A ConfigManager rooted in a throwaway directory."""
    return ConfigManager(root_dir=project_root)


@pytest.fixture
def catalog(project_root: Path) -> CatalogManager:
    """An empty CatalogManager backed by a throwaway catalog file."""
    return CatalogManager(project_root / "config" / "catalog.json")


@pytest.fixture
def sample_version() -> ProductVersion:
    """An active, convert-eligible version modelled on a real docsite record."""
    return ProductVersion(
        version="10.4.0",
        title="TIBCO Enterprise Message Service 10.4.0",
        folder_path="ems/10.4.0",
        zip_url="https://docs.tibco.com/pub/ems/10.4.0/doc/zip/tib_ems_10.4.0_doc.zip",
        release_date="2025-11-04",
        is_archived=False,
        convert_eligible=True,
    )


@pytest.fixture
def archived_version() -> ProductVersion:
    """An archived version, which is inventoried but not convert-eligible."""
    return ProductVersion(
        version="8.6.0",
        title="TIBCO Enterprise Message Service 8.6.0",
        zip_url="https://docs.tibco.com/pub/ems/tibco-ems-8-6-0_documentation.zip",
        release_date="June 2020",
        is_archived=True,
        convert_eligible=False,
    )


@pytest.fixture
def sample_product(sample_version: ProductVersion, archived_version: ProductVersion) -> Product:
    """A product carrying one active and one archived version."""
    return Product(
        product_code="ems",
        display_name="TIBCO Enterprise Message Service™",
        slug="tibco-ems",
        bu="tibco",
        family="messaging",
        versions={
            sample_version.version: sample_version,
            archived_version.version: archived_version,
        },
    )
