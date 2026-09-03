"""Unit tests for the CLI command tree.

Two contracts are asserted here. Stages that are not built yet must fail loudly
rather than silently succeed -- a no-op `convert` that exits 0 is worse than a
missing one. Stages that *are* built must be reachable end-to-end from argv. The
surface asserted is the one documented in docs/user-guide.md.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from docushift import __version__
from docushift.catalog import CatalogManager
from docushift.cli import main
from docushift.state import StateStore
from tests.conftest import make_product, make_version

PENDING_COMMANDS = [
    ["catalog", "fetch", "--all"],
    ["download", "--all"],
    ["download", "--batch", "poc-1"],
    ["extract", "--all"],
    ["convert", "--product", "ems", "--version", "10.4.0"],
    ["archive", "download", "--product", "ems", "--version", "8.6.0"],
    ["sync", "--target-dir", "workspace"],
    ["validate", "--target-dir", "workspace"],
    ["status", "--bu", "tibco"],
    ["report", "--engines"],
]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def populated_root(tmp_path: Path) -> Path:
    """A project root whose catalog CSVs already hold one product with two versions."""
    (tmp_path / "config").mkdir(exist_ok=True)
    state = StateStore(tmp_path / "cache" / "state.db")
    manager = CatalogManager(tmp_path / "config" / "products.csv", tmp_path / "config" / "versions.csv", state)
    product = make_product("ems", display_name="TIBCO EMS", family="messaging")
    product.versions = {
        "10.4.0": make_version("ems", "10.4.0", zip_url="https://docs.tibco.com/ems.zip"),
        "8.6.0": make_version("ems", "8.6.0", is_archived=True, convert_eligible=False),
    }
    manager.merge_fetch_results([product])
    state.close()
    return tmp_path


def _invoke(runner: CliRunner, root: Path, *argv: str):
    return runner.invoke(main, ["--root", str(root), *argv], color=False)


def test_version_flag(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_the_pipeline_commands(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    for command in (
        "catalog",
        "archive",
        "download",
        "extract",
        "convert",
        "sync",
        "validate",
        "status",
        "report",
        "doctor",
    ):
        assert command in result.output


def test_catalog_help_lists_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(main, ["catalog", "--help"])

    assert result.exit_code == 0
    for command in ("fetch", "list", "show", "enable", "set", "import", "triage", "batches"):
        assert command in result.output


def test_archive_help_lists_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(main, ["archive", "--help"])

    assert result.exit_code == 0
    for command in ("list", "download"):
        assert command in result.output


@pytest.mark.parametrize("command", ["download", "extract", "convert", "sync", "catalog list", "catalog fetch"])
def test_batch_is_a_selector_on_every_stage(runner: CliRunner, command: str) -> None:
    """A POC scope must be expressible on every command that walks the catalog."""
    result = runner.invoke(main, [*command.split(), "--help"])

    assert result.exit_code == 0
    assert "--batch" in result.output


@pytest.mark.parametrize("argv", PENDING_COMMANDS, ids=lambda a: " ".join(a[:2]))
def test_unimplemented_stages_exit_nonzero(runner: CliRunner, argv: list[str], tmp_path: Path) -> None:
    result = _invoke(runner, tmp_path, *argv)

    assert result.exit_code != 0
    assert "not implemented yet" in result.output


def test_catalog_fetch_names_the_phase_that_blocks_it(runner: CliRunner, tmp_path: Path) -> None:
    """The merge engine landed in Phase 2; only the crawler is outstanding."""
    result = _invoke(runner, tmp_path, "catalog", "fetch", "--all")

    assert "Phase 3" in result.output


# -- implemented catalog commands ---------------------------------------------


def test_catalog_list_on_an_empty_catalog_is_not_an_error(runner: CliRunner, tmp_path: Path) -> None:
    result = _invoke(runner, tmp_path, "catalog", "list")

    assert result.exit_code == 0
    assert "No matching catalog rows" in result.output


def test_catalog_list_shows_versions(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "list")

    assert result.exit_code == 0
    assert "10.4.0" in result.output
    assert "8.6.0" in result.output


def test_catalog_list_eligible_only_filters(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "list", "--eligible-only")

    assert result.exit_code == 0
    assert "10.4.0" in result.output
    assert "8.6.0" not in result.output


def test_catalog_show_describes_one_product(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "show", "--product", "ems")

    assert result.exit_code == 0
    assert "messaging" in result.output


def test_catalog_show_on_a_missing_product_fails(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "show", "--product", "nope")

    assert result.exit_code != 0
    assert "No product 'nope'" in result.output


def test_catalog_enable_writes_through_to_the_csv(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "enable", "--product", "ems", "--version", "8.6.0")

    assert result.exit_code == 0
    text = (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")
    assert "8.6.0,true,true" in text


def test_catalog_enable_disable_flag(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(
        runner, populated_root, "catalog", "enable", "--product", "ems", "--version", "10.4.0", "--disable"
    )

    assert result.exit_code == 0
    assert "convert_eligible = false" in result.output


def test_catalog_set_engine_pins_it_as_manual(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(
        runner, populated_root, "catalog", "set", "--product", "ems", "--version", "8.6.0", "--engine", "webworks"
    )

    assert result.exit_code == 0
    assert "webworks,manual" in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")


def test_catalog_set_family_pins_provenance(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--family", "integration")

    assert result.exit_code == 0
    assert "integration,manual" in (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")


def test_catalog_set_rejects_unknown_engine(runner: CliRunner, tmp_path: Path) -> None:
    """The engine vocabulary is closed -- a typo must not become a catalog value."""
    result = _invoke(runner, tmp_path, "catalog", "set", "--product", "ems", "--engine", "framemaker")

    assert result.exit_code != 0
    assert "framemaker" in result.output


def test_catalog_set_requires_a_version_for_version_fields(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--engine", "flare")

    assert result.exit_code != 0
    assert "pass --version" in result.output


def test_catalog_set_with_nothing_to_set_fails(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems")

    assert result.exit_code != 0
    assert "Nothing to set" in result.output


def test_catalog_import_normalizes_a_clean_catalog(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "import")

    assert result.exit_code == 0
    assert "re-imported" in result.output


def test_catalog_import_refuses_to_absorb_a_lost_version_key(runner: CliRunner, populated_root: Path) -> None:
    """Excel coercing a version key must abort the import, not delete the row."""
    versions = populated_root / "config" / "versions.csv"
    versions.write_text(
        versions.read_text(encoding="utf-8-sig").replace("8.6.0", "8.6"), encoding="utf-8-sig", newline=""
    )

    result = _invoke(runner, populated_root, "catalog", "import")

    assert result.exit_code != 0
    assert "8.6.0" in result.output


def test_catalog_triage_reports_progress(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "triage")

    assert result.exit_code == 0
    assert "need triage" in result.output


def test_catalog_triage_on_an_empty_catalog(runner: CliRunner, tmp_path: Path) -> None:
    result = _invoke(runner, tmp_path, "catalog", "triage")

    assert result.exit_code == 0
    assert "empty" in result.output


def test_doctor_reports_project_artifacts(runner: CliRunner, tmp_path: Path) -> None:
    result = _invoke(runner, tmp_path, "doctor")

    assert result.exit_code == 0
    assert "families" in result.output
    assert "state.db" in result.output
    assert "en-us" in result.output


# -- batch scheduling --------------------------------------------------------


def test_catalog_set_batch_tags_a_version(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(
        runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0", "--batch", "poc-1"
    )

    assert result.exit_code == 0
    listed = _invoke(runner, populated_root, "catalog", "list", "--batch", "poc-1")
    assert "10.4.0" in listed.output
    assert "8.6.0" not in listed.output


def test_catalog_set_batch_requires_a_version(runner: CliRunner, populated_root: Path) -> None:
    """`--batch` on a product row is ambiguous: it would schedule the whole history."""
    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--batch", "poc-1")

    assert result.exit_code != 0
    assert "--batch" in result.output


def test_catalog_batches_lists_scheduled_work(runner: CliRunner, populated_root: Path) -> None:
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0", "--batch", "poc-1")

    result = _invoke(runner, populated_root, "catalog", "batches")

    assert result.exit_code == 0
    assert "poc-1" in result.output


def test_catalog_batches_when_nothing_is_scheduled(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "batches")

    assert result.exit_code == 0
    assert "No versions are tagged" in result.output


def test_catalog_show_reports_the_family_workspace(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "show", "--product", "ems")

    assert result.exit_code == 0
    assert "en-us-tibco-messaging" in result.output


# -- archived versions -------------------------------------------------------


def test_archive_list_shows_only_archived_versions(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "archive", "list")

    assert result.exit_code == 0
    assert "8.6.0" in result.output
    assert "10.4.0" not in result.output


def test_archive_list_when_nothing_is_archived(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "archive", "list", "--product", "nosuchproduct")

    assert result.exit_code == 0
    assert "No archived versions" in result.output
