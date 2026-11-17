"""Re-index a placed version folder so git records the case the disk has (Phase 83).

The publish repos run with `core.ignorecase=true`. `sync` swaps a version folder
whose links and files agree (`resources/images/x.png`), and on disk they do; but a
path git already tracks as `Resources/Images/x.png` keeps its index spelling
through any `git add`, and a new file under that folder takes the folder's index
spelling. `git status` stays clean while AEM serves the old case and the links 404
(DOCOPS-374: 21,458 links in 149 versions on 17 Nov, every one an old folder
spelling the index never let go of).

Dropping the folder from the index and adding it back makes git read the names
from the disk, so a case-only change becomes a rename. Blobs are unchanged.

This is the one place `sync` runs git (`sync/__init__.py`): only when the version
folder sits in a git work tree under the target, and only on the folder it placed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

Rename = tuple[str, str]


def repo_of(path: Path, within: Path) -> Path | None:
    """The git work tree holding `path`, searched no higher than `within`."""
    path, within = path.absolute(), within.absolute()
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return folder
        if folder == within:
            break
    return None


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True,
                          timeout=600).stdout


def _tracked(repo: Path, relative: str) -> list[str]:
    out = _git(repo, "ls-files", "-z", "--", relative)
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def reindex_case(repo: Path, folder: Path) -> list[Rename]:
    """Re-index `folder` from disk; return the case-only renames git now records.

    `git rm -r --cached` then `git add`, as planning.md Phase 83 (1). A folder git
    does not track yet is left alone: `git add` would record the disk's case for
    it anyway, and staging new work is the publisher's step, not this one's.
    A file tracked despite `.gitignore` is added back by force, so the re-index
    never turns a tracked file into an untracked one. Raises
    `subprocess.CalledProcessError` or `OSError` when git fails.
    """
    relative = folder.absolute().relative_to(repo.absolute()).as_posix()
    before = _tracked(repo, relative)
    if not before:
        return []
    _git(repo, "rm", "-r", "--cached", "-q", "--", relative)
    _git(repo, "add", "--", relative)
    after = _tracked(repo, relative)
    folded = {name.lower(): name for name in after}
    lost = [name for name in before if name.lower() not in folded and (repo / name).exists()]
    if lost:
        _git(repo, "add", "-f", "--", *lost)
        folded.update({name.lower(): name for name in _tracked(repo, relative)})
    return sorted((old, folded[old.lower()]) for old in before
                  if old.lower() in folded and folded[old.lower()] != old)
