"""Unit tests for the CLI command tree.

Stage commands are scaffolded in Phase 1 and must fail loudly, not silently
succeed -- a no-op `convert` that exits 0 is worse than a missing one. The surface
asserted here is the one documented in docs/user-guide.md.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from docushift import __version__
from docushift.cli import main

STAGE_COMMANDS = [
    ["catalog", "fetch", "--all"],
    ["catalog", "list"],
    ["catalog", "show", "--product", "ems"],
    ["catalog", "enable", "--product", "ems", "--version", "10.4.0"],
    ["catalog", "set", "--product", "ems", "--version", "8.6.0", "--engine", "webworks"],
    ["catalog", "import", "--allow-deletes"],
    ["catalog", "triage"],
    ["download", "--all"],
    ["extract", "--all"],
    ["convert", "--product", "ems", "--version", "10.4.0"],
    ["sync", "--target-dir", "workspace"],
    ["validate", "--target-dir", "workspace"],
    ["status", "--bu", "tibco"],
    ["report", "--engines"],
]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_version_flag(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_the_pipeline_commands(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    for command in ("catalog", "download", "extract", "convert", "sync", "validate", "status", "report", "doctor"):
        assert command in result.output


def test_catalog_help_lists_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(main, ["catalog", "--help"])

    assert result.exit_code == 0
    for command in ("fetch", "list", "show", "enable", "set", "import", "triage"):
        assert command in result.output


@pytest.mark.parametrize("argv", STAGE_COMMANDS, ids=lambda a: " ".join(a[:2]))
def test_unimplemented_stages_exit_nonzero(runner: CliRunner, argv: list[str], tmp_path: Path) -> None:
    result = runner.invoke(main, ["--root", str(tmp_path), *argv])

    assert result.exit_code != 0
    assert "not implemented yet" in result.output


def test_catalog_set_rejects_unknown_engine(runner: CliRunner, tmp_path: Path) -> None:
    """The engine vocabulary is closed -- a typo must not become a catalog value."""
    result = runner.invoke(
        main, ["--root", str(tmp_path), "catalog", "set", "--product", "ems", "--engine", "framemaker"]
    )

    assert result.exit_code != 0
    assert "not implemented yet" not in result.output


def test_doctor_reports_project_artifacts(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, ["--root", str(tmp_path), "doctor"], color=False)

    assert result.exit_code == 0
    assert "downloads" in result.output
    assert "state.db" in result.output
