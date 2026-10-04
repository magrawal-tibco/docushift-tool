"""Unit tests for the build-and-swap helper (`utils/swap.py`).

The race these cover is real and was measured, not imagined: roughly one run in
seven of the Stage 5 suite failed with `WinError 5` renaming a nine-file tree
that had been written correctly. The tests fake the scanner, because a test
that waits for a real one would be flaky in the other direction.
"""

import sys
from pathlib import Path

import pytest

from docushift.utils import swap as swap_module
from docushift.utils.swap import recover, remove, swap


def tree(root: Path, name: str) -> Path:
    path = root / name
    (path / "sub").mkdir(parents=True)
    (path / "sub" / "a.md").write_text(name, encoding="utf-8")
    return path


def test_a_swap_replaces_the_whole_target_rather_than_merging_into_it(tmp_path: Path) -> None:
    """The reason the stages stage at all: a dropped guide must not survive."""
    staging = tree(tmp_path, "out.part")
    target = tree(tmp_path, "out")
    (target / "yesterday.md").write_text("stale", encoding="utf-8")

    swap(staging, target)

    assert (target / "sub" / "a.md").read_text(encoding="utf-8") == "out.part"
    assert not (target / "yesterday.md").exists()
    assert not staging.exists()


def test_a_swap_onto_a_missing_target_creates_its_parent(tmp_path: Path) -> None:
    staging = tree(tmp_path, "out.part")
    target = tmp_path / "deep" / "nested" / "out"

    swap(staging, target)

    assert (target / "sub" / "a.md").is_file()


def test_a_scanner_holding_the_directory_is_waited_out_not_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two denials then success -- the shape of an on-access scan finishing."""
    staging = tree(tmp_path, "out.part")
    target = tmp_path / "out"
    real = Path.replace
    calls = []

    def flaky(self: Path, other):
        calls.append(other)
        if len(calls) < 3:
            raise PermissionError(5, "Access is denied")
        return real(self, other)

    monkeypatch.setattr(Path, "replace", flaky)
    monkeypatch.setattr(swap_module, "DELAY", 0.001)

    swap(staging, target, delay=0.001)

    assert len(calls) == 3
    assert (target / "sub" / "a.md").is_file()


def test_a_denial_that_never_clears_is_still_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A full disk or a locked target is a real failure and stays one."""
    staging = tree(tmp_path, "out.part")

    def denied(self: Path, other):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", denied)

    with pytest.raises(PermissionError):
        swap(staging, tmp_path / "out", attempts=2, delay=0.001)


def test_remove_takes_a_tree_a_file_or_nothing_at_all(tmp_path: Path) -> None:
    directory = tree(tmp_path, "out.part")
    file = tmp_path / "loose.md"
    file.write_text("x", encoding="utf-8")

    remove(directory)
    remove(file)
    remove(tmp_path / "never-existed")

    assert not directory.exists()
    assert not file.exists()


def _files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def wide_tree(root: Path, name: str) -> Path:
    """A tree whose files sort on both sides of `rename-map.csv`, as a merged tree's do."""
    path = tree(root, name)
    for leaf in ("a.md", "rename-map.csv", "review-queue.csv", "toc.yml", "z/zz.md"):
        (path / leaf).parent.mkdir(parents=True, exist_ok=True)
        (path / leaf).write_text(name, encoding="utf-8")
    return path


@pytest.mark.skipif(sys.platform != "win32", reason="a held handle blocks a rename only on Windows")
def test_a_file_held_open_in_the_target_leaves_the_target_whole(tmp_path: Path) -> None:
    """X2-01. The swap deleted file by file and stopped at the locked one: a
    `rename-map.csv` open in Excel took a 199-file merged tree down to 6. CPython
    opens without `FILE_SHARE_DELETE`, as Excel does."""
    target = wide_tree(tmp_path, "out")
    staging = wide_tree(tmp_path, "out.part")
    before = _files(target)

    with (target / "review-queue.csv").open("rb"), pytest.raises(OSError):
        swap(staging, target, attempts=2, delay=0.001)

    assert _files(target) == before
    assert (target / "a.md").read_text(encoding="utf-8") == "out"
    assert not (tmp_path / "out.old").exists()


def test_a_failed_rename_in_puts_the_old_tree_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """X2-01's other half: a scanner holding the *staging* tree used to leave no
    target at all, because the old one was already deleted."""
    target = wide_tree(tmp_path, "out")
    staging = wide_tree(tmp_path, "out.part")
    before = _files(target)
    real = Path.replace

    def scanned(self: Path, other):
        if self.name == "out.part":
            raise PermissionError(5, "Access is denied")
        return real(self, other)

    monkeypatch.setattr(Path, "replace", scanned)

    with pytest.raises(PermissionError):
        swap(staging, target, attempts=2, delay=0.001)

    assert _files(target) == before
    assert (target / "a.md").read_text(encoding="utf-8") == "out"
    assert staging.is_dir()
    assert not (tmp_path / "out.old").exists()


def test_a_run_killed_between_the_renames_is_put_back_by_recover(tmp_path: Path) -> None:
    """X3-03. The kill window is two renames now; what it leaves is the whole old
    tree at `.old`, which the next visit renames back before anything reads it."""
    old = wide_tree(tmp_path, "out.old")
    wide_tree(tmp_path, "out.part")
    before = _files(old)

    recover(tmp_path / "out")

    assert _files(tmp_path / "out") == before
    assert not (tmp_path / "out.old").exists()
    assert not (tmp_path / "out.part").exists()


def test_recover_sweeps_residue_beside_a_live_target(tmp_path: Path) -> None:
    """X3-09. A `current` run left `.part` from a killed build until a forced one."""
    target = wide_tree(tmp_path, "out")
    wide_tree(tmp_path, "out.old")
    wide_tree(tmp_path, "out.part")

    recover(target)

    assert (target / "a.md").read_text(encoding="utf-8") == "out"
    assert not (tmp_path / "out.old").exists()
    assert not (tmp_path / "out.part").exists()


def test_recover_can_leave_an_orphaned_staging_tree_for_a_caller_that_reads_it(
    tmp_path: Path,
) -> None:
    """X3-02: an older tool's interrupted swap left no target and a whole `.part`."""
    wide_tree(tmp_path, "out.part")

    recover(tmp_path / "out", keep_orphan_staging=True)

    assert (tmp_path / "out.part" / "rename-map.csv").is_file()

    target = wide_tree(tmp_path, "out")
    recover(target, keep_orphan_staging=True)

    assert not (tmp_path / "out.part").exists()


def test_a_swap_over_a_set_aside_tree_with_no_target_replaces_it(tmp_path: Path) -> None:
    """A caller that did not `recover` first still ends with the new tree only."""
    wide_tree(tmp_path, "out.old")
    staging = wide_tree(tmp_path, "out.part")

    swap(staging, tmp_path / "out")

    assert (tmp_path / "out" / "a.md").read_text(encoding="utf-8") == "out.part"
    assert not (tmp_path / "out.old").exists()
