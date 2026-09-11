"""Is a path part of a generated API-reference tree?

One predicate, three callers -- Stage 4 splits `_api_files` from `_doc_files`
with it, Stage 5 skips conversion with it, Stage 7 routes into the
`api-references` doc-class with it (`design.md` §6.3). Three copies would let a
file be counted as documentation, skipped by the converter, and published as an
API reference. It sits at the top level rather than under `extractor/` for the
same reason: it belongs to no single stage, and filing it under the one that
needed it first would have the other two importing from the extractor.

**A marker decides; a name never does.** The rule comes from a survey of the
predecessor's 2,201,528-file cache (`design.md` §6.3.1). The inherited
seven-name list missed most of the corpus's real API trees -- `apidocs/`,
`apischemas/`, `components-api/`, `api reference/` (with a space) -- and
widening it to a substring test is worse rather than better: `api-exchange-
gateway/` is a *product name* carrying 15,677 files of ordinary documentation,
and the predecessor's `/c` substring matched 186,856 files including the
WebWorks `ctx/` directory, which is a CSH source.

What a tree contains is knowable; what someone named it is not. The same
conclusion `engines/detector.py` reaches, for the same reason.
"""

import re
from pathlib import Path

# Finding 5: each generator leaves an unmistakable marker at its tree root.
# Files first (the cheap `is_file` test), then the two that need a pattern.
_MARKER_FILES = frozenset({
    # Javadoc
    "allclasses-frame.html", "package-frame.html", "index-all.html",
    # Doxygen
    "annotated.html",
})
_MARKER_DIRS = frozenset({
    # Javadoc again -- the frame files are absent from some newer layouts.
    "class-use",
})
# Doxygen's per-header page: `tibrv_8h.html`. Anchored so it cannot match a
# topic that merely ends in `8h`.
_DOXYGEN_HEADER = re.compile(r"^.+_8h\.html?$")
# Sandcastle's full-text index shards.
_SANDCASTLE_INDEX = re.compile(r"^fti_.+\.json$")
# Markers that are a nested path rather than a name in the directory itself.
_MARKER_PATHS = (
    ("styles", "jsdoc-default.css"),   # JSDoc
    ("lib", "godoc", "godocs.js"),     # godoc
)

# The *only* names in the tool that classify nothing. They raise the triage flag
# and do no more than that. Compared as whole segments, case-folded (Finding 3:
# `API`/`api`, `C`/`c`, `JavaDoc`/`javadoc`, `Java_API` all occur).
API_NAME_SEGMENTS = frozenset({
    "api", "apidocs", "api-docs", "api_docs", "apischemas",
    "api_reference", "api-reference", "api reference", "apireference",
    "javadoc", "java_api", "java", "c", "cpp", "golang", "go", "tibdg",
})
_API_NAME_SUFFIXES = ("-api", "_api", "-api-reference", "_api_ref")


def has_api_marker(directory: Path) -> bool:
    """Does `directory` sit at the root of a generated API-reference tree?"""
    try:
        entries = list(directory.iterdir())
    except OSError:
        return False
    for entry in entries:
        name = entry.name.lower()
        try:
            is_dir = entry.is_dir()
        except OSError:
            continue
        if is_dir:
            if name in _MARKER_DIRS:
                return True
            continue
        if name in _MARKER_FILES or _DOXYGEN_HEADER.match(name):
            return True
    if any((directory / Path(*parts)).is_file() for parts in _MARKER_PATHS):
        return True
    # Sandcastle shards live in `fti/`, one JSON per index bucket.
    fti = directory / "fti"
    try:
        return fti.is_dir() and any(_SANDCASTLE_INDEX.match(c.name.lower()) for c in fti.iterdir())
    except OSError:
        return False


def find_api_roots(tree: Path) -> list[Path]:
    """The outermost API-reference roots in `tree`, shallowest first.

    **The descent stops at a match.** A Javadoc tree inside a Doxygen tree is one
    artefact, not two, and the corpus's `api-reference/javascript/` JSDoc output
    must be counted once through its parent rather than twice (§6.3.1 Finding 4).
    That is the whole difference between this and `engines.roots.find_output_roots`,
    where nesting is real and the innermost root owns a file.
    """
    roots: list[Path] = []
    stack = [tree]
    while stack:
        current = stack.pop()
        if has_api_marker(current):
            roots.append(current)
            continue
        try:
            stack.extend(child for child in current.iterdir() if child.is_dir())
        except OSError:
            continue
    return sorted(roots, key=lambda path: (len(path.parts), str(path)))


def is_api_reference(path: Path, roots: list[Path]) -> bool:
    """Is `path` inside one of `roots`? Pure -- no I/O, so callers pass what they hold.

    Stage 4 has the roots from its own walk, Stages 5 and 7 read them back from
    `version_metadata` under `api_roots`. Nobody re-derives them, and nobody
    reaches a different answer.
    """
    return any(path == root or root in path.parents for root in roots)


def looks_like_api_name(segment: str) -> bool:
    """Does this one path segment *look* like an API reference?

    Used for exactly one thing: the unmarked-candidate triage line. It never
    classifies a file. Whole segment, case-folded -- never a substring, which is
    the rule `api-exchange-gateway/` exists to enforce.
    """
    name = segment.strip().lower()
    return name in API_NAME_SEGMENTS or name.endswith(_API_NAME_SUFFIXES)
