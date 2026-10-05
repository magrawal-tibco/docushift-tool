"""Phase 38: `versions.csv`'s four status columns, and the dated events behind them.

`_status` / `_status_date` say where a version stands and when it got there;
`_sync_status` / `_sync_date` say when `sync` last placed it. Success is read
from what each stage left behind, the funnel's evidence, so the sheet and
`docushift status` count alike; `stage_event` supplies the dates and failures.
The sync columns are this tool's own record of a placement and never a claim
about the target (`architecture.md` §7.2).
"""

import csv
import io
from pathlib import Path

import pytest
from click.testing import CliRunner
from rich.console import Console

from docushift import cli
from docushift import state as state_module
from docushift.catalog import VERSION_COLUMNS, CatalogError, CatalogManager
from docushift.config import ConfigManager
from docushift.models import ReleaseStatus, SourceEngine
from docushift.reporting.status import StatusEvidence, version_status
from docushift.state import StateStore
from docushift.sync.distributor import SyncOutcome, SyncResult, WorkspaceDistributor
from tests.conftest import make_product, make_version


class Clock:
    """`state._now`, set by the test: every write until the next `today = N` is dated 2026-10-N."""

    today = 1

    def __call__(self) -> str:
        return f"2026-10-{self.today:02d}T09:00:00+00:00"


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(state_module, "_now", clock)
    return clock


@pytest.fixture
def catalog(tmp_path: Path) -> CatalogManager:
    """One version behind each gate, and one in the work (`ems@10.4.0`, Flare)."""
    state = StateStore(tmp_path / "state.db")
    manager = CatalogManager(
        tmp_path / "products.csv", tmp_path / "versions.csv", state,
        config=ConfigManager(root_dir=tmp_path),
    )
    live = make_product("ems", family="messaging")
    live.versions = {
        "10.4.0": make_version("ems", "10.4.0", engine=SourceEngine.FLARE),
        "9.0.0": make_version("ems", "9.0.0"),
        "8.6.0": make_version("ems", "8.6.0", is_archived=True, convert_eligible=False),
    }
    excluded = make_product("bwce", family="integration")
    excluded.versions = {"2.9.0": make_version("bwce", "2.9.0")}
    manager.merge_fetch_results([live, excluded])
    loaded = manager.load()
    loaded.products["bwce"].in_scope = False
    loaded.products["ems"].versions["9.0.0"].release_status = ReleaseStatus.RETIRED
    return manager


def _status(catalog: CatalogManager, slug: str = "ems", number: str = "10.4.0"):
    product = catalog.get_product(slug)
    return version_status(product, product.versions[number], StatusEvidence.read(catalog.state))


def _sheet(catalog: CatalogManager) -> dict[tuple[str, str], dict[str, str]]:
    catalog.save()
    with catalog.versions_path.open(encoding="utf-8-sig", newline="") as handle:
        return {(row["slug"], row["version"]): row for row in csv.DictReader(handle)}


# -- _status ---------------------------------------------------------------------


def test_each_gate_is_its_own_value_and_carries_no_date(catalog: CatalogManager) -> None:
    assert _status(catalog, "bwce", "2.9.0").status == "out-of-scope"
    assert _status(catalog, "ems", "9.0.0").status == "retired"
    assert _status(catalog, "ems", "8.6.0").status == "not-selected"
    untouched = _status(catalog)
    assert (untouched.status, untouched.status_date) == ("not-started", "")


def test_a_gate_wins_over_work_already_done(catalog: CatalogManager, clock) -> None:
    """A version converted and then disabled reads as the gate, like the funnel counts it."""
    catalog.state.set_version_state("ems", "8.6.0", download_path="a.zip", extract_path="t")
    catalog.state.record_output_map("ems", "8.6.0", [("a.htm", "a.md", "guide")])

    assert _status(catalog, "ems", "8.6.0").status == "not-selected"


def test_the_furthest_stage_with_evidence_is_the_status_dated_by_its_event(
    catalog: CatalogManager, clock
) -> None:
    state = catalog.state
    state.set_version_state("ems", "10.4.0", download_path="a.zip")
    clock.today = 1
    state.record_stage("ems", "10.4.0", "download", True)  # 10-01
    assert (_status(catalog).status, _status(catalog).status_date) == ("downloaded", "2026-10-01")

    state.set_version_state("ems", "10.4.0", extract_path="tree")
    clock.today = 2
    state.record_stage("ems", "10.4.0", "extract", True)  # 10-02
    assert (_status(catalog).status, _status(catalog).status_date) == ("extracted", "2026-10-02")

    state.record_output_map("ems", "10.4.0", [("a.htm", "a.md", "guide")])
    clock.today = 3
    state.record_stage("ems", "10.4.0", "convert", True)  # 10-03
    assert (_status(catalog).status, _status(catalog).status_date) == ("converted", "2026-10-03")

    catalog.get_version("ems", "10.4.0").reframed_md_files = 12
    clock.today = 4
    state.record_stage("ems", "10.4.0", "reframe", True)  # 10-04
    assert (_status(catalog).status, _status(catalog).status_date) == ("merged", "2026-10-04")


def test_an_unpacked_version_with_no_converter_is_format_unknown(catalog: CatalogManager) -> None:
    """It needs a person, not a re-run -- unlike an unpacked Flare version awaiting `convert`."""
    catalog.state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    catalog.get_version("ems", "10.4.0").engine = SourceEngine.AUTO
    assert _status(catalog).status == "format-unknown"

    catalog.get_version("ems", "10.4.0").engine = SourceEngine.DOXIA
    assert _status(catalog).status == "format-unknown"


def test_a_failure_beyond_the_furthest_success_wins_until_the_stage_succeeds(
    catalog: CatalogManager, clock
) -> None:
    state = catalog.state
    state.set_version_state("ems", "10.4.0", download_path="a.zip")
    clock.today = 1
    state.record_stage("ems", "10.4.0", "download", True)  # 10-01
    clock.today = 2
    state.record_stage("ems", "10.4.0", "extract", False)  # 10-02
    assert (_status(catalog).status, _status(catalog).status_date) == ("extract-failed", "2026-10-02")

    state.set_version_state("ems", "10.4.0", extract_path="tree")
    clock.today = 3
    state.record_stage("ems", "10.4.0", "extract", True)  # 10-03
    assert _status(catalog).status == "extracted"


def test_a_failed_rebuild_does_not_hide_the_tree_that_is_still_there(
    catalog: CatalogManager, clock
) -> None:
    """The failure is not beyond the furthest stage, so the version still reads converted."""
    state = catalog.state
    state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    state.record_output_map("ems", "10.4.0", [("a.htm", "a.md", "guide")])
    state.record_stage("ems", "10.4.0", "convert", True)
    clock.today = 2
    state.record_stage("ems", "10.4.0", "convert", False)

    assert _status(catalog).status == "converted"


def test_a_download_failure_recorded_before_events_existed_still_reads_as_one(
    catalog: CatalogManager,
) -> None:
    """`version_state.error` names no stage; with no package, it can only be the download."""
    catalog.state.set_version_state("ems", "10.4.0", status="error", error="not a ZIP")

    status = _status(catalog)
    assert status.status == "download-failed"
    assert status.status_date  # dated by the row's own write


def test_a_build_with_no_event_is_dated_by_the_run_that_built_it(catalog: CatalogManager) -> None:
    """Back-fill: `convert_run` is the only dated record of a build from before Phase 38."""
    state = catalog.state
    state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    state.record_output_map("ems", "10.4.0", [("a.htm", "a.md", "guide")])
    with state._tx() as conn:
        run = conn.execute(
            "INSERT INTO runs (command, started_at) VALUES ('convert', '2026-09-12T06:00:00+00:00')"
        ).lastrowid
    state.set_version_metadata("ems", "10.4.0", "convert_run", run)

    assert _status(catalog).status_date == "2026-09-12"


def _inventory(catalog: CatalogManager, *rows: tuple[str, int]) -> None:
    catalog.state.record_asset_inventory(
        "ems", "10.4.0", [("", category, "output-root", files, files * 100) for category, files in rows]
    )


def test_a_package_of_only_pdfs_is_pdf_only_not_format_unknown(catalog: CatalogManager) -> None:
    """Phase 39: no HTML help means nothing to convert, which is not being stuck."""
    catalog.state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    catalog.get_version("ems", "10.4.0").engine = SourceEngine.AUTO
    _inventory(catalog, ("document", 3), ("other", 2))

    assert _status(catalog).status == "pdf-only"


def test_html_the_tool_cannot_convert_is_still_format_unknown(catalog: CatalogManager) -> None:
    catalog.state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    catalog.get_version("ems", "10.4.0").engine = SourceEngine.DOXIA
    _inventory(catalog, ("topic", 141), ("document", 2))

    assert _status(catalog).status == "format-unknown"


def test_a_pdf_only_version_is_synced_by_its_documents_and_dated_against_extract(
    catalog: CatalogManager, clock
) -> None:
    state = catalog.state
    state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    catalog.get_version("ems", "10.4.0").engine = SourceEngine.AUTO
    _inventory(catalog, ("document", 3))
    clock.today = 1
    state.record_stage("ems", "10.4.0", "extract", True)
    clock.today = 2
    state.record_stage("ems", "10.4.0", "sync-docs", True, "D:/target")
    assert (_status(catalog).sync_status, _status(catalog).sync_date) == ("synced", "2026-10-02")

    clock.today = 3
    state.record_stage("ems", "10.4.0", "extract", True)  # new PDFs since the placement
    assert _status(catalog).sync_status == "out-of-date"


def test_a_converted_version_is_not_synced_by_its_documents_alone(catalog: CatalogManager, clock) -> None:
    state = catalog.state
    state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    state.record_output_map("ems", "10.4.0", [("a.htm", "a.md", "guide")])
    state.record_stage("ems", "10.4.0", "sync-docs", True, "D:/target")

    assert _status(catalog).sync_status == ""


# -- _sync_status ---------------------------------------------------------------


def test_sync_status_follows_this_tools_own_placements(catalog: CatalogManager, clock) -> None:
    state = catalog.state
    assert (_status(catalog).sync_status, _status(catalog).sync_date) == ("", "")

    clock.today = 1
    state.record_stage("ems", "10.4.0", "sync", True, "D:/target")  # 10-01
    assert (_status(catalog).sync_status, _status(catalog).sync_date) == ("synced", "2026-10-01")

    clock.today = 2
    state.record_stage("ems", "10.4.0", "convert", True)  # 10-02
    assert (_status(catalog).sync_status, _status(catalog).sync_date) == ("out-of-date", "2026-10-01")

    clock.today = 3
    state.record_stage("ems", "10.4.0", "sync", False, "D:/target")  # 10-03
    assert (_status(catalog).sync_status, _status(catalog).sync_date) == ("sync-failed", "2026-10-03")

    clock.today = 4
    state.record_stage("ems", "10.4.0", "sync", True, "D:/target")  # 10-04
    assert (_status(catalog).sync_status, _status(catalog).sync_date) == ("synced", "2026-10-04")


def test_a_gated_version_still_says_where_it_was_placed(catalog: CatalogManager, clock) -> None:
    catalog.state.record_stage("ems", "8.6.0", "sync", True, "D:/target")

    status = _status(catalog, "ems", "8.6.0")
    assert (status.status, status.sync_status) == ("not-selected", "synced")


def test_sync_records_a_placement_only_for_the_converted_help(catalog: CatalogManager, clock) -> None:
    """`CURRENT` is a placement (the target matched); `NO_OUTPUT` attempted nothing."""
    distributor = WorkspaceDistributor(ConfigManager(root_dir=catalog.versions_path.parent), catalog)
    product = catalog.get_product("ems")
    version = product.versions["10.4.0"]
    target = Path("D:/target")

    distributor._date(product, version, target, [SyncResult("ems", "10.4.0", SyncOutcome.NO_OUTPUT)])
    assert catalog.state.stage_events() == {}

    documents = SyncResult("ems", "10.4.0", SyncOutcome.SYNCED, doc_class="user-guides")
    distributor._date(product, version, target, [documents])
    recorded = catalog.state.stage_events()[("ems", "10.4.0")]
    assert ("sync", "ok") not in recorded  # the help was not placed
    assert ("sync-docs", "ok") in recorded  # Phase 39: what a PDF-only version reads

    distributor._date(product, version, target, [SyncResult("ems", "10.4.0", SyncOutcome.CURRENT)])
    clock.today = 2
    assert catalog.state.stage_events()[("ems", "10.4.0")][("sync", "ok")][1] == str(target)

    failed = SyncResult("ems", "10.4.0", SyncOutcome.FAILED, doc_class="user-guides")
    distributor._date(product, version, target, [SyncResult("ems", "10.4.0", SyncOutcome.SYNCED), failed])
    assert _status(catalog).sync_status == "sync-failed"


# -- the sheet -------------------------------------------------------------------


def test_the_columns_sit_after_the_family_and_are_written_on_every_save(
    catalog: CatalogManager, clock
) -> None:
    columns = list(VERSION_COLUMNS)
    family = columns.index("_family")
    assert columns[family + 1:family + 5] == ["_status", "_status_date", "_sync_status", "_sync_date"]

    catalog.state.set_version_state("ems", "10.4.0", download_path="a.zip")
    catalog.state.record_stage("ems", "10.4.0", "download", True)
    rows = _sheet(catalog)

    assert rows[("ems", "10.4.0")]["_status"] == "downloaded"
    assert rows[("ems", "10.4.0")]["_status_date"] == "2026-10-01"
    assert rows[("bwce", "2.9.0")]["_status"] == "out-of-scope"


def test_a_hand_edit_to_a_status_cell_is_discarded(catalog: CatalogManager) -> None:
    _sheet(catalog)
    text = catalog.versions_path.read_text(encoding="utf-8-sig")
    catalog.versions_path.write_text(text.replace("not-started", "published"), encoding="utf-8")

    reread = CatalogManager(catalog.products_path, catalog.versions_path, catalog.state)
    assert _sheet(reread)[("ems", "10.4.0")]["_status"] == "not-started"


def test_a_save_without_a_database_keeps_what_the_sheet_already_said(catalog: CatalogManager, clock) -> None:
    """No `state.db`, no claim: a stateless save must not blank the columns."""
    catalog.state.set_version_state("ems", "10.4.0", download_path="a.zip")
    catalog.state.record_stage("ems", "10.4.0", "download", True)
    _sheet(catalog)

    stateless = CatalogManager(catalog.products_path, catalog.versions_path, None)
    assert _sheet(stateless)[("ems", "10.4.0")]["_status"] == "downloaded"


def test_a_sheet_open_in_excel_warns_and_does_not_fail_the_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    out = io.StringIO()
    monkeypatch.setattr(cli, "console", Console(file=out, width=200))

    class Locked:
        def save(self) -> None:
            raise CatalogError("Could not write versions.csv (Permission denied).")

    cli._refresh_status(Locked())  # no exception

    assert "catalog refresh" in out.getvalue()


def test_catalog_refresh_rewrites_the_columns_and_counts_them(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    manager = CatalogManager(
        tmp_path / "config" / "products.csv", tmp_path / "config" / "versions.csv",
        StateStore(tmp_path / "cache" / "state.db"),
    )
    product = make_product("ems", family="messaging")
    product.versions = {"10.4.0": make_version("ems", "10.4.0")}
    manager.merge_fetch_results([product])
    manager.state.close()

    result = CliRunner().invoke(cli.main, ["--root", str(tmp_path), "catalog", "refresh"], color=False)

    assert result.exit_code == 0, result.output
    assert "not-started" in result.output
    header = (tmp_path / "config" / "versions.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert "_family,_status,_status_date,_sync_status,_sync_date," in header
