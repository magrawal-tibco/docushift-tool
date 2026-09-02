"""Data models for DocuShift."""

from enum import Enum
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field


class ConversionStatus(str, Enum):
    """Lifecycle status of a product version."""
    DISCOVERED = "DISCOVERED"
    DOWNLOADED = "DOWNLOADED"
    EXTRACTED = "EXTRACTED"
    CONVERTED = "CONVERTED"
    SYNCED = "SYNCED"
    ERROR = "ERROR"


class SourceEngine(str, Enum):
    """Source documentation generator engine."""
    FLARE = "flare"
    DITA = "dita"
    WEBWORKS = "webworks"
    DOCBOOK = "docbook"
    AUTO = "auto"


class ProductVersion(BaseModel):
    """Represents a specific published version of a product."""
    version: str
    title: Optional[str] = None
    slug: Optional[str] = None
    folder_path: Optional[str] = None
    zip_url: Optional[str] = None
    zip_size: Optional[int] = None
    zip_etag: Optional[str] = None
    release_date: Optional[str] = None
    is_archived: bool = False
    convert_eligible: bool = True
    source: str = "tool_fetch"  # "tool_fetch" or "manual"
    custom_override: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Product(BaseModel):
    """Represents a product entry in the catalog."""
    product_code: str
    display_name: str
    slug: Optional[str] = None
    bu: str = "tibco"  # "tibco" or "ibi"
    family: str = "general"
    engine: SourceEngine = SourceEngine.FLARE
    docsite_id: Optional[int] = None
    custom_override: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    versions: Dict[str, ProductVersion] = Field(default_factory=dict)


class Catalog(BaseModel):
    """Master Additive Product Catalog."""
    version: str = "1.0"
    last_updated: Optional[str] = None
    products: Dict[str, Product] = Field(default_factory=dict)
