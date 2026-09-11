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
# Phase 4b-2's `csh_source` and `asset_inventory` did *not* bump this. The v2 bump
# was forced by a column *rename*, which `CREATE TABLE IF NOT EXISTS` cannot
# repair on a file that already exists; two new tables are additive and an
# existing v2 database grows them on open.
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
        row = self.connect().execute(
            "SELECT * FROM product_snapshot WHERE slug = ?", (slug,)
        ).fetchone()
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
        row = self.connect().execute(
            "SELECT * FROM version_snapshot WHERE slug = ? AND version = ?",
            (slug, version),
        ).fetchone()
        return dict(row) if row else None

    def known_versions(self, slug: str) -> set[str]:
        """Version keys discovery has previously returned for this product.

        Used by the importer to detect keys that vanished from the CSV -- typically
        Excel coercing `1.10` to `1.1` -- and abort rather than delete silently.
        """
        rows = self.connect().execute(
            "SELECT version FROM version_snapshot WHERE slug = ?", (slug,)
        ).fetchall()
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
        row = self.connect().execute(
            "SELECT * FROM version_state WHERE slug = ? AND version = ?",
            (slug, version),
        ).fetchone()
        return dict(row) if row else None

    def versions_with_status(self, status: ConversionStatus | str) -> list[tuple[str, str]]:
        """All `(slug, version)` pairs currently at a given lifecycle stage."""
        rows = self.connect().execute(
            "SELECT slug, version FROM version_state WHERE status = ? ORDER BY slug, version",
            (str(status),),
        ).fetchall()
        return [(row["slug"], row["version"]) for row in rows]

    def status_counts(self) -> dict[str, int]:
        """Lifecycle histogram, for the migration dashboard."""
        rows = self.connect().execute(
            "SELECT status, COUNT(*) AS n FROM version_state WHERE status IS NOT NULL GROUP BY status"
        ).fetchall()
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
        rows = self.connect().execute(
            "SELECT key, value FROM product_metadata WHERE slug = ?", (slug,)
        ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_version_metadata(self, slug: str, version: str, key: str, value: Any) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO version_metadata (slug, version, key, value) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(slug, version, key) DO UPDATE SET value = excluded.value",
                (slug, version, key, None if value is None else str(value)),
            )

    def get_version_metadata(self, slug: str, version: str) -> dict[str, str]:
        rows = self.connect().execute(
            "SELECT key, value FROM version_metadata WHERE slug = ? AND version = ?",
            (slug, version),
        ).fetchall()
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
        rows = self.connect().execute(
            "SELECT folder, engine FROM engine_folder_map WHERE slug = ? AND version = ? ORDER BY folder",
            (slug, version),
        ).fetchall()
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
        rows = self.connect().execute(
            "SELECT path, doc_set, format, entries, status FROM csh_source "
            "WHERE slug = ? AND version = ? ORDER BY path",
            (slug, version),
        ).fetchall()
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
        rows = self.connect().execute(
            "SELECT output_root, category, destination, files, bytes FROM asset_inventory "
            "WHERE slug = ? AND version = ? ORDER BY output_root, category, destination",
            (slug, version),
        ).fetchall()
        return [dict(row) for row in rows]

    # -- batching ------------------------------------------------------------

    @staticmethod
    def batches(items: list[Any], size: int) -> Iterator[list[Any]]:
        """Slices work into batches, for phased runs across ~250 products."""
        if size <= 0:
            raise ValueError("Batch size must be positive")
        for start in range(0, len(items), size):
            yield items[start : start + size]
