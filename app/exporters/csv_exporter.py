"""CSV exporter for validated invoices and document exceptions."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from app.models.invoice import ValidatedInvoice
from app.models.processing_result import DocumentException

INVOICE_CSV_COLUMNS = [
    "file_name",
    "file_hash",
    "invoice_number",
    "supplier_name",
    "invoice_date",
    "due_date",
    "total_amount",
    "currency",
    "status",
]

EXCEPTION_CSV_COLUMNS = [
    "file_name",
    "file_hash",
    "issue_type",
    "details",
]


class CSVExporter:
    """Exports validated invoices and exceptions to standardized CSV format."""

    @staticmethod
    def export_invoices(
        invoices: Sequence[ValidatedInvoice],
        output_path: Path | str,
    ) -> Path:
        """Export list of ValidatedInvoice objects to CSV."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=INVOICE_CSV_COLUMNS)
            writer.writeheader()
            for inv in invoices:
                writer.writerow(
                    {
                        "file_name": inv.file_name,
                        "file_hash": inv.file_hash,
                        "invoice_number": inv.invoice_number,
                        "supplier_name": inv.supplier_name,
                        "invoice_date": inv.invoice_date.isoformat(),
                        "due_date": inv.due_date.isoformat() if inv.due_date else "",
                        "total_amount": f"{inv.total_amount:.2f}",
                        "currency": inv.currency,
                        "status": inv.status,
                    }
                )

        return path

    @staticmethod
    def export_exceptions(
        exceptions: Sequence[DocumentException],
        output_path: Path | str,
    ) -> Path:
        """Export list of DocumentException objects to CSV."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EXCEPTION_CSV_COLUMNS)
            writer.writeheader()
            for exc in exceptions:
                writer.writerow(
                    {
                        "file_name": exc.file_name,
                        "file_hash": exc.file_hash,
                        "issue_type": exc.issue_type,
                        "details": exc.details,
                    }
                )

        return path
