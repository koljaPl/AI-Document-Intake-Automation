"""Tests for SQLite idempotency cache and deduplication storage."""

from app.pipeline.cache import IntakeCache


def test_cache_initialization(temp_cache: IntakeCache) -> None:
    assert temp_cache.db_path.exists()
    assert not temp_cache.is_cached("nonexistent_hash")


def test_save_and_retrieve_record(temp_cache: IntakeCache) -> None:
    file_hash = "abc123456789"
    temp_cache.save_record(
        file_hash=file_hash,
        file_name="invoice_test.pdf",
        status="OK",
        supplier_name="Acme Corp",
        invoice_number="INV-001",
    )

    assert temp_cache.is_cached(file_hash)
    record = temp_cache.get_record(file_hash)
    assert record is not None
    assert record["file_hash"] == file_hash
    assert record["file_name"] == "invoice_test.pdf"
    assert record["supplier_name"] == "Acme Corp"
    assert record["invoice_number"] == "INV-001"
    assert record["status"] == "OK"
    assert record["processed_at"] is not None


def test_cache_deduplication_queries(temp_cache: IntakeCache) -> None:
    temp_cache.save_record(
        file_hash="hash1",
        file_name="inv1.pdf",
        status="OK",
        supplier_name="Alpha Tech",
        invoice_number="A-100",
    )
    temp_cache.save_record(
        file_hash="hash2",
        file_name="inv2.pdf",
        status="FLAGGED",
        supplier_name="Beta Logistics",
        invoice_number="B-200",
    )
    temp_cache.save_record(
        file_hash="hash3",
        file_name="inv3.pdf",
        status="EXCEPTION",
        supplier_name="Gamma Bad",
        invoice_number="G-300",
        issue_type="INVALID_AMOUNT",
    )

    existing = temp_cache.get_existing_invoices()
    assert ("alpha tech", "a-100") in existing
    assert ("beta logistics", "b-200") in existing
    # Exceptions are not treated as valid committed invoices
    assert ("gamma bad", "g-300") not in existing


def test_cache_stats_and_clear(temp_cache: IntakeCache) -> None:
    temp_cache.save_record("h1", "f1.pdf", "OK")
    temp_cache.save_record("h2", "f2.pdf", "OK")
    temp_cache.save_record("h3", "f3.pdf", "FLAGGED")
    temp_cache.save_record("h4", "f4.pdf", "EXCEPTION", issue_type="LOW_CONFIDENCE")

    stats = temp_cache.get_cache_stats()
    assert stats["TOTAL"] == 4
    assert stats["OK"] == 2
    assert stats["FLAGGED"] == 1
    assert stats["EXCEPTION"] == 1

    temp_cache.clear()
    cleared_stats = temp_cache.get_cache_stats()
    assert cleared_stats["TOTAL"] == 0
    assert not temp_cache.is_cached("h1")
