"""Stage 4: ZIP extractor & asset/CSH analyzer.

`safe_unzip` is built (Phase 4a, since `archive download --extract` needs it);
the inventory walk is Phase 4b. See docs/planning.md.
"""

from docushift.extractor.safe_unzip import UnsafeArchiveError, safe_extract

__all__ = ["UnsafeArchiveError", "safe_extract"]
