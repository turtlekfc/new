"""
db.py
------
Low-level SQLite connection handling for a single ledger (club) database.

Design decision (Phase 1 / scaffold stage):
Each ledger is one SQLite file containing a single generic key-value table
(kv_store). This intentionally mirrors the JSON-blob-per-key model the
browser prototype already used (window.storage.get/set), so the large,
already-tested frontend business logic (transactions, budgets, reports...)
can be ported with a MINIMAL diff: only the storage bridge changes, not the
application logic itself.

Phase 2 (future, optional): normalize kv_store into real relational tables
(transactions, accounts, departments, categories, projects, books, ...)
for better query performance and referential integrity once the ported
app is verified to be feature-complete. The 內帳/外帳 "real separate book"
design you asked about maps naturally onto a `books` table plus a
`transaction_books` join table at that point.
"""
import sqlite3
import json
import threading
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv_store (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

class LedgerDB:
    """Wraps one SQLite connection to one ledger .db file. Thread-safe enough
    for a single-window desktop app (pywebview calls JS-API methods from a
    background thread, so we use a lock + check_same_thread=False)."""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---- generic key/value API (mirrors the old window.storage.* shape) ----
    def get(self, key: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def set(self, key: str, value: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv_store(key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
                (key, value),
            )
            self._conn.commit()
            return True

    def delete(self, key: str):
        with self._lock:
            self._conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            self._conn.commit()
            return True

    def list_keys(self, prefix: str = ""):
        with self._lock:
            rows = self._conn.execute(
                "SELECT key FROM kv_store WHERE key LIKE ? ORDER BY key",
                (f"{prefix}%",),
            ).fetchall()
            return [r["key"] for r in rows]

    def export_all(self):
        """Return the entire kv_store as a plain dict (used for JSON export/backup)."""
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM kv_store").fetchall()
            out = {}
            for r in rows:
                try:
                    out[r["key"]] = json.loads(r["value"])
                except (json.JSONDecodeError, TypeError):
                    out[r["key"]] = r["value"]
            return out

    def restore_all(self, data: dict, replace: bool = False):
        """Restore a validated JSON snapshot in a single SQLite transaction
        (used by備份還原). If anything fails partway through, the whole
        restore is rolled back instead of leaving the ledger half-written —
        Api.import_active_ledger_json() already validates key/value shapes
        before calling this, so this layer only needs to guarantee atomicity."""
        if not isinstance(data, dict):
            raise ValueError("restore data must be a dict")
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                if replace:
                    self._conn.execute("DELETE FROM kv_store")
                for key, value in data.items():
                    self._conn.execute(
                        "INSERT INTO kv_store(key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
                        (key, json.dumps(value, ensure_ascii=False)),
                    )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self):
        with self._lock:
            self._conn.close()
