"""SQLite-backed idempotency cache and deduplication storage."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class IntakeCache:
    """Manages processed file hashes and historical invoice metadata in SQLite."""

    def __init__(self, db_path: Path | str = "intake_cache.db") -> None:
        self.db_path = Path(db_path)
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure SQLite connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self) -> None:
        """Initialize database tables and indexes if they do not exist."""
        # Ensure parent directory exists
        if self.db_path.parent:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_documents (
                    file_hash TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    supplier_name TEXT,
                    invoice_number TEXT,
                    status TEXT NOT NULL,
                    issue_type TEXT,
                    processed_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_supplier_invoice 
                ON processed_documents(supplier_name, invoice_number)
                """
            )
            conn.commit()

    def is_cached(self, file_hash: str) -> bool:
        """Check if a file SHA-256 hash has already been processed."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT 1 FROM processed_documents WHERE file_hash = ?",
                (file_hash,),
            )
            return cur.fetchone() is not None

    def get_record(self, file_hash: str) -> dict[str, Any] | None:
        """Retrieve cached metadata for a given file hash."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM processed_documents WHERE file_hash = ?",
                (file_hash,),
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            return None

    def save_record(
        self,
        file_hash: str,
        file_name: str,
        status: str,
        supplier_name: str | None = None,
        invoice_number: str | None = None,
        issue_type: str | None = None,
    ) -> None:
        """Insert or update a document processing entry in the cache."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO processed_documents (
                    file_hash, file_name, supplier_name, invoice_number, status, issue_type, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    file_name=excluded.file_name,
                    supplier_name=excluded.supplier_name,
                    invoice_number=excluded.invoice_number,
                    status=excluded.status,
                    issue_type=excluded.issue_type,
                    processed_at=excluded.processed_at
                """,
                (
                    file_hash,
                    file_name,
                    supplier_name,
                    invoice_number,
                    status,
                    issue_type,
                    now_iso,
                ),
            )
            conn.commit()

    def get_existing_invoices(self) -> set[tuple[str, str]]:
        """Retrieve existing (supplier_name, invoice_number) pairs for deduplication."""
        existing: set[tuple[str, str]] = set()
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT supplier_name, invoice_number 
                FROM processed_documents 
                WHERE status IN ('OK', 'FLAGGED')
                  AND supplier_name IS NOT NULL 
                  AND invoice_number IS NOT NULL
                """
            )
            for row in cur.fetchall():
                supp = (row["supplier_name"] or "").strip().lower()
                inv = (row["invoice_number"] or "").strip().lower()
                if supp and inv:
                    existing.add((supp, inv))
        return existing

    def get_cache_stats(self) -> dict[str, int]:
        """Return counts of processed records by status."""
        stats: dict[str, int] = {}
        with self._get_connection() as conn:
            cur = conn.execute("SELECT status, COUNT(*) as cnt FROM processed_documents GROUP BY status")
            for row in cur.fetchall():
                stats[row["status"]] = int(row["cnt"])
            cur_tot = conn.execute("SELECT COUNT(*) FROM processed_documents")
            stats["TOTAL"] = int(cur_tot.fetchone()[0])
        return stats

    def clear(self) -> None:
        """Clear all cached records."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM processed_documents")
            conn.commit()
