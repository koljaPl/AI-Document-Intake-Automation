"""Business validation rules and domain checks for extracted invoice data."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import get_args

from app.models.invoice import AllowedCurrency, RawInvoiceExtraction, ValidatedInvoice
from app.models.processing_result import DocumentException

ALLOWED_CURRENCIES: set[str] = set(get_args(AllowedCurrency))

# Mapping common currency symbols to ISO codes for robustness
CURRENCY_SYMBOL_MAP: dict[str, str] = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "¥": "JPY",
    "C$": "CAD",
    "A$": "AUD",
    "Fr.": "CHF",
    "CHF": "CHF",
}


def parse_date_string(date_str: str | None) -> date | None:
    """Parse various common date representations into a python date object."""
    if not date_str:
        return None

    cleaned = date_str.strip()
    if not cleaned:
        return None

    # First try standard ISO format YYYY-MM-DD
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass

    # Try other common European / US business date formats
    date_patterns = [
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    for pattern in date_patterns:
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue

    return None


def normalize_currency(currency_str: str | None) -> str | None:
    """Normalize raw currency string or symbol to 3-letter uppercase ISO code."""
    if not currency_str:
        return None

    cleaned = currency_str.strip().upper()
    if cleaned in CURRENCY_SYMBOL_MAP:
        return CURRENCY_SYMBOL_MAP[cleaned]

    for sym, iso in CURRENCY_SYMBOL_MAP.items():
        if sym.upper() == cleaned:
            return iso

    # Match 3-letter alphabetic ISO code
    match = re.search(r"\b[A-Z]{3}\b", cleaned)
    if match:
        return match.group(0)

    return cleaned


class InvoiceValidator:
    """Validates raw AI extractions against strict business rules and deduplication state."""

    def __init__(self, confidence_floor: float = 0.80) -> None:
        self.confidence_floor = confidence_floor

    def validate(
        self,
        raw: RawInvoiceExtraction,
        file_name: str,
        file_hash: str,
        existing_invoices: set[tuple[str, str]] | None = None,
    ) -> tuple[ValidatedInvoice | None, DocumentException | None]:
        """Validate raw extraction against multi-layer business rules.

        Returns:
            A tuple of (ValidatedInvoice, None) on success or flagged review,
            or (None, DocumentException) if a critical business rule fails.
        """
        # Rule 1: Confidence Floor
        if raw.confidence_score is None or raw.confidence_score < self.confidence_floor:
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="LOW_CONFIDENCE",
                details=(
                    f"Model confidence score {raw.confidence_score} is below the "
                    f"minimum threshold of {self.confidence_floor:.2f}"
                ),
            )

        # Rule 2: Required Invoice Number
        if not raw.invoice_number or not raw.invoice_number.strip():
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="MISSING_INVOICE_NUMBER",
                details="Invoice number is missing or empty in document extraction",
            )
        cleaned_invoice_number = raw.invoice_number.strip()

        # Rule 3: Required Supplier Name
        if not raw.supplier_name or not raw.supplier_name.strip():
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="EXTRACTION_FAILED",
                details="Supplier name is missing or empty in document extraction",
            )
        cleaned_supplier_name = raw.supplier_name.strip()

        # Rule 4: Required and Valid Invoice Date
        if not raw.invoice_date or not raw.invoice_date.strip():
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="MISSING_INVOICE_DATE",
                details="Invoice date is missing or empty",
            )

        parsed_invoice_date = parse_date_string(raw.invoice_date)
        if parsed_invoice_date is None:
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="MISSING_INVOICE_DATE",
                details=(
                    f"Invoice date '{raw.invoice_date}' could not be parsed into a valid "
                    "calendar date (expected YYYY-MM-DD)"
                ),
            )

        # Rule 5: Positive Total Amount
        if raw.total_amount is None or raw.total_amount <= 0:
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="INVALID_AMOUNT",
                details=(
                    f"Total amount must be greater than 0.00. "
                    f"Received: {raw.total_amount}"
                ),
            )

        # Rule 6: Currency Whitelist
        norm_currency = normalize_currency(raw.currency)
        if not norm_currency or norm_currency not in ALLOWED_CURRENCIES:
            allowed_list_str = ", ".join(sorted(ALLOWED_CURRENCIES))
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="UNKNOWN_CURRENCY",
                details=(
                    f"Currency '{raw.currency}' (normalized: '{norm_currency}') is not "
                    f"in the whitelisted currencies: [{allowed_list_str}]"
                ),
            )

        # Rule 7: Deduplication Check
        dedup_key = (
            cleaned_supplier_name.lower(),
            cleaned_invoice_number.lower(),
        )
        if existing_invoices is not None and dedup_key in existing_invoices:
            return None, DocumentException(
                file_name=file_name,
                file_hash=file_hash,
                issue_type="DUPLICATE_INVOICE",
                details=(
                    f"Invoice number '{cleaned_invoice_number}' from supplier "
                    f"'{cleaned_supplier_name}' already exists in batch or database"
                ),
            )

        # Rule 8: Parse Optional Due Date & Review Flags
        status = "OK"
        parsed_due_date = parse_date_string(raw.due_date) if raw.due_date else None

        if not raw.due_date or parsed_due_date is None:
            # Missing due date flags invoice for human review
            status = "FLAGGED"
        elif parsed_due_date < parsed_invoice_date:
            # Due date prior to invoice date flags invoice for review
            status = "FLAGGED"

        validated = ValidatedInvoice(
            file_name=file_name,
            file_hash=file_hash,
            invoice_number=cleaned_invoice_number,
            supplier_name=cleaned_supplier_name,
            invoice_date=parsed_invoice_date,
            due_date=parsed_due_date,
            total_amount=round(float(raw.total_amount), 2),
            currency=norm_currency,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
        )

        return validated, None
