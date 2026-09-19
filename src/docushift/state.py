"""SQLite state and delta engine.

Two distinct responsibilities, deliberately in one store:

1. **Fetch snapshots** -- the *base* of the snapshot-based 3-way merge
   (docs/architecture.md §3.5). Recording what discovery last wrote is what lets
   the merger infer "the CSV differs from this, so a human edited it" without
   asking the user to tick a protection column on 4,000 rows.
2. **Volatile machine state** -- etags, sizes, checksums, per-stage lifecycle
   status, free-form metadata. Evicted from the catalog CSVs precisely so those
   files only change when discovery finds something genuinely new.
"""

import sqlite3
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docushift.models import ConversionStatus, Product, ProductVersion

# 2 (2026-09-10): every table re-keyed from `product_code` to `slug`, because the
# code is not unique -- docs/planning.md Phase 3.6. There is no migration: the DB
# holds only snapshots and volatile machine state, all of it rebuildable by one
# `catalog fetch`, so deleting it costs a crawl rather than any user data.
#
# Phase 4b-2's `csh_source` and `asset_inventory` did *not* bump this, and neither
# do Phase 5a's `runs`, `findings` and `output_map`. The v2 bump was forced by a
# column *rename*, which `CREATE TABLE IF NOT EXISTS` cannot repair on a file that
# already exists; a new table is additive and an existing v2 database grows it on
# open.
SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER NOT NULL
);

-- Base of the 3-way merge: the product fields as discovery last returned them.
CREATE TABLE IF NOT EXISTS product_snapshot (
    slug          TEXT PRIMARY KEY,
    product_code  TEXT,
    display_name  TEXT,
    bu            TEXT,
    family        TEXT,
    family_source TEXT,
    fetched_at    TEXT NOT NULL
);

-- Base of the 3-way merge: the version fields as discovery last returned them.
-- `engine` is absent by design -- it is written by the detector, not discovery.
CREATE TABLE IF NOT EXISTS version_snapshot (
    slug     TEXT NOT NULL,
    version          TEXT NOT NULL,
    is_archived      TEXT,
    convert_eligible TEXT,
    release_date     TEXT,
    zip_url          TEXT,
    fetched_at       TEXT NOT NULL,
    PRIMARY KEY (slug, version)
);

-- Volatile per-version machine state, evicted from the catalog CSVs.
CREATE TABLE IF NOT EXISTS version_state (
    slug   TEXT NOT NULL,
    version        TEXT NOT NULL,
    status         TEXT,
    zip_etag       TEXT,
    zip_size       INTEGER,
    checksum       TEXT,
    download_path  TEXT,
    extract_path   TEXT,
    error          TEXT,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (slug, version)
);

-- Free-form key/value metadata (docsite ids, folder paths, API leftovers).
CREATE TABLE IF NOT EXISTS version_metadata (
    slug TEXT NOT NULL,
    version      TEXT NOT NULL,
    key          TEXT NOT NULL,
    value        TEXT,
    PRIMARY KEY (slug, version, key)
);

CREATE TABLE IF NOT EXISTS product_metadata (
    slug TEXT NOT NULL,
    key          TEXT NOT NULL,
    value        TEXT,
    PRIMARY KEY (slug, key)
);

-- Per-guide-folder engine map, so a bundle that genuinely mixes generators is
-- visible rather than flattened into the single CSV column (architecture §3.4).
CREATE TABLE IF NOT EXISTS engine_folder_map (
    slug TEXT NOT NULL,
    version      TEXT NOT NULL,
    folder       TEXT NOT NULL,
    engine       TEXT NOT NULL,
    PRIMARY KEY (slug, version, folder)
);

-- Stage 4's CSH inventory: one row per located help map (design.md §6.2). The
-- per-doc-set detail stays here; only the two summary columns reach versions.csv.
CREATE TABLE IF NOT EXISTS csh_source (
    slug    TEXT NOT NULL,
    version TEXT NOT NULL,
    path    TEXT NOT NULL,   -- relative to the extracted tree
    doc_set TEXT NOT NULL,
    format  TEXT NOT NULL,   -- flare_alias | dita_head_js | webworks_topics
    entries INTEGER NOT NULL,
    status  TEXT NOT NULL,   -- ok | empty | unparseable | unreadable
    PRIMARY KEY (slug, version, path)
);

-- Stage 4's asset inventory: files and bytes per output root, category and
-- destination (design.md §6.4 step 1). Not an extension allow-list -- the corpus
-- holds 100 extensions and every one of them is counted somewhere.
CREATE TABLE IF NOT EXISTS asset_inventory (
    slug        TEXT NOT NULL,
    version     TEXT NOT NULL,
    output_root TEXT NOT NULL,   -- relative to the tree; '' when none claims it
    category    TEXT NOT NULL,
    destination TEXT NOT NULL,
    files       INTEGER NOT NULL,
    bytes       INTEGER NOT NULL,
    PRIMARY KEY (slug, version, output_root, category, destination)
);

-- Stage 5's source-HTML -> output-Markdown map (design.md §9.3). Recorded by the
-- converter and read by CSH resolution, so the two cannot disagree about renaming,
-- deduplication or a dropped topic. Keyed on the *source* path, which is unique
-- within a version by construction; two sources may legitimately produce one
-- output only where an engine collapses republished topics (DITA `_unique_N`).
CREATE TABLE IF NOT EXISTS output_map (
    slug     TEXT NOT NULL,
    version  TEXT NOT NULL,
    source   TEXT NOT NULL,   -- relative to the extracted tree, POSIX
    output   TEXT NOT NULL,   -- relative to the version's output root, POSIX
    unit     TEXT NOT NULL,   -- the doc-set / output root / book that produced it
    PRIMARY KEY (slug, version, source)
);

-- Stage-agnostic findings (planning.md §7.1). One row per run, and one per
-- error/warning; notes arrive pre-aggregated with a count. `run_id` is an
-- explicit column rather than a rowid alias so a run survives a `findings` purge.
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL,
    batch       TEXT NOT NULL DEFAULT '',
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    exit_code   INTEGER
);

CREATE TABLE IF NOT EXISTS findings (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id   INTEGER NOT NULL,
    stage    TEXT NOT NULL,
    severity TEXT NOT NULL,   -- error | warning | note
    code     TEXT NOT NULL,
    slug     TEXT NOT NULL DEFAULT '',
    version  TEXT NOT NULL DEFAULT '',
    path     TEXT NOT NULL DEFAULT '',
    message  TEXT NOT NULL DEFAULT '',
    count    INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS findings_by_run ON findings (run_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class StateStore:
    """Owns `state.db`. Safe to construct against a path that does not exist yet."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        # >0 while inside `transaction()`. Counted, not a flag, so nesting is safe.
        self._batch_depth = 0
        # Reentrant, because `transaction()` holds it across nested `_tx()` calls.
        self._lock = threading.RLock()

    # -- connection ---------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        # Double-checked: the fast path is one attribute read per query, and only
        # the first caller pays for the lock.
        if self._conn is not None:
            return self._conn
        with self._lock:
            return self._connect_locked()

    def _connect_locked(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            # Stage 3 downloads run on a thread pool and each worker records its own
            # version's state, so the connection has to outlive the thread that made
            # it. `sqlite3` is built serialized (`threadsafety == 3`), which makes a
            # shared connection safe at the C level; `_tx` adds the lock that keeps
            # one thread's commit from landing inside another's write.
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
            if self._conn.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0] == 0:
                self._conn.execute("INSERT INTO schema_info (version) VALUES (?)", (SCHEMA_VERSION,))
            self._conn.commit()
            self._check_schema_version()
        return self._conn

    def _check_schema_version(self) -> None:
        """Refuses an older database rather than reading it as if it were current.

        `CREATE TABLE IF NOT EXISTS` leaves a v1 file's `product_code` columns in
        place, so every query would fail deep inside a fetch with a bare
        `no such column: slug`. Saying so up front, with the fix, is the difference
        between a one-line answer and a debugging session.
        """
        assert self._conn is not None
        found = self._conn.execute("SELECT MAX(version) FROM schema_info").fetchone()[0]
        if found is not None and int(found) < SCHEMA_VERSION:
            raise RuntimeError(
                f"{self.db_path} is schema v{found}; this build needs v{SCHEMA_VERSION}. "
                f"It holds only fetch snapshots and machine state -- delete the file and re-run "
                f"`docushift catalog fetch --all` to rebuild it."
            )

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- reads ----------------------------------------------------------------
    #
    # Reads take the same lock the writes do (Phase 14c). They did not, and the
    # gap was not theoretical: `download --family ems` failed with
    # `sqlite3.InterfaceError: bad parameter or other API misuse`, intermittently,
    # under four workers and never when a version was fetched alone. Every write
    # went through `_tx` and every read went straight to `connect().execute(...)`,
    # so one worker's `commit()` could land while another was stepping a
    # statement on the same shared connection. `check_same_thread=False` makes
    # that legal, not safe.
    #
    # Reproduced deliberately before it was fixed -- 8 threads interleaving a
    # read, a write and a read raised 2-3 times per 3,200 rounds, and **one of
    # those was an `IndexError` rather than an `InterfaceError`**: a row coming
    # back malformed instead of an exception, which is the worse half of the same
    # race and the reason this is a lock rather than a retry.
    #
    # Both helpers materialize inside the lock. Returning a live cursor would
    # hand the caller a statement to step after the lock was dropped, which is
    # the bug with an extra step in it.

    def _one(self, sql: str, params: "tuple[Any, ...]" = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.connect().execute(sql, params).fetchone()

    def _all(self, sql: str, params: "tuple[Any, ...]" = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.connect().execute(sql, params).fetchall()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self.connect()
            # Inside a `transaction()` the caller owns the commit, so the write joins the open
            # transaction instead of forcing its own fsync.
            if self._batch_depth:
                yield conn
                return
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def transaction(self) -> Iterator["StateStore"]:
        """Collapses many writes into one transaction.

        Every `record_*` commits on its own by default, which is right for the
        interactive commands -- one edit, one durable write. It is wrong for a full
        fetch: recording 634 product and 4,462 version snapshots one commit at a time
        costs ~5,100 fsyncs and about a minute of wall clock, all of it disk sync.

        Nesting is counted rather than rejected, so a caller can wrap a helper that
        already batches without having to know that it does.

        The lock is held for the whole batch: a concurrent single-write `_tx` would
        otherwise commit the half-finished batch along with its own row.
        """
        with self._lock:
            conn = self.connect()
            self._batch_depth += 1
            try:
                yield self
            except Exception:
                self._batch_depth -= 1
                if not self._batch_depth:
                    conn.rollback()
                raise
            else:
                self._batch_depth -= 1
                if not self._batch_depth:
                    conn.commit()

    def __enter__(self) -> "StateStore":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- fetch snapshots (merge base) ---------------------------------------

    def record_product_snapshot(self, product: Product) -> None:
        """Records the product fields exactly as discovery returned them."""
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO product_snapshot
                    (slug, product_code, display_name, bu, family, family_source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    product_code=excluded.product_code,
                    display_name=excluded.display_name,
                    bu=excluded.bu,
                    family=excluded.family,
                    family_source=excluded.family_source,
                    fetched_at=excluded.fetched_at
                """,
                (
                    product.slug,
                    product.product_code,
                    product.display_name,
                    product.bu,
                    product.family,
                    str(product.family_source),
                    _now(),
                ),
            )

    def get_product_snapshot(self, slug: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM product_snapshot WHERE slug = ?", (slug,)
        )
        return dict(row) if row else None

    def record_version_snapshot(self, version: ProductVersion) -> None:
        """Records the discovery-owned version fields.

        The engine columns, `convert_batch`, `zip_source`, the Stage 4 inventory
        columns and the three release-status columns are all absent from
        `version_snapshot` structurally rather than by rule -- discovery does not
        write them, so there is no base value a merge could legitimately compare
        against (docs/architecture.md §3.5, §3.11). The schema is therefore
        unchanged by the end-of-support work: no migration, no version bump.
        """
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO version_snapshot
                    (slug, version, is_archived, convert_eligible, release_date, zip_url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug, version) DO UPDATE SET
                    is_archived=excluded.is_archived,
                    convert_eligible=excluded.convert_eligible,
                    release_date=excluded.release_date,
                    zip_url=excluded.zip_url,
                    fetched_at=excluded.fetched_at
                """,
                (
                    version.slug,
                    version.version,
                    "true" if version.is_archived else "false",
                    "true" if version.convert_eligible else "false",
                    version.release_date or "",
                    version.zip_url or "",
                    _now(),
                ),
            )

    def get_version_snapshot(self, slug: str, version: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM version_snapshot WHERE slug = ? AND version = ?",
            (slug, version),
        )
        return dict(row) if row else None

    def known_versions(self, slug: str) -> set[str]:
        """Version keys discovery has previously returned for this product.

        Used by the importer to detect keys that vanished from the CSV -- typically
        Excel coercing `1.10` to `1.1` -- and abort rather than delete silently.
        """
        rows = self._all(
            "SELECT version FROM version_snapshot WHERE slug = ?", (slug,)
        )
        return {row["version"] for row in rows}

    def forget_version(self, slug: str, version: str) -> None:
        """Drops all trace of a version. Only called on an explicit --allow-deletes."""
        with self._tx() as conn:
            for table in ("version_snapshot", "version_state", "version_metadata", "engine_folder_map"):
                conn.execute(f"DELETE FROM {table} WHERE slug = ? AND version = ?", (slug, version))

    def forget_product(self, slug: str) -> None:
        """Drops a product and every version beneath it."""
        with self._tx() as conn:
            for table in ("version_snapshot", "version_state", "version_metadata", "engine_folder_map"):
                conn.execute(f"DELETE FROM {table} WHERE slug = ?", (slug,))
            conn.execute("DELETE FROM product_snapshot WHERE slug = ?", (slug,))
            conn.execute("DELETE FROM product_metadata WHERE slug = ?", (slug,))

    # -- volatile machine state ---------------------------------------------

    def set_version_state(self, slug: str, version: str, **fields: Any) -> None:
        """Upserts volatile state. Only the fields passed are touched."""
        allowed = {"status", "zip_etag", "zip_size", "checksum", "download_path", "extract_path", "error"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown version_state fields: {sorted(unknown)}")

        values = {k: (str(v) if isinstance(v, ConversionStatus) else v) for k, v in fields.items()}
        with self._tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO version_state (slug, version, updated_at) VALUES (?, ?, ?)",
                (slug, version, _now()),
            )
            if values:
                assignments = ", ".join(f"{key} = ?" for key in values)
                conn.execute(
                    f"UPDATE version_state SET {assignments}, updated_at = ? "
                    f"WHERE slug = ? AND version = ?",
                    (*values.values(), _now(), slug, version),
                )

    def get_version_state(self, slug: str, version: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM version_state WHERE slug = ? AND version = ?",
            (slug, version),
        )
        return dict(row) if row else None

    def versions_with_status(self, status: ConversionStatus | str) -> list[tuple[str, str]]:
        """All `(slug, version)` pairs currently at a given lifecycle stage."""
        rows = self._all(
            "SELECT slug, version FROM version_state WHERE status = ? ORDER BY slug, version",
            (str(status),),
        )
        return [(row["slug"], row["version"]) for row in rows]

    def progress(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Per-version pipeline evidence, keyed `(slug, version)` -- `status`'s funnel.

        Read from what each stage *recorded* rather than from `status` alone,
        because `status` is one column holding the furthest point reached and
        `ERROR` overwrites it: a version that downloaded, extracted and then failed
        to convert would otherwise vanish from the downloaded count as well, and a
        funnel whose steps do not nest is worse than no funnel. `converted` is the
        presence of an `output_map`, which is written after the tree swap -- so an
        interrupted conversion is not counted as one.
        """
        rows: dict[tuple[str, str], dict[str, Any]] = {}
        for row in self._all(
            "SELECT slug, version, status, download_path, extract_path, error FROM version_state"
        ):
            rows[(row["slug"], row["version"])] = {
                "status": row["status"],
                "downloaded": bool(row["download_path"]),
                "extracted": bool(row["extract_path"]),
                "converted": False,
                "error": row["error"],
            }
        for row in self._all(
            "SELECT DISTINCT slug, version FROM output_map"
        ):
            entry = rows.setdefault(
                (row["slug"], row["version"]),
                {"status": None, "downloaded": False, "extracted": False,
                 "converted": False, "error": None},
            )
            entry["converted"] = True
        return rows

    def status_counts(self) -> dict[str, int]:
        """Lifecycle histogram, for the migration dashboard."""
        rows = self._all(
            "SELECT status, COUNT(*) AS n FROM version_state WHERE status IS NOT NULL GROUP BY status"
        )
        return {row["status"]: row["n"] for row in rows}

    # -- metadata ------------------------------------------------------------

    def set_product_metadata(self, slug: str, key: str, value: Any) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO product_metadata (slug, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT(slug, key) DO UPDATE SET value = excluded.value",
                (slug, key, None if value is None else str(value)),
            )

    def get_product_metadata(self, slug: str) -> dict[str, str]:
        rows = self._all(
            "SELECT key, value FROM product_metadata WHERE slug = ?", (slug,)
        )
        return {row["key"]: row["value"] for row in rows}

    def set_version_metadata(self, slug: str, version: str, key: str, value: Any) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO version_metadata (slug, version, key, value) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(slug, version, key) DO UPDATE SET value = excluded.value",
                (slug, version, key, None if value is None else str(value)),
            )

    def get_version_metadata(self, slug: str, version: str) -> dict[str, str]:
        rows = self._all(
            "SELECT key, value FROM version_metadata WHERE slug = ? AND version = ?",
            (slug, version),
        )
        return {row["key"]: row["value"] for row in rows}

    # -- engine detection ----------------------------------------------------

    def record_engine_folder(self, slug: str, version: str, folder: str, engine: str) -> None:
        """Records one guide folder's detected engine."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO engine_folder_map (slug, version, folder, engine) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(slug, version, folder) DO UPDATE SET engine = excluded.engine",
                (slug, version, folder, str(engine)),
            )

    def get_engine_folder_map(self, slug: str, version: str) -> dict[str, str]:
        rows = self._all(
            "SELECT folder, engine FROM engine_folder_map WHERE slug = ? AND version = ? ORDER BY folder",
            (slug, version),
        )
        return {row["folder"]: row["engine"] for row in rows}

    # -- stage 4 inventory ----------------------------------------------------

    def record_csh_sources(self, slug: str, version: str, rows: Iterable[tuple]) -> None:
        """Replaces this version's CSH inventory wholesale.

        Replaced rather than merged, in one transaction with the delete: a
        re-extract of a package that dropped a help output must not leave the old
        source behind, and a half-replaced inventory is worse than either.
        """
        with self._tx() as conn:
            conn.execute("DELETE FROM csh_source WHERE slug = ? AND version = ?", (slug, version))
            conn.executemany(
                "INSERT INTO csh_source (slug, version, path, doc_set, format, entries, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(slug, version, *row) for row in rows],
            )

    def get_csh_sources(self, slug: str, version: str) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT path, doc_set, format, entries, status FROM csh_source "
            "WHERE slug = ? AND version = ? ORDER BY path",
            (slug, version),
        )
        return [dict(row) for row in rows]

    def record_asset_inventory(self, slug: str, version: str, rows: Iterable[tuple]) -> None:
        """Replaces this version's asset inventory wholesale, for the same reason."""
        with self._tx() as conn:
            conn.execute(
                "DELETE FROM asset_inventory WHERE slug = ? AND version = ?", (slug, version)
            )
            conn.executemany(
                "INSERT INTO asset_inventory "
                "(slug, version, output_root, category, destination, files, bytes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(slug, version, *row) for row in rows],
            )

    def get_asset_inventory(self, slug: str, version: str) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT output_root, category, destination, files, bytes FROM asset_inventory "
            "WHERE slug = ? AND version = ? ORDER BY output_root, category, destination",
            (slug, version),
        )
        return [dict(row) for row in rows]

    # -- stage 5 output map ----------------------------------------------------

    def record_output_map(self, slug: str, version: str, rows: Iterable[tuple]) -> None:
        """Replaces this version's source -> output map wholesale.

        Same rule as the two Stage 4 inventories: a re-convert of a package that
        dropped a guide must not leave the old topic's mapping behind, or §9.3
        would resolve a Help identifier onto a Markdown file nothing wrote.
        """
        with self._tx() as conn:
            conn.execute("DELETE FROM output_map WHERE slug = ? AND version = ?", (slug, version))
            conn.executemany(
                "INSERT INTO output_map (slug, version, source, output, unit) VALUES (?, ?, ?, ?, ?)",
                [(slug, version, *row) for row in rows],
            )

    def get_output_map(self, slug: str, version: str) -> dict[str, str]:
        """Source path -> output path, for §9.3's resolver."""
        rows = self._all(
            "SELECT source, output FROM output_map WHERE slug = ? AND version = ? ORDER BY source",
            (slug, version),
        )
        return {row["source"]: row["output"] for row in rows}

    # -- findings (planning.md §7.1) -------------------------------------------

    def start_run(self, command: str, batch: str = "") -> int:
        """Opens a run row and returns its id. Never fails a stage: an unopened
        run would silently discard every finding the stage is about to make."""
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (command, batch, started_at) VALUES (?, ?, ?)",
                (command, batch, _now()),
            )
            return int(cursor.lastrowid or 0)

    def finish_run(self, run_id: int, exit_code: int) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE runs SET finished_at = ?, exit_code = ? WHERE run_id = ?",
                (_now(), exit_code, run_id),
            )

    def record_findings(self, run_id: int, rows: Iterable[tuple]) -> None:
        """Appends findings to a run. Rows are `(stage, severity, code, slug,
        version, path, message, count)`.

        Appends rather than replaces, because a stage flushes per version: the
        rows for version 200 must not delete the rows for version 1.
        """
        with self._tx() as conn:
            conn.executemany(
                "INSERT INTO findings "
                "(run_id, stage, severity, code, slug, version, path, message, count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(run_id, *row) for row in rows],
            )

    def get_findings(self, run_id: int) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT stage, severity, code, slug, version, path, message, count "
            "FROM findings WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [dict(row) for row in rows]

    def last_run(self, command: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM runs"
        params: tuple[Any, ...] = ()
        if command is not None:
            sql += " WHERE command = ?"
            params = (command,)
        row = self._one(sql + " ORDER BY run_id DESC LIMIT 1", params)
        return dict(row) if row is not None else None

    # -- the read side (Phase 7a, architecture.md §7.3) -------------------------
    #
    # Five methods, all of them `report`'s. They are here rather than in
    # `reporting/` for the reason every other query is: `state.db`'s schema has one
    # owner, and a second module writing SQL against `findings` is how a column
    # rename becomes a silent empty table.

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        )
        return dict(row) if row is not None else None

    def recent_runs(self, limit: int = 20, command: str | None = None) -> list[dict[str, Any]]:
        """Newest first, with each run's finding count -- the `--run` picker's list."""
        sql = (
            "SELECT r.*, (SELECT COUNT(*) FROM findings f WHERE f.run_id = r.run_id) AS findings "
            "FROM runs r"
        )
        params: tuple[Any, ...] = ()
        if command is not None:
            sql += " WHERE r.command = ?"
            params = (command,)
        rows = self._all(
            sql + " ORDER BY r.run_id DESC LIMIT ?", (*params, limit)
        )
        return [dict(row) for row in rows]

    def query_findings(
        self,
        run_id: int,
        stage: str | None = None,
        severity: str | None = None,
        code: str | None = None,
        slug: str | None = None,
    ) -> list[dict[str, Any]]:
        """`get_findings` with `report`'s four filters, applied in SQL.

        Filtered here rather than in the caller because a convert run over the
        whole catalog writes tens of thousands of rows and `--code X` is how you
        look at one of them.
        """
        sql = (
            "SELECT id, stage, severity, code, slug, version, path, message, count "
            "FROM findings WHERE run_id = ?"
        )
        params: list[Any] = [run_id]
        for column, value in (
            ("stage", stage), ("severity", severity), ("code", code), ("slug", slug)
        ):
            if value:
                sql += f" AND {column} = ?"
                params.append(value)
        rows = self._all(sql + " ORDER BY id", params)
        return [dict(row) for row in rows]

    def findings_tally(self, run_id: int) -> dict[str, int]:
        """`{severity: rows}` for one run, without loading the rows."""
        rows = self._all(
            "SELECT severity, COUNT(*) AS rows FROM findings WHERE run_id = ? GROUP BY severity",
            (run_id,),
        )
        return {row["severity"]: row["rows"] for row in rows}

    def prune_findings(self, keep: int) -> tuple[int, int]:
        """Drops the findings of all but the newest `keep` runs. Returns `(runs, rows)`.

        The `runs` rows survive, which is what `run_id` being an explicit column
        rather than a rowid alias is for: a pruned run is still a dated record that
        something ran, and a report can still say its findings are gone rather than
        that the run never happened.
        """
        if keep < 0:
            raise ValueError("--keep cannot be negative")
        stale = [
            int(row["run_id"])
            for row in self._all(
                "SELECT run_id FROM runs WHERE run_id IN "
                "(SELECT DISTINCT run_id FROM findings) ORDER BY run_id DESC"
            )
        ][keep:]
        if not stale:
            return 0, 0
        placeholders = ",".join("?" * len(stale))
        with self._tx() as conn:
            cursor = conn.execute(
                f"DELETE FROM findings WHERE run_id IN ({placeholders})", stale
            )
            return len(stale), int(cursor.rowcount or 0)

    # -- batching ------------------------------------------------------------

    @staticmethod
    def batches(items: list[Any], size: int) -> Iterator[list[Any]]:
        """Slices work into batches, for phased runs across ~250 products."""
        if size <= 0:
            raise ValueError("Batch size must be positive")
        for start in range(0, len(items), size):
            yield items[start : start + size]
