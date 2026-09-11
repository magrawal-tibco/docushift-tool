"""Unit tests for the build-and-swap helper (`utils/swap.py`).

The race these cover is real and was measured, not imagined: roughly one run in
seven of the Stage 5 suite failed with `WinError 5` renaming a nine-file tree
that had been written correctly. The tests fake the scanner, because a test
that waits for a real one would be flaky in the other direction.
"""

from pathlib import Path

import pytest

from docushift.utils import swap as swap_module
from docushift.utils.swap import remove, swap


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
