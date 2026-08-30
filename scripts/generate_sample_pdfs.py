"""Synthetic PDF invoice generator for demonstration and edge-case testing."""

from __future__ import annotations

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def create_invoice_pdf(
    output_path: Path | str,
    supplier_name: str,
    invoice_number: str | None,
    invoice_date: str | None,
    due_date: str | None,
    currency: str,
    line_items: list[tuple[str, int, float]],
    override_total: float | None = None,
    low_contrast: bool = False,
    notes: str = "Thank you for your business!",
) -> Path:
    """Generate a clean synthetic PDF invoice with realistic typography and tables."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Define color scheme
    if low_contrast:
        primary_color = colors.HexColor("#7f8c8d")
        text_color = colors.HexColor("#95a5a6")
        accent_color = colors.HexColor("#bdc3c7")
    else:
        primary_color = colors.HexColor("#1a365d")
        text_color = colors.HexColor("#2d3748")
        accent_color = colors.HexColor("#e2e8f0")

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=primary_color,
        spaceAfter=4,
    )

    header_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=primary_color,
    )

    normal_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=text_color,
        leading=14,
    )

    bold_style = ParagraphStyle(
        "BoldBodyStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=text_color,
        leading=14,
    )

    story = []

    # Header section: Supplier Name & INVOICE Header
    header_data = [
        [
            Paragraph(f"<b>{supplier_name}</b><br/>100 Enterprise Blvd, Suite 400<br/>Tech City, TC 94107<br/>billing@{supplier_name.lower().replace(' ', '')}.com", normal_style),
            Paragraph("<b>INVOICE</b>", title_style),
        ]
    ]
    t_header = Table(header_data, colWidths=[4.0 * inch, 3.2 * inch])
    t_header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story.append(t_header)
    story.append(Spacer(1, 15))

    # Meta Details: Invoice #, Date, Due Date, Bill To
    inv_num_display = f"<b>Invoice Number:</b> {invoice_number}" if invoice_number else "<b>Reference:</b> Order Pending"
    inv_date_display = f"<b>Invoice Date:</b> {invoice_date}" if invoice_date else "<b>Invoice Date:</b> [Not Stated]"
    due_date_display = f"<b>Due Date:</b> {due_date}" if due_date else ""

    meta_left = (
        "<b>Billed To:</b><br/>"
        "Apex Global Enterprises Inc.<br/>"
        "742 Evergreen Terrace<br/>"
        "Finance & Accounts Payable<br/>"
        "ap@apexglobal.example.com"
    )

    meta_right = f"{inv_num_display}<br/>{inv_date_display}"
    if due_date_display:
        meta_right += f"<br/>{due_date_display}"
    meta_right += f"<br/><b>Currency:</b> {currency}"

    meta_data = [
        [
            Paragraph(meta_left, normal_style),
            Paragraph(meta_right, normal_style),
        ]
    ]
    t_meta = Table(meta_data, colWidths=[4.0 * inch, 3.2 * inch])
    t_meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 20))

    # Line Items Table
    table_rows = [
        [
            Paragraph("<b>Description</b>", header_style),
            Paragraph("<b>Qty</b>", header_style),
            Paragraph("<b>Unit Price</b>", header_style),
            Paragraph("<b>Amount</b>", header_style),
        ]
    ]

    calculated_subtotal = 0.0
    for desc, qty, unit_price in line_items:
        line_total = qty * unit_price
        calculated_subtotal += line_total
        table_rows.append([
            Paragraph(desc, normal_style),
            Paragraph(str(qty), normal_style),
            Paragraph(f"{unit_price:,.2f} {currency}", normal_style),
            Paragraph(f"{line_total:,.2f} {currency}", normal_style),
        ])

    final_total = override_total if override_total is not None else calculated_subtotal

    # Summary Rows
    table_rows.append(["", "", Paragraph("<b>Subtotal:</b>", bold_style), Paragraph(f"{calculated_subtotal:,.2f} {currency}", normal_style)])
    table_rows.append(["", "", Paragraph("<b>Total Amount:</b>", bold_style), Paragraph(f"<b>{final_total:,.2f} {currency}</b>", bold_style)])

    item_table = Table(table_rows, colWidths=[3.6 * inch, 0.8 * inch, 1.4 * inch, 1.4 * inch])
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -3), 0.5, colors.HexColor("#e2e8f0")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, primary_color),
        ("LINEBELOW", (2, -1), (3, -1), 1.5, primary_color),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 25))

    # Notes & Payment Details
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=10))
    story.append(Paragraph(f"<b>Notes:</b> {notes}", normal_style))
    story.append(Paragraph("Payment Terms: Net 30 days. Remit payment to bank details on file.", normal_style))

    doc.build(story)
    return path


def generate_all_samples(output_directory: Path | str = "sample_documents") -> list[Path]:
    """Generate all synthetic test and edge-case PDF invoices."""
    out_dir = Path(output_directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

    # 1. Clean normal EUR invoice
    p1 = create_invoice_pdf(
        output_path=out_dir / "invoice_001_clean.pdf",
        supplier_name="Acme Industrial Supplies Ltd",
        invoice_number="INV-2024-001",
        invoice_date="2024-03-01",
        due_date="2024-03-31",
        currency="EUR",
        line_items=[
            ("Standard CNC Milling Components", 10, 85.00),
            ("High-Tensile Fasteners (Box of 500)", 4, 100.00),
        ],
        notes="Standard corporate delivery order #9421",
    )
    generated_files.append(p1)

    # 2. Missing due date & low contrast layout (FLAGGED for human review)
    p2 = create_invoice_pdf(
        output_path=out_dir / "invoice_002_missing_due_date.pdf",
        supplier_name="TechCorp Cloud Solutions",
        invoice_number="INV-2024-002",
        invoice_date="2024-03-05",
        due_date=None,  # Intentionally missing due date
        currency="USD",
        line_items=[
            ("Cloud Infrastructure Compute Units (Tier 2)", 1, 450.00),
        ],
        low_contrast=True,
        notes="Monthly cloud usage. Due date omitted on standard draft.",
    )
    generated_files.append(p2)

    # 3. Invalid amount: negative total (-75.00 EUR)
    p3 = create_invoice_pdf(
        output_path=out_dir / "invoice_003_invalid_amount.pdf",
        supplier_name="Logistics Prime Services",
        invoice_number="INV-2024-003",
        invoice_date="2024-03-10",
        due_date="2024-04-10",
        currency="EUR",
        line_items=[
            ("Expedited Freight Shipping Credit Adjustment", 1, -75.00),
        ],
        override_total=-75.00,
        notes="Credit note / negative adjustment processed erroneously as invoice.",
    )
    generated_files.append(p3)

    # 4. Duplicate invoice: exact same supplier & invoice number as invoice_001
    p4 = create_invoice_pdf(
        output_path=out_dir / "invoice_004_duplicate.pdf",
        supplier_name="Acme Industrial Supplies Ltd",
        invoice_number="INV-2024-001",  # Matches invoice_001
        invoice_date="2024-03-01",
        due_date="2024-03-31",
        currency="EUR",
        line_items=[
            ("Standard CNC Milling Components (Duplicate Copy)", 10, 85.00),
            ("High-Tensile Fasteners (Box of 500)", 4, 100.00),
        ],
        notes="Duplicate billing submission for order #9421",
    )
    generated_files.append(p4)

    # 5. Missing invoice number header
    p5 = create_invoice_pdf(
        output_path=out_dir / "invoice_005_clean.pdf",
        supplier_name="Vertex Global Advisory",
        invoice_number="INV-2024-005",
        invoice_date="2024-03-12",
        due_date="2024-04-12",
        currency="GBP",
        line_items=[
            ("Strategic Enterprise Architecture Consulting (Days)", 2, 1700.00),
        ],
        notes="Q1 Technology Roadmap assessment.",
    )
    generated_files.append(p5)

    # 6. Missing invoice number header edge case
    p6 = create_invoice_pdf(
        output_path=out_dir / "invoice_006_missing_invoice_number.pdf",
        supplier_name="Omni Hardware Supply",
        invoice_number=None,  # Missing invoice number
        invoice_date="2024-03-14",
        due_date="2024-04-14",
        currency="USD",
        line_items=[
            ("Server Rack Cooling Units", 2, 600.00),
        ],
        notes="Invoice number missing from supplier vendor template.",
    )
    generated_files.append(p6)

    # 7. Unsupported currency (JPY - not in whitelist)
    p7 = create_invoice_pdf(
        output_path=out_dir / "invoice_007_unsupported_currency.pdf",
        supplier_name="Tokyo Robotics Group",
        invoice_number="INV-2024-007",
        invoice_date="2024-03-18",
        due_date="2024-04-18",
        currency="JPY",
        line_items=[
            ("Robotic Arm Sensor Maintenance", 1, 150000.00),
        ],
        notes="Foreign currency invoice requiring manual currency conversion.",
    )
    generated_files.append(p7)

    return generated_files


if __name__ == "__main__":
    print("Generating synthetic sample PDF invoices...")
    files = generate_all_samples("sample_documents")
    print(f"Successfully generated {len(files)} sample invoices in sample_documents/:")
    for f in files:
        print(f" - {f.name}")
