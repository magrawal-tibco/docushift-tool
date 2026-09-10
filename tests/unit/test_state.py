"""Unit tests for the SQLite state and delta engine.

`state.db` carries two things the CSVs deliberately do not: the *base* of the
3-way merge (what discovery last returned) and volatile machine state (etags,
checksums, lifecycle status). Keeping the second out of the CSVs is what stops
`versions.csv` churning on every run. See docs/architecture.md §3.5.
"""

from pathlib import Path

import pytest

from docushift.models import ConversionStatus, SourceEngine
from docushift.state import StateStore
from tests.conftest import make_product, make_version


def test_database_is_created_lazily(project_root: Path) -> None:
    """Constructing a store must not touch the disk -- `doctor` reports absence."""
    path = project_root / "cache" / "state.db"
    store = StateStore(path)

    assert not path.exists()

    store.connect()
    assert path.exists()
    store.close()


def test_context_manager_opens_and_closes(project_root: Path) -> None:
    with StateStore(project_root / "cache" / "state.db") as store:
        assert store.get_product_snapshot("ems") is None
    assert store._conn is None


def test_reads_on_an_empty_store_return_none(state: StateStore) -> None:
    assert state.get_product_snapshot("ems") is None
    assert state.get_version_snapshot("ems", "10.4.0") is None
    assert state.get_version_state("ems", "10.4.0") is None
    assert state.known_versions("ems") == set()


# -- merge base ---------------------------------------------------------------


def test_product_snapshot_round_trips(state: StateStore) -> None:
    state.record_product_snapshot(make_product("ems", display_name="EMS", family="messaging"))

    snapshot = state.get_product_snapshot("ems")

    assert snapshot["display_name"] == "EMS"
    assert snapshot["family"] == "messaging"
    assert snapshot["fetched_at"]


def test_product_snapshot_is_upserted_not_duplicated(state: StateStore) -> None:
    state.record_product_snapshot(make_product("ems", display_name="Old"))
    state.record_product_snapshot(make_product("ems", display_name="New"))

    assert state.get_product_snapshot("ems")["display_name"] == "New"


def test_version_snapshot_stores_booleans_as_csv_text(state: StateStore) -> None:
    """The snapshot is compared against CSV text, so it is stored in that form."""
    state.record_version_snapshot(make_version("ems", "8.6.0", is_archived=True, convert_eligible=False))

    snapshot = state.get_version_snapshot("ems", "8.6.0")

    assert (snapshot["is_archived"], snapshot["convert_eligible"]) == ("true", "false")


def test_version_snapshot_holds_no_engine_columns(state: StateStore) -> None:
    """Discovery does not own the engine; the detector does (architecture §3.4)."""
    state.record_version_snapshot(make_version("ems", "10.4.0", engine=SourceEngine.FLARE))

    snapshot = state.get_version_snapshot("ems", "10.4.0")

    assert "engine" not in snapshot
    assert "engine_source" not in snapshot


def test_known_versions_lists_what_discovery_returned(state: StateStore) -> None:
    for version in ("10.4.0", "8.6.0"):
        state.record_version_snapshot(make_version("ems", version))
    state.record_version_snapshot(make_version("ebx", "6.2.0"))

    assert state.known_versions("ems") == {"10.4.0", "8.6.0"}


def test_forget_version_clears_every_table(state: StateStore) -> None:
    state.record_version_snapshot(make_version("ems", "10.4.0"))
    state.set_version_state("ems", "10.4.0", status=ConversionStatus.DOWNLOADED)
    state.set_version_metadata("ems", "10.4.0", "folder_path", "ems/10.4.0")
    state.record_engine_folder("ems", "10.4.0", "admin", "flare")

    state.forget_version("ems", "10.4.0")

    assert state.get_version_snapshot("ems", "10.4.0") is None
    assert state.get_version_state("ems", "10.4.0") is None
    assert state.get_version_metadata("ems", "10.4.0") == {}
    assert state.get_engine_folder_map("ems", "10.4.0") == {}


def test_forget_product_takes_its_versions_with_it(state: StateStore) -> None:
    state.record_product_snapshot(make_product("ems"))
    state.record_version_snapshot(make_version("ems", "10.4.0"))
    state.set_product_metadata("ems", "docsite_id", "42")

    state.forget_product("ems")

    assert state.get_product_snapshot("ems") is None
    assert state.known_versions("ems") == set()
    assert state.get_product_metadata("ems") == {}


# -- volatile machine state ----------------------------------------------------


def test_version_state_is_created_on_first_write(state: StateStore) -> None:
    state.set_version_state("ems", "10.4.0", status=ConversionStatus.DISCOVERED)

    assert state.get_version_state("ems", "10.4.0")["status"] == "DISCOVERED"


def test_partial_updates_leave_other_fields_alone(state: StateStore) -> None:
    """Stages write independently; `convert` must not clear the downloader's etag."""
    state.set_version_state("ems", "10.4.0", zip_etag='W/"abc"', zip_size=12345)

    state.set_version_state("ems", "10.4.0", status=ConversionStatus.CONVERTED)

    row = state.get_version_state("ems", "10.4.0")
    assert (row["zip_etag"], row["zip_size"], row["status"]) == ('W/"abc"', 12345, "CONVERTED")


def test_unknown_state_field_is_rejected(state: StateStore) -> None:
    """A typo must not be interpolated into the UPDATE statement."""
    with pytest.raises(ValueError, match="Unknown version_state fields"):
        state.set_version_state("ems", "10.4.0", stat_us="DONE")


def test_set_version_state_with_no_fields_still_creates_the_row(state: StateStore) -> None:
    state.set_version_state("ems", "10.4.0")

    assert state.get_version_state("ems", "10.4.0")["status"] is None


def test_versions_with_status_selects_the_work_queue(state: StateStore) -> None:
    state.set_version_state("ems", "10.4.0", status=ConversionStatus.DOWNLOADED)
    state.set_version_state("ems", "8.6.0", status=ConversionStatus.EXTRACTED)
    state.set_version_state("ebx", "6.2.0", status=ConversionStatus.DOWNLOADED)

    assert state.versions_with_status(ConversionStatus.DOWNLOADED) == [("ebx", "6.2.0"), ("ems", "10.4.0")]
    assert state.versions_with_status("EXTRACTED") == [("ems", "8.6.0")]


def test_status_counts_ignores_rows_with_no_status(state: StateStore) -> None:
    state.set_version_state("ems", "10.4.0", status=ConversionStatus.CONVERTED)
    state.set_version_state("ems", "8.6.0", status=ConversionStatus.CONVERTED)
    state.set_version_state("ebx", "6.2.0")

    assert state.status_counts() == {"CONVERTED": 2}


def test_error_is_recorded_alongside_the_status(state: StateStore) -> None:
    state.set_version_state("ems", "10.4.0", status=ConversionStatus.ERROR, error="404 on zip_url")

    row = state.get_version_state("ems", "10.4.0")
    assert (row["status"], row["error"]) == ("ERROR", "404 on zip_url")


# -- metadata ------------------------------------------------------------------


def test_metadata_is_upserted_per_key(state: StateStore) -> None:
    state.set_version_metadata("ems", "10.4.0", "folder_path", "old")
    state.set_version_metadata("ems", "10.4.0", "folder_path", "new")
    state.set_version_metadata("ems", "10.4.0", "title", "EMS 10.4.0")

    assert state.get_version_metadata("ems", "10.4.0") == {"folder_path": "new", "title": "EMS 10.4.0"}


def test_metadata_values_are_stringified(state: StateStore) -> None:
    state.set_product_metadata("ems", "docsite_id", 1234)

    assert state.get_product_metadata("ems") == {"docsite_id": "1234"}


# -- engine detection ----------------------------------------------------------


def test_engine_folder_map_records_a_mixed_bundle(state: StateStore) -> None:
    """One ZIP can genuinely mix generators; the CSV column flattens it, this does not."""
    state.record_engine_folder("ems", "10.4.0", "admin", SourceEngine.FLARE)
    state.record_engine_folder("ems", "10.4.0", "legacy-api", SourceEngine.WEBWORKS)

    assert state.get_engine_folder_map("ems", "10.4.0") == {"admin": "flare", "legacy-api": "webworks"}


def test_engine_folder_is_upserted(state: StateStore) -> None:
    state.record_engine_folder("ems", "10.4.0", "admin", SourceEngine.WEBWORKS)
    state.record_engine_folder("ems", "10.4.0", "admin", SourceEngine.FLARE)

    assert state.get_engine_folder_map("ems", "10.4.0") == {"admin": "flare"}


# -- batching ------------------------------------------------------------------


def test_batches_slices_evenly_and_keeps_the_remainder() -> None:
    assert list(StateStore.batches(list(range(7)), 3)) == [[0, 1, 2], [3, 4, 5], [6]]


def test_batches_of_an_empty_list_is_empty() -> None:
    assert list(StateStore.batches([], 10)) == []


def test_batch_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        list(StateStore.batches([1, 2], 0))


# -- transactions ----------------------------------------------------------------


def test_a_transaction_commits_every_write_together(project_root: Path) -> None:
    """One fetch is one commit. The point is ~5,100 fsyncs collapsing into one."""
    path = project_root / "cache" / "state.db"
    store = StateStore(path)

    with store.transaction():
        store.record_product_snapshot(make_product("tibco-ems"))
        store.record_version_snapshot(make_version("tibco-ems", "10.4.0"))

    reopened = StateStore(path)
    assert reopened.get_product_snapshot("tibco-ems") is not None
    assert reopened.get_version_snapshot("tibco-ems", "10.4.0") is not None
    reopened.close()
    store.close()


def test_a_failed_transaction_leaves_no_half_written_base(project_root: Path) -> None:
    """A partial merge base is worse than none: the missing rows read as manual edits."""
    path = project_root / "cache" / "state.db"
    store = StateStore(path)

    with pytest.raises(RuntimeError), store.transaction():
        store.record_product_snapshot(make_product("tibco-ems"))
        raise RuntimeError("crawl died mid-merge")

    assert store.get_product_snapshot("tibco-ems") is None
    store.close()


def test_transactions_nest_without_committing_early(project_root: Path) -> None:
    """A caller may wrap a helper that already batches, without knowing that it does."""
    store = StateStore(project_root / "cache" / "state.db")

    with pytest.raises(RuntimeError), store.transaction():
        with store.transaction():
            store.record_product_snapshot(make_product("tibco-ems"))
        # The inner block ended, but the outer one still owns the commit.
        raise RuntimeError("failed after the inner batch closed")

    assert store.get_product_snapshot("tibco-ems") is None
    store.close()
