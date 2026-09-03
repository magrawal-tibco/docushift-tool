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
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docushift.models import ConversionStatus, Product, ProductVersion

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER NOT NULL
);

-- Base of the 3-way merge: the product fields as discovery last returned them.
CREATE TABLE IF NOT EXISTS product_snapshot (
    product_code  TEXT PRIMARY KEY,
    display_name  TEXT,
    bu            TEXT,
    family        TEXT,
    family_source TEXT,
    slug          TEXT,
    fetched_at    TEXT NOT NULL
);

-- Base of the 3-way merge: the version fields as discovery last returned them.
-- `engine` is absent by design -- it is written by the detector, not discovery.
CREATE TABLE IF NOT EXISTS version_snapshot (
    product_code     TEXT NOT NULL,
    version          TEXT NOT NULL,
    is_archived      TEXT,
    convert_eligible TEXT,
    release_date     TEXT,
    zip_url          TEXT,
    fetched_at       TEXT NOT NULL,
    PRIMARY KEY (product_code, version)
);

-- Volatile per-version machine state, evicted from the catalog CSVs.
CREATE TABLE IF NOT EXISTS version_state (
    product_code   TEXT NOT NULL,
    version        TEXT NOT NULL,
    status         TEXT,
    zip_etag       TEXT,
    zip_size       INTEGER,
    checksum       TEXT,
    download_path  TEXT,
    extract_path   TEXT,
    error          TEXT,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (product_code, version)
);

-- Free-form key/value metadata (docsite ids, folder paths, API leftovers).
CREATE TABLE IF NOT EXISTS version_metadata (
    product_code TEXT NOT NULL,
    version      TEXT NOT NULL,
    key          TEXT NOT NULL,
    value        TEXT,
    PRIMARY KEY (product_code, version, key)
);

CREATE TABLE IF NOT EXISTS product_metadata (
    product_code TEXT NOT NULL,
    key          TEXT NOT NULL,
    value        TEXT,
    PRIMARY KEY (product_code, key)
);

-- Per-guide-folder engine map, so a bundle that genuinely mixes generators is
-- visible rather than flattened into the single CSV column (architecture §3.4).
CREATE TABLE IF NOT EXISTS engine_folder_map (
    product_code TEXT NOT NULL,
    version      TEXT NOT NULL,
    folder       TEXT NOT NULL,
    engine       TEXT NOT NULL,
    PRIMARY KEY (product_code, version, folder)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class StateStore:
    """Owns `state.db`. Safe to construct against a path that does not exist yet."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # -- connection ---------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
            if self._conn.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0] == 0:
                self._conn.execute("INSERT INTO schema_info (version) VALUES (?)", (SCHEMA_VERSION,))
            self._conn.commit()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

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
                    (product_code, display_name, bu, family, family_source, slug, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_code) DO UPDATE SET
                    display_name=excluded.display_name,
                    bu=excluded.bu,
                    family=excluded.family,
                    family_source=excluded.family_source,
                    slug=excluded.slug,
                    fetched_at=excluded.fetched_at
                """,
                (
                    product.product_code,
                    product.display_name,
                    product.bu,
                    product.family,
                    str(product.family_source),
                    product.slug or "",
                    _now(),
                ),
            )

    def get_product_snapshot(self, product_code: str) -> dict[str, Any] | None:
        row = self.connect().execute(
            "SELECT * FROM product_snapshot WHERE product_code = ?", (product_code,)
        ).fetchone()
        return dict(row) if row else None

    def record_version_snapshot(self, version: ProductVersion) -> None:
        """Records the discovery-owned version fields. Engine fields are excluded."""
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO version_snapshot
                    (product_code, version, is_archived, convert_eligible, release_date, zip_url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_code, version) DO UPDATE SET
                    is_archived=excluded.is_archived,
                    convert_eligible=excluded.convert_eligible,
                    release_date=excluded.release_date,
                    zip_url=excluded.zip_url,
                    fetched_at=excluded.fetched_at
                """,
                (
                    version.product_code,
                    version.version,
                    "true" if version.is_archived else "false",
                    "true" if version.convert_eligible else "false",
                    version.release_date or "",
                    version.zip_url or "",
                    _now(),
                ),
            )

    def get_version_snapshot(self, product_code: str, version: str) -> dict[str, Any] | None:
        row = self.connect().execute(
            "SELECT * FROM version_snapshot WHERE product_code = ? AND version = ?",
            (product_code, version),
        ).fetchone()
        return dict(row) if row else None

    def known_versions(self, product_code: str) -> set[str]:
        """Version keys discovery has previously returned for this product.

        Used by the importer to detect keys that vanished from the CSV -- typically
        Excel coercing `1.10` to `1.1` -- and abort rather than delete silently.
        """
        rows = self.connect().execute(
            "SELECT version FROM version_snapshot WHERE product_code = ?", (product_code,)
        ).fetchall()
        return {row["version"] for row in rows}

    def forget_version(self, product_code: str, version: str) -> None:
        """Drops all trace of a version. Only called on an explicit --allow-deletes."""
        with self._tx() as conn:
            for table in ("version_snapshot", "version_state", "version_metadata", "engine_folder_map"):
                conn.execute(f"DELETE FROM {table} WHERE product_code = ? AND version = ?", (product_code, version))

    def forget_product(self, product_code: str) -> None:
        """Drops a product and every version beneath it."""
        with self._tx() as conn:
            for table in ("version_snapshot", "version_state", "version_metadata", "engine_folder_map"):
                conn.execute(f"DELETE FROM {table} WHERE product_code = ?", (product_code,))
            conn.execute("DELETE FROM product_snapshot WHERE product_code = ?", (product_code,))
            conn.execute("DELETE FROM product_metadata WHERE product_code = ?", (product_code,))

    # -- volatile machine state ---------------------------------------------

    def set_version_state(self, product_code: str, version: str, **fields: Any) -> None:
        """Upserts volatile state. Only the fields passed are touched."""
        allowed = {"status", "zip_etag", "zip_size", "checksum", "download_path", "extract_path", "error"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown version_state fields: {sorted(unknown)}")

        values = {k: (str(v) if isinstance(v, ConversionStatus) else v) for k, v in fields.items()}
        with self._tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO version_state (product_code, version, updated_at) VALUES (?, ?, ?)",
                (product_code, version, _now()),
            )
            if values:
                assignments = ", ".join(f"{key} = ?" for key in values)
                conn.execute(
                    f"UPDATE version_state SET {assignments}, updated_at = ? "
                    f"WHERE product_code = ? AND version = ?",
                    (*values.values(), _now(), product_code, version),
                )

    def get_version_state(self, product_code: str, version: str) -> dict[str, Any] | None:
        row = self.connect().execute(
            "SELECT * FROM version_state WHERE product_code = ? AND version = ?",
            (product_code, version),
        ).fetchone()
        return dict(row) if row else None

    def versions_with_status(self, status: ConversionStatus | str) -> list[tuple[str, str]]:
        """All `(product_code, version)` pairs currently at a given lifecycle stage."""
        rows = self.connect().execute(
            "SELECT product_code, version FROM version_state WHERE status = ? ORDER BY product_code, version",
            (str(status),),
        ).fetchall()
        return [(row["product_code"], row["version"]) for row in rows]

    def status_counts(self) -> dict[str, int]:
        """Lifecycle histogram, for the migration dashboard."""
        rows = self.connect().execute(
            "SELECT status, COUNT(*) AS n FROM version_state WHERE status IS NOT NULL GROUP BY status"
        ).fetchall()
        return {row["status"]: row["n"] for row in rows}

    # -- metadata ------------------------------------------------------------

    def set_product_metadata(self, product_code: str, key: str, value: Any) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO product_metadata (product_code, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT(product_code, key) DO UPDATE SET value = excluded.value",
                (product_code, key, None if value is None else str(value)),
            )

    def get_product_metadata(self, product_code: str) -> dict[str, str]:
        rows = self.connect().execute(
            "SELECT key, value FROM product_metadata WHERE product_code = ?", (product_code,)
        ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_version_metadata(self, product_code: str, version: str, key: str, value: Any) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO version_metadata (product_code, version, key, value) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(product_code, version, key) DO UPDATE SET value = excluded.value",
                (product_code, version, key, None if value is None else str(value)),
            )

    def get_version_metadata(self, product_code: str, version: str) -> dict[str, str]:
        rows = self.connect().execute(
            "SELECT key, value FROM version_metadata WHERE product_code = ? AND version = ?",
            (product_code, version),
        ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    # -- engine detection ----------------------------------------------------

    def record_engine_folder(self, product_code: str, version: str, folder: str, engine: str) -> None:
        """Records one guide folder's detected engine."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO engine_folder_map (product_code, version, folder, engine) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(product_code, version, folder) DO UPDATE SET engine = excluded.engine",
                (product_code, version, folder, str(engine)),
            )

    def get_engine_folder_map(self, product_code: str, version: str) -> dict[str, str]:
        rows = self.connect().execute(
            "SELECT folder, engine FROM engine_folder_map WHERE product_code = ? AND version = ? ORDER BY folder",
            (product_code, version),
        ).fetchall()
        return {row["folder"]: row["engine"] for row in rows}

    # -- batching ------------------------------------------------------------

    @staticmethod
    def batches(items: list[Any], size: int) -> Iterator[list[Any]]:
        """Slices work into batches, for phased runs across ~250 products."""
        if size <= 0:
            raise ValueError("Batch size must be positive")
        for start in range(0, len(items), size):
            yield items[start : start + size]
