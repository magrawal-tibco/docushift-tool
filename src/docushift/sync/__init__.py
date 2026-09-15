"""Stage 7: publishing-layout organizer.

Writes repo-shaped directory trees under the sync target. Deliberately runs no
git command and creates no repository -- publishing is out of scope for this
tool (docs/architecture.md §6.0).

Phase 6b built the spine and placed `online-help`; 6c added the three document
doc-classes -- `user-guides`, `release-information` and `reference-documents` --
routed out of the *extracted* tree rather than the converted one. 6d adds the
`-resources` sibling. See docs/planning.md.
"""

from docushift.sync.distributor import (
    DOC_CLASSES,
    ONLINE_HELP,
    SyncOutcome,
    SyncResult,
    SyncStats,
    WorkspaceDistributor,
)
from docushift.sync.router import (
    DOCUMENT_DOC_CLASSES,
    REFERENCE_DOCUMENTS,
    RELEASE_INFORMATION,
    USER_GUIDES,
)

__all__ = [
    "DOCUMENT_DOC_CLASSES",
    "DOC_CLASSES",
    "ONLINE_HELP",
    "REFERENCE_DOCUMENTS",
    "RELEASE_INFORMATION",
    "USER_GUIDES",
    "SyncOutcome",
    "SyncResult",
    "SyncStats",
    "WorkspaceDistributor",
]
