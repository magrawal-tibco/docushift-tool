"""Stage 4: ZIP extractor & asset/CSH analyzer.

`safe_unzip` landed in Phase 4a, since `archive download --extract` needs it.
`unpacker` is Phase 4b-1: unpack, then identify the engine and its output roots.
The inventory walk -- assets, CSH and the five `versions.csv` columns -- is
Phase 4b-2. See docs/planning.md.
"""

from docushift.extractor.safe_unzip import UnsafeArchiveError, safe_extract
from docushift.extractor.unpacker import (
    ExtractOutcome,
    ExtractResult,
    ExtractStats,
    Identified,
    PackageExtractor,
)

__all__ = [
    "ExtractOutcome",
    "ExtractResult",
    "ExtractStats",
    "Identified",
    "PackageExtractor",
    "UnsafeArchiveError",
    "safe_extract",
]
