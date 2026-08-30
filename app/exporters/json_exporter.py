"""JSON exporter for validated invoices, exceptions, and run summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from app.models.invoice import ValidatedInvoice
from app.models.processing_result import BatchRunSummary, DocumentException


class JSONExporter:
    """Exports structured invoice data, exceptions, and execution metrics to JSON."""

    @staticmethod
    def _serialize_object(obj: Any) -> Any:
        """Helper to serialize datetime, date, and Pydantic models."""
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @classmethod
    def export_invoices(
        cls,
        invoices: Sequence[ValidatedInvoice],
        output_path: Path | str,
    ) -> Path:
        """Export validated invoices as a formatted JSON array."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = [inv.model_dump(mode="json") for inv in invoices]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=cls._serialize_object)

        return path

    @classmethod
    def export_exceptions(
        cls,
        exceptions: Sequence[DocumentException],
        output_path: Path | str,
    ) -> Path:
        """Export document exceptions as a formatted JSON array."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = [exc.model_dump(mode="json") for exc in exceptions]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=cls._serialize_object)

        return path

    @classmethod
    def export_summary(
        cls,
        summary: BatchRunSummary,
        output_path: Path | str,
    ) -> Path:
        """Export batch run metrics summary to JSON."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(mode="json"), f, indent=2, default=cls._serialize_object)

        return path
