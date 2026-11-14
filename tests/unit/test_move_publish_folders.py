"""Phase 80: `scratch/move_publish_folders.py` -- the dry run, and the move it plans."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

SLUG = "tibco-activematrix-businessworks-plug-in-for-apache-kafka"
FOLDER = "tibco-bw-plugin-apache-kafka"
DOCS, RESOURCES = "en-us-tib-bw-plugin-userdocs", "en-us-tib-bw-plugin-userdocs-resources"


def _script():
    spec = importlib.util.spec_from_file_location("move_publish_folders",
                                                  REPO_ROOT / "scratch" / "move_publish_folders.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout


def _repo(root: Path, name: str, files: dict[str, str]) -> Path:
    repo = root / name
    for rel, body in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body.encode("utf-8"))
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def setup(tmp_path: Path, monkeypatch):
    if shutil.which("git") is None:  # pragma: no cover
        pytest.skip("git not available")
    root = tmp_path / "tool"
    (root / "config").mkdir(parents=True)
    (root / "config" / "publish-names.yaml").write_text(f"{SLUG}: {FOLDER}\n", encoding="utf-8")
    (root / "config" / "products.csv").write_text(f"slug,family\n{SLUG},bw-plugin\ntibco-ems,ems\n",
                                                  encoding="utf-8")
    base = f"en-us/{SLUG}/online-help"
    target = tmp_path / "repos"
    _repo(target, DOCS, {
        f"{base}/6-10-0/page.md": "# Page\n",
        f"{base}/6-10-0/301.yml": (
            f'"https://docs.tibco.com/pub/x.htm": "/en-us/{SLUG}/online-help/6-10-0/page.md"\n'
            f'"https://docs.tibco.com/pub/x.pdf": "/content/dam/tibco/us/en/{SLUG}/user-guides/6-10-0/x.pdf"\n'),
        f"{base}/6-10-0/csh.yml": f'"id": "/en-us/{SLUG}/online-help/6-10-0/page.md"\r\n',
        f"{base}/redirects.yml": f"redirects:\n- from: us/en/{SLUG}/online-help/6-10-0/a.html\n"
                                 f"  to: us/en/{SLUG}/online-help/6-10-0/page.html\n  status: 301\n",
        f"en-us/{SLUG}/metadata.yml": "csg-product: Kafka\n",
        "en-us/tibco-ems/metadata.yml": "csg-product: EMS\n",
    })
    _repo(target, RESOURCES, {f"en-us/{SLUG}/archives/index.md": "# Archives\n"})
    monkeypatch.chdir(root)
    return root, target


def _main(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["move_publish_folders.py", *args])
    return _script().main()


def test_the_dry_run_lists_each_repo_and_moves_nothing(setup, monkeypatch, capsys) -> None:
    _root, target = setup

    assert _main(monkeypatch, "--target", str(target), "--family", "bw-plugin") == 0

    out = capsys.readouterr().out
    assert f"{DOCS}: en-us/{SLUG} -> en-us/{FOLDER}  (5 tracked file(s); 5 map row(s) in 3 file(s))" in out
    assert f"{RESOURCES}: en-us/{SLUG} -> en-us/{FOLDER}  (1 tracked file(s); 0 map row(s)" in out
    assert "DRY RUN summary: 2 folder move(s) in 2 repo(s), 6 tracked file(s), 5 map row(s) to rewrite" in out
    assert (target / DOCS / "en-us" / SLUG).is_dir()
    assert not (target / DOCS / "en-us" / FOLDER).exists()
    assert _git(target / DOCS, "status", "--porcelain") == ""


def test_apply_renames_in_git_and_rewrites_the_maps(setup, monkeypatch) -> None:
    _root, target = setup

    assert _main(monkeypatch, "--target", str(target), "--product", SLUG, "--apply") == 0

    docs = target / DOCS
    status = _git(docs, "status", "--porcelain")
    assert f"R  en-us/{SLUG}/online-help/6-10-0/page.md -> en-us/{FOLDER}/online-help/6-10-0/page.md" in status
    moved = docs / "en-us" / FOLDER / "online-help"
    assert SLUG not in (moved / "6-10-0" / "301.yml").read_text(encoding="utf-8")
    assert f"/content/dam/tibco/us/en/{FOLDER}/user-guides/" in (moved / "6-10-0" / "301.yml").read_text(
        encoding="utf-8")
    assert (moved / "6-10-0" / "csh.yml").read_bytes().endswith(b"6-10-0/page.md\"\r\n")  # line ending kept
    assert f"from: us/en/{FOLDER}/online-help/" in (moved / "redirects.yml").read_text(encoding="utf-8")
    assert (target / RESOURCES / "en-us" / FOLDER / "archives" / "index.md").is_file()
    assert (docs / "en-us" / "tibco-ems").is_dir()  # an unlisted product is not touched


def test_an_unknown_product_is_refused(setup, monkeypatch, capsys) -> None:
    _root, target = setup

    assert _main(monkeypatch, "--target", str(target), "--product", "tibco-ems") == 2
    assert "not in config/publish-names.yaml: tibco-ems" in capsys.readouterr().out
