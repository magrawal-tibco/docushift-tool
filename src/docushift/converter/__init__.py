"""Stage 5: extracted HTML to AEM-ready GFM.

The driver is engine-neutral. Everything that knows what a MadCap file looks like
lives in `engines/`, everything shared lives in `transforms/`, and this package
only sequences them: select, dispatch, write, resolve help, synthesize, swap,
report.

Stage 6a's navigation synthesis (`navigation.py`) sits in this package and not in
`aem/` for one reason: the node list the engines report exists only while their
units are in hand, and the pages it generates are Markdown documents that have to
land in the staging tree. A synthesizer that ran after the swap would write into a
live tree.
"""

from docushift.converter.driver import (
    ConvertOutcome,
    ConvertResult,
    ConvertStats,
    DocumentConverter,
)

__all__ = ["ConvertOutcome", "ConvertResult", "ConvertStats", "DocumentConverter"]
