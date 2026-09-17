"""Unit tests for the findings register (planning.md §7.1, §7.2, §7.5).

The register's whole value is that it is enumerable, so these tests assert on
*codes* and on the shape of the table -- never on message text, which §7.1 says
is prose and may be reworded freely.
"""

from pathlib import Path

import pytest

from docushift.reporting.findings import (
    NOT_YET_EMITTED,
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
    rather than being frozen at the number the plan first guessed. 6c adds the
    29th, `DOCUMENT_UNREADABLE`, for the same reason and as the first code added
    by the phase that raises it. 6d nets zero -- one added, `ARCHIVE_ALSO_LIVE`
    removed as unreachable -- and 6e adds the 30th, `API_LINK_REWRITTEN`.

    7b adds seven at once and that is not the register growing loosely: `validate`
    is the first command whose whole job is to raise findings, so its §7.4 and §9.6
    obligations had no codes because nothing had ever been written to emit them.

    Phase 8 adds the 38th, `CODE_LINK_FLATTENED`, and it is the first code added to
    name what a phase deliberately did *not* fix: the links a GFM fence cannot
    hold. The defect it closes was invisible for six phases precisely because
    nothing counted it.

    Phase 10b adds the 39th, `INDEX_UNLINKED`, which is the reverse of
    `LINK_BROKEN` -- a file with no link rather than a link with no file. It is
    expected to raise nothing, because `render_index` is handed the same routed
    list that decides what gets copied; it exists so that would stop being true
    loudly rather than silently.
    """
    assert len(REGISTRY) == 39


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


def test_the_outstanding_debt_is_one_code_and_it_belongs_to_an_unbuilt_check() -> None:
    """§7.5's guarantee, asserted **equal** rather than as a subset (Phase 7a).

    Equality is what makes the test fail in both directions. The eight-deep
    `REACHABLE_IN_PHASE_*` chain it replaces was asserted as a subset, so a code
    that quietly started firing never surfaced and the named debt could only ever
    be an overstatement.

    Nine before 7a, three after it, one after 7c: 7b closed `LINK_BROKEN` and 7c
    closed `CSH_IDENTIFIER_DROPPED`. What is left belongs to §10.7's class 2, the
    document router's escape check -- a check that does not exist yet, which is
    the only honest kind of debt here. Before 7a four of the nine belonged to
    `catalog` and `extract`, which computed their findings and opened no run to
    put them in.
    """
    assert set(REGISTRY) >= NOT_YET_EMITTED
    assert set(unreachable_codes(set(REGISTRY) - NOT_YET_EMITTED)) == set(NOT_YET_EMITTED)

    assert set(NOT_YET_EMITTED) == {"DOC_REFERENCE_MISSING"}
    assert {REGISTRY[code].stage for code in NOT_YET_EMITTED} == {Stage.SYNC}
    assert "ARCHIVE_ALSO_LIVE" not in REGISTRY


def test_every_registered_code_is_written_down_somewhere_in_src() -> None:
    """The static half of §7.5's reachability test, and its limit.

    A literal scan, because the obvious version of this -- grepping for
    `record("CODE"` -- is what produced a wrong count of twenty unemitted codes:
    it misses every continuation-line and every variable call site. This proves a
    code is **written**, not that it fires, which is why `NOT_YET_EMITTED` above
    is curated by hand rather than derived from this.
    """
    src = Path(__file__).resolve().parents[2] / "src" / "docushift"
    register = src / "reporting" / "findings.py"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(src.rglob("*.py"))
        if path != register
    )

    written = {code for code in REGISTRY if f'"{code}"' in text or f"'{code}'" in text}
    assert set(REGISTRY) - written == set(NOT_YET_EMITTED)
