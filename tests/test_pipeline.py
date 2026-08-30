"""End-to-end tests for the document intake pipeline."""

from pathlib import Path
import csv
import json
import pytest

from app.extraction.ai_extractor import AIExtractor
from app.extraction.pdf_extractor import PDFExtractor
from app.models.invoice import RawInvoiceExtraction
from app.pipeline.cache import IntakeCache
from app.pipeline.processor import DocumentPipeline
from app.validation.rules import InvoiceValidator


@pytest.fixture
def sample_pdf_dir(tmp_path: Path, create_test_pdf) -> Path:
    """Create directory containing multiple test PDFs."""
    pdf_dir = tmp_path / "invoices_batch"
    pdf_dir.mkdir()

    # 1. Clean invoice
    create_test_pdf("inv_01_clean.pdf", ["Acme Supplies", "INV-001", "Date: 2024-03-01", "Due: 2024-03-31", "100.00 EUR"])
    # 2. Missing due date
    create_test_pdf("inv_02_no_due.pdf", ["Beta Corp", "INV-002", "Date: 2024-03-05", "250.00 USD"])
    # 3. Invalid amount
    create_test_pdf("inv_03_bad_amt.pdf", ["Gamma LLC", "INV-003", "Date: 2024-03-10", "Due: 2024-04-10", "-50.00 EUR"])
    # 4. Duplicate of inv 01
    create_test_pdf("inv_04_dup.pdf", ["Acme Supplies Duplicate", "INV-001", "Date: 2024-03-01", "100.00 EUR"])

    # Move them to pdf_dir
    for f in tmp_path.glob("*.pdf"):
        f.rename(pdf_dir / f.name)

    return pdf_dir


def test_pipeline_dry_run(
    sample_pdf_dir: Path,
    temp_cache: IntakeCache,
    mock_openai_client,
    tmp_path: Path,
) -> None:
    ai_extractor = AIExtractor(api_key="mock", client=mock_openai_client)
    pipeline = DocumentPipeline(
        cache=temp_cache,
        ai_extractor=ai_extractor,
        output_dir=tmp_path / "out",
    )

    dry_run_stats = pipeline.dry_run(sample_pdf_dir)
    assert dry_run_stats["total_documents"] == 4
    assert dry_run_stats["new_documents"] == 4
    assert dry_run_stats["already_cached"] == 0
    assert dry_run_stats["estimated_api_calls"] == 4
    # Ensure no API calls made
    mock_openai_client.beta.chat.completions.parse.assert_not_called()


def test_pipeline_batch_processing_and_exports(
    sample_pdf_dir: Path,
    temp_cache: IntakeCache,
    mock_openai_client,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output_test"

    # Define mock returns depending on filename in user prompt
    def mock_parse(model, messages, response_format):
        user_content = messages[1]["content"]
        choice = mock_openai_client.MagicMock() if hasattr(mock_openai_client, "MagicMock") else None
        
        from unittest.mock import MagicMock
        choice = MagicMock()
        
        if "inv_01_clean.pdf" in user_content:
            choice.message.parsed = RawInvoiceExtraction(
                invoice_number="INV-001",
                supplier_name="Acme Supplies",
                invoice_date="2024-03-01",
                due_date="2024-03-31",
                total_amount=100.00,
                currency="EUR",
                confidence_score=0.99,
            )
        elif "inv_02_no_due.pdf" in user_content:
            choice.message.parsed = RawInvoiceExtraction(
                invoice_number="INV-002",
                supplier_name="Beta Corp",
                invoice_date="2024-03-05",
                due_date=None,  # Missing due date
                total_amount=250.00,
                currency="USD",
                confidence_score=0.95,
            )
        elif "inv_03_bad_amt.pdf" in user_content:
            choice.message.parsed = RawInvoiceExtraction(
                invoice_number="INV-003",
                supplier_name="Gamma LLC",
                invoice_date="2024-03-10",
                due_date="2024-04-10",
                total_amount=-50.00,  # Invalid amount
                currency="EUR",
                confidence_score=0.90,
            )
        elif "inv_04_dup.pdf" in user_content:
            choice.message.parsed = RawInvoiceExtraction(
                invoice_number="INV-001",
                supplier_name="Acme Supplies",  # Duplicate invoice number & supplier
                invoice_date="2024-03-01",
                due_date="2024-03-31",
                total_amount=100.00,
                currency="EUR",
                confidence_score=0.99,
            )
        else:
            choice.message.parsed = RawInvoiceExtraction()

        choice.message.refusal = None
        completion = MagicMock()
        completion.choices = [choice]
        return completion

    mock_openai_client.beta.chat.completions.parse.side_effect = mock_parse

    ai_extractor = AIExtractor(api_key="mock", client=mock_openai_client)
    pipeline = DocumentPipeline(
        cache=temp_cache,
        ai_extractor=ai_extractor,
        output_dir=output_dir,
    )

    summary, results = pipeline.process_batch(sample_pdf_dir)

    assert summary.total_scanned == 4
    assert summary.processed_ok == 1  # inv_01_clean
    assert summary.flagged_review == 1  # inv_02_no_due
    assert summary.exceptions_count == 2  # inv_03_bad_amt and inv_04_dup
    assert summary.skipped_cached == 0

    # Verify CSV files
    invoices_csv = output_dir / "invoices.csv"
    assert invoices_csv.exists()
    with open(invoices_csv, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 2  # 1 OK + 1 FLAGGED
        assert reader[0]["invoice_number"] == "INV-001"
        assert reader[0]["status"] == "OK"
        assert reader[1]["invoice_number"] == "INV-002"
        assert reader[1]["status"] == "FLAGGED"

    exceptions_csv = output_dir / "exceptions.csv"
    assert exceptions_csv.exists()
    with open(exceptions_csv, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 2
        issue_types = {r["issue_type"] for r in reader}
        assert "INVALID_AMOUNT" in issue_types
        assert "DUPLICATE_INVOICE" in issue_types

    # Verify JSON files
    invoices_json = output_dir / "invoices.json"
    assert invoices_json.exists()
    with open(invoices_json, encoding="utf-8") as f:
        inv_data = json.load(f)
        assert len(inv_data) == 2

    summary_json = output_dir / "run_summary.json"
    assert summary_json.exists()
    with open(summary_json, encoding="utf-8") as f:
        sum_data = json.load(f)
        assert sum_data["processed_ok"] == 1
        assert sum_data["flagged_review"] == 1
        assert sum_data["exceptions_count"] == 2

    # Verify Idempotency on second run: All files should be cached and skipped!
    mock_openai_client.beta.chat.completions.parse.reset_mock()
    summary2, results2 = pipeline.process_batch(sample_pdf_dir)
    assert summary2.total_scanned == 4
    assert summary2.skipped_cached == 4
    assert summary2.processed_ok == 0
    mock_openai_client.beta.chat.completions.parse.assert_not_called()

    # Verify Force flag overrides cache
    summary3, results3 = pipeline.process_batch(sample_pdf_dir, force=True)
    assert summary3.total_scanned == 4
    assert summary3.skipped_cached == 0
    assert summary3.processed_ok == 1
