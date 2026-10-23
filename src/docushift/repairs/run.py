"""`repair census` and `repair apply`: measure, then rewrite, the published versions (Phase 59).

**Census** reads each published repo once per repair with `git grep -l -z --untracked
-E <pattern>` -- seconds per repo, where a file walk of one family took 37 minutes
(Phase 56) -- and counts only the files it names, exactly, with the repair's own
`detect`. A repo outside git falls back to a walk. Every published version gets a
count, 0 included, so "none left" is measured, never assumed.

**Apply** rewrites a version's published folders **and** its `output/` and `reframed/`
trees together (`sync` re-copies a page that differs from its local source), then
counts the published folders again so the status reflects what is on disk.
"""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from docushift.repairs import Repair
from docushift.validation.tree import VersionFolder, walk

Key = tuple[str, str]  # (slug, published segment)


def published_versions(target: Path, product: str | None = None) -> dict[Key, list[VersionFolder]]:
    """Every published version folder under `target`, every doc-class, by (slug, segment)."""
    found: dict[Key, list[VersionFolder]] = defaultdict(list)
    for entry in walk(target, product):
        for folder in entry.versions:
            if folder.segment:
                found[(folder.slug, folder.segment)].append(folder)
    return dict(found)


def markdown_files(root: Path):
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(names):
            if name.lower().endswith(".md"):
                yield Path(current) / name


def _read(path: Path) -> str | None:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def count_tree(root: Path, repair: Repair) -> int:
    """The repair's occurrences under `root`, by walking it. For a tree outside git."""
    return sum(repair.detect(text) for path in markdown_files(root) if (text := _read(path)) is not None)


def _grep(repo: Path, repair: Repair) -> list[Path] | None:
    """Files in `repo` the pattern matches, or None when `repo` is not a git work tree."""
    if not (repo / ".git").exists():
        return None
    done = subprocess.run(
        ["git", "-C", str(repo), "grep", "-l", "-z", "--untracked", "-E", repair.pattern, "--", "*.md"],
        capture_output=True, timeout=600,
    )
    if done.returncode not in (0, 1):  # 1 is "no match"
        return None
    names = done.stdout.decode("utf-8", errors="replace").split("\0")
    return [repo / name for name in names if name]


def _grep_counts(repo: Path, repair: Repair) -> dict[Path, int] | None:
    """`{file: matching lines}` from `git grep -c`, or None when `repo` is not in git."""
    if not (repo / ".git").exists():
        return None
    done = subprocess.run(
        ["git", "-C", str(repo), "grep", "-c", "-z", "--untracked", "-E", repair.pattern, "--", "*.md"],
        capture_output=True, timeout=600,
    )
    if done.returncode not in (0, 1):
        return None
    counts: dict[Path, int] = {}
    # `-z` with `-c`: `path NUL count`, one per line -- and no quoting of the path.
    for line in done.stdout.decode("utf-8", errors="replace").splitlines():
        name, _, count = line.rpartition("\0")
        if name and count.isdigit():
            counts[repo / name] = int(count)
    return counts


def census(target: Path, repair: Repair, versions: dict[Key, list[VersionFolder]],
           exact: set[Key] = frozenset()) -> dict[Key, int]:
    """The repair's count for every version in `versions`, 0 included.

    Counted from `git grep -c`, which reads git's index: opening the 17,253 matched
    files of one repo folder cost a minute on Windows (2026-10-23). The pattern also
    matches inside fenced code, which `detect` does not, so for the versions in
    `exact` -- the ones recorded as no longer needing the repair -- the matched files
    are read and counted exactly. A marker in a code sample then never turns a
    repaired version back into `needed`.
    """
    counts: dict[Key, int] = dict.fromkeys(versions, 0)
    by_tree: dict[str, list[Key]] = defaultdict(list)
    for key, folders in versions.items():
        for folder in folders:
            by_tree[folder.tree].append(key)
    for tree, keys in by_tree.items():
        repo = target / tree
        found = _grep_counts(repo, repair)
        if found is None:
            for key in set(keys):
                for folder in versions[key]:
                    if folder.tree == tree:
                        counts[key] += count_tree(folder.path, repair)
            continue
        mine = set(keys)
        for path, matched in found.items():
            parts = path.relative_to(repo).parts
            owner = (parts[1], parts[3]) if len(parts) > 4 else None
            if owner not in mine:
                continue
            if owner in exact:
                text = _read(path)
                counts[owner] += repair.detect(text) if text is not None else matched
            else:
                counts[owner] += matched
    return counts


def census_exact(target: Path, repair: Repair, versions: dict[Key, list[VersionFolder]]) -> dict[Key, int]:
    """The previous, read-every-matched-file census. Kept for `exact` and the tests."""
    counts: dict[Key, int] = dict.fromkeys(versions, 0)
    by_tree: dict[str, list[Key]] = defaultdict(list)
    for key, folders in versions.items():
        for folder in folders:
            by_tree[folder.tree].append(key)
    for tree, keys in by_tree.items():
        repo = target / tree
        files = _grep(repo, repair)
        if files is None:
            for key in set(keys):
                for folder in versions[key]:
                    if folder.tree == tree:
                        counts[key] += count_tree(folder.path, repair)
            continue
        mine = set(keys)
        for path in files:
            # The published layout names the version in the path itself:
            # `{locale}/{slug}/{doc-class}/{segment}/...` below the repo. Read from
            # the name, not by resolving every file on disk, which is what made the
            # first census take minutes (2026-10-23).
            parts = path.relative_to(repo).parts
            owner = (parts[1], parts[3]) if len(parts) > 4 else None
            if owner not in mine:
                continue
            text = _read(path)
            if text is not None:
                counts[owner] += repair.detect(text)
    return counts


@dataclass
class Applied:
    """One version's rewrite, per tree."""

    files: int = 0
    fixed: int = 0
    published_fixed: int = 0
    failed: list[str] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)


def apply_tree(root: Path, repair: Repair, dry_run: bool, published: bool, into: Applied) -> None:
    """Rewrites every Markdown file under `root` that the repair changes."""
    files = fixed = 0
    for path in markdown_files(root):
        text = _read(path)
        if text is None:
            into.failed.append(f"{path}: not readable as UTF-8")
            continue
        new, count = repair.fix(text)
        if not count or new == text:
            continue
        if not dry_run:
            try:
                path.write_bytes(new.encode("utf-8"))
            except OSError as exc:
                into.failed.append(f"{path}: {exc}")
                continue
        files += 1
        fixed += count
    into.files += files
    into.fixed += fixed
    if published:
        into.published_fixed += fixed
    into.rows.append({"tree": str(root), "published": "yes" if published else "no",
                      "files_changed": str(files), "fixed": str(fixed)})


def commit_of(path: Path) -> str:
    try:
        done = subprocess.run(["git", "-C", str(path), "log", "-1", "--format=%h", "--", "."],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""
