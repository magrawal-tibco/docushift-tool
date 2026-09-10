"""Engine-specific knowledge: which generator made a tree, and where its work is.

The engine is a per-version property detected from package contents by
``detector.py`` -- never declared at product level (docs/architecture.md §3.4).
``roots.py`` is the separate step that locates the units of work inside a tree,
because one version commonly ships several (docs/design.md §7.1). Both land in
Phase 4b-1, since extraction is where they run; the HTML profile extractors that
consume them are Phase 5.
"""

from docushift.engines.detector import Detection, detect_tree, detect_version
from docushift.engines.roots import find_output_roots, owning_root

__all__ = ["Detection", "detect_tree", "detect_version", "find_output_roots", "owning_root"]
