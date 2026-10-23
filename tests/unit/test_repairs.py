"""Phase 59: a generic fix is a registered repair, measured and applied per version."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from docushift import repairs
from docushift.cli import main
from docushift.reporting.status import _repairs
from docushift.repairs import run
from docushift.state import StateStore
from docushift.transforms import callouts
from tests.unit.test_cli import populated_root, runner  # noqa: F401 -- fixtures

R001 = repairs.get("R001")
SLUG = "tibco-enterprise-message-service"


# -- the register ---------------------------------------------------------------


def test_r001_is_registered_with_its_ticket_and_confirming_finding() -> None:
    assert R001 is not None and R001.ticket == "DOCOPS-250"
    assert R001.confirm == "VERIFY_PUBLISHED_CALLOUT_UNRENDERED"
    assert [r.id for r in repairs.registered()][0] == "R001"


def test_r001_detects_fixes_and_a_second_run_changes_nothing() -> None:
    text = "> [!NOTE]\n> Keep it.\n\n```\n> [!TIP]\n```\n"

    assert R001.detect(text) == 1
    fixed, count = R001.fix(text)
    assert (fixed, count) == ("> **Note:**\n> Keep it.\n\n```\n> [!TIP]\n```\n", 1)
    assert R001.fix(fixed) == (fixed, 0) and R001.detect(fixed) == 0


def test_a_fresh_conversion_never_needs_r001() -> None:
    """The converter change ships with the repair (Phase 56): new output detects 0."""
    for kind in callouts.Alert:
        assert R001.detect(callouts.render(kind, "Body.\n\nMore.")) == 0


# -- state ----------------------------------------------------------------------


def test_a_version_moves_needed_fixed_confirmed_and_back_when_it_regresses(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state.db")

    assert state.record_census("p", "1.0", "R001", 5, "2026-10-23T01:00:00+00:00") == "needed"
    assert state.record_census("p", "1.0", "R001", 0, "2026-10-23T02:00:00+00:00", fixed=5) == "fixed"
    assert state.confirm_repair("p", "1.0", "R001", "2026-10-24T01:00:00+00:00")
    assert state.record_census("p", "1.0", "R001", 0, "2026-10-25T01:00:00+00:00") == "confirmed"
    assert state.record_census("p", "1.0", "R001", 2, "2026-10-26T01:00:00+00:00") == "needed"


def test_a_version_that_never_had_it_is_none_and_cannot_be_confirmed(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state.db")

    assert state.record_census("p", "1.0", "R001", 0, "2026-10-23T01:00:00+00:00") == "none"
    assert not state.confirm_repair("p", "1.0", "R001", "2026-10-24T01:00:00+00:00")


def test_versions_csv_lists_only_what_a_version_still_needs() -> None:
    rows = [{"repair": "R002", "state": "needed", "remaining": 12, "checked_at": "2026-10-23T01:00:00"},
            {"repair": "R001", "state": "needed", "remaining": 1404, "checked_at": "2026-10-24T01:00:00"},
            {"repair": "R003", "state": "fixed", "remaining": 0, "checked_at": "2026-10-22T01:00:00"}]

    assert _repairs(rows) == ("R001(1404) R002(12)", "2026-10-24")
    assert _repairs(None) == ("", "")


# -- census and apply -------------------------------------------------------------


def _published(root: Path, segment: str, body: str) -> Path:
    folder = root / "en-us-tib-messaging-userdocs/en-us" / SLUG / "online-help" / segment
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "page.md").write_text(body, encoding="utf-8")
    return folder


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def target(tmp_path: Path) -> Path:
    if shutil.which("git") is None:  # pragma: no cover - git is on every dev box this runs on
        pytest.skip("git not available")
    root = tmp_path / "repos"
    _published(root, "10-4-0", "# Page\n\n> [!NOTE]\n> One.\n\n> [!TIP]\n> Two.\n")
    _published(root, "8-6-0", "# Page\n\nNo notes here.\n\n```\n> [!NOTE]\n```\n")
    repo = root / "en-us-tib-messaging-userdocs"
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    return root


def test_the_census_counts_per_version_from_git_and_exactly_where_asked(target: Path) -> None:
    versions = run.published_versions(target)

    assert run.census(target, R001, versions) == {(SLUG, "10-4-0"): 2, (SLUG, "8-6-0"): 1}
    # A marker in a code sample is not a note: counted exactly, it is none.
    assert run.census(target, R001, versions, exact={(SLUG, "8-6-0")})[(SLUG, "8-6-0")] == 0


def test_a_tree_outside_git_is_counted_by_walking_it(tmp_path: Path) -> None:
    _published(tmp_path, "10-4-0", "> [!NOTE]\n> One.\n")

    assert run.census(tmp_path, R001, run.published_versions(tmp_path)) == {(SLUG, "10-4-0"): 1}


def test_census_then_apply_fixes_the_repo_and_the_local_tree_together(
    runner: CliRunner, populated_root: Path, target: Path  # noqa: F811
) -> None:
    from docushift.config import ConfigManager

    cfg = ConfigManager(root_dir=populated_root)
    local = cfg.output_path("tibco", "messaging", SLUG, "10.4.0")
    local.mkdir(parents=True)
    (local / "page.md").write_text("> [!NOTE]\n> One.\n", encoding="utf-8")

    def invoke(*argv: str):
        return runner.invoke(main, ["--root", str(populated_root), *argv], color=False)

    assert invoke("repair", "census", "--target-dir", str(target)).exit_code == 0
    dry = invoke("repair", "apply", "R001", "--target-dir", str(target), "--dry-run")
    assert dry.exit_code == 0, dry.output
    assert "[!NOTE]" in (target / "en-us-tib-messaging-userdocs/en-us" / SLUG
                         / "online-help/10-4-0/page.md").read_text(encoding="utf-8")

    done = invoke("repair", "apply", "R001", "--target-dir", str(target))

    assert done.exit_code == 0, done.output
    page = target / "en-us-tib-messaging-userdocs/en-us" / SLUG / "online-help/10-4-0/page.md"
    assert page.read_text(encoding="utf-8") == "# Page\n\n> **Note:**\n> One.\n\n> **Tip:**\n> Two.\n"
    assert (local / "page.md").read_text(encoding="utf-8") == "> **Note:**\n> One.\n"
    rows = StateStore(populated_root / "cache" / "state.db").repair_rows()
    assert rows[(SLUG, "10.4.0", "R001")]["state"] == "fixed"
    assert rows[(SLUG, "10.4.0", "R001")]["fixed_count"] == 2
    assert (populated_root / "reports/repairs/INDEX.html").is_file()

    again = invoke("repair", "apply", "R001", "--target-dir", str(target))
    assert "No version needs R001" in again.output


def test_apply_refuses_a_version_synced_after_its_census(
    runner: CliRunner, populated_root: Path, target: Path  # noqa: F811
) -> None:
    def invoke(*argv: str):
        return runner.invoke(main, ["--root", str(populated_root), *argv], color=False)

    assert invoke("repair", "census", "--target-dir", str(target)).exit_code == 0
    state = StateStore(populated_root / "cache" / "state.db")
    with state._tx() as conn:
        conn.execute("INSERT OR REPLACE INTO stage_event (slug, version, stage, outcome, at, target) "
                     "VALUES (?, '10.4.0', 'sync', 'ok', '2999-01-01T00:00:00+00:00', '')", (SLUG,))

    result = invoke("repair", "apply", "R001", "--target-dir", str(target))

    assert "synced after the last census" in result.output
    assert "[!NOTE]" in (target / "en-us-tib-messaging-userdocs/en-us" / SLUG
                         / "online-help/10-4-0/page.md").read_text(encoding="utf-8")
