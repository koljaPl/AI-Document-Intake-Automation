"""Shared pytest fixtures for AI Document Intake test suite."""

from __future__ import annotations

from pathlib import Path
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.models.invoice import RawInvoiceExtraction
from app.pipeline.cache import IntakeCache


@pytest.fixture
def temp_cache(tmp_path: Path) -> IntakeCache:
    """Fixture providing an isolated temporary SQLite cache database."""
    db_file = tmp_path / "test_cache.db"
    return IntakeCache(db_path=db_file)


@pytest.fixture
def create_test_pdf(tmp_path: Path):
    """Factory fixture to generate custom PDF files for tests."""

    def _generate_pdf(filename: str, lines: list[str]) -> Path:
        pdf_path = tmp_path / filename
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        y = 750
        for line in lines:
            c.drawString(100, y, line)
            y -= 25
        c.save()
        return pdf_path

    return _generate_pdf


@pytest.fixture
def sample_clean_pdf(create_test_pdf) -> Path:
    """Creates a basic clean PDF with invoice text."""
    return create_test_pdf(
        "sample_invoice.pdf",
        [
            "ACME SUPPLIES LTD.",
            "INVOICE #: INV-2024-999",
            "Invoice Date: 2024-03-10",
            "Due Date: 2024-04-10",
            "Total Amount: 500.00 EUR",
        ],
    )


@pytest.fixture
def mock_openai_client(mocker):
    """Mocks OpenAI client beta.chat.completions.parse method."""
    mock_client = mocker.MagicMock()

    def set_parsed_return_value(raw: RawInvoiceExtraction, refusal: str | None = None):
        mock_choice = mocker.MagicMock()
        mock_choice.message.parsed = raw
        mock_choice.message.refusal = refusal
        mock_completion = mocker.MagicMock()
        mock_completion.choices = [mock_choice]
        mock_client.beta.chat.completions.parse.return_value = mock_completion

    mock_client.set_parsed_return_value = set_parsed_return_value
    return mock_client
