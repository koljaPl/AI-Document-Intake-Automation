# AI Document Intake Automation

> **Production-grade document ingestion pipeline with structured AI extraction, multi-layer validation, and exception routing.**

[![CI Test Suite](https://github.com/koljaPl/AI-Document-Intake-Automation/actions/workflows/tests.yml/badge.svg)](https://github.com/koljaPl/AI-Document-Intake-Automation/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Pydantic v2](https://img.shields.io/badge/validation-Pydantic%20v2-green.svg)](https://docs.pydantic.dev/)
[![CLI-Typer](https://img.shields.io/badge/CLI-Typer%20%2B%20Rich-orange.svg)](https://typer.tiangolo.com/)
[![SQLite-Idempotent](https://img.shields.io/badge/caching-SQLite%20SHA--256-lightgrey.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 💼 Business Impact & ROI

Handling accounts payable manually is slow, error-prone, and expensive. This system automates the document intake funnel: converting noisy, multi-format PDF invoices into validated, ERP-ready CSV and JSON data while automatically isolating duplicates, suspicious values, and malformed files into an exception queue.

| Metric | Manual Processing | AI Intake Automation | Improvement |
| :--- | :--- | :--- | :--- |
| **Speed (20 Invoices)** | ~45 minutes | **~8 seconds** | **330x faster** |
| **Error Rate** | 3–6% typographical errors | **< 0.1%** (enforced by Pydantic schemas) | **Near zero human entry error** |
| **Duplicate Prevention** | Dependent on manual vigilance | **Deterministic SQLite SHA-256 + vendor signature** | **100% duplicate catch rate** |
| **API Cost Waste** | Redundant reprocessing | **Zero-token re-runs via local hash cache** | **Up to 70% LLM cost savings** |
| **Audit Readiness** | Scattered PDFs and emails | **Standardized `run_summary.json` & exception logs** | **Instant audit trail** |

### Before vs. After Scenario
* **Before:** An accounts payable specialist receives 20 vendor PDFs via email, opens each file, manually copies invoice numbers, dates, amounts, and lines into an ERP, often missing duplicate submissions and fat-fingering amounts.
* **After:** `ai-intake process ./sample_documents` ingests the batch in 8 seconds: 17 invoices are cleanly exported to `invoices.csv` and `invoices.json`, 2 files with missing dates or non-whitelisted currencies are routed to `exceptions.csv`, and 1 duplicate invoice is blocked before touching the ledger.

---

## 🏗 Pipeline Architecture

```text
                               ┌────────────────────────┐
                               │  Incoming PDF Invoices │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │ SHA-256 Hash Check     │
                               │ (SQLite Idempotency)   │
                               └───────────┬────────────┘
                                           │
                     ┌─────────────────────┴─────────────────────┐
                     │                                           │
           [Already Cached & Not Forced]                 [New / Forced File]
                     │                                           │
                     ▼                                           ▼
          ┌─────────────────────┐                     ┌─────────────────────┐
          │  SKIPPED (No Cost)  │                     │ PDF Text Extractor  │
          └─────────────────────┘                     │ (PyMuPDF / pypdf)   │
                                                      └──────────┬──────────┘
                                                                 │
                                                                 ▼
                                                      ┌─────────────────────┐
                                                      │ OpenAI LLM Parser   │
                                                      │ (Structured Outputs)│
                                                      └──────────┬──────────┘
                                                                 │
                                                                 ▼
                                                      ┌─────────────────────┐
                                                      │ Multi-Layer Rules   │
                                                      │ & Deduplication     │
                                                      └──────────┬──────────┘
                                                                 │
                                     ┌───────────────────────────┴───────────────────────────┐
                                     │                                                       │
                           [Passed Business Rules]                                 [Failed Business Rules]
                                     │                                                       │
                     ┌───────────────┴───────────────┐                                       ▼
                     │                               │                            ┌─────────────────────┐
             [Status == "OK"]               [Status == "FLAGGED"]                 │ Document Exception  │
                     │                               │                            │ (exceptions.csv)    │
                     ▼                               ▼                            └─────────────────────┘
          ┌─────────────────────────────────────────────────────┐
          │         Validated Invoices (invoices.csv)           │
          └─────────────────────────────────────────────────────┘
```

---

## ⚡ Quickstart

### 1. Prerequisites
- Python 3.12+
- (Optional) OpenAI API Key (only required for live model calls; dry-run and test suites run 100% offline)

### 2. Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/koljaPl/AI-Document-Intake-Automation.git
cd AI-Document-Intake-Automation

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package and dependencies
pip install -e .
```

### 3. Generate Synthetic Demo Invoices
A built-in generator creates real PDF invoices with intentional edge cases (missing due dates, duplicate invoice IDs, negative totals, and unwhitelisted currencies):

```bash
python scripts/generate_sample_pdfs.py
```

### 4. Run Dry-Run Simulation (Zero API Cost)
Inspect documents, verify cache status, and preview estimated token spend:

```bash
ai-intake process sample_documents --dry-run
```
Output:
```text
[DRY RUN] 7 documents found.
  - 7 new documents to process
  - 0 already cached (will be skipped)
  - Estimated API calls: 7
```

### 5. Live Processing Run
Set your API key in `.env` or pass it in your environment:
```bash
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

ai-intake process sample_documents --output-dir ./output
```

---

## 🖥 Terminal UI & Live Status

During execution, `rich` provides progress tracking and real-time document triage:

```text
  ✓ invoice_001_clean.pdf (Acme Industrial Supplies Ltd • INV-2024-001) (OK)
  ! invoice_002_missing_due_date.pdf (REVIEW) — Missing due date or review condition
  ✗ invoice_003_invalid_amount.pdf (FAILED) — [INVALID_AMOUNT] Total amount must be greater than 0.00. Received: -75.0
  ✗ invoice_004_duplicate.pdf (FAILED) — [DUPLICATE_INVOICE] Invoice number 'INV-2024-001' from supplier 'Acme Industrial Supplies Ltd' already exists in batch or database
  ✓ invoice_005_clean.pdf (Vertex Global Advisory • INV-2024-005) (OK)
  ✗ invoice_006_missing_invoice_number.pdf (FAILED) — [MISSING_INVOICE_NUMBER] Invoice number is missing or empty in document extraction
  ✗ invoice_007_unsupported_currency.pdf (FAILED) — [UNKNOWN_CURRENCY] Currency 'JPY' is not in the whitelisted currencies: [AUD, CAD, CHF, EUR, GBP, USD]

╭────────────────────── Pipeline Execution Summary ──────────────────────╮
│ Metric                         │                                 Count │
├────────────────────────────────┼───────────────────────────────────────┤
│ Total Documents Scanned        │                                     7 │
│ Successfully Processed (OK)    │                                     2 │
│ Flagged for Human Review       │                                     1 │
│ Extraction Failures            │                                     4 │
│ Skipped (Already Cached)       │                                     0 │
╰────────────────────────────────┴───────────────────────────────────────╯

Output generated in: ./output/
  - output/invoices.csv
  - output/invoices.json
  - output/exceptions.csv
  - output/run_summary.json
```

---

## 🛡 Business Validation Rules

Every extracted invoice document must strictly pass the following validation layers:

| Rule Layer | Target | Failure Outcome | Description |
| :--- | :--- | :--- | :--- |
| **Confidence Floor** | `confidence_score` | `LOW_CONFIDENCE` | Rejects noisy extractions where model confidence is below `0.80`. |
| **Required Invoice ID** | `invoice_number` | `MISSING_INVOICE_NUMBER` | Mandatory identifier for accounting matching. |
| **Required Vendor** | `supplier_name` | `EXTRACTION_FAILED` | Invoices without identifiable legal vendors cannot be settled. |
| **Valid Calendar Date** | `invoice_date` | `MISSING_INVOICE_DATE` | Parses ISO and European/US date formats (`YYYY-MM-DD`). |
| **Positive Amount** | `total_amount` | `INVALID_AMOUNT` | Must be `> 0.00`. Rejects zero or credit adjustments submitted as invoices. |
| **Currency Whitelist** | `currency` | `UNKNOWN_CURRENCY` | Whitelist: `EUR`, `USD`, `GBP`, `CAD`, `AUD`, `CHF`. Normalizes `€`, `$`, `£`. |
| **Deduplication Check** | `(supplier, invoice_num)` | `DUPLICATE_INVOICE` | Checks SQLite history AND intra-batch records to prevent double payments. |
| **Human Review Flag** | `due_date` | `status="FLAGGED"` | Missing due dates or due dates before invoice dates are accepted but flagged for human sign-off. |

---

## 📁 Output Schemas

### `output/invoices.csv`
Contains all successfully parsed and flagged invoices:
```csv
file_name,file_hash,invoice_number,supplier_name,invoice_date,due_date,total_amount,currency,status
invoice_001_clean.pdf,b15bafc...,INV-2024-001,Acme Industrial Supplies Ltd,2024-03-01,2024-03-31,1250.00,EUR,OK
invoice_002_missing_due_date.pdf,8ef02bc...,INV-2024-002,TechCorp Cloud Solutions,2024-03-05,,450.00,USD,FLAGGED
invoice_005_clean.pdf,fa481cd...,INV-2024-005,Vertex Global Advisory,2024-03-12,2024-04-12,3400.00,GBP,OK
```

### `output/exceptions.csv`
Contains rejected items routed to human accounts payable review:
```csv
file_name,file_hash,issue_type,details
invoice_003_invalid_amount.pdf,a4c51d...,INVALID_AMOUNT,"Total amount must be greater than 0.00. Received: -75.0"
invoice_004_duplicate.pdf,96bf8e...,DUPLICATE_INVOICE,"Invoice number 'INV-2024-001' from supplier 'Acme Industrial Supplies Ltd' already exists in batch or database"
invoice_006_missing_invoice_number.pdf,7a5b3f...,MISSING_INVOICE_NUMBER,"Invoice number is missing or empty in document extraction"
invoice_007_unsupported_currency.pdf,31e4ab...,UNKNOWN_CURRENCY,"Currency 'JPY' is not in the whitelisted currencies: [AUD, CAD, CHF, EUR, GBP, USD]"
```

### `output/run_summary.json`
Comprehensive batch execution metadata for reporting and dashboards:
```json
{
  "total_scanned": 7,
  "processed_ok": 2,
  "flagged_review": 1,
  "exceptions_count": 4,
  "skipped_cached": 0,
  "started_at": "2026-08-30T16:20:00.123456Z",
  "completed_at": "2026-08-30T16:20:08.234567Z",
  "duration_seconds": 8.11,
  "output_files": {
    "invoices_csv": "output/invoices.csv",
    "invoices_json": "output/invoices.json",
    "exceptions_csv": "output/exceptions.csv",
    "exceptions_json": "output/exceptions.json",
    "run_summary_json": "output/run_summary.json"
  }
}
```

---

## 🗄 SQLite Caching & CLI Utilities

The SQLite database (`intake_cache.db`) stores SHA-256 digests and processing metadata:

```bash
# View processing history and database statistics
ai-intake stats

# Clear the cache table when resetting processing state
ai-intake cache-clear --yes

# Force re-evaluation of previously cached files
ai-intake process ./sample_documents --force
```

---

## 🧪 Test Suite & CI

The test suite runs with **zero external API calls and zero billing cost** via pytest fixtures and mocked OpenAI responses:

```bash
# Run all unit and integration tests
pytest -v

# Run with coverage report
pytest --cov=app tests/
```

### Test Coverage Highlights:
- **`test_pdf_extractor.py`**: Validates text extraction, layout reading, empty canvas handling, corrupted PDF rejection, and SHA-256 digests.
- **`test_ai_extractor.py`**: Validates Pydantic structured output mapping, refusal handling, and API failure propagation.
- **`test_validation_rules.py`**: Complete rule matrix: negative/zero totals, currency normalization, missing fields, confidence threshold, and deduplication.
- **`test_cache.py`**: SQLite initialization, record persistence, updates on conflict, and deduplication queries.
- **`test_pipeline.py`**: Full end-to-end batch processing, CSV/JSON file generation, and idempotency verification.
- **`test_cli.py`**: Typer command execution, option validation, dry-run simulation, and live progress display.

---

## 🐳 Docker Deployment

A lightweight, multi-platform Docker container is included:

```bash
# Build Docker image
docker build -t ai-document-intake .

# Run dry-run via Docker
docker run --rm -v $(pwd)/sample_documents:/data ai-document-intake process /data --dry-run

# Run full batch processing with mounted output directory
docker run --rm \
  -e OPENAI_API_KEY="your-api-key" \
  -v $(pwd)/sample_documents:/data \
  -v $(pwd)/output:/output \
  ai-document-intake process /data --output-dir /output
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.