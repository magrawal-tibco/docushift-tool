"""Stage 7: publishing-layout organizer.

Writes repo-shaped directory trees under the sync target. Deliberately runs no
git command and creates no repository -- publishing is out of scope for this
tool (docs/architecture.md §6.0).

Phase 6b builds the spine and places `online-help`; 6c adds the three document
doc-classes and 6d the `-resources` sibling. See docs/planning.md.
"""

from docushift.sync.distributor import (
    ONLINE_HELP,
    SyncOutcome,
    SyncResult,
    SyncStats,
    WorkspaceDistributor,
)

__all__ = [
    "ONLINE_HELP",
    "SyncOutcome",
    "SyncResult",
    "SyncStats",
    "WorkspaceDistributor",
]
