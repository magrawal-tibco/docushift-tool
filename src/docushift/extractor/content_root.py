"""Where a version's content actually starts, which is not always its directory.

`planning.md` Phase 15b. A downloaded package usually unpacks to a **single
wrapper directory** named after itself -- `tibco-enterprise-message-service-10-4-0/`
with `doc/ html/ javadoc/ pdf/` inside it -- so the version directory holds one
child and no content at all. Measured over 60 eligible versions in 24 families,
read from each ZIP's central directory over HTTP Range requests:

| shape | packages |
|---|---|
| one wrapper directory, named exactly `{slug}-{version_dashed}` | **46** |
| flat: `doc/`, `html/`, `pdf/` at the root | 4 |
| a single child that *is* content | 0 |

Every step written before this one reads the version directory directly, because
every extracted tree in this repo arrived by hand-copy from the predecessor's
cache and the cache stores no wrapper. Two of them failed outright on the first
real package (`sync/router.py`, `sync/apirefs.py`) and the rest were working by
luck of never having been reached.

**"Exactly one child" is not the rule on its own.** `doc/` is a single child too
in the five DataSynapse cache trees, and it is content -- `router.source_folders`
looks for `doc/pdf` and `doc/doc` by name, so descending into it would break the
versions that work today. The rule is: descend through a single child directory
only when its name is **not** a known content segment.

**The name is not matched against the package stem**, though it was the stem in
all 46. The sample reached no archived package and none of the products whose
endpoint is still unknown (§2.2), which are exactly the shapes a stem test would
reject. Guessing wrong here costs nothing: descending into a directory that turns
out not to be a wrapper finds no `doc/` or `pdf/`, which is what happens without
the descent anyway.
"""

from pathlib import Path

# Names that mean "content lives here", so a directory bearing one is never a
# wrapper however alone it stands. The first three are what the four flat
# packages in the sample have at their root; the rest are the container segments
# `sync/apirefs.py` already knows, repeated rather than imported because
# `extractor` must not depend on `sync`.
CONTENT_SEGMENTS = frozenset({
    "doc", "docs", "html", "pdf", "pdfs",
    "api", "apis", "apidocs", "api-docs", "api_docs",
    "api-reference", "api_reference", "apireference", "reference",
    "javadoc", "dotnetdoc", "help", "content", "resources",
})

# Where the answer is kept once `extract` has worked it out. Free-form metadata
# rather than a `versions.csv` column: it describes the package's internal shape,
# which is machine bookkeeping, and the CSV is the sheet a human tags batches in.
METADATA_KEY = "content_root"


def resolve(tree: Path) -> Path:
    """The directory a version's content starts in, given its extracted tree.

    Returns `tree` itself for a flat package. Descends **one level at most**: no
    package in the sample nests two wrappers, and an unbounded descent would walk
    a single-guide package straight past its own content.
    """
    if not tree.is_dir():
        return tree
    children = list(tree.iterdir())
    if len(children) != 1:
        return tree
    only = children[0]
    if not only.is_dir() or only.name.lower() in CONTENT_SEGMENTS:
        return tree
    return only


def relative(tree: Path, root: Path | None = None) -> str:
    """The recorded form: `""` for a flat package, else the wrapper's name.

    Stored relative rather than absolute so a workspace that moves, or a tree
    another machine extracted, does not carry a path that resolves nowhere.
    """
    root = resolve(tree) if root is None else root
    return "" if root == tree else root.name


def of(tree: Path, recorded: str | None = None) -> Path:
    """What every consumer calls: the recorded root, or the tree read afresh.

    `recorded` is what `extract` wrote for this version. It is honoured when the
    directory it names is still there, and otherwise ignored rather than trusted
    -- a stale record would send a reader into a directory that no longer exists,
    which is worse than the measurement it was meant to save.

    `None` means no `extract` has run under this rule, which is the state of every
    tree hand-copied from the predecessor's cache, so the shape is read from the
    disk. That fallback is not a migration step to be removed later: `convert` and
    `sync` accept a tree they were handed (`--input-dir`, `--tree`), and a tree
    nobody extracted has nothing recorded about it by construction.
    """
    if recorded:
        candidate = tree / recorded
        if candidate.is_dir():
            return candidate
    return resolve(tree)
