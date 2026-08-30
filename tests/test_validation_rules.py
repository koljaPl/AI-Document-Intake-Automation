"""Unit tests for business validation rules."""

from datetime import date
import pytest
from app.models.invoice import RawInvoiceExtraction
from app.validation.rules import InvoiceValidator, normalize_currency, parse_date_string


@pytest.fixture
def validator() -> InvoiceValidator:
    return InvoiceValidator(confidence_floor=0.80)


@pytest.fixture
def valid_raw_extraction() -> RawInvoiceExtraction:
    return RawInvoiceExtraction(
        invoice_number="INV-2024-001",
        supplier_name="Acme Industrial Supplies",
        invoice_date="2024-03-15",
        due_date="2024-04-15",
        total_amount=1250.50,
        currency="EUR",
        confidence_score=0.98,
    )


def test_clean_invoice_validation(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="invoice_001.pdf",
        file_hash="hash123",
    )
    assert exception is None
    assert invoice is not None
    assert invoice.invoice_number == "INV-2024-001"
    assert invoice.supplier_name == "Acme Industrial Supplies"
    assert invoice.invoice_date == date(2024, 3, 15)
    assert invoice.due_date == date(2024, 4, 15)
    assert invoice.total_amount == 1250.50
    assert invoice.currency == "EUR"
    assert invoice.status == "OK"


def test_missing_due_date_flags_for_review(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    valid_raw_extraction.due_date = None
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="invoice_002.pdf",
        file_hash="hash123",
    )
    assert exception is None
    assert invoice is not None
    assert invoice.due_date is None
    assert invoice.status == "FLAGGED"


def test_due_date_before_invoice_date_flags_for_review(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    valid_raw_extraction.invoice_date = "2024-03-15"
    valid_raw_extraction.due_date = "2024-02-01"  # Prior to invoice date
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="invoice_002.pdf",
        file_hash="hash123",
    )
    assert exception is None
    assert invoice is not None
    assert invoice.status == "FLAGGED"


def test_missing_invoice_number(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    valid_raw_extraction.invoice_number = "   "
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="invoice_missing_num.pdf",
        file_hash="hash123",
    )
    assert invoice is None
    assert exception is not None
    assert exception.issue_type == "MISSING_INVOICE_NUMBER"


def test_missing_supplier_name(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    valid_raw_extraction.supplier_name = ""
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="invoice_missing_supp.pdf",
        file_hash="hash123",
    )
    assert invoice is None
    assert exception is not None
    assert exception.issue_type == "EXTRACTION_FAILED"


def test_missing_and_invalid_invoice_date(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    # Empty date
    valid_raw_extraction.invoice_date = None
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="doc.pdf",
        file_hash="h1",
    )
    assert invoice is None
    assert exception is not None
    assert exception.issue_type == "MISSING_INVOICE_DATE"

    # Malformed date
    valid_raw_extraction.invoice_date = "invalid-date-format"
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="doc.pdf",
        file_hash="h1",
    )
    assert invoice is None
    assert exception is not None
    assert exception.issue_type == "MISSING_INVOICE_DATE"


@pytest.mark.parametrize("invalid_amount", [0.0, -100.0, None])
def test_invalid_amounts(
    validator: InvoiceValidator,
    valid_raw_extraction: RawInvoiceExtraction,
    invalid_amount: float | None,
) -> None:
    valid_raw_extraction.total_amount = invalid_amount
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="doc.pdf",
        file_hash="h1",
    )
    assert invoice is None
    assert exception is not None
    assert exception.issue_type == "INVALID_AMOUNT"


def test_currency_whitelist_and_normalization(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    # Test symbol conversion € -> EUR
    valid_raw_extraction.currency = "€"
    inv_eur, err_eur = validator.validate(valid_raw_extraction, "doc.pdf", "h1")
    assert err_eur is None
    assert inv_eur is not None
    assert inv_eur.currency == "EUR"

    # Test $ -> USD
    valid_raw_extraction.currency = "$"
    inv_usd, err_usd = validator.validate(valid_raw_extraction, "doc.pdf", "h1")
    assert err_usd is None
    assert inv_usd is not None
    assert inv_usd.currency == "USD"

    # Test unknown currency
    valid_raw_extraction.currency = "BITCOIN"
    inv_err, err = validator.validate(valid_raw_extraction, "doc.pdf", "h1")
    assert inv_err is None
    assert err is not None
    assert err.issue_type == "UNKNOWN_CURRENCY"


def test_confidence_floor(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    valid_raw_extraction.confidence_score = 0.79
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="doc.pdf",
        file_hash="h1",
    )
    assert invoice is None
    assert exception is not None
    assert exception.issue_type == "LOW_CONFIDENCE"


def test_duplicate_invoice_detection(
    validator: InvoiceValidator, valid_raw_extraction: RawInvoiceExtraction
) -> None:
    existing = {("acme industrial supplies", "inv-2024-001")}
    invoice, exception = validator.validate(
        raw=valid_raw_extraction,
        file_name="invoice_duplicate.pdf",
        file_hash="h2",
        existing_invoices=existing,
    )
    assert invoice is None
    assert exception is not None
    assert exception.issue_type == "DUPLICATE_INVOICE"


def test_parse_date_string_formats() -> None:
    assert parse_date_string("2024-01-15") == date(2024, 1, 15)
    assert parse_date_string("15.01.2024") == date(2024, 1, 15)
    assert parse_date_string("15/01/2024") == date(2024, 1, 15)
    assert parse_date_string("2024/01/15") == date(2024, 1, 15)
    assert parse_date_string("") is None
    assert parse_date_string(None) is None


def test_normalize_currency_symbols() -> None:
    assert normalize_currency("EUR") == "EUR"
    assert normalize_currency("usd") == "USD"
    assert normalize_currency("£") == "GBP"
    assert normalize_currency("C$") == "CAD"
    assert normalize_currency("Unknown") == "UNKNOWN"
