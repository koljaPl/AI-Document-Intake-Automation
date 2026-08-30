"""LLM Structured Output Extractor using OpenAI Structured Outputs."""

from __future__ import annotations

import os
from typing import Any, Protocol

from app.models.invoice import RawInvoiceExtraction

SYSTEM_PROMPT = """You are an expert AI document data extraction assistant specialized in processing corporate invoices.
Extract key business metadata from the provided document text into the exact requested JSON schema:

1. invoice_number: The unique invoice or billing reference identifier.
2. supplier_name: The company or vendor name issuing the invoice.
3. invoice_date: The issue date in ISO YYYY-MM-DD format.
4. due_date: The payment due date in ISO YYYY-MM-DD format if present; null/None if missing.
5. total_amount: The final gross total amount payable as a decimal number (float).
6. currency: The 3-letter ISO currency code (e.g., EUR, USD, GBP, CAD, AUD, CHF).
7. confidence_score: A confidence score between 0.0 and 1.0 reflecting how clear, complete, and unambiguous the invoice information was extracted.

If a field cannot be confidently determined or is missing from the document, set it to null and adjust the confidence_score accordingly.
Do not invent or extrapolate missing values."""


class AIExtractionError(Exception):
    """Raised when LLM extraction fails due to API errors, rate limits, or refusals."""

    def __init__(self, message: str, issue_type: str = "EXTRACTION_FAILED") -> None:
        super().__init__(message)
        self.issue_type = issue_type


class LLMClientProtocol(Protocol):
    """Protocol for OpenAI chat completions parsing client."""

    @property
    def beta(self) -> Any: ...


class AIExtractor:
    """Extracts structured invoice data using LLM Structured Outputs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = client

    @property
    def client(self) -> Any:
        """Lazily initialize OpenAI client if not injected."""
        if self._client is None:
            from openai import OpenAI

            if not self.api_key:
                raise AIExtractionError(
                    "OPENAI_API_KEY environment variable is not set. "
                    "Please provide an API key or configure .env",
                    issue_type="EXTRACTION_FAILED",
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def extract(self, document_text: str, file_name: str = "") -> RawInvoiceExtraction:
        """Extract structured invoice data from raw text using OpenAI Structured Outputs.

        Args:
            document_text: Raw plain text extracted from invoice PDF.
            file_name: Optional file name for logging / error context.

        Returns:
            RawInvoiceExtraction parsed Pydantic model.

        Raises:
            AIExtractionError: If API call fails, times out, or returns an unparseable response.
        """
        if not document_text or not document_text.strip():
            raise AIExtractionError(
                f"Cannot extract from empty document text for file {file_name}",
                issue_type="EXTRACTION_FAILED",
            )

        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Filename: {file_name}\n\n"
                            f"Document Content:\n{document_text}"
                        ),
                    },
                ],
                response_format=RawInvoiceExtraction,
            )

            message = completion.choices[0].message
            if getattr(message, "refusal", None):
                raise AIExtractionError(
                    f"Model refused to process {file_name}: {message.refusal}",
                    issue_type="EXTRACTION_FAILED",
                )

            parsed = message.parsed
            if parsed is None:
                raise AIExtractionError(
                    f"Structured output returned null parsed data for {file_name}",
                    issue_type="EXTRACTION_FAILED",
                )

            return parsed

        except AIExtractionError:
            raise
        except Exception as err:
            raise AIExtractionError(
                f"OpenAI extraction failed for {file_name}: {err}",
                issue_type="EXTRACTION_FAILED",
            ) from err
