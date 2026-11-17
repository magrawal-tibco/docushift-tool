"""The register of repairs: generic text fixes for versions already published (Phase 59).

Nearly every in-scope version is converted and published, so a generic problem found
now is in hundreds of versions at once. Re-converting all of them for a one-line
rewrite is the wrong cost. A **repair** is that rewrite, registered once:

- **detect**: how many times the problem occurs in one Markdown text;
- **pattern**: the same thing as a `git grep -E` pattern, so a census of every
  published version reads git's index instead of walking 87,208 files per family.
  Files the pattern matches are then counted exactly with `detect`, so a match in a
  code sample never keeps a version `needed`;
- **fix**: the rewrite, returning the new text and how many occurrences it fixed;
- **confirm**: the `verify` finding whose absence on staging proves the fix reached
  readers.

**What a repair may change** (`design.md` §8.11): matched lines only, every other byte
identical, line endings kept, fenced code untouched, and a second run a no-op. A fix
that moves a page -- the menu, a merge, a file name -- is not a repair; those
versions go back through the pipeline. Each repair ships with the converter change
that makes new conversions clean, so a repair is only ever catch-up.

**Repo-scope repairs** (Phase 83, `scope="repo"`): R004 fixes git's index, not page
text -- a path committed in a letter case the disk and the links no longer use. It
brings its own `census_repo` and `apply_repo`; the text repairs are unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Repair:
    id: str
    title: str
    ticket: str
    pattern: str
    detect: Callable[[str], int]
    fix: Callable[[str], tuple[str, int]]
    confirm: str = ""
    phase: str = ""
    # A fallback waiting on a decision (R003, DOCOPS-371): left out of a `census`
    # that names no repair, so it never shows as pending until someone asks for it.
    optional: bool = False
    # Phase 83 (R004). `"repo"`: the repair is to a repo's git index, not to page
    # text, so `pattern`/`detect`/`fix` are unused and these two stand in for them.
    # `census_repo(repo, ref) -> {(product folder, segment): count}` reads git at
    # `ref` (the index when None); `apply_repo(repo, folders, dry_run) -> RepoApplied`.
    scope: str = "text"
    census_repo: Callable[..., dict[tuple[str, str], int]] | None = None
    apply_repo: Callable[..., RepoApplied] | None = None


@dataclass
class RepoApplied:
    """What a repo-scope repair did to one version: renames git recorded, links rewritten."""

    renamed: list[tuple[str, str]] = field(default_factory=list)
    # `{file, line, before, after}`: links the re-index could not fix, respelled.
    rewritten: list[dict[str, str]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


_REGISTRY: dict[str, Repair] = {}


def register(repair: Repair) -> Repair:
    if repair.id in _REGISTRY:  # pragma: no cover - two modules claiming one ID
        raise ValueError(f"repair {repair.id} registered twice")
    _REGISTRY[repair.id] = repair
    return repair


def get(repair_id: str) -> Repair | None:
    return _REGISTRY.get(repair_id.upper())


def registered() -> list[Repair]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


# The register is the list of modules imported here, in ID order.
from docushift.repairs import (  # noqa: E402,F401
    r001_note_labels,
    r002_escapes,
    r003_inline_tags,
    r004_path_case,
)
