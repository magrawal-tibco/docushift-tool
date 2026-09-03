"""Data models for DocuShift.

These are the in-memory representation. The on-disk form is the CSV pair
`config/products.csv` + `config/versions.csv` (docs/architecture.md §3); volatile
machine state (etags, sizes, checksums, per-stage status, free-form metadata)
deliberately lives in `state.db` instead, so the CSVs stay stable enough to leave
open in a spreadsheet.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ConversionStatus(StrEnum):
    """Lifecycle status of a product version."""
    DISCOVERED = "DISCOVERED"
    DOWNLOADED = "DOWNLOADED"
    EXTRACTED = "EXTRACTED"
    CONVERTED = "CONVERTED"
    SYNCED = "SYNCED"
    ERROR = "ERROR"


class SourceEngine(StrEnum):
    """Source documentation generator engine.

    A property of a *version*, not a product -- see docs/architecture.md §3.4.
    `AUTO` means "not yet determined"; it is never a guess.
    """
    FLARE = "flare"
    DITA = "dita"
    WEBWORKS = "webworks"
    DOCBOOK = "docbook"
    AUTO = "auto"


class EngineSource(StrEnum):
    """How a version's engine was arrived at. Precedence: manual > detected > auto."""
    MANUAL = "manual"
    DETECTED = "detected"
    AUTO = "auto"


class FamilySource(StrEnum):
    """How a product's family was arrived at. Precedence: first listed wins."""
    MANUAL = "manual"
    TAXONOMY_RULE = "taxonomy_rule"
    DOCSITE_CATEGORY = "docsite_category"
    UNCLASSIFIED = "unclassified"


class ProductVersion(BaseModel):
    """One published version of a product -- one row of `versions.csv`.

    `convert_eligible` and `convert_batch` answer two different questions and are
    deliberately separate columns -- see docs/architecture.md §3.7. Eligibility is
    long-lived policy ("may this version ever be converted?"); the batch is
    scheduling ("is it in *this* run?"). Collapsing them would mean a three-version
    POC required flipping `convert_eligible` to false on every other row.
    """
    product_code: str
    version: str
    is_archived: bool = False
    convert_eligible: bool = True
    # Free-text run label, e.g. `poc-1` or `wave-2`. Empty means "not scheduled".
    # Opt-in by design: tagging three rows is the whole cost of scoping a POC.
    convert_batch: str = ""
    release_date: str | None = None
    engine: SourceEngine = SourceEngine.AUTO
    engine_source: EngineSource = EngineSource.AUTO
    zip_url: str | None = None
    custom_override: bool = False


class Product(BaseModel):
    """One product -- one row of `products.csv`, plus its versions."""
    product_code: str
    display_name: str
    bu: str = "tibco"
    family: str = "general"
    family_source: FamilySource = FamilySource.UNCLASSIFIED
    slug: str | None = None
    custom_override: bool = False
    versions: dict[str, ProductVersion] = Field(default_factory=dict)


class Catalog(BaseModel):
    """The master additive product catalog."""
    products: dict[str, Product] = Field(default_factory=dict)
