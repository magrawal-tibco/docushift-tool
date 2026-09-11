"""Stage 5: extracted HTML to AEM-ready GFM.

The driver is engine-neutral. Everything that knows what a MadCap file looks like
lives in `engines/`, everything shared lives in `transforms/`, and this package
only sequences them: select, dispatch, write, resolve help, swap, report.
"""

from docushift.converter.driver import (
    ConvertOutcome,
    ConvertResult,
    ConvertStats,
    DocumentConverter,
)

__all__ = ["ConvertOutcome", "ConvertResult", "ConvertStats", "DocumentConverter"]
