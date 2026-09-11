"""Engine-specific knowledge: which generator made a tree, and where its work is.

The engine is a per-version property detected from package contents by
``detector.py`` -- never declared at product level (docs/architecture.md §3.4).
``roots.py`` is the separate step that locates the units of work inside a tree,
because one version commonly ships several (docs/design.md §7.1). Both land in
Phase 4b-1, since extraction is where they run; the HTML profile extractors that
consume them are Phase 5.

``csh.py`` is the third piece of per-engine knowledge and lands in Phase 4b-2:
the three help-map readers, one per HTML engine. It is here rather than in
``transforms/`` because docs/design.md §9.2 puts the *readers* with the engines
and the schema, resolver and writer with the transform.
"""

from docushift.engines.csh import (
    CshEntry,
    CshFormat,
    CshSource,
    CshStatus,
    csh_format_of,
    read_csh_source,
)
from docushift.engines.detector import Detection, detect_tree, detect_version
from docushift.engines.roots import find_output_roots, owning_root

__all__ = [
    "CshEntry",
    "CshFormat",
    "CshSource",
    "CshStatus",
    "Detection",
    "csh_format_of",
    "detect_tree",
    "detect_version",
    "find_output_roots",
    "owning_root",
    "read_csh_source",
]
