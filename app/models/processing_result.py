"""Processing results, exception models, and batch execution summary."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.models.invoice import ValidatedInvoice

ExceptionIssueType = Literal[
    "MISSING_INVOICE_NUMBER",
    "INVALID_AMOUNT",
    "UNKNOWN_CURRENCY",
    "MISSING_INVOICE_DATE",
    "LOW_CONFIDENCE",
    "DUPLICATE_INVOICE",
    "EXTRACTION_FAILED",
    "UNREADABLE_PDF",
]

ProcessingStatusType = Literal["OK", "FLAGGED", "EXCEPTION", "SKIPPED_CACHED"]


class DocumentException(BaseModel):
    """Represents a document that failed validation or extraction and was routed to the exception queue."""

    model_config = ConfigDict(extra="forbid")

    file_name: str
    file_hash: str
    issue_type: ExceptionIssueType
    details: str


class DocumentProcessingResult(BaseModel):
    """Result of processing an individual document through the intake pipeline."""

    model_config = ConfigDict(extra="ignore")

    file_name: str
    file_path: str
    file_hash: str
    status: ProcessingStatusType
    invoice: ValidatedInvoice | None = None
    exception: DocumentException | None = None
    message: str = ""


class BatchRunSummary(BaseModel):
    """Summary metrics of a batch processing run."""

    model_config = ConfigDict(extra="ignore")

    total_scanned: int = 0
    processed_ok: int = 0
    flagged_review: int = 0
    exceptions_count: int = 0
    skipped_cached: int = 0
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    output_files: dict[str, str] = Field(default_factory=dict)
