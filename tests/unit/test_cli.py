"""Unit tests for the CLI command tree.

Two contracts are asserted here. Stages that are not built yet must fail loudly
rather than silently succeed -- a no-op `convert` that exits 0 is worse than a
missing one. Stages that *are* built must be reachable end-to-end from argv. The
surface asserted is the one documented in docs/user-guide.md.
"""

import shutil
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from docushift import __version__
from docushift.catalog import CatalogManager
from docushift.cli import console, main
from docushift.discovery import CrawlResult, DocsiteCrawler
from docushift.state import StateStore
from tests.conftest import REPO_ROOT, make_product, make_version


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def populated_root(tmp_path: Path) -> Path:
    """A project root whose catalog CSVs already hold one product with two versions.

    The shipped AEM templates are copied in for the reason `conftest.project_root`
    copies them: from Phase 6a a version that cannot find `toc.yml.j2` fails to
    convert, and from 6b a product that cannot find `metadata.yml.j2` fails to
    sync. A root without them is a condition no installation is in.
    """
    (tmp_path / "config").mkdir(exist_ok=True)
    shutil.copytree(REPO_ROOT / "config" / "aem_templates", tmp_path / "config" / "aem_templates")
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
        "reframe",
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


@pytest.mark.parametrize(
    "command",
    ["download", "extract", "convert", "reframe", "sync", "catalog list", "catalog fetch"],
)
def test_batch_is_a_selector_on_every_stage(runner: CliRunner, command: str) -> None:
    """A POC scope must be expressible on every command that walks the catalog."""
    result = runner.invoke(main, [*command.split(), "--help"])

    assert result.exit_code == 0
    assert "--batch" in result.output


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

        # Mirrors the real signature exactly, `family` included by its absence:
        # Phase 32 removed that parameter, and a fake that still tolerated it
        # would let the CLI quietly start passing one again.
        def discover(self, bu=None, selectors=None, on_progress=None):
            calls.append({"bu": bu, "selectors": selectors})
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


def test_catalog_fetch_resolves_a_family_to_crawl_selectors(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """Phase 32. --family had to move from filtering output to scoping the crawl.

    Discovery assigns no family any more, so filtering the crawl's results by one
    would match nothing whatever the user typed. A family is a fact the catalog
    holds, so it is read from there -- which also turns a family fetch into N
    requests instead of 700.
    """
    calls = fake_crawl()
    result = _invoke(runner, populated_root, "catalog", "fetch", "--family", "messaging")

    assert result.exit_code == 0
    assert calls[0]["selectors"] == {"tibco-enterprise-message-service"}


def test_catalog_fetch_with_an_empty_family_fails_rather_than_crawling_everything(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """The failure mode the selector rewrite had to avoid.

    An unmatched family used to mean "crawl all 700 and filter to nothing". It
    must not silently become "crawl all 700 and keep everything" either.
    """
    calls = fake_crawl()
    result = _invoke(runner, populated_root, "catalog", "fetch", "--family", "fulfillment")

    assert result.exit_code != 0
    assert "fulfillment" in result.output
    assert calls == []


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


def test_catalog_set_rejects_a_family_taxonomy_does_not_declare(
    runner: CliRunner, populated_root: Path
) -> None:
    """Phase 32. With a human as the only author, an undeclared key is a typo.

    Letting it through would auto-register a workspace folder and, downstream, a
    publishing repository -- so the near-miss has to fail rather than warn. The
    declared keys are named in the message because that is what makes the typo
    obvious.
    """
    (populated_root / "config" / "taxonomy.yaml").write_text(
        """version: "1.0"
business_units:
  tibco:
    name: TIBCO
    families:
      messaging: {name: Messaging}
rules: []
""",
        encoding="utf-8",
    )
    before = (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")

    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--family", "mesaging")

    assert result.exit_code != 0
    assert "not declared in taxonomy.yaml" in result.output
    assert "messaging" in result.output
    assert (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig") == before


def test_catalog_triage_suggests_a_family_without_assigning_one(
    runner: CliRunner, populated_root: Path
) -> None:
    """Phase 32 kept the rules' family key as advice, so triage must actually show it."""
    (populated_root / "config" / "taxonomy.yaml").write_text(
        """version: "1.0"
business_units:
  tibco:
    name: TIBCO
    families:
      messaging: {name: Messaging}
rules:
  - match: ["ems"]
    bu: tibco
    family: messaging
""",
        encoding="utf-8",
    )
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--family", "messaging")
    # Back to untriaged, which is the only state a suggestion is offered for.
    products = populated_root / "config" / "products.csv"
    products.write_text(
        products.read_text(encoding="utf-8-sig").replace("messaging,manual", "general,unclassified"),
        encoding="utf-8-sig",
    )

    result = _invoke(runner, populated_root, "catalog", "triage")

    assert result.exit_code == 0
    assert "Suggestions only" in result.output
    assert "messaging" in result.output
    # Advice, not an assignment: nothing was written.
    assert "general,unclassified" in products.read_text(encoding="utf-8-sig")


def test_catalog_set_family_is_unrestricted_when_no_family_is_declared(
    runner: CliRunner, populated_root: Path
) -> None:
    """An empty reference means unconfigured, not "every family is a typo".

    `populated_root` ships no taxonomy.yaml, which is the state a fresh checkout
    and most of this module are in; validating against nothing would turn the
    Phase 32 guard into a blanket refusal.
    """
    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--family", "anything")

    assert result.exit_code == 0


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


def test_download_dry_run_says_which_name_each_url_carries(runner: CliRunner, populated_root: Path) -> None:
    """Phase 40: a version the sitemap lists under an older name shows it, labelled `sitemap`."""
    from docushift.discovery.sitemap import SitemapCache

    # The shipped template: without one neither name can be built.
    shutil.copy(REPO_ROOT / "config" / "docsite.yaml", populated_root / "config" / "docsite.yaml")
    SitemapCache(populated_root / "cache" / "coveo").save_manifest(
        {"files": {}, "products": {"tibco-enterprise-message-service": ["tibco-ems-old-10-4-0"]}}
    )

    result = _invoke(runner, populated_root, "download", "--all", "--dry-run")

    assert result.exit_code == 0
    # The totals line, not the URL cell: a narrow console wraps the cell.
    assert "1 sitemap" in result.output


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


# -- sync ------------------------------------------------------------------------


def _convert_output(root: Path, version: str, files: dict[str, str]) -> Path:
    """Writes a converted tree where `sync` expects one, bypassing Stage 5."""
    target = (
        root / "output" / "en-us-tibco-messaging"
        / "tibco-enterprise-message-service" / version
    )
    for name, body in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return target


def test_sync_places_a_converted_version_in_the_publishing_form(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    _convert_output(populated_root, "10.4.0", {"index.md": "# x\n", "toc.yml": "nodes: []\n"})
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _invoke(runner, populated_root, "sync", "--all", "--target-dir", str(workspace))

    assert result.exit_code == 0
    published = (
        workspace / "en-us-tibco-messaging-userdocs" / "en-us"
        / "tibco-enterprise-message-service" / "online-help" / "10-4-0"
    )
    assert (published / "index.md").is_file()
    assert (published.parent / "version.yml").is_file()
    assert (published.parent.parent / "metadata.yml").is_file()
    assert "Synced" in result.output


def test_sync_reports_a_version_with_no_converted_tree_without_failing(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _invoke(runner, populated_root, "sync", "--all", "--target-dir", str(workspace))

    assert result.exit_code == 0
    assert "docushift convert" in result.output


def test_sync_dry_run_names_the_destination_without_writing(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    _convert_output(populated_root, "10.4.0", {"index.md": "# x\n"})
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _invoke(
        runner, populated_root, "sync", "--all", "--target-dir", str(workspace), "--dry-run"
    )

    assert result.exit_code == 0
    assert "Would sync" in result.output
    assert not (workspace / "en-us-tibco-messaging-userdocs").exists()



def test_sync_dry_run_reports_the_tree_the_run_would_publish(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    """X1-12. The dry run tested `output/` for every product, so a product that
    publishes merged, with no merge, read "present" and the real run refused it.

    Flare, since Phase 42: only an engine Reframe merges is held to the merged tree."""
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems",
            "--version", "10.4.0", "--engine", "flare")
    _convert_output(populated_root, "10.4.0", {"index.md": "# x\n"})
    (populated_root / "config" / "reframe.yaml").write_text(
        "products:\n  tibco-enterprise-message-service:\n    publish: true\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _invoke(
        runner, populated_root, "sync", "--product", "tibco-enterprise-message-service",
        "--version", "10.4.0", "--target-dir", str(workspace), "--dry-run"
    )

    assert result.exit_code == 0
    assert "present" not in result.output
    assert "refused" in result.output
    assert "publishes merged and no merged tree" in " ".join(result.output.split())

def test_sync_exits_non_zero_when_a_version_fails(
    runner: CliRunner, populated_root: Path, tmp_path: Path, monkeypatch
) -> None:
    """Phase 15e. The first `sync --family ems` run printed six red `x` rows and
    exited **0**, because the exit rule read findings and a failed copy is a row.
    A batch driver reading that status is told six failures were a success.
    """
    _convert_output(populated_root, "10.4.0", {"index.md": "# x\n"})
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def refuse(*args, **kwargs):
        raise OSError("the disk said no")

    monkeypatch.setattr("docushift.sync.distributor.shutil.copytree", refuse)

    result = _invoke(runner, populated_root, "sync", "--all", "--target-dir", str(workspace))

    assert result.exit_code == 1
    assert "Failed" in result.output


def test_sync_needs_a_scope_like_every_other_stage(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _invoke(runner, populated_root, "sync", "--target-dir", str(workspace))

    assert result.exit_code != 0
    assert "Choose a scope" in result.output


# -- status and report (Phase 7a) ----------------------------------------------


def test_status_prints_the_funnel_and_names_no_findings(
    runner: CliRunner, populated_root: Path
) -> None:
    """The §7.1 boundary at the command level: `status` is about progress only."""
    result = _invoke(runner, populated_root, "status")

    assert result.exit_code == 0
    for step in ("Catalogued", "In scope", "Convert eligible", "Downloaded", "Converted"):
        assert step in result.output
    # No Published row without --target-dir: sync currency is compared, never
    # recorded, so the database cannot answer it (§7.2).
    assert "Published" not in result.output


def test_status_counts_published_versions_from_the_target_tree(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    _convert_output(populated_root, "10.4.0", {"index.md": "# x\n", "toc.yml": "nodes: []\n"})
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _invoke(runner, populated_root, "sync", "--all", "--target-dir", str(workspace))

    result = _invoke(runner, populated_root, "status", "--target-dir", str(workspace))

    assert result.exit_code == 0
    assert "Published" in result.output


def test_status_engines_separates_undetermined_from_unconvertible(
    runner: CliRunner, populated_root: Path
) -> None:
    result = _invoke(runner, populated_root, "status", "--engines")

    assert result.exit_code == 0
    assert "Engines" in result.output
    assert "still `auto`" in result.output


def test_report_explains_a_code_without_a_run_or_a_database(
    runner: CliRunner, populated_root: Path
) -> None:
    """`--explain` is answered from the register, so it works on a fresh checkout."""
    result = _invoke(runner, populated_root, "report", "--explain", "csh_unresolved")

    assert result.exit_code == 0
    assert "CSH_UNRESOLVED" in result.output
    assert "specified in" in result.output


def test_report_rejects_a_code_that_is_not_in_the_register(
    runner: CliRunner, populated_root: Path
) -> None:
    result = _invoke(runner, populated_root, "report", "--explain", "ASSET_WOBBLY")

    assert result.exit_code != 0
    assert "not a registered finding code" in result.output


def test_report_on_an_empty_database_says_so_rather_than_printing_nothing(
    runner: CliRunner, populated_root: Path
) -> None:
    result = _invoke(runner, populated_root, "report")

    assert result.exit_code != 0
    assert "No run has been recorded" in result.output


def test_catalog_eos_records_what_it_prints(runner: CliRunner, populated_root: Path) -> None:
    """The gap 7a closes: these numbers were already computed and already printed.

    Before this phase `catalog eos` was one of four stage commands that opened no
    run, so everything it found lived only in the terminal scrollback.
    """
    (populated_root / "config" / "scope.yaml").write_text(
        'out_of_scope:\n  - slug: gone-upstream\n    reason: "renamed"\n', encoding="utf-8"
    )

    result = _invoke(runner, populated_root, "catalog", "eos")

    assert result.exit_code == 0
    store = StateStore(populated_root / "cache" / "state.db")
    run = store.last_run("catalog")
    codes = [row["code"] for row in store.get_findings(run["run_id"])]
    assert "SCOPE_RULE_UNMATCHED" in codes
    store.close()


def test_report_reads_back_the_run_a_stage_just_wrote(
    runner: CliRunner, populated_root: Path
) -> None:
    (populated_root / "config" / "scope.yaml").write_text(
        'out_of_scope:\n  - slug: gone-upstream\n    reason: "renamed"\n', encoding="utf-8"
    )
    _invoke(runner, populated_root, "catalog", "eos")

    result = _invoke(runner, populated_root, "report", "--run", "last")

    assert result.exit_code == 0
    assert "catalog" in result.output
    assert "SCOPE_RULE_UNMATCHED" in result.output


def test_report_filters_on_a_code_and_exports_markdown(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    (populated_root / "config" / "scope.yaml").write_text(
        'out_of_scope:\n  - slug: gone-upstream\n    reason: "renamed"\n', encoding="utf-8"
    )
    _invoke(runner, populated_root, "catalog", "eos")
    export = tmp_path / "reports" / "eos.md"

    result = _invoke(
        runner, populated_root, "report", "--code", "SCOPE_RULE_UNMATCHED", "--export", str(export)
    )

    assert result.exit_code == 0
    assert export.is_file()
    text = export.read_text(encoding="utf-8")
    assert "SCOPE_RULE_UNMATCHED" in text
    assert "code=SCOPE_RULE_UNMATCHED" in text


def test_report_prune_drops_old_findings_and_keeps_the_run_rows(
    runner: CliRunner, populated_root: Path
) -> None:
    (populated_root / "config" / "scope.yaml").write_text(
        'out_of_scope:\n  - slug: gone-upstream\n    reason: "renamed"\n', encoding="utf-8"
    )
    _invoke(runner, populated_root, "catalog", "eos")
    _invoke(runner, populated_root, "catalog", "eos")

    result = _invoke(runner, populated_root, "report", "--prune", "--keep", "1")

    assert result.exit_code == 0
    store = StateStore(populated_root / "cache" / "state.db")
    assert len(store.recent_runs()) == 2
    assert store.recent_runs()[1]["findings"] == 0
    store.close()


@pytest.mark.parametrize("command", ["download", "extract", "convert", "sync"])
def test_a_selection_that_matches_nothing_exits_one(
    runner: CliRunner, populated_root: Path, tmp_path: Path, command: str
) -> None:
    """§7.4. Until 7a a typo in --product was indistinguishable from a clean run."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    extra = ["--target-dir", str(workspace)] if command == "sync" else []

    result = _invoke(runner, populated_root, command, "--family", "nothing-like-this", *extra)

    assert result.exit_code == 1
    assert "No convert-eligible versions match" in result.output


def test_a_dry_run_over_an_empty_selection_exits_one_too(
    runner: CliRunner, populated_root: Path
) -> None:
    """Not exempt: it is the same mistake, discovered one command earlier."""
    result = _invoke(runner, populated_root, "extract", "--family", "nope", "--dry-run")

    assert result.exit_code == 1


def test_a_run_that_found_errors_still_exits_zero(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    """A stage that did its work exits 0 -- notes and warnings are not failures.

    `validate` and, since Phase 15e, `sync` gate on *errors* and on failed rows;
    neither is present here, so the rule this pins is the other half: a clean run
    with findings in it is still a clean run.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _convert_output(populated_root, "10.4.0", {"index.md": "# x\n", "toc.yml": "nodes: []\n"})

    result = _invoke(runner, populated_root, "sync", "--all", "--target-dir", str(workspace))

    assert result.exit_code == 0


# -- the reframe funnel (planning.md Phase 24) --------------------------------


def _funnel_line(stats, manager) -> str:
    """The rendered line, unwrapped. Rich hard-wraps at the console width."""
    from docushift.cli import _report_reframe_funnel

    with console.capture() as captured:
        _report_reframe_funnel(stats, manager)
    return " ".join(captured.get().split())


def _merged(slug: str, version: str, md: int, files: int):
    from docushift.reframe import ReframeOutcome, ReframeResult

    return ReframeResult(
        slug, version, ReframeOutcome.REFRAMED, reframed_md_files=md, reframed_files=files
    )


class _Rows:
    """The two "before" counts, keyed as `CatalogManager.get_version` returns them."""

    def __init__(self, rows: dict[tuple[str, str], tuple[int, int]]) -> None:
        self._rows = rows

    def get_version(self, slug: str, version: str):
        found = self._rows.get((slug, version))
        return make_version(slug, version, doc_files=found[0], md_files=found[1]) if found else None


def test_the_funnel_reports_both_percentages() -> None:
    """One figure alone is a lie by omission in whichever direction it is read.

    The pilot's real numbers: the merge turned 1,441 converted files into 124, and
    the gap between that and the source count is mostly `convert` declining to
    emit a file at all rather than anything being compressed.
    """
    from docushift.reframe import ReframeStats

    stats = ReframeStats(results=[_merged("ems", "10.5.1", 124, 163)])
    rows = _Rows({("ems", "10.5.1"): (2268, 1441)})

    line = _funnel_line(stats, rows)

    assert "2268 source doc -> 1441 converted -> 124 merged" in line
    assert "91.4% fewer at the merge" in line
    assert "94.5% end to end" in line
    assert "163 file(s)" in line


def test_the_funnel_sums_only_the_versions_it_measured() -> None:
    """A version this run did not reach must not deflate the ratio for the ones it did."""
    from docushift.reframe import ReframeOutcome, ReframeResult, ReframeStats

    stats = ReframeStats(results=[
        _merged("ems", "10.5.1", 124, 163),
        _merged("ems", "10.4.0", 128, 169),
        ReframeResult("ems", "10.3.0", ReframeOutcome.NOT_FLARE),
    ])
    rows = _Rows({
        ("ems", "10.5.1"): (2268, 1441),
        ("ems", "10.4.0"): (2276, 1457),
        ("ems", "10.3.0"): (9999, 9999),
    })

    line = _funnel_line(stats, rows)

    assert "4544 source doc -> 2898 converted -> 252 merged" in line


def test_the_funnel_is_silent_for_a_standalone_run() -> None:
    """`--input` names a catalog row to key metadata, not to measure against, and a
    funnel with one of its three columns missing is not a funnel."""
    from docushift.reframe import ReframeStats

    stats = ReframeStats(results=[_merged("ems", "10.5.1", 124, 163)])

    assert _funnel_line(stats, None) == ""


def test_the_funnel_is_silent_when_nothing_was_merged() -> None:
    """A selection that was entirely not-Flare has no ratio to report."""
    from docushift.reframe import ReframeOutcome, ReframeResult, ReframeStats

    stats = ReframeStats(results=[ReframeResult("ems", "10.3.0", ReframeOutcome.NOT_FLARE)])

    assert _funnel_line(stats, _Rows({})) == ""


def test_a_version_whose_conversion_was_never_measured_contributes_nothing() -> None:
    """Blank is not zero: a row with no `_md_files` cannot be an end of a ratio."""
    from docushift.reframe import ReframeStats

    stats = ReframeStats(results=[_merged("ems", "10.5.1", 124, 163)])

    assert _funnel_line(stats, _Rows({("ems", "10.5.1"): (0, 0)})) == ""


# -- the command layer (Phase 34, R12) ---------------------------------------


def _runs(root: Path) -> list[dict]:
    store = StateStore(root / "cache" / "state.db")
    try:
        return store.recent_runs()
    finally:
        store.close()


def _traceback_free(result) -> bool:
    """True when the command ended through Click, not an uncaught exception."""
    return result.exception is None or isinstance(result.exception, SystemExit)


def test_archive_download_from_file_adds_an_unknown_version_outside_the_pipeline(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    """R12-01. The row took the model defaults -- active and convert-eligible -- so a
    reference ZIP for an old release became `download --all` work, and `archive
    list` did not show it."""
    source = _zip(tmp_path / "ems-5.0.0.zip")

    result = _invoke(
        runner, populated_root, "archive", "download",
        "--product", "ems", "--version", "5.0.0", "--from-file", str(source),
    )

    assert result.exit_code == 0
    assert "archived row" in result.output
    queued = _invoke(runner, populated_root, "download", "--all", "--dry-run")
    assert "5.0.0" not in queued.output
    listed = _invoke(runner, populated_root, "archive", "list")
    assert "5.0.0" in listed.output
    manager = CatalogManager(populated_root / "config" / "products.csv", populated_root / "config" / "versions.csv")
    row = manager.get_version("tibco-enterprise-message-service", "5.0.0")
    assert row.is_archived and not row.convert_eligible


def test_a_fetch_keeps_a_version_archive_download_added(
    runner: CliRunner, populated_root: Path, tmp_path: Path, fake_crawl
) -> None:
    """INDEX.md's batch-1 known gap: the hand-added archived row blocked the next
    fetch as a "deletion", because discovery has never returned it."""
    _invoke(
        runner, populated_root, "archive", "download",
        "--product", "ems", "--version", "5.0.0", "--from-file", str(_zip(tmp_path / "old.zip")),
    )
    discovered = make_product(
        "tibco-enterprise-message-service", product_code="ems", display_name="TIBCO EMS", family="messaging"
    )
    discovered.versions = {
        "10.4.0": make_version("tibco-enterprise-message-service", "10.4.0", zip_url="https://docs.tibco.com/ems.zip"),
        "8.6.0": make_version("tibco-enterprise-message-service", "8.6.0", is_archived=True, convert_eligible=False),
    }
    fake_crawl(products=[discovered])

    result = _invoke(runner, populated_root, "catalog", "fetch", "--product", "ems")

    assert result.exit_code == 0, result.output
    assert "5.0.0" in (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")


def test_download_from_file_dry_run_writes_nothing(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    """R12-02. `--dry-run` was accepted and the real ingest ran: the ZIP copied, the
    row added, and the version pinned manual -- exempt from every later download."""
    before = (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig")

    result = _invoke(
        runner, populated_root, "download", "--product", "ems", "--version", "11.0.0",
        "--from-file", str(_zip(tmp_path / "pkg.zip")), "--dry-run",
    )

    assert result.exit_code == 0
    assert "Would file" in result.output
    assert not list((populated_root / "families").rglob("*.zip"))
    assert (populated_root / "config" / "versions.csv").read_text(encoding="utf-8-sig") == before


def test_download_from_file_refuses_a_scope_flag(
    runner: CliRunner, populated_root: Path, tmp_path: Path
) -> None:
    result = _invoke(
        runner, populated_root, "download", "--all", "--product", "ems", "--version", "10.4.0",
        "--from-file", str(_zip(tmp_path / "pkg.zip")),
    )

    assert result.exit_code == 2
    assert "--all" in result.output
    assert not list((populated_root / "families").rglob("*.zip"))


@pytest.mark.parametrize(
    "argv",
    [["catalog", "batches"], ["catalog", "triage"], ["status"], ["archive", "list"], ["catalog", "import"]],
    ids=lambda a: " ".join(a),
)
def test_a_version_row_with_no_product_row_is_an_error_line_not_a_traceback(
    runner: CliRunner, populated_root: Path, argv: list[str]
) -> None:
    """R12-03. `load()` raises `CatalogError` for a version whose slug has no product
    row; these commands let it escape as a Python traceback."""
    versions = populated_root / "config" / "versions.csv"
    lines = versions.read_text(encoding="utf-8-sig").splitlines()
    lines.append(lines[1].replace("tibco-enterprise-message-service", "tibco-enterprise-message-servce", 1))
    versions.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _invoke(runner, populated_root, *argv)

    assert result.exit_code == 1
    assert _traceback_free(result), repr(result.exception)
    assert "Error:" in result.output


@pytest.mark.parametrize(
    "argv",
    [["catalog", "enable", "--product", "ems", "--version", "8.6.0"], ["catalog", "import"]],
    ids=lambda a: " ".join(a[:2]),
)
def test_a_catalog_held_open_in_excel_is_an_error_line_not_a_traceback(
    runner: CliRunner, populated_root: Path, monkeypatch, argv: list[str]
) -> None:
    """R12-03. `save()` raises `CatalogError` for a locked CSV (R1-04); `catalog
    enable` and `catalog import` did not catch it."""
    from docushift.catalog import CatalogError

    def locked(self):
        raise CatalogError("config/versions.csv is open in another program (Excel?)")

    monkeypatch.setattr(CatalogManager, "save", locked)

    result = _invoke(runner, populated_root, *argv)

    assert result.exit_code == 1
    assert _traceback_free(result), repr(result.exception)
    assert "open in another program" in result.output


def test_a_download_run_is_recorded_as_finished(runner: CliRunner, populated_root: Path) -> None:
    """R12-04. `finish()` was never called, so every download read back as "did not
    finish" -- the display for a crashed run."""
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--version", "10.4.0",
            "--zip-source", "manual")

    result = _invoke(runner, populated_root, "download", "--product", "ems")

    assert result.exit_code == 0
    run = _runs(populated_root)[0]
    assert run["command"] == "download"
    assert run["finished_at"] is not None
    assert run["exit_code"] == 0


def _stub_sitemap(root: Path, monkeypatch) -> None:
    """A docsite.yaml with a sitemap root, and a fetch that reaches no network."""
    from types import SimpleNamespace

    (root / "config" / "docsite.yaml").write_text("sitemap:\n  root: /sitemap.xml\n", encoding="utf-8")
    monkeypatch.setattr(
        "docushift.cli.sitemap.fetch",
        lambda *args, **kwargs: SimpleNamespace(
            errors=[], products={}, fetched=0, reused=0, missing=[], not_served=0, duplicates=[]
        ),
    )


def test_catalog_sitemap_reports_a_report_held_open_in_excel(
    runner: CliRunner, populated_root: Path, monkeypatch
) -> None:
    """R12-05. The report write was bare, so a locked CSV ended the run in a
    `PermissionError` traceback after the whole fetch."""
    _stub_sitemap(populated_root, monkeypatch)
    report = populated_root / "reports" / "coveo-sitemap.csv"
    report.parent.mkdir()
    report.write_text("slug,version\n", encoding="utf-8")
    report.chmod(0o444)
    try:
        result = _invoke(runner, populated_root, "catalog", "sitemap")
    finally:
        report.chmod(0o666)

    assert result.exit_code == 1
    assert _traceback_free(result), repr(result.exception)
    assert "open in Excel" in result.output


def test_catalog_sitemap_refuses_a_product_the_catalog_does_not_hold(
    runner: CliRunner, populated_root: Path, monkeypatch
) -> None:
    """R12-12. An unknown code resolved to itself, matched no row, exited 0, and
    rewrote the whole-catalog report with its header alone."""
    _stub_sitemap(populated_root, monkeypatch)
    report = populated_root / "reports" / "coveo-sitemap.csv"
    report.parent.mkdir()
    report.write_text("slug,version,archived,leaf,pages,access_levels\nother,1.0,False,no,,\n", encoding="utf-8")

    result = _invoke(runner, populated_root, "catalog", "sitemap", "--product", "tibco-ems")

    assert result.exit_code == 1
    assert "No product 'tibco-ems'" in result.output
    assert "other,1.0" in report.read_text(encoding="utf-8")


def test_catalog_sitemap_for_one_product_keeps_every_other_products_rows(
    runner: CliRunner, populated_root: Path, monkeypatch
) -> None:
    """R12-12. `--product X` replaced the whole-catalog report with X's rows."""
    _stub_sitemap(populated_root, monkeypatch)
    report = populated_root / "reports" / "coveo-sitemap.csv"
    report.parent.mkdir()
    report.write_text(
        "slug,version,archived,leaf,pages,access_levels\n"
        "aaa-other,1.0,False,no,,\n"
        "tibco-enterprise-message-service,0.1,False,no,,\n"
        "zzz-other,2.0,False,yes,4,public\n",
        encoding="utf-8",
    )

    result = _invoke(runner, populated_root, "catalog", "sitemap", "--product", "ems")

    assert result.exit_code == 0, result.output
    lines = report.read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith("aaa-other,1.0")
    assert lines[-1].startswith("zzz-other,2.0")
    ems = [line.split(",")[1] for line in lines if line.startswith("tibco-enterprise-message-service,")]
    # The stale 0.1 row is replaced by the catalog's own versions.
    assert sorted(ems) == ["10.4.0", "8.6.0"]


def test_extract_exits_one_when_a_package_fails(runner: CliRunner, populated_root: Path) -> None:
    """R12-06, the user's call: `download`, `extract` and `convert` exit 1 on a failed
    version, like `reframe` and `sync`. A corrupt ZIP reported `Failed 1` and exit 0."""
    downloads = populated_root / "families" / "en-us-tibco-messaging" / "downloads"
    downloads.mkdir(parents=True)
    (downloads / "tibco-enterprise-message-service-10.4.0.zip").write_bytes(b"PK\x03\x04not-a-zip")

    result = _invoke(runner, populated_root, "extract", "--product", "ems")

    assert result.exit_code == 1
    assert _runs(populated_root)[0]["exit_code"] == 1


def _unconvertible_flare_tree(runner: CliRunner, root: Path) -> None:
    """A Flare version whose tree holds nothing convertible: a failed convert row
    whose only finding is `OUTPUT_ROOT_MISSING`, about the full product slug."""
    _invoke(runner, root, "catalog", "set", "--product", "ems", "--version", "10.4.0", "--engine", "flare")
    tree = root / "families" / "en-us-tibco-messaging" / "extracted" / "tibco-enterprise-message-service" / "10.4.0"
    tree.mkdir(parents=True)
    (tree / "junk.txt").write_text("x", encoding="utf-8")


def test_convert_exits_one_when_a_version_fails(runner: CliRunner, populated_root: Path) -> None:
    """R12-06. A Flare tree with nothing convertible is a failed version; `convert`
    exited 0 and its run recorded exit 0."""
    _unconvertible_flare_tree(runner, populated_root)

    result = _invoke(runner, populated_root, "convert", "--product", "ems")

    assert result.exit_code == 1
    assert "Failed" in result.output
    run = _runs(populated_root)[0]
    assert run["command"] == "convert" and run["exit_code"] == 1


def test_download_exits_one_when_a_version_fails(
    runner: CliRunner, populated_root: Path, monkeypatch
) -> None:
    """R12-06."""
    from docushift.downloader import PackageDownloader

    def unreachable(self, *args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(
        PackageDownloader, "resolve_urls", lambda self, product, version: [("template", "https://x.invalid/a.zip")]
    )
    monkeypatch.setattr(PackageDownloader, "_fetch", unreachable)

    result = _invoke(runner, populated_root, "download", "--product", "ems")

    assert result.exit_code == 1
    run = _runs(populated_root)[0]
    assert run["finished_at"] is not None and run["exit_code"] == 1


def test_convert_finishes_its_run_when_the_batch_raises(
    runner: CliRunner, populated_root: Path, monkeypatch
) -> None:
    """R12-09. `finish()` was not in a `finally`, so an exception left the run open."""
    from docushift.converter import DocumentConverter

    def explode(self, *args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(DocumentConverter, "convert_many", explode)

    _invoke(runner, populated_root, "convert", "--product", "ems")

    run = _runs(populated_root)[0]
    assert run["finished_at"] is not None and run["exit_code"] == 1


def test_catalog_set_refuses_a_bu_taxonomy_does_not_declare(
    runner: CliRunner, populated_root: Path
) -> None:
    """R12-07. `--bu` took any value, and an unknown bu declares no families, which
    switched the `--family` typo guard off: the workspace silently moved."""
    shutil.copyfile(REPO_ROOT / "config" / "taxonomy.yaml", populated_root / "config" / "taxonomy.yaml")
    before = (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")

    alone = _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--bu", "tibcoo")
    paired = _invoke(runner, populated_root, "catalog", "set", "--product", "ems",
                     "--bu", "tibcoo", "--family", "nosuchfam")

    for result in (alone, paired):
        assert result.exit_code == 1
        assert "bu 'tibcoo' is not declared" in result.output
    assert (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig") == before


def test_catalog_set_writes_nothing_when_the_version_is_unknown(
    runner: CliRunner, populated_root: Path
) -> None:
    """R12-08. Each field saved on its own, so the product edit landed before the
    version was found missing."""
    before = (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig")

    result = _invoke(runner, populated_root, "catalog", "set", "--product", "ems",
                     "--display-name", "CHANGED", "--version", "9.9.9", "--batch", "poc")

    assert result.exit_code == 1
    assert "No version '9.9.9'" in result.output
    assert (populated_root / "config" / "products.csv").read_text(encoding="utf-8-sig") == before


def test_catalog_eos_leaves_no_open_run_when_the_report_is_missing(
    runner: CliRunner, populated_root: Path
) -> None:
    """R12-09. The run opened before the report was read, so a missing report left
    a run with no finish time, which became `report --run last`."""
    (populated_root / "config" / "eos.yaml").write_text("report: eos/missing.csv\n", encoding="utf-8")

    result = _invoke(runner, populated_root, "catalog", "eos")

    assert result.exit_code == 1
    assert all(run["finished_at"] is not None for run in _runs(populated_root))


def test_catalog_migrate_leaves_no_open_run_when_the_sheet_is_missing(
    runner: CliRunner, populated_root: Path
) -> None:
    (populated_root / "config" / "docsite-migration.yaml").write_text(
        "sheet: migration/missing.csv\ndecision_column: X\naliases: []\n", encoding="utf-8"
    )

    result = _invoke(runner, populated_root, "catalog", "migrate")

    assert result.exit_code == 1
    assert all(run["finished_at"] is not None for run in _runs(populated_root))


def test_catalog_fetch_dry_run_names_no_run_id(
    runner: CliRunner, populated_root: Path, fake_crawl
) -> None:
    """R12-10. A dry run records nothing, yet it said `report --run 0`."""
    _invoke(runner, populated_root, "catalog", "set", "--product", "ems", "--version", "8.6.0",
            "--batch", "poc-1")
    fake_crawl()

    result = _invoke(runner, populated_root, "catalog", "fetch", "--product", "ems", "--dry-run")

    assert result.exit_code == 0
    assert "--run 0" not in result.output
    assert "Would record" in result.output


def test_report_normalises_a_lower_case_code(runner: CliRunner, populated_root: Path) -> None:
    """R12-11. `--code output_root_missing` matched nothing and read as a clean run."""
    _unconvertible_flare_tree(runner, populated_root)
    _invoke(runner, populated_root, "convert", "--product", "ems")

    result = _invoke(runner, populated_root, "report", "--code", "output_root_missing")

    assert result.exit_code == 0
    assert "Nothing to report" not in result.output
    assert "OUTPUT_ROOT_MISSING" in result.output


def test_report_refuses_a_code_the_register_does_not_know(runner: CliRunner, populated_root: Path) -> None:
    _unconvertible_flare_tree(runner, populated_root)
    _invoke(runner, populated_root, "convert", "--product", "ems")

    result = _invoke(runner, populated_root, "report", "--code", "OUTPUT_ROOT_MISING")

    assert result.exit_code == 1
    assert "not a registered finding code" in result.output


def test_report_takes_a_stage_in_any_case_and_refuses_an_unknown_one(
    runner: CliRunner, populated_root: Path
) -> None:
    _unconvertible_flare_tree(runner, populated_root)
    _invoke(runner, populated_root, "convert", "--product", "ems")

    capitalised = _invoke(runner, populated_root, "report", "--stage", "Convert")
    unknown = _invoke(runner, populated_root, "report", "--stage", "conversion")

    assert capitalised.exit_code == 0
    assert "OUTPUT_ROOT_MISSING" in capitalised.output
    assert unknown.exit_code == 2


def test_report_says_when_a_slug_matches_no_finding_in_the_run(
    runner: CliRunner, populated_root: Path
) -> None:
    """`report` reads no catalog, so `--slug ems` stays exact -- but it must not read
    as "nothing to report" when the run's findings are keyed on the full slug."""
    _unconvertible_flare_tree(runner, populated_root)
    _invoke(runner, populated_root, "convert", "--product", "ems")

    result = _invoke(runner, populated_root, "report", "--slug", "ems")

    assert "Nothing to report" not in result.output
    assert "No finding in this run is about slug 'ems'" in result.output


def test_report_prune_refuses_a_negative_keep(runner: CliRunner, populated_root: Path) -> None:
    """R12-13. A negative `--keep` reached the store and ended in a traceback."""
    result = _invoke(runner, populated_root, "report", "--prune", "--keep", "-1")

    assert result.exit_code == 2
    assert _traceback_free(result), repr(result.exception)
