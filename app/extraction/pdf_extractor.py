"""PDF text extraction and SHA-256 hashing utilities."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be opened or parsed."""

    def __init__(self, message: str, issue_type: str = "UNREADABLE_PDF") -> None:
        super().__init__(message)
        self.issue_type = issue_type


@dataclass(frozen=True)
class ExtractedDocument:
    """Container for extracted text and metadata from a document file."""

    file_path: Path
    file_name: str
    file_hash: str
    raw_text: str
    page_count: int


def calculate_sha256(file_path: Path | str) -> str:
    """Calculate SHA-256 hexadecimal digest for a given file."""
    path = Path(file_path)
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


class PDFExtractor:
    """Extracts raw text and metadata from PDF invoices."""

    def extract(self, file_path: Path | str) -> ExtractedDocument:
        """Extract text content and compute SHA-256 hash from a PDF file.

        Raises:
            PDFExtractionError: If the file does not exist, is not a valid PDF,
                                or contains no readable text.
        """
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            raise PDFExtractionError(
                f"File not found or is not a regular file: {path}",
                issue_type="UNREADABLE_PDF",
            )

        file_hash = calculate_sha256(path)
        extracted_text_pages: list[str] = []
        page_count = 0

        # Try PyMuPDF (fitz) first for speed and layout accuracy
        try:
            import fitz  # PyMuPDF

            with fitz.open(path) as doc:
                page_count = len(doc)
                if page_count == 0:
                    raise PDFExtractionError(
                        f"PDF document contains 0 pages: {path.name}",
                        issue_type="UNREADABLE_PDF",
                    )
                for page in doc:
                    text = page.get_text() or ""
                    extracted_text_pages.append(text)
        except (ImportError, Exception) as fitz_err:
            # Fallback to pypdf
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                page_count = len(reader.pages)
                if page_count == 0:
                    raise PDFExtractionError(
                        f"PDF document contains 0 pages: {path.name}",
                        issue_type="UNREADABLE_PDF",
                    )
                for page in reader.pages:
                    text = page.extract_text() or ""
                    extracted_text_pages.append(text)
            except PDFExtractionError:
                raise
            except Exception as pypdf_err:
                raise PDFExtractionError(
                    f"Failed to read PDF {path.name}: {pypdf_err} (fitz error: {fitz_err})",
                    issue_type="UNREADABLE_PDF",
                ) from pypdf_err

        full_text = "\n\n".join(extracted_text_pages).strip()

        if not full_text:
            raise PDFExtractionError(
                f"No extractable text found in PDF: {path.name} (scanned/empty document)",
                issue_type="UNREADABLE_PDF",
            )

        return ExtractedDocument(
            file_path=path,
            file_name=path.name,
            file_hash=file_hash,
            raw_text=full_text,
            page_count=page_count,
        )
