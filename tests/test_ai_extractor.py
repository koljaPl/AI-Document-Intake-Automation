"""Tests for AI structured extraction using mocked LLM outputs."""

import pytest
from app.extraction.ai_extractor import AIExtractionError, AIExtractor
from app.models.invoice import RawInvoiceExtraction


def test_ai_extractor_success(mock_openai_client) -> None:
    expected = RawInvoiceExtraction(
        invoice_number="INV-2024-100",
        supplier_name="Global Tech Ltd",
        invoice_date="2024-03-01",
        due_date="2024-03-31",
        total_amount=1950.00,
        currency="USD",
        confidence_score=0.96,
    )
    mock_openai_client.set_parsed_return_value(expected)

    extractor = AIExtractor(api_key="mock-key", client=mock_openai_client)
    result = extractor.extract(
        document_text="Invoice text content here...",
        file_name="invoice_100.pdf",
    )

    assert result.invoice_number == "INV-2024-100"
    assert result.supplier_name == "Global Tech Ltd"
    assert result.total_amount == 1950.00
    assert result.currency == "USD"
    assert result.confidence_score == 0.96


def test_ai_extractor_empty_text_error(mock_openai_client) -> None:
    extractor = AIExtractor(api_key="mock-key", client=mock_openai_client)
    with pytest.raises(AIExtractionError) as exc_info:
        extractor.extract("", file_name="empty.pdf")
    assert exc_info.value.issue_type == "EXTRACTION_FAILED"


def test_ai_extractor_api_failure(mock_openai_client) -> None:
    mock_openai_client.beta.chat.completions.parse.side_effect = RuntimeError("OpenAI 500 error")

    extractor = AIExtractor(api_key="mock-key", client=mock_openai_client)
    with pytest.raises(AIExtractionError) as exc_info:
        extractor.extract("Some document text", file_name="fail.pdf")
    assert exc_info.value.issue_type == "EXTRACTION_FAILED"
    assert "OpenAI 500 error" in str(exc_info.value)


def test_ai_extractor_refusal(mock_openai_client) -> None:
    mock_openai_client.set_parsed_return_value(None, refusal="I cannot process this document")

    extractor = AIExtractor(api_key="mock-key", client=mock_openai_client)
    with pytest.raises(AIExtractionError) as exc_info:
        extractor.extract("Some document text", file_name="refused.pdf")
    assert exc_info.value.issue_type == "EXTRACTION_FAILED"
    assert "refused" in str(exc_info.value).lower()


def test_ai_extractor_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    extractor = AIExtractor(api_key=None, client=None)
    with pytest.raises(AIExtractionError) as exc_info:
        _ = extractor.client
    assert "OPENAI_API_KEY" in str(exc_info.value)
