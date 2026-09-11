"""Unit tests for the findings register (planning.md §7.1, §7.2, §7.5).

The register's whole value is that it is enumerable, so these tests assert on
*codes* and on the shape of the table -- never on message text, which §7.1 says
is prose and may be reworded freely.
"""

import pytest

from docushift.reporting.findings import (
    REACHABLE_IN_PHASE_5A,
    REACHABLE_IN_PHASE_5B,
    REGISTRY,
    FindingsRun,
    Severity,
    Stage,
    UnregisteredCode,
    unreachable_codes,
)
from docushift.state import StateStore


def test_every_registered_code_names_a_real_severity_and_stage() -> None:
    assert REGISTRY
    for code, row in REGISTRY.items():
        assert row.code == code
        assert isinstance(row.severity, Severity)
        assert isinstance(row.stage, Stage)
        assert row.obligation and row.specified_in


def test_the_register_carries_every_row_of_7_5() -> None:
    """A half-populated register cannot be audited, so all 20 landed in 5a.

    5b adds 8 more, which were *not* in §7.5: they are the Flare engine's own
    obligations, and the register grows with the code paths that can raise them
    rather than being frozen at the number the plan first guessed.
    """
    assert len(REGISTRY) == 28


def test_severity_comes_from_the_registry_and_not_from_the_call_site() -> None:
    run = FindingsRun("convert")

    error = run.record("REFERENCE_UNRESOLVED", slug="ems", version="10.4.0")
    note = run.record("ASSET_ORPHANED", slug="ems", version="10.4.0")

    assert error.severity is Severity.ERROR
    assert note.severity is Severity.NOTE
    assert error.stage is Stage.CONVERT


def test_an_unregistered_code_raises_at_the_call_site() -> None:
    """The one exception in the module: reporting it as a finding needs a code."""
    with pytest.raises(UnregisteredCode):
        FindingsRun("convert").record("ASSET_WOBBLY")


def test_notes_aggregate_by_slug_and_version_while_errors_do_not() -> None:
    """Per-file notes would be hundreds of thousands of rows for ASSET_ORPHANED."""
    run = FindingsRun("convert")

    run.record("ASSET_ORPHANED", slug="ems", version="10.4.0", count=4)
    run.record("ASSET_ORPHANED", slug="ems", version="10.4.0", count=6)
    run.record("ASSET_ORPHANED", slug="ems", version="10.5.0", count=1)
    run.record("REFERENCE_UNRESOLVED", slug="ems", version="10.4.0", path="a")
    run.record("REFERENCE_UNRESOLVED", slug="ems", version="10.4.0", path="b")

    notes = run.by_severity(Severity.NOTE)
    assert [note.count for note in notes] == [10, 1]
    assert len(run.by_severity(Severity.ERROR)) == 2


def test_the_first_message_of_an_aggregated_note_stands() -> None:
    run = FindingsRun("convert")

    first = run.record("ASSET_ORPHANED", slug="ems", version="1", message="images")
    run.record("ASSET_ORPHANED", slug="ems", version="1", message="pdfs")

    assert first.message == "images"
    assert len(run.all) == 1


def test_a_run_with_no_store_records_and_never_flushes(tmp_path) -> None:
    """The path a --dry-run and a unit test share with a real run."""
    run = FindingsRun("convert").start()

    run.record("ENGINE_UNKNOWN", slug="ems", version="10.4.0")
    run.finish()

    assert run.run_id == 0
    assert [f.code for f in run.all] == ["ENGINE_UNKNOWN"]


def test_flushing_per_version_keeps_earlier_versions_after_a_later_one_fails(tmp_path) -> None:
    """§7.1: a crash on version 200 must not discard the first 199."""
    store = StateStore(tmp_path / "state.db")
    run = FindingsRun("convert", store=store).start()

    run.record("ENGINE_UNKNOWN", slug="ems", version="1")
    run.flush()
    run.record("ENGINE_UNKNOWN", slug="ems", version="2")  # never flushed

    rows = store.get_findings(run.run_id)
    assert [row["version"] for row in rows] == ["1"]
    assert rows[0]["severity"] == "warning"
    store.close()


def test_a_finished_run_records_its_exit_code(tmp_path) -> None:
    store = StateStore(tmp_path / "state.db")
    run = FindingsRun("convert", batch="poc-1", store=store).start()

    run.record("ENGINE_UNKNOWN", slug="ems", version="1")
    run.finish(exit_code=0)

    last = store.last_run("convert")
    assert last["batch"] == "poc-1"
    assert last["exit_code"] == 0
    assert last["finished_at"]
    assert len(store.get_findings(run.run_id)) == 1
    store.close()


def test_summary_counts_note_rows_not_note_occurrences() -> None:
    run = FindingsRun("convert")
    run.record("ASSET_ORPHANED", slug="ems", version="1", count=900)
    run.record("ENGINE_UNKNOWN", slug="ems", version="2")

    assert run.summary() == "1 warning, 1 note"


def test_the_reachability_debt_is_named_rather_than_asserted_away() -> None:
    """§7.5's guarantee, allowed to pass with a *named* list of unreached codes."""
    outstanding = unreachable_codes(REACHABLE_IN_PHASE_5B)

    assert set(REACHABLE_IN_PHASE_5A) <= set(REACHABLE_IN_PHASE_5B) <= set(REGISTRY)
    # With the first engine built, `convert` owes nothing: every remaining debt
    # belongs to `sync` or `validate`. The 5a exemption for `NAV_NODE_DROPPED` is
    # gone, which is the point of the sub-phase.
    for code in outstanding:
        assert REGISTRY[code].stage is not Stage.CONVERT, code
