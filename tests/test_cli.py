"""Tests for the Typer CLI interface."""

from pathlib import Path
import pytest
from typer.testing import CliRunner
from app.cli import app
from app.models.invoice import RawInvoiceExtraction

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "AI Document Intake Automation" in result.output
    assert "0.1.0" in result.output


def test_cli_stats_and_cache_clear(tmp_path: Path) -> None:
    db_file = tmp_path / "cli_test_cache.db"
    
    # Test stats on new DB
    res_stats = runner.invoke(app, ["stats", "--db-path", str(db_file)])
    assert res_stats.exit_code == 0
    assert "Cache Database Statistics" in res_stats.output

    # Test cache-clear
    res_clear = runner.invoke(app, ["cache-clear", "--db-path", str(db_file), "--yes"])
    assert res_clear.exit_code == 0
    assert "Successfully cleared cache database" in res_clear.output


def test_cli_process_dry_run(tmp_path: Path, create_test_pdf) -> None:
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    create_test_pdf("doc1.pdf", ["Invoice 1", "Total: 100 EUR"])
    create_test_pdf("doc2.pdf", ["Invoice 2", "Total: 200 EUR"])

    for f in tmp_path.glob("*.pdf"):
        f.rename(doc_dir / f.name)

    db_file = tmp_path / "dry_run_cache.db"

    result = runner.invoke(
        app,
        ["process", str(doc_dir), "--dry-run", "--db-path", str(db_file)],
    )
    assert result.exit_code == 0
    assert "[DRY RUN]" in result.output
    assert "2 documents found" in result.output
    assert "Estimated API calls" in result.output


def test_cli_process_live_mocked(tmp_path: Path, create_test_pdf, mocker) -> None:
    doc_dir = tmp_path / "docs_live"
    doc_dir.mkdir()
    create_test_pdf("clean_inv.pdf", ["Supplier Corp", "INV-101", "Date: 2024-03-01", "Due: 2024-03-31", "500 EUR"])
    for f in tmp_path.glob("*.pdf"):
        f.rename(doc_dir / f.name)

    out_dir = tmp_path / "out"
    db_file = tmp_path / "live_cache.db"

    # Mock AIExtractor to avoid real OpenAI network calls
    mock_raw = RawInvoiceExtraction(
        invoice_number="INV-101",
        supplier_name="Supplier Corp",
        invoice_date="2024-03-01",
        due_date="2024-03-31",
        total_amount=500.0,
        currency="EUR",
        confidence_score=0.98,
    )
    mocker.patch("app.extraction.ai_extractor.AIExtractor.extract", return_value=mock_raw)

    result = runner.invoke(
        app,
        [
            "process",
            str(doc_dir),
            "--output-dir",
            str(out_dir),
            "--db-path",
            str(db_file),
        ],
    )
    assert result.exit_code == 0
    assert "Pipeline Execution Summary" in result.output
    assert "clean_inv.pdf" in result.output

    # Check generated files
    assert (out_dir / "invoices.csv").exists()
    assert (out_dir / "invoices.json").exists()
    assert (out_dir / "exceptions.csv").exists()
    assert (out_dir / "run_summary.json").exists()
