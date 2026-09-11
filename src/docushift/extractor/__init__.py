"""Stage 4: ZIP extractor & asset/CSH analyzer.

`safe_unzip` landed in Phase 4a, since `archive download --extract` needs it.
`unpacker` is Phase 4b-1: unpack, then identify the engine and its output roots.
`inventory` is Phase 4b-2: the one walk that partitions API-reference files,
categorises assets by destination, locates the CSH sources, and writes the five
`versions.csv` columns. See docs/planning.md.
"""

from docushift.extractor.inventory import (
    AssetCategory,
    Bucket,
    Destination,
    Inventory,
    inventory_tree,
)
from docushift.extractor.safe_unzip import UnsafeArchiveError, safe_extract
from docushift.extractor.unpacker import (
    ExtractOutcome,
    ExtractResult,
    ExtractStats,
    Identified,
    PackageExtractor,
)

__all__ = [
    "AssetCategory",
    "Bucket",
    "Destination",
    "ExtractOutcome",
    "ExtractResult",
    "ExtractStats",
    "Identified",
    "Inventory",
    "PackageExtractor",
    "UnsafeArchiveError",
    "inventory_tree",
    "safe_extract",
]
