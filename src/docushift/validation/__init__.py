"""Stage 8: the link, asset and AEM-artifact linter over a published tree.

`docushift validate` -- `planning.md` §7.4, `design.md` §8.4, Phase 7b. The one
command in the tool that gates on what it finds, and the one that reads the
*published* tree rather than the database.

Four modules, and the split is the one `sync/` already uses: `tree.py` enumerates
what is on the shelf, and `links.py`, `artifacts.py` and `csh.py` are pure
functions over one folder that take no `CatalogManager`, no `StateStore` and no
`FindingsRun`. `driver.py` is the only thing that records. `references.py` is the
reader they share.
"""

from docushift.validation.driver import (
    FolderResult,
    ValidationStats,
    Validator,
)
from docushift.validation.links import FolderIndex, LinkContext, LinkReport
from docushift.validation.tree import (
    PUBLISHED_DOC_CLASSES,
    ProductFolder,
    VersionFolder,
    walk,
)

__all__ = [
    "PUBLISHED_DOC_CLASSES",
    "FolderIndex",
    "FolderResult",
    "LinkContext",
    "LinkReport",
    "ProductFolder",
    "ValidationStats",
    "Validator",
    "VersionFolder",
    "walk",
]
