"""Shared pytest fixtures for the DocuShift suite."""

import json
from pathlib import Path

import pytest

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.models import FamilySource, Product, ProductVersion
from docushift.state import StateStore

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
    """A ConfigManager rooted in a throwaway directory, with no taxonomy.yaml."""
    return ConfigManager(root_dir=project_root)


# Mirrors the families the shipped config/taxonomy.yaml declares, trimmed to the
# ones the fixtures below actually use.
TAXONOMY_YAML = """\
business_units:
  tibco:
    name: TIBCO
    families:
      messaging: {name: Messaging}
      data_management: {name: Data Management}
      general: {name: General}
  ibi:
    name: ibi
    families:
      webfocus: {name: WebFOCUS}
      general: {name: General}
rules: []
"""


@pytest.fixture
def taxonomy_config(project_root: Path) -> ConfigManager:
    """A ConfigManager whose taxonomy.yaml declares the families the fixtures use.

    Needed wherever a test asserts on family *validation*: the bare `config`
    fixture has no taxonomy file, so every family reads as undeclared there.
    """
    (project_root / "config" / "taxonomy.yaml").write_text(TAXONOMY_YAML, encoding="utf-8")
    return ConfigManager(root_dir=project_root)


@pytest.fixture
def state(project_root: Path) -> StateStore:
    """A StateStore backed by a throwaway SQLite file."""
    store = StateStore(project_root / "cache" / "state.db")
    yield store
    store.close()


@pytest.fixture
def catalog(project_root: Path, state: StateStore) -> CatalogManager:
    """An empty CatalogManager over a throwaway CSV pair, with snapshots enabled."""
    return CatalogManager(
        project_root / "config" / "products.csv",
        project_root / "config" / "versions.csv",
        state,
    )


@pytest.fixture
def stateless_catalog(project_root: Path) -> CatalogManager:
    """A CatalogManager with no state store, to exercise the no-snapshot path."""
    return CatalogManager(
        project_root / "config" / "products.csv",
        project_root / "config" / "versions.csv",
    )


@pytest.fixture
def sample_version() -> ProductVersion:
    """An active, convert-eligible version modelled on a real docsite record."""
    return ProductVersion(
        slug="tibco-ems",
        version="10.4.0",
        is_archived=False,
        convert_eligible=True,
        release_date="2025-11-04",
        zip_url="https://docs.tibco.com/pub/ems/10.4.0/doc/zip/tib_ems_10.4.0_doc.zip",
    )


@pytest.fixture
def archived_version() -> ProductVersion:
    """An archived version: inventoried for completeness, but not convert-eligible."""
    return ProductVersion(
        slug="tibco-ems",
        version="8.6.0",
        is_archived=True,
        convert_eligible=False,
        release_date="June 2020",
        zip_url="https://docs.tibco.com/pub/ems/tibco-ems-8-6-0_documentation.zip",
    )


@pytest.fixture
def sample_product(sample_version: ProductVersion, archived_version: ProductVersion) -> Product:
    """A product carrying one active and one archived version."""
    return Product(
        slug="tibco-ems",
        product_code="ems",
        display_name="TIBCO Enterprise Message Service™",
        bu="tibco",
        family="messaging",
        family_source=FamilySource.TAXONOMY_RULE,
        versions={
            sample_version.version: sample_version,
            archived_version.version: archived_version,
        },
    )


@pytest.fixture
def discovered_products() -> list[Product]:
    """The whole 2026-09-09 crawl, replayed from disk as discovery would hand it over.

    Committed as JSONL (one product per line) rather than as a JSON document, so the
    next re-crawl shows up in a diff as the products that changed and not as one
    159 KB line. Trimmed to the identity and version columns: engines, dates and
    document listings are not what this fixture is for, which is scale and the ten
    real `product_code` collisions hiding in it.
    """
    products = []
    for line in (FIXTURES_DIR / "discovery" / "crawl_2026_09_09.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        versions = record.pop("versions")
        product = Product(**record, family_source=FamilySource.TAXONOMY_RULE)
        for number in versions:
            product.versions[number] = ProductVersion(slug=product.slug, version=number)
        products.append(product)
    return products


def make_product(slug: str, **overrides) -> Product:
    """Builds a discovery-shaped product for merge tests.

    Takes the *slug*, which is the catalog key. `product_code` defaults to the same
    string so a test that does not care about the distinction reads as it always
    did; the tests that do care pass `product_code=` explicitly.
    """
    versions = overrides.pop("versions", {})
    defaults = {
        "slug": slug,
        "product_code": slug,
        "display_name": slug.upper(),
        "bu": "tibco",
        "family": "general",
        "family_source": FamilySource.UNCLASSIFIED,
    }
    defaults.update(overrides)
    return Product(**defaults, versions=versions)


def make_version(slug: str, version: str, **overrides) -> ProductVersion:
    """Builds a discovery-shaped version for merge tests."""
    defaults = {"slug": slug, "version": version}
    defaults.update(overrides)
    return ProductVersion(**defaults)
