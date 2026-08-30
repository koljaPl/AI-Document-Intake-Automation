"""Tests for PDF text extraction and file hashing."""

from pathlib import Path
import pytest
from app.extraction.pdf_extractor import (
    PDFExtractionError,
    PDFExtractor,
    calculate_sha256,
)


def test_extract_clean_pdf(sample_clean_pdf: Path) -> None:
    extractor = PDFExtractor()
    extracted = extractor.extract(sample_clean_pdf)

    assert extracted.file_name == "sample_invoice.pdf"
    assert len(extracted.file_hash) == 64  # SHA-256 is 64 hex characters
    assert extracted.page_count >= 1
    assert "ACME SUPPLIES" in extracted.raw_text
    assert "INV-2024-999" in extracted.raw_text
    assert "500.00 EUR" in extracted.raw_text


def test_calculate_sha256(sample_clean_pdf: Path) -> None:
    hash1 = calculate_sha256(sample_clean_pdf)
    hash2 = calculate_sha256(sample_clean_pdf)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_nonexistent_file_raises_error(tmp_path: Path) -> None:
    extractor = PDFExtractor()
    non_existent = tmp_path / "non_existent.pdf"
    with pytest.raises(PDFExtractionError) as exc_info:
        extractor.extract(non_existent)
    assert exc_info.value.issue_type == "UNREADABLE_PDF"


def test_corrupted_file_raises_error(tmp_path: Path) -> None:
    extractor = PDFExtractor()
    corrupt_file = tmp_path / "corrupt.pdf"
    corrupt_file.write_bytes(b"THIS IS NOT A VALID PDF CONTENT")

    with pytest.raises(PDFExtractionError) as exc_info:
        extractor.extract(corrupt_file)
    assert exc_info.value.issue_type == "UNREADABLE_PDF"


def test_empty_canvas_pdf_raises_error(create_test_pdf) -> None:
    # A PDF with no text strings drawn
    blank_pdf = create_test_pdf("blank.pdf", [])
    extractor = PDFExtractor()
    with pytest.raises(PDFExtractionError) as exc_info:
        extractor.extract(blank_pdf)
    assert exc_info.value.issue_type == "UNREADABLE_PDF"
