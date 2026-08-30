"""Core pipeline coordinator for scanning, extracting, validating, and exporting invoices."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.exporters.csv_exporter import CSVExporter
from app.exporters.json_exporter import JSONExporter
from app.extraction.ai_extractor import AIExtractionError, AIExtractor
from app.extraction.pdf_extractor import (
    PDFExtractionError,
    PDFExtractor,
    calculate_sha256,
)
from app.models.invoice import ValidatedInvoice
from app.models.processing_result import (
    BatchRunSummary,
    DocumentException,
    DocumentProcessingResult,
)
from app.pipeline.cache import IntakeCache
from app.validation.rules import InvoiceValidator


class DocumentPipeline:
    """Orchestrates end-to-end document intake batch processing."""

    def __init__(
        self,
        cache: IntakeCache | None = None,
        pdf_extractor: PDFExtractor | None = None,
        ai_extractor: AIExtractor | None = None,
        validator: InvoiceValidator | None = None,
        output_dir: Path | str = "./output",
    ) -> None:
        self.cache = cache or IntakeCache()
        self.pdf_extractor = pdf_extractor or PDFExtractor()
        self.ai_extractor = ai_extractor or AIExtractor()
        self.validator = validator or InvoiceValidator()
        self.output_dir = Path(output_dir)

    def scan_directory(self, directory: Path | str) -> list[Path]:
        """Scan given directory recursively or top-level for PDF invoice files."""
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {dir_path}")

        # Find all files with .pdf extension (case insensitive)
        pdf_files = [
            p for p in dir_path.glob("**/*") if p.is_file() and p.suffix.lower() == ".pdf"
        ]
        return sorted(pdf_files, key=lambda p: p.name)

    def dry_run(self, directory: Path | str) -> dict[str, int]:
        """Perform a dry-run check of the directory against the cache without API calls."""
        files = self.scan_directory(directory)
        total_docs = len(files)
        cached_count = 0
        new_docs = 0

        for f in files:
            file_hash = calculate_sha256(f)
            if self.cache.is_cached(file_hash):
                cached_count += 1
            else:
                new_docs += 1

        return {
            "total_documents": total_docs,
            "new_documents": new_docs,
            "already_cached": cached_count,
            "estimated_api_calls": new_docs,
        }

    def process_batch(
        self,
        directory: Path | str,
        force: bool = False,
        on_progress: Callable[[DocumentProcessingResult], None] | None = None,
    ) -> tuple[BatchRunSummary, list[DocumentProcessingResult]]:
        """Process a directory of PDF documents through extraction, validation, and export.

        Args:
            directory: Path to directory containing PDF files.
            force: If True, re-process files even if SHA-256 hash exists in cache.
            on_progress: Optional callback invoked after each file is processed.

        Returns:
            Tuple of (BatchRunSummary, list[DocumentProcessingResult]).
        """
        start_time = datetime.now(timezone.utc)
        files = self.scan_directory(directory)

        existing_invoices = self.cache.get_existing_invoices()
        validated_invoices: list[ValidatedInvoice] = []
        exceptions: list[DocumentException] = []
        results: list[DocumentProcessingResult] = []

        processed_ok = 0
        flagged_review = 0
        exceptions_count = 0
        skipped_cached = 0

        for file_path in files:
            file_name = file_path.name
            file_hash = calculate_sha256(file_path)

            # Step 1: Idempotency & Cache Check
            if not force and self.cache.is_cached(file_hash):
                skipped_cached += 1
                res = DocumentProcessingResult(
                    file_name=file_name,
                    file_path=str(file_path),
                    file_hash=file_hash,
                    status="SKIPPED_CACHED",
                    message="Already processed; skipped via cache",
                )
                results.append(res)
                if on_progress:
                    on_progress(res)
                continue

            # Step 2: PDF Text Extraction
            try:
                extracted_doc = self.pdf_extractor.extract(file_path)
            except PDFExtractionError as err:
                exc = DocumentException(
                    file_name=file_name,
                    file_hash=file_hash,
                    issue_type="UNREADABLE_PDF",
                    details=str(err),
                )
                exceptions.append(exc)
                exceptions_count += 1
                self.cache.save_record(
                    file_hash=file_hash,
                    file_name=file_name,
                    status="EXCEPTION",
                    issue_type="UNREADABLE_PDF",
                )
                res = DocumentProcessingResult(
                    file_name=file_name,
                    file_path=str(file_path),
                    file_hash=file_hash,
                    status="EXCEPTION",
                    exception=exc,
                    message=str(err),
                )
                results.append(res)
                if on_progress:
                    on_progress(res)
                continue

            # Step 3: AI Structured Output Extraction
            try:
                raw_extraction = self.ai_extractor.extract(
                    extracted_doc.raw_text, file_name=file_name
                )
            except AIExtractionError as err:
                exc = DocumentException(
                    file_name=file_name,
                    file_hash=file_hash,
                    issue_type=err.issue_type,  # type: ignore[arg-type]
                    details=str(err),
                )
                exceptions.append(exc)
                exceptions_count += 1
                self.cache.save_record(
                    file_hash=file_hash,
                    file_name=file_name,
                    status="EXCEPTION",
                    issue_type=err.issue_type,
                )
                res = DocumentProcessingResult(
                    file_name=file_name,
                    file_path=str(file_path),
                    file_hash=file_hash,
                    status="EXCEPTION",
                    exception=exc,
                    message=str(err),
                )
                results.append(res)
                if on_progress:
                    on_progress(res)
                continue

            # Step 4: Multi-Layer Business Validation & Deduplication
            validated_inv, val_exc = self.validator.validate(
                raw=raw_extraction,
                file_name=file_name,
                file_hash=file_hash,
                existing_invoices=existing_invoices,
            )

            if val_exc is not None:
                exceptions.append(val_exc)
                exceptions_count += 1
                self.cache.save_record(
                    file_hash=file_hash,
                    file_name=file_name,
                    status="EXCEPTION",
                    supplier_name=raw_extraction.supplier_name,
                    invoice_number=raw_extraction.invoice_number,
                    issue_type=val_exc.issue_type,
                )
                res = DocumentProcessingResult(
                    file_name=file_name,
                    file_path=str(file_path),
                    file_hash=file_hash,
                    status="EXCEPTION",
                    exception=val_exc,
                    message=val_exc.details,
                )
                results.append(res)
                if on_progress:
                    on_progress(res)
                continue

            # Step 5: Successful Validation (OK or FLAGGED)
            assert validated_inv is not None
            validated_invoices.append(validated_inv)

            # Record deduplication signature in runtime batch dictionary
            dedup_key = (
                validated_inv.supplier_name.lower().strip(),
                validated_inv.invoice_number.lower().strip(),
            )
            existing_invoices.setdefault(dedup_key, set()).add(file_hash)

            if validated_inv.status == "OK":
                processed_ok += 1
                msg = "Validated successfully"
            else:
                flagged_review += 1
                msg = "Flagged for review (missing or check due date)"

            self.cache.save_record(
                file_hash=file_hash,
                file_name=file_name,
                status=validated_inv.status,
                supplier_name=validated_inv.supplier_name,
                invoice_number=validated_inv.invoice_number,
            )

            res = DocumentProcessingResult(
                file_name=file_name,
                file_path=str(file_path),
                file_hash=file_hash,
                status=validated_inv.status,
                invoice=validated_inv,
                message=msg,
            )
            results.append(res)
            if on_progress:
                on_progress(res)

        # Step 6: Export Data Outputs
        self.output_dir.mkdir(parents=True, exist_ok=True)
        invoices_csv_path = self.output_dir / "invoices.csv"
        invoices_json_path = self.output_dir / "invoices.json"
        exceptions_csv_path = self.output_dir / "exceptions.csv"
        exceptions_json_path = self.output_dir / "exceptions.json"
        summary_json_path = self.output_dir / "run_summary.json"

        CSVExporter.export_invoices(validated_invoices, invoices_csv_path)
        JSONExporter.export_invoices(validated_invoices, invoices_json_path)

        CSVExporter.export_exceptions(exceptions, exceptions_csv_path)
        JSONExporter.export_exceptions(exceptions, exceptions_json_path)

        end_time = datetime.now(timezone.utc)
        duration = round((end_time - start_time).total_seconds(), 2)

        summary = BatchRunSummary(
            total_scanned=len(files),
            processed_ok=processed_ok,
            flagged_review=flagged_review,
            exceptions_count=exceptions_count,
            skipped_cached=skipped_cached,
            started_at=start_time,
            completed_at=end_time,
            duration_seconds=duration,
            output_files={
                "invoices_csv": str(invoices_csv_path),
                "invoices_json": str(invoices_json_path),
                "exceptions_csv": str(exceptions_csv_path),
                "exceptions_json": str(exceptions_json_path),
                "run_summary_json": str(summary_json_path),
            },
        )

        JSONExporter.export_summary(summary, summary_json_path)

        return summary, results
