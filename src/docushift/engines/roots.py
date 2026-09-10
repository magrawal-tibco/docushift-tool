"""Where an engine's output roots are, inside an extracted tree.

`design.md` §7.1 is explicit that this is a **separate step from engine
detection**: the engine answers "which converter", once per version, while the
roots answer "which units of work", and one version commonly has several. It
lives in `engines/` rather than `extractor/` because it is engine-specific
knowledge -- Phase 5's converters locate their work with the same function that
Phase 4b's extract reports with. One function, one answer, two callers.

Roots are found **by content, never by a configured path**. Measured against the
`html-to-md` cache (`architecture.md` §5.1.1, §5.1.3, §5.3.2):

- Flare: a directory holding `Data/HelpSystem.xml`. 51 of 595 versions ship more
  than one, and 153 roots nest inside another, so the walk descends rather than
  stopping at the first match.
- DITA (SDL): a directory holding a `GUID-*.html`, at no fixed depth.
- WebWorks: the parent of a `wwhdata/` directory -- 195 of 195, zero either way.
"""

from pathlib import Path

from docushift.engines.detector import GUID_HTML_NAME
from docushift.models import SourceEngine


def _walk_dirs(tree: Path):
    """Every directory in `tree`, `tree` itself included, unreadable ones skipped."""
    stack = [tree]
    while stack:
        current = stack.pop()
        yield current
        try:
            stack.extend(child for child in current.iterdir() if child.is_dir())
        except OSError:
            continue


def _is_flare_root(directory: Path) -> bool:
    return (directory / "Data" / "HelpSystem.xml").is_file()


def _is_dita_root(directory: Path) -> bool:
    try:
        return any(GUID_HTML_NAME.match(child.name.lower()) for child in directory.iterdir() if child.is_file())
    except OSError:
        return False


def _is_webworks_root(directory: Path) -> bool:
    return (directory / "wwhdata").is_dir()


_RULES = {
    SourceEngine.FLARE: _is_flare_root,
    SourceEngine.DITA: _is_dita_root,
    SourceEngine.WEBWORKS: _is_webworks_root,
}


def find_output_roots(tree: Path, engine: SourceEngine) -> list[Path]:
    """The output roots of `tree` for `engine`, sorted shallowest first.

    An **empty list means no rule applies** -- either the engine has none (DocBook
    publishes flat HTML with nothing to anchor on, and no unconvertible engine has
    a rule at all) or the markers are absent from a tree that detected on content.
    Callers treat that as "the version tree is the single unit of work"; what they
    must not do is treat it as "there is nothing here", which is a different fact
    and one this function never reports.

    Roots are returned even when one nests inside another, because that is the
    measured shape of the corpus rather than a defect. `owning_root` resolves
    which of them owns a given file.
    """
    rule = _RULES.get(engine)
    if rule is None:
        return []
    roots = [directory for directory in _walk_dirs(tree) if rule(directory)]
    # Sorted by depth then by path: deterministic, and the shallowest root first
    # is the order a human reads a bundle in.
    return sorted(roots, key=lambda path: (len(path.parts), str(path)))


def owning_root(path: Path, roots: list[Path]) -> Path | None:
    """Which root owns `path`. **The innermost one** (`architecture.md` §5.1.3).

    153 Flare roots nest inside another, and a file under a nested root belongs to
    that root and not to its container -- getting this backwards silently
    attributes a sub-guide's topics to its parent guide.
    """
    best: Path | None = None
    for root in roots:
        contains = path == root or root in path.parents
        if contains and (best is None or len(root.parts) > len(best.parts)):
            best = root
    return best
