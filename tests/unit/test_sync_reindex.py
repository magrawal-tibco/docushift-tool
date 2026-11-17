"""Phase 83 (DOCOPS-374): sync re-indexes a placed folder so git records the disk's case."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from docushift.sync.distributor import WorkspaceDistributor
from docushift.sync.reindex import reindex_case, repo_of

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout


def _respell(path: Path, name: str) -> Path:
    """Renames `path` to `name` in a case-only way, on a case-folding disk too."""
    aside = path.with_name(path.name + ".aside")
    path.rename(aside)
    aside.rename(path.with_name(name))
    return path.with_name(name)


def tracked_in_old_case(tmp_path: Path) -> tuple[Path, Path]:
    """`Resources/Images/a.png` in the index, `resources/images/a.png` on disk."""
    target = tmp_path / "repos"
    repo = target / "en-us-tib-general-userdocs"
    folder = repo / "en-us" / "widget" / "online-help" / "1-0-0"
    (folder / "Resources" / "Images").mkdir(parents=True)
    (folder / "Resources" / "Images" / "a.png").write_bytes(b"png")
    (folder / "page.md").write_bytes(b"![a](resources/images/a.png)\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "core.ignorecase", "true")
    _git(repo, "add", "-A")
    resources = _respell(folder / "Resources", "resources")
    _respell(resources / "Images", "images")
    return target, folder


def test_reindex_records_a_case_only_rename_and_keeps_the_blob(tmp_path: Path) -> None:
    target, folder = tracked_in_old_case(tmp_path)
    repo = target / "en-us-tib-general-userdocs"
    blob = _git(repo, "ls-files", "-s", "--", "en-us/widget/online-help/1-0-0/Resources/Images/a.png").split()[1]

    renamed = reindex_case(repo, folder)

    old = "en-us/widget/online-help/1-0-0/Resources/Images/a.png"
    new = "en-us/widget/online-help/1-0-0/resources/images/a.png"
    assert renamed == [(old, new)]
    assert new in _git(repo, "ls-files").splitlines() and old not in _git(repo, "ls-files").splitlines()
    assert _git(repo, "ls-files", "-s", "--", new).split()[1] == blob
    assert reindex_case(repo, folder) == []


def test_reindex_leaves_an_untracked_folder_unstaged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    folder = repo / "en-us" / "widget" / "online-help" / "1-0-0"
    folder.mkdir(parents=True)
    (folder / "page.md").write_text("# Page\n", encoding="utf-8")
    _git(repo, "init", "-q")

    assert reindex_case(repo, folder) == []
    assert _git(repo, "ls-files") == ""


def test_sync_reindexes_only_inside_a_git_tree_under_its_target(tmp_path: Path) -> None:
    target, folder = tracked_in_old_case(tmp_path)

    renamed, message = WorkspaceDistributor._reindex(folder, target)

    assert message == "" and len(renamed) == 1
    plain = tmp_path / "plain" / "en-us" / "widget" / "online-help" / "1-0-0"
    plain.mkdir(parents=True)
    assert repo_of(plain, tmp_path / "plain") is None
    assert WorkspaceDistributor._reindex(plain, tmp_path / "plain") == ([], "")
