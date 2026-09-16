"""The Phase 7a read layer: `reporting/report.py` and `reporting/status.py`.

Two rules shape every test here, and both come from `architecture.md` §7.

The first is the boundary: `report` reads `runs` and `findings` and never the
catalog; `status` reads the catalog and `version_state` and never `findings`.
These tests assert it directly rather than trusting it, because the two commands
were declared in Phase 1 with overlapping help text and left alone they converge.

The second is that the export is prose. `design.md` §8.6 forbids asserting on a
rendered *message*, so what these check in the Markdown is structure and codes --
the code is the contract, the message is wording that may change freely.
"""

from pathlib import Path

import pytest

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.models import ReleaseStatus, SourceEngine
from docushift.reporting import report as report_view
from docushift.reporting import status as status_view
from docushift.reporting.findings import REGISTRY, FindingsRun
from docushift.state import StateStore
from tests.conftest import make_product, make_version


def _rows(*specs) -> list[dict]:
    """Findings-table rows, as `query_findings` hands them over."""
    out = []
    for index, (stage, code, slug, count) in enumerate(specs, start=1):
        out.append(
            {
                "id": index,
                "stage": stage,
                "severity": str(REGISTRY[code].severity),
                "code": code,
                "slug": slug,
                "version": "1.0",
                "path": "",
                "message": f"{code} happened",
                "count": count,
            }
        )
    return out


# -- grouping ------------------------------------------------------------------


def test_stages_group_in_pipeline_order_and_errors_come_first() -> None:
    """Not alphabetical: a reader works through a run in the order it ran."""
    rows = _rows(
        ("convert", "ASSET_ORPHANED", "ems", 12),
        ("convert", "REFERENCE_UNRESOLVED", "ems", 1),
        ("catalog", "SCOPE_RULE_UNMATCHED", "gone", 1),
        ("convert", "ENGINE_UNKNOWN", "bex", 1),
    )

    groups = report_view.group(rows)

    assert [g.stage for g in groups] == ["catalog", "convert"]
    assert [c.code for c in groups[1].codes] == [
        "REFERENCE_UNRESOLVED",  # error
        "ENGINE_UNKNOWN",  # warning
        "ASSET_ORPHANED",  # note
    ]


def test_a_note_reports_occurrences_and_an_error_reports_rows() -> None:
    """1,308 orphaned images is the number; printing `1` would be true and useless."""
    rows = _rows(
        ("convert", "ASSET_ORPHANED", "ems", 900),
        ("convert", "ASSET_ORPHANED", "bex", 408),
        ("convert", "REFERENCE_UNRESOLVED", "ems", 1),
    )

    by_code = {c.code: c for c in report_view.group(rows)[0].codes}

    assert by_code["ASSET_ORPHANED"].occurrences == 1308
    assert len(by_code["ASSET_ORPHANED"].rows) == 2
    assert by_code["REFERENCE_UNRESOLVED"].occurrences == 1


def test_a_retired_code_still_groups_rather_than_vanishing() -> None:
    """`ARCHIVE_ALSO_LIVE` left the register in 6d; runs that recorded it happened.

    Dropping the row would make an old report quietly disagree with the run it
    describes, which is the one thing the `runs` table exists to prevent.
    """
    rows = [
        {
            "id": 1, "stage": "sync", "severity": "warning", "code": "ARCHIVE_ALSO_LIVE",
            "slug": "ems", "version": "8.6.0", "path": "", "message": "gone", "count": 1,
        }
    ]

    group = report_view.group(rows)[0].codes[0]

    assert group.code == "ARCHIVE_ALSO_LIVE"
    assert group.registered is None
    assert "ARCHIVE_ALSO_LIVE" in report_view.render_markdown({"run_id": 1, "command": "sync"}, rows)


def test_the_summary_counts_rows_at_each_severity() -> None:
    rows = _rows(
        ("convert", "REFERENCE_UNRESOLVED", "ems", 1),
        ("convert", "ENGINE_UNKNOWN", "bex", 1),
        ("convert", "ASSET_ORPHANED", "ems", 900),
    )

    assert report_view.summarize(rows) == "1 error, 1 warning, 1 note"
    assert report_view.summarize([]) == "no findings"


# -- explain -------------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(REGISTRY))
def test_every_registered_code_explains_itself(code: str) -> None:
    """All 30, including the three nothing emits yet -- `--explain` needs no run."""
    lines = report_view.explain(code)

    assert lines[0] == code
    assert REGISTRY[code].specified_in in lines[-1]


def test_explaining_an_unknown_code_raises_rather_than_inventing_an_entry() -> None:
    with pytest.raises(KeyError):
        report_view.explain("ASSET_WOBBLY")


# -- the Markdown export -------------------------------------------------------


def test_the_export_names_the_run_the_filters_and_every_code() -> None:
    """Structure and codes, never a message: §8.6's rule about what may be asserted."""
    run = {
        "run_id": 7, "command": "convert", "batch": "poc-1",
        "started_at": "2026-09-16T10:00:00", "finished_at": "2026-09-16T10:04:00", "exit_code": 0,
    }
    rows = _rows(("convert", "REFERENCE_UNRESOLVED", "ems", 1), ("convert", "ASSET_ORPHANED", "ems", 900))

    text = report_view.render_markdown(run, rows, filters="slug=ems")

    assert text.startswith("# DocuShift findings -- convert run 7")
    assert "poc-1" in text and "slug=ems" in text
    assert "## convert" in text
    assert "### REFERENCE_UNRESOLVED (error)" in text
    assert "### ASSET_ORPHANED (note)" in text
    # The note table carries the magnitude column and the error table does not.
    assert "| Product | Path | Count | Message |" in text
    assert "| Product | Path | Message |" in text


def test_an_empty_selection_exports_a_document_that_says_so() -> None:
    """A blank file is indistinguishable from a failed write."""
    text = report_view.render_markdown({"run_id": 1, "command": "extract"}, [])

    assert "# DocuShift findings" in text
    assert "No findings" in text


def test_a_pipe_in_a_message_cannot_break_the_table() -> None:
    rows = _rows(("convert", "REFERENCE_UNRESOLVED", "ems", 1))
    rows[0]["message"] = "href=a|b"

    text = report_view.render_markdown({"run_id": 1, "command": "convert"}, rows)

    assert "a\\|b" in text


def test_a_run_that_did_not_finish_says_so_rather_than_showing_a_blank() -> None:
    line = report_view.describe_run({"run_id": 3, "command": "convert", "started_at": "t"})

    assert "did not finish" in line


# -- status --------------------------------------------------------------------


@pytest.fixture
def catalog(tmp_path: Path) -> CatalogManager:
    """Four versions covering every gate the funnel measures."""
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

    # Set after the merge, not before: scope comes from `config/scope.yaml` and
    # release status from the end-of-support report, so a value passed to
    # `make_product` is overwritten on the way in. This fixture is about what the
    # funnel counts, not about how the catalog decides it.
    loaded = manager.load()
    loaded.products["bwce"].in_scope = False
    loaded.products["ems"].versions["9.0.0"].release_status = ReleaseStatus.RETIRED
    return manager


def test_the_funnel_steps_nest_and_each_gate_shows_what_it_costs(catalog: CatalogManager) -> None:
    """`eligible_only=False` on purpose: excluded is not absent (§3.10)."""
    result = status_view.funnel(catalog)

    assert result.catalogued == 4
    assert result.in_scope == 3  # bwce excluded by scope.yaml
    assert result.not_retired == 2  # 9.0.0 retired
    assert result.eligible == 1  # 8.6.0 archived and not eligible
    assert result.downloaded == result.extracted == result.converted == 0


def test_the_funnel_reads_recorded_paths_rather_than_the_status_column(
    catalog: CatalogManager,
) -> None:
    """ERROR overwrites `status`, so a funnel built on it would not nest.

    This is the case that proves it: a version that downloaded and extracted and
    then failed still counts as downloaded and extracted, because it was.
    """
    catalog.state.set_version_state(
        "ems", "10.4.0", status="error", download_path="a.zip", extract_path="tree", error="boom"
    )

    result = status_view.funnel(catalog)

    assert result.downloaded == 1
    assert result.extracted == 1
    assert result.converted == 0
    assert result.errors == 1


def test_converted_is_evidenced_by_output_rows_not_by_a_status(catalog: CatalogManager) -> None:
    """`output_map` is written after the tree swap, so an interrupted run is not counted."""
    catalog.state.set_version_state("ems", "10.4.0", download_path="a.zip", extract_path="tree")
    catalog.state.record_output_map("ems", "10.4.0", [("topic.htm", "topic.md", "guide")])

    assert status_view.funnel(catalog).converted == 1


def test_there_is_no_published_row_without_a_target_directory(catalog: CatalogManager) -> None:
    """§7.2: sync currency is compared and never recorded, so the db cannot answer it."""
    labels = [label for label, _count, _source in status_view.funnel(catalog).rows()]
    assert "Published" not in labels

    with_target = status_view.funnel(catalog, published={"ems": 2})
    assert ("Published", 2, "target tree") in with_target.rows()


def test_engines_separate_undetermined_from_unconvertible(catalog: CatalogManager) -> None:
    """Two different decisions: a detector that has not run, and a scoping call."""
    catalog.load().products["ems"].versions["10.4.0"].engine = SourceEngine.AUTO

    result = status_view.engines(catalog)

    assert result.undetermined == ["ems@10.4.0"]
    assert result.unconvertible == []
    assert result.counts == {"auto": 1}


def test_status_reads_no_findings_and_report_reads_no_catalog() -> None:
    """The §7.1 boundary, asserted on the modules rather than trusted.

    Left to drift these two commands answer each other's question differently on
    the same day, so the separation is checked the only way a boundary can be:
    by what each module is allowed to name.
    """
    root = Path(__file__).resolve().parents[2] / "src" / "docushift" / "reporting"
    status_src = (root / "status.py").read_text(encoding="utf-8")
    report_src = (root / "report.py").read_text(encoding="utf-8")

    body = status_src.split('"""', 2)[2]
    assert "findings" not in body.replace("no `findings`", "")
    assert "catalog" not in report_src.split('"""', 2)[2]


# -- the state readers report is built on --------------------------------------


def test_query_findings_filters_in_sql_and_prune_keeps_the_run_rows(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    first = FindingsRun("convert", store=store).start()
    first.record("ENGINE_UNKNOWN", slug="ems", version="1")
    first.record("ASSET_ORPHANED", slug="bex", version="2", count=40)
    first.finish()
    second = FindingsRun("extract", store=store).start()
    second.record("CSH_SOURCE_EMPTY", slug="ems", version="1", count=3)
    second.finish()

    assert len(store.query_findings(first.run_id)) == 2
    assert len(store.query_findings(first.run_id, slug="ems")) == 1
    assert len(store.query_findings(first.run_id, severity="note")) == 1
    assert store.findings_tally(first.run_id) == {"warning": 1, "note": 1}
    assert [r["run_id"] for r in store.recent_runs()] == [second.run_id, first.run_id]
    assert store.recent_runs()[0]["findings"] == 1

    runs, rows = store.prune_findings(keep=1)

    assert (runs, rows) == (1, 2)
    assert store.query_findings(first.run_id) == []
    # The run is still a dated record that something ran.
    assert store.get_run(first.run_id) is not None
    store.close()
