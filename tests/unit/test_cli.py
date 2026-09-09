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
from docushift.discovery import CrawlResult, DocsiteCrawler
from docushift.state import StateStore
from tests.conftest import make_product, make_version

PENDING_COMMANDS = [
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
    # The slug is deliberately not the product code: that is the real docsite
    # relationship, and several fetch tests turn on it.
    product = make_product(
        "ems", display_name="TIBCO EMS", family="messaging", slug="tibco-enterprise-message-service"
    )
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


# -- catalog fetch -------------------------------------------------------------


@pytest.fixture
def fake_crawl(monkeypatch: pytest.MonkeyPatch):
    """Replaces the crawler's network walk with a canned result.

    The crawl itself is covered in test_discovery.py; what these tests assert is
    the wiring -- scope validation, the merge call, and what reaches the CSVs.
    """
    calls: list[dict] = []

    def factory(products=None, errors=None):
        result = CrawlResult(
            products=products if products is not None else [_discovered_ems()],
            errors=list(errors or []),
            product_metadata={"ems": {"docsite_id": "1042"}},
            version_metadata={("ems", "10.4.0"): {"folder_path": "ems/10.4.0"}},
        )

        def discover(self, bu=None, family=None, selectors=None, on_progress=None):
            calls.append({"bu": bu, "family": family, "selectors": selectors})
            return result

        monkeypatch.setattr(DocsiteCrawler, "discover", discover)
        return calls

    return factory


def _discovered_ems():
    product = make_product("ems", display_name="TIBCO EMS", family="messaging")
    product.versions = {
        "10.4.0": make_version("ems", "10.4.0", zip_url="https://docs.tibco.com/ems.zip"),
        "10.5.0": make_version("ems", "10.5.0", zip_url="https://docs.tibco.com/ems105.zip"),
        "8.6.0": make_version("ems", "8.6.0", is_archived=True, convert_eligible=False),
    }
    return product


def test_catalog_fetch_requires_a_scope(runner: CliRunner, tmp_path: Path) -> None:
    """A bare fetch would crawl ~250 products; make that an explicit choice."""
    result = _invoke(runner, tmp_path, "catalog", "fetch")

    assert result.exit_code != 0
    assert "Choose a scope" in result.output


def test_catalog_fetch_rejects_a_version_filter(runner: CliRunner, tmp_path: Path) -> None:
    """Fetching one version of a product would make its siblings look deleted."""
    result = _invoke(runner, tmp_path, "catalog", "fetch", "--product", "ems", "--version", "10.4.0")

    assert result.exit_code != 0
    assert "per product" in result.output


def test_catalog_fetch_merges_into_the_csvs(runner: CliRunner, populated_root: Path, fake_crawl) -> None:
    fake_crawl()
    result = _invoke(runner, populated_root, "catalog", "fetch", "--all")

    assert result.exit_code == 0
    assert "10.5.0" in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")


def test_catalog_fetch_dry_run_writes_nothing(runner: CliRunner, populated_root: Path, fake_crawl) -> None:
    fake_crawl()
    before = (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")
    result = _invoke(runner, populated_root, "catalog", "fetch", "--all", "--dry-run")

    assert result.exit_code == 0
    assert "dry run" in result.output
    assert (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig") == before


def test_catalog_fetch_resolves_a_batch_to_crawl_selectors(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """--batch must narrow the crawl itself, not just the rows printed afterwards.

    The docsite is addressed by slug, so the catalog's slug goes along with the code.
    """
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0", "--batch", "poc-1")
    calls = fake_crawl()
    result = _invoke(runner, populated_root, "catalog", "fetch", "--batch", "poc-1")

    assert result.exit_code == 0
    assert calls[0]["selectors"] == {"ems", "tibco-enterprise-message-service"}


def test_catalog_fetch_with_an_unused_batch_fails(runner: CliRunner, populated_root: Path, fake_crawl) -> None:
    fake_crawl()
    result = _invoke(runner, populated_root, "catalog", "fetch", "--batch", "nope")

    assert result.exit_code != 0
    assert "nope" in result.output


def test_catalog_fetch_excludes_a_listed_product_on_arrival(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """The rule is applied during the merge, so nothing is ever eligible even once."""
    (populated_root / "config" / "scope.yaml").write_text(
        'out_of_scope:\n  - slug: ems\n    reason: "test"\n', encoding="utf-8"
    )
    fake_crawl()

    result = _invoke(runner, populated_root, "catalog", "fetch", "--all")

    assert result.exit_code == 0
    assert "products out of scope" in result.output
    assert "false,scope_rule" in (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")


def test_catalog_fetch_reports_a_rule_that_matched_nothing(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """Only on `--all`: on a scoped fetch every rule it did not visit would look dead."""
    (populated_root / "config" / "scope.yaml").write_text(
        'out_of_scope:\n  - slug: renamed-upstream\n    reason: "test"\n', encoding="utf-8"
    )
    fake_crawl()

    result = _invoke(runner, populated_root, "catalog", "fetch", "--all")

    assert result.exit_code == 0
    assert "renamed-upstream" in result.output


def test_catalog_fetch_reports_unreachable_products_without_failing(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    fake_crawl(errors=["tibco-ebx: GET ... returned HTTP 503"])
    result = _invoke(runner, populated_root, "catalog", "fetch", "--all")

    assert result.exit_code == 0
    assert "503" in result.output
    assert "left as-is" in result.output


def test_catalog_fetch_leaves_the_catalog_alone_when_discovery_returns_nothing(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """An empty crawl is a failed crawl, not a signal that every product vanished."""
    fake_crawl(products=[], errors=["product list: GET ... failed"])
    before = (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")
    result = _invoke(runner, populated_root, "catalog", "fetch", "--all")

    assert result.exit_code != 0
    assert (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig") == before


def test_catalog_fetch_preserves_a_manual_edit(runner: CliRunner, populated_root: Path, fake_crawl) -> None:
    """The whole point of the 3-way merge, asserted end-to-end from argv."""
    _invoke(
        runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0",
        "--zip-url", "https://internal.example/ems.zip",
    )
    fake_crawl()
    result = _invoke(runner, populated_root, "catalog", "fetch", "--all")

    assert result.exit_code == 0
    assert "https://internal.example/ems.zip" in (
        populated_root / "config" / "versions.csv"
    ).read_text(encoding="utf-8-sig")


def test_catalog_fetch_parks_folder_paths_in_the_state_db(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """Machine detail belongs in state.db, not in a spreadsheet column."""
    fake_crawl()
    _invoke(runner, populated_root, "catalog", "fetch", "--all")

    store = StateStore(populated_root / "cache" / "state.db")
    assert store.get_version_metadata("ems", "10.4.0")["folder_path"] == "ems/10.4.0"
    assert store.get_product_metadata("ems")["docsite_id"] == "1042"
    store.close()


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


# -- product scope (architecture.md §3.10) -----------------------------------


def test_catalog_set_out_of_scope_pins_the_decision_as_manual(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--out-of-scope")

    assert result.exit_code == 0
    row = (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")
    assert "false,manual" in row


def test_catalog_set_in_scope_readmits_a_product(runner: CliRunner, populated_root: Path) -> None:
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--out-of-scope")

    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--in-scope")

    assert result.exit_code == 0
    assert "true,manual" in (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")


def test_catalog_list_out_of_scope_shows_only_excluded_products(runner: CliRunner, populated_root: Path) -> None:
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--out-of-scope")

    result = _invoke(runner, populated_root, "catalog", "list", "--out-of-scope")

    assert result.exit_code == 0
    assert "10.4.0" in result.output
    # The Scope column appears only when something is excluded; its cell text is
    # width-truncated by Rich at 80 columns, so the header is what is asserted.
    assert "Scope" in result.output


def test_catalog_list_out_of_scope_when_nothing_is_excluded(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "list", "--out-of-scope")

    assert result.exit_code == 0
    assert "No out-of-scope products" in result.output


def test_catalog_list_rejects_the_two_disjoint_scope_flags(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "list", "--out-of-scope", "--eligible-only")

    assert result.exit_code != 0
    assert "disjoint" in result.output


def test_catalog_list_eligible_only_skips_an_out_of_scope_product(runner: CliRunner, populated_root: Path) -> None:
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--out-of-scope")

    result = _invoke(runner, populated_root, "catalog", "list", "--eligible-only")

    assert result.exit_code == 0
    assert "No matching catalog rows" in result.output


def test_catalog_show_says_an_excluded_product_is_never_converted(runner: CliRunner, populated_root: Path) -> None:
    """The version rows below still say Eligible, so the scope line has to overrule them."""
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--out-of-scope")

    result = _invoke(runner, populated_root, "catalog", "show", "--product", "ems")

    assert result.exit_code == 0
    assert "in_scope=false" in result.output
    assert "10.4.0" in result.output


def test_catalog_triage_counts_scope_alongside_family(runner: CliRunner, populated_root: Path) -> None:
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--out-of-scope")

    result = _invoke(runner, populated_root, "catalog", "triage")

    assert result.exit_code == 0
    assert "1 of 1" in result.output
    assert "out of scope" in result.output


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


def test_catalog_set_zip_source_marks_a_hand_supplied_package(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(
        runner, populated_root, "catalog", "set", "--product", "ems", "--version", "8.6.0",
        "--zip-source", "manual",
    )

    assert result.exit_code == 0
    assert ",manual" in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")


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
