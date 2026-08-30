"""Invoice domain models for raw extraction and validated records."""

from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

AllowedCurrency = Literal["EUR", "USD", "GBP", "CAD", "AUD", "CHF"]
ValidationStatus = Literal["OK", "FLAGGED"]


class RawInvoiceExtraction(BaseModel):
    """Raw extraction schema output by LLM Structured Outputs."""

    model_config = ConfigDict(extra="ignore")

    invoice_number: str | None = Field(
        default=None,
        description="The unique invoice identifier/number as stated on the document",
    )
    supplier_name: str | None = Field(
        default=None,
        description="Legal or commercial name of the vendor/supplier issuing the invoice",
    )
    invoice_date: str | None = Field(
        default=None,
        description="Date of invoice issuance in ISO YYYY-MM-DD format",
    )
    due_date: str | None = Field(
        default=None,
        description="Payment due date in ISO YYYY-MM-DD format if present",
    )
    total_amount: float | None = Field(
        default=None,
        description="Total gross amount payable on the invoice as a float",
    )
    currency: str | None = Field(
        default=None,
        description="Three-letter ISO currency code, e.g. EUR, USD, GBP, CAD, AUD, CHF",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 and 1.0 reflecting document clarity",
    )


class ValidatedInvoice(BaseModel):
    """Validated domain model ready for downstream ERP/accounting export."""

    model_config = ConfigDict(extra="forbid")

    file_name: str
    file_hash: str
    invoice_number: str
    supplier_name: str
    invoice_date: date
    due_date: date | None = None
    total_amount: float
    currency: AllowedCurrency
    status: ValidationStatus
