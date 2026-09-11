"""Unit tests for the CLI command tree.

Two contracts are asserted here. Stages that are not built yet must fail loudly
rather than silently succeed -- a no-op `convert` that exits 0 is worse than a
missing one. Stages that *are* built must be reachable end-to-end from argv. The
surface asserted is the one documented in docs/user-guide.md.
"""

import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from docushift import __version__
from docushift.catalog import CatalogManager
from docushift.cli import main
from docushift.discovery import CrawlResult, DocsiteCrawler
from docushift.state import StateStore
from tests.conftest import make_product, make_version

# `download` and `archive download` left this list in Phase 4a, `extract` in 4b-1,
# `convert` in 5a.
PENDING_COMMANDS = [
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
        "tibco-enterprise-message-service", product_code="ems", display_name="TIBCO EMS", family="messaging"
    )
    product.versions = {
        "10.4.0": make_version(
            "tibco-enterprise-message-service", "10.4.0", zip_url="https://docs.tibco.com/ems.zip"
        ),
        "8.6.0": make_version(
            "tibco-enterprise-message-service", "8.6.0", is_archived=True, convert_eligible=False
        ),
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

    The catalog is keyed on the docsite slug, which is also how the crawler addresses
    the A-to-Z list, so a batch resolves straight to the selector with nothing to
    translate -- the `--product ems` path is the one that still has to resolve a code.
    """
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0", "--batch", "poc-1")
    calls = fake_crawl()
    result = _invoke(runner, populated_root, "catalog", "fetch", "--batch", "poc-1")

    assert result.exit_code == 0
    assert calls[0]["selectors"] == {"tibco-enterprise-message-service"}


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


def test_catalog_show_accepts_either_spelling_of_the_product(runner: CliRunner, populated_root: Path) -> None:
    """`--product` takes the slug or the code, and reports the slug either way.

    The slug is the catalog key, so it is what the Product column prints and what a
    user copies back onto the next command line; the code stays accepted because
    typing `ems` is the whole reason it is still a column.
    """
    by_code = _invoke(runner, populated_root, "catalog", "show", "--product", "ems")
    by_slug = _invoke(runner, populated_root, "catalog", "show", "--product", "tibco-enterprise-message-service")

    assert by_code.exit_code == 0
    assert by_slug.exit_code == 0
    assert "tibco-enterprise-message-service" in by_code.output


def test_an_ambiguous_product_code_is_refused_with_the_choices(runner: CliRunner, tmp_path: Path) -> None:
    """Ten real codes name more than one product; the CLI must ask rather than pick one.

    A `ClickException`, not a traceback: the user typed a reasonable thing and needs the
    two slugs to choose between, which is information only the catalog has.
    """
    (tmp_path / "config").mkdir(exist_ok=True)
    state = StateStore(tmp_path / "cache" / "state.db")
    manager = CatalogManager(tmp_path / "config" / "products.csv", tmp_path / "config" / "versions.csv", state)
    manager.merge_fetch_results(
        [
            make_product("spotfire-service-for-statistica", product_code="stat-sts"),
            make_product("tibco-data-science-service-for-tibco-spotfire", product_code="stat-sts"),
        ]
    )
    state.close()

    result = _invoke(runner, tmp_path, "catalog", "show", "--product", "stat-sts")

    assert result.exit_code != 0
    assert "shared by 2 products" in result.output
    assert "spotfire-service-for-statistica" in result.output
    assert "tibco-data-science-service-for-tibco-spotfire" in result.output


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


# -- end-of-support retirement (architecture.md §3.11) -----------------------


def _write_eos(root: Path, rows: str, aliases: str = "") -> None:
    """Drops an end-of-support report and its alias file into a project root.

    `rows` is the report body without its header. `TIBCO Enterprise Message
    Service` is the name that slugifies onto `populated_root`'s only product.
    """
    report = root / "config" / "eos" / "report.csv"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "Product Name,Version,Release Status,Retirement Date,Last Updated On,\n" + rows, encoding="utf-8-sig"
    )
    (root / "config" / "eos.yaml").write_text(f"report: eos/report.csv\n{aliases}", encoding="utf-8")


RETIRED_ROW = "TIBCO Enterprise Message Service,10.4.0,Retired,12-31-2024,01-05-2025,\n"


def test_catalog_eos_applies_the_report(runner: CliRunner, populated_root: Path) -> None:
    _write_eos(populated_root, RETIRED_ROW)

    result = _invoke(runner, populated_root, "catalog", "eos")

    assert result.exit_code == 0
    assert "1 in-scope eligible version(s) are retired" in result.output
    assert "retired" in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")


def test_catalog_eos_names_every_emptied_product(runner: CliRunner, populated_root: Path) -> None:
    """10.4.0 is the product's only eligible version, so retiring it publishes nothing."""
    _write_eos(populated_root, RETIRED_ROW)

    result = _invoke(runner, populated_root, "catalog", "eos")

    assert "no convertible version left" in result.output
    assert "tibco-enterprise-message-service" in result.output


def test_catalog_eos_reports_coverage_alongside_a_clean_result(
    runner: CliRunner, populated_root: Path
) -> None:
    """'Nothing retired' over one covered product and over zero are different findings."""
    _write_eos(populated_root, "Some Other Product,1.0.0,Retired,12-31-2024,01-05-2025,\n")

    result = _invoke(runner, populated_root, "catalog", "eos")

    assert result.exit_code == 0
    assert "rows for 0 of 1 catalogued products" in result.output
    assert "No in-scope eligible version is retired" in result.output


def test_catalog_eos_warns_about_a_stale_alias(runner: CliRunner, populated_root: Path) -> None:
    _write_eos(
        populated_root,
        RETIRED_ROW,
        aliases='aliases:\n  - report_name: "Renamed Upstream"\n    slug: tibco-ebx\n',
    )

    result = _invoke(runner, populated_root, "catalog", "eos")

    assert result.exit_code == 0
    assert "Renamed Upstream" in result.output


def test_catalog_eos_on_a_project_with_no_report(runner: CliRunner, populated_root: Path) -> None:
    """The file is optional; the command must still run and say nothing was retired."""
    result = _invoke(runner, populated_root, "catalog", "eos")

    assert result.exit_code == 0
    assert "No in-scope eligible version is retired" in result.output


def test_catalog_list_retired_shows_only_retired_versions(runner: CliRunner, populated_root: Path) -> None:
    _write_eos(populated_root, RETIRED_ROW)
    _invoke(runner, populated_root, "catalog", "eos")

    result = _invoke(runner, populated_root, "catalog", "list", "--retired")

    assert result.exit_code == 0
    assert "10.4.0" in result.output
    assert "8.6.0" not in result.output
    assert "Status" in result.output


def test_catalog_list_retired_when_nothing_is_retired(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "catalog", "list", "--retired")

    assert result.exit_code == 0
    assert "No retired versions" in result.output


def test_catalog_list_rejects_the_two_disjoint_retirement_flags(
    runner: CliRunner, populated_root: Path
) -> None:
    result = _invoke(runner, populated_root, "catalog", "list", "--retired", "--eligible-only")

    assert result.exit_code != 0
    assert "disjoint" in result.output


def test_catalog_list_eligible_only_skips_a_retired_version(runner: CliRunner, populated_root: Path) -> None:
    _write_eos(populated_root, RETIRED_ROW)
    _invoke(runner, populated_root, "catalog", "eos")

    result = _invoke(runner, populated_root, "catalog", "list", "--eligible-only")

    assert result.exit_code == 0
    assert "No matching catalog rows" in result.output


def test_catalog_set_release_status_overrides_the_report(runner: CliRunner, populated_root: Path) -> None:
    """The escape hatch, from argv: convert a version support has retired."""
    _write_eos(populated_root, RETIRED_ROW)
    _invoke(runner, populated_root, "catalog", "eos")

    result = _invoke(
        runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0",
        "--release-status", "ga",
    )

    assert result.exit_code == 0
    # The retirement date is left standing: support really did retire this on that
    # day, and the override is the record of converting it anyway, not a denial.
    assert "ga,2024-12-31,manual" in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")
    listed = _invoke(runner, populated_root, "catalog", "list", "--eligible-only")
    assert "10.4.0" in listed.output


def test_catalog_set_release_status_requires_a_version(runner: CliRunner, populated_root: Path) -> None:
    """Retirement is a per-version fact; applying one to a whole product is meaningless."""
    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--release-status", "retired")

    assert result.exit_code != 0
    assert "--release-status" in result.output


def test_catalog_set_rejects_an_unknown_release_status(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(
        runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0",
        "--release-status", "end-of-life",
    )

    assert result.exit_code != 0


def test_catalog_show_lists_the_lifecycle_status(runner: CliRunner, populated_root: Path) -> None:
    _write_eos(populated_root, RETIRED_ROW)
    _invoke(runner, populated_root, "catalog", "eos")

    result = _invoke(runner, populated_root, "catalog", "show", "--product", "ems")

    assert result.exit_code == 0
    assert "Status" in result.output


def test_catalog_triage_reports_retirement(runner: CliRunner, populated_root: Path) -> None:
    _write_eos(populated_root, RETIRED_ROW)
    _invoke(runner, populated_root, "catalog", "eos")

    result = _invoke(runner, populated_root, "catalog", "triage")

    assert result.exit_code == 0
    assert "would otherwise be converted" in result.output
    assert "no convertible version left" in result.output


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
    """No taxonomy.yaml here, so the BU token falls back to the slugified key."""
    result = _invoke(runner, populated_root, "catalog", "show", "--product", "ems")

    assert result.exit_code == 0
    assert "en-us-tibco-messaging" in result.output
    # The workspace is not a repository name and carries no publishing suffix.
    assert "userdocs" not in result.output


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


# -- download (design.md §5.1, §5.2) -----------------------------------------


def _zip(path: Path, members: dict[str, str] | None = None) -> Path:
    """A readable ZIP on disk, built in-process rather than committed."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in (members or {"docs/index.html": "hi"}).items():
            archive.writestr(name, text)
    return path


def test_download_without_a_scope_is_refused(runner: CliRunner, populated_root: Path) -> None:
    """A bare `download` over 4,000 versions is never what anyone meant."""
    result = _invoke(runner, populated_root, "download")

    assert result.exit_code != 0
    assert "Choose a scope" in result.output


def test_download_dry_run_lists_targets_without_writing(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "download", "--all", "--dry-run")

    assert result.exit_code == 0
    assert "10.4.0" in result.output
    # The archived version is not the pipeline's business -- `archive download` is.
    assert "8.6.0" not in result.output
    # `families/` itself is created by every invocation; the family workspace is not.
    assert not (populated_root / "families" / "en-us-tibco-messaging").exists()


def test_download_from_file_files_the_package_and_pins_the_row(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    source = _zip(tmp_path / "handed-over.zip")

    result = _invoke(
        runner, populated_root, "download",
        "--product", "ems", "--version", "10.4.0", "--from-file", str(source),
    )

    assert result.exit_code == 0
    assert "zip_source=manual" in result.output
    landed = (
        populated_root / "families" / "en-us-tibco-messaging" / "downloads"
        / "tibco-enterprise-message-service-10.4.0.zip"
    )
    assert landed.exists()
    assert source.exists()


def test_download_from_file_needs_both_selectors(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    source = _zip(tmp_path / "handed-over.zip")

    result = _invoke(runner, populated_root, "download", "--product", "ems", "--from-file", str(source))

    assert result.exit_code != 0
    assert "--product and --version" in result.output


def test_download_from_file_adds_an_unknown_version_with_a_warning(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    source = _zip(tmp_path / "handed-over.zip")

    result = _invoke(
        runner, populated_root, "download",
        "--product", "ems", "--version", "9.9.9", "--from-file", str(source),
    )

    assert result.exit_code == 0
    assert "adding the row" in result.output
    assert "9.9.9" in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")


def test_download_from_file_on_an_unknown_product_is_an_error(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    """A typo'd code would otherwise seed a junk product row from a single ZIP."""
    source = _zip(tmp_path / "handed-over.zip")

    result = _invoke(
        runner, populated_root, "download",
        "--product", "nope", "--version", "1.0", "--from-file", str(source),
    )

    assert result.exit_code != 0
    assert "catalog fetch" in result.output


def test_download_from_file_rejects_a_sign_in_page(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    source = tmp_path / "handed-over.zip"
    source.write_text("<html>Please sign in</html>", encoding="utf-8")

    result = _invoke(
        runner, populated_root, "download",
        "--product", "ems", "--version", "10.4.0", "--from-file", str(source),
    )

    assert result.exit_code != 0
    assert "readable ZIP" in result.output


# -- archive download --------------------------------------------------------


def test_archive_download_from_file_lands_outside_the_working_set(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    """In `archive/`, because an archived ZIP in `downloads/` would look to `extract`
    like a package awaiting conversion."""
    source = _zip(tmp_path / "ems-8.6.0.zip")

    result = _invoke(
        runner, populated_root, "archive", "download",
        "--product", "ems", "--version", "8.6.0", "--from-file", str(source),
    )

    assert result.exit_code == 0
    family = populated_root / "families" / "en-us-tibco-messaging"
    assert (family / "archive" / "tibco-enterprise-message-service-8.6.0.zip").exists()
    assert not (family / "downloads").exists()
    # The pipeline's package for 8.6.0 was never supplied, so the row must not be
    # pinned manual -- that would make `download` skip it forever.
    assert "manual" not in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")


def test_archive_download_extract_unpacks_within_archive(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    source = _zip(tmp_path / "ems-8.6.0.zip", {"docs/index.html": "hi", "docs/a.html": "a"})

    result = _invoke(
        runner, populated_root, "archive", "download",
        "--product", "ems", "--version", "8.6.0", "--from-file", str(source), "--extract",
    )

    assert result.exit_code == 0
    unpacked = (
        populated_root / "families" / "en-us-tibco-messaging" / "archive"
        / "tibco-enterprise-message-service-8.6.0" / "docs" / "index.html"
    )
    assert unpacked.read_text(encoding="utf-8") == "hi"
    assert not (populated_root / "families" / "en-us-tibco-messaging" / "extracted").exists()


def test_archive_download_refuses_an_archive_that_escapes_its_target(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    source = _zip(tmp_path / "ems-8.6.0.zip", {"docs/index.html": "hi", "../escape.txt": "owned"})

    result = _invoke(
        runner, populated_root, "archive", "download",
        "--product", "ems", "--version", "8.6.0", "--from-file", str(source), "--extract",
    )

    assert result.exit_code != 0
    assert not (tmp_path / "escape.txt").exists()


def test_archive_download_without_a_url_points_at_from_file(
    runner: CliRunner, populated_root: Path
) -> None:
    """Archived `zipPath` values are the ones most likely to be stale or absent."""
    result = _invoke(runner, populated_root, "archive", "download", "--product", "ems", "--version", "8.6.0")

    assert result.exit_code != 0
    assert "--from-file" in result.output


# -- extract (design.md §6.1, §7) ----------------------------------------------


def _place(root: Path, version: str, members: dict[str, str]) -> Path:
    """Files a ZIP where `download` would have left it, for the populated_root product."""
    downloads = root / "families" / "en-us-tibco-messaging" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    return _zip(downloads / f"tibco-enterprise-message-service-{version}.zip", members)


def test_extract_requires_a_scope(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "extract")

    assert result.exit_code != 0
    assert "Choose a scope" in result.output


def test_extract_unpacks_and_names_the_engine(runner: CliRunner, populated_root: Path) -> None:
    _place(populated_root, "10.4.0", {"guide/Output.mcwebhelp": "", "guide/a.htm": "<html/>"})

    result = _invoke(runner, populated_root, "extract", "--all")

    assert result.exit_code == 0
    unpacked = (
        populated_root / "families" / "en-us-tibco-messaging" / "extracted"
        / "tibco-enterprise-message-service" / "10.4.0" / "guide" / "a.htm"
    )
    assert unpacked.is_file()
    assert "flare" in result.output
    # The archived 8.6.0 row is not convert-eligible, so it is never unpacked.
    assert not (unpacked.parents[2] / "8.6.0").exists()


def test_extract_writes_the_engine_back_to_the_catalog(runner: CliRunner, populated_root: Path) -> None:
    _place(populated_root, "10.4.0", {"topics/GUID-AAA.html": "<html/>"})

    _invoke(runner, populated_root, "extract", "--all")

    rows = (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")
    assert "dita,detected" in rows


def test_extract_dry_run_lists_targets_without_writing(runner: CliRunner, populated_root: Path) -> None:
    _place(populated_root, "10.4.0", {"guide/a.htm": "<html/>"})

    result = _invoke(runner, populated_root, "extract", "--all", "--dry-run")

    assert result.exit_code == 0
    assert "Would extract" in result.output
    assert not (populated_root / "families" / "en-us-tibco-messaging" / "extracted").exists()


def test_extract_names_an_undetected_version_rather_than_counting_it(
    runner: CliRunner, populated_root: Path
) -> None:
    """`auto` is a detector bug and an unconvertible engine is a scoping call (§7.3 step 2)."""
    _place(populated_root, "10.4.0", {"readme.html": "<html><body>x</body></html>"})

    result = _invoke(runner, populated_root, "extract", "--all")

    assert result.exit_code == 0
    assert "engine undetected" in result.output


def test_extract_names_an_identified_engine_that_has_no_converter(
    runner: CliRunner, populated_root: Path
) -> None:
    _place(populated_root, "10.4.0", {"lib/snext.css": "", "fn.html": "<html/>"})

    result = _invoke(runner, populated_root, "extract", "--all")

    assert result.exit_code == 0
    # Not the whole sentence: Rich wraps the line at the console width.
    assert "r-help is identified but has no" in result.output


def test_extract_reports_a_missing_package_without_failing(runner: CliRunner, populated_root: Path) -> None:
    result = _invoke(runner, populated_root, "extract", "--all")

    assert result.exit_code == 0
    assert "docushift download" in result.output


def test_extract_reports_the_csh_tally_and_the_asset_table(
    runner: CliRunner, populated_root: Path
) -> None:
    """The four §6.2/§6.4 report blocks. A version with no help map is visible now."""
    _place(populated_root, "10.4.0", {
        "guide/Output.mcwebhelp": "",
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Data/Alias.xml": '<CatapultAliasFile><Map Name="X" Link="a.htm"/></CatapultAliasFile>',
        "guide/images/d.gif": "x",
    })

    result = _invoke(runner, populated_root, "extract", "--all")

    assert result.exit_code == 0
    assert "CSH: 1 source(s), 1 identifier(s)." in result.output
    assert "Assets" in result.output
    assert "image" in result.output


def test_extract_names_an_unmarked_api_candidate_and_the_unclaimed_residue(
    runner: CliRunner, populated_root: Path
) -> None:
    """Two report lines, never a classification -- the files stay documentation."""
    _place(populated_root, "10.4.0", {
        "guide/Output.mcwebhelp": "",
        "guide/Data/HelpSystem.xml": "<x/>",
        "components-api/a.html": "<html/>",
    })

    result = _invoke(runner, populated_root, "extract", "--all")

    assert result.exit_code == 0
    # Not the whole sentence: Rich wraps the line at the console width.
    assert "components-api/ 1 file(s), no known" in result.output
    assert "unclaimed" in result.output
    rows = (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")
    # `_has_api_ref` stays false: a name has classified nothing.
    assert ",false,0," in rows


def test_extract_writes_the_five_inventory_columns_back(
    runner: CliRunner, populated_root: Path
) -> None:
    _place(populated_root, "10.4.0", {"guide/Output.mcwebhelp": "", "guide/a.htm": "<html/>"})

    _invoke(runner, populated_root, "extract", "--all")

    rows = (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")
    line = next(row for row in rows.splitlines() if "10.4.0" in row)
    # false,0,false,0,2 -- measured zeroes, not the blanks of a row nobody opened.
    assert "false,0,false,0,2" in line
