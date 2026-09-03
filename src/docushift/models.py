"""Data models for DocuShift."""

from enum import StrEnum
from typing import Any

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
    """Source documentation generator engine."""
    FLARE = "flare"
    DITA = "dita"
    WEBWORKS = "webworks"
    DOCBOOK = "docbook"
    AUTO = "auto"


class ProductVersion(BaseModel):
    """Represents a specific published version of a product."""
    version: str
    title: str | None = None
    slug: str | None = None
    folder_path: str | None = None
    zip_url: str | None = None
    zip_size: int | None = None
    zip_etag: str | None = None
    release_date: str | None = None
    is_archived: bool = False
    convert_eligible: bool = True
    source: str = "tool_fetch"  # "tool_fetch" or "manual"
    custom_override: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Product(BaseModel):
    """Represents a product entry in the catalog."""
    product_code: str
    display_name: str
    slug: str | None = None
    bu: str = "tibco"  # "tibco" or "ibi"
    family: str = "general"
    engine: SourceEngine = SourceEngine.FLARE
    docsite_id: int | None = None
    custom_override: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    versions: dict[str, ProductVersion] = Field(default_factory=dict)


class Catalog(BaseModel):
    """Master Additive Product Catalog."""
    version: str = "1.0"
    last_updated: str | None = None
    products: dict[str, Product] = Field(default_factory=dict)
