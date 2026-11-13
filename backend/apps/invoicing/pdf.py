"""PDF previews for Stage 7A test documents.

The PDF is generated on demand; no file is persisted. A test document carries a
prominent banner and is never presented as a valid tax invoice. Company legal
details come from settings or are shown as not configured.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.invoicing.models import (
    CustomerInvoice,
    CustomerReceipt,
    InvoiceNote,
    InvoiceSettings,
    SupplierInvoice,
)
from apps.invoicing.services import customer_statement_data


def _safe(value) -> str:
    return escape(str(value or ""))


def customer_statement_pdf(receipt: CustomerReceipt, download: bool = False) -> FileResponse:
    settings = InvoiceSettings.load()
    start = date(receipt.receipt_date.year, 1, 1)
    data = customer_statement_data(receipt.customer, start, receipt.receipt_date)
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    story = _banner(settings, receipt.is_test)
    story += _header(
        settings,
        "CUSTOMER ACCOUNT STATEMENT",
        [
            ("Customer", receipt.customer.legal_name),
            ("Customer code", receipt.customer.code),
            ("Period", f"{start:%d %b %Y} to {receipt.receipt_date:%d %b %Y}"),
            ("Currency", receipt.currency),
        ],
    )
    story.append(
        _total_table(
            [
                ("Opening balance", f"{receipt.currency} {data['opening']}"),
                ("Closing balance", f"{receipt.currency} {data['closing']}"),
                ("Outstanding invoices", f"{receipt.currency} {data['outstanding']}"),
                ("Unapplied receipts", f"{receipt.currency} {data['unapplied']}"),
            ]
        )
    )
    story.append(Spacer(1, 5 * mm))
    rows = [
        [
            row["date"].strftime("%d %b %Y"),
            row["type"],
            row["reference"],
            row["detail"] or "",
            f"{row['debit']}" if row["debit"] else "",
            f"{row['credit']}" if row["credit"] else "",
            f"{row['balance']}",
        ]
        for row in data["rows"]
    ]
    if not rows:
        rows = [["", "No movements in the period", "", "", "", "", ""]]
    story.append(
        _lines_table(
            ["Date", "Type", "Reference", "Detail", "Debit", "Credit", "Balance"],
            [[_safe(cell) for cell in row] for row in rows],
            [24 * mm, 24 * mm, 25 * mm, 43 * mm, 20 * mm, 20 * mm, 24 * mm],
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(
        Paragraph(
            "This statement is generated from approved customer invoices, approved notes and "
            "recorded receipts. Unapplied receipts are credits on account. It is a test "
            "document while invoice production is disabled.",
            styles["Italic"],
        )
    )
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    document.build(story)
    return _response(
        buffer,
        f"customer-statement-{_safe(receipt.customer.code)}-{receipt.receipt_date}.pdf",
        download,
    )


def _response(buffer: BytesIO, filename: str, download: bool) -> FileResponse:
    buffer.seek(0)
    disposition = "attachment" if download else "inline"
    response = FileResponse(
        buffer,
        as_attachment=download,
        filename=filename,
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


def _company(settings: InvoiceSettings) -> list[str]:
    name = _safe(settings.company_legal_name.strip() or "TMD LIMITED")
    lines = [name]
    if settings.company_address.strip():
        lines.append(
            "<br/>".join(_safe(part) for part in settings.company_address.strip().splitlines())
        )
    if settings.company_tax_identification_number.strip():
        lines.append(f"Tax ID: {_safe(settings.company_tax_identification_number.strip())}")
    if settings.company_email.strip():
        lines.append(_safe(settings.company_email.strip()))
    if settings.company_phone.strip():
        lines.append(_safe(settings.company_phone.strip()))
    return lines


def _banner(settings: InvoiceSettings, is_test: bool) -> list:
    styles = getSampleStyleSheet()
    story = []
    if is_test:
        story.append(
            Paragraph(
                "<b>TEST DOCUMENT — NOT A TAX INVOICE</b>",
                styles["Heading2"],
            )
        )
        story.append(
            Paragraph(
                "Created in Stage 7A. It is not issued, does not create a receivable or "
                "payable, and must not be sent to a customer or tax authority.",
                styles["Italic"],
            )
        )
    else:
        story.append(Paragraph("<b>TAX INVOICE</b>", styles["Heading2"]))
    if settings.test_mode:
        story.append(
            Paragraph(
                "Invoice production is disabled. This preview is for development and UAT only.",
                styles["Italic"],
            )
        )
    story.append(Spacer(1, 6 * mm))
    return story


def _header(settings: InvoiceSettings, title: str, meta: list[tuple[str, str]]) -> list:
    styles = getSampleStyleSheet()
    company = _company(settings)
    left = [Paragraph(f"<b>{company[0]}</b>", styles["Normal"])]
    for line in company[1:]:
        left.append(Paragraph(line, styles["Normal"]))
    right = [Paragraph(f"<b>{_safe(title)}</b>", styles["Heading2"])]
    for label, value in meta:
        right.append(Paragraph(f"<b>{_safe(label)}:</b> {_safe(value)}", styles["Normal"]))
    table = Table([[left, right]], colWidths=[105 * mm, 75 * mm])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [table, Spacer(1, 6 * mm)]


def _total_table(rows: list[tuple[str, str]]) -> Table:
    table = Table([[label, value] for label, value in rows], colWidths=[135 * mm, 45 * mm])
    table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _lines_table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    table = Table([headers, *rows], colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def supplier_invoice_pdf_bytes(invoice: SupplierInvoice) -> bytes:
    settings = InvoiceSettings.load()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, title=invoice.number, pageCompression=0)
    story = _banner(settings, invoice.is_test)
    story += _header(
        settings,
        "Supplier invoice record",
        [
            ("Internal number", invoice.number),
            ("Supplier invoice", invoice.supplier_invoice_number),
            ("Invoice date", invoice.invoice_date.isoformat()),
            ("Due date", invoice.due_date.isoformat() if invoice.due_date else "—"),
            ("Status", invoice.get_status_display()),
            ("Match", invoice.get_match_status_display()),
        ],
    )
    story.append(
        Paragraph(
            f"<b>Supplier:</b> {_safe(invoice.supplier.legal_name)}",
            getSampleStyleSheet()["Normal"],
        )
    )
    if invoice.purchase_order_id:
        story.append(
            Paragraph(
                f"<b>Purchase order:</b> {_safe(invoice.purchase_order.number)}",
                getSampleStyleSheet()["Normal"],
            )
        )
    story.append(Spacer(1, 4 * mm))
    rows = []
    for line in invoice.lines.select_related("item", "vat_tax", "wht_tax"):
        rows.append(
            [
                _safe(line.description or (line.item.name if line.item_id else "—")),
                str(line.quantity),
                f"{line.unit_price}",
                f"{line.vat_amount}",
                f"{line.wht_amount}",
                f"{line.total}",
            ]
        )
    story.append(
        _lines_table(
            ["Description", "Qty", "Unit price", "VAT", "WHT", "Line total"],
            rows,
            [70 * mm, 18 * mm, 27 * mm, 20 * mm, 20 * mm, 25 * mm],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        _total_table(
            [
                ("Subtotal", f"{invoice.currency} {invoice.subtotal}"),
                ("VAT", f"{invoice.currency} {invoice.vat_total}"),
                (
                    "Recoverable input VAT",
                    f"{invoice.currency} {invoice.vat_recoverable_total}",
                ),
                ("WHT (withheld at payment)", f"{invoice.currency} {invoice.wht_total}"),
                ("Invoice total", f"{invoice.currency} {invoice.total}"),
                ("Credits / debits", f"{invoice.credited_total} / {invoice.debited_total}"),
                ("Payment due", f"{invoice.currency} {invoice.payment_due}"),
                ("Paid", f"{invoice.currency} {invoice.amount_paid}"),
                ("Balance", f"{invoice.currency} {invoice.balance}"),
            ]
        )
    )
    if invoice.notes.strip():
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(f"<b>Notes:</b> {_safe(invoice.notes)}", getSampleStyleSheet()["Normal"])
        )
    document.build(story)
    return buffer.getvalue()


def supplier_invoice_pdf(invoice: SupplierInvoice, download: bool = False) -> FileResponse:
    return _response(
        BytesIO(supplier_invoice_pdf_bytes(invoice)), f"{invoice.number}.pdf", download
    )


def customer_invoice_pdf_bytes(invoice: CustomerInvoice) -> bytes:
    settings = InvoiceSettings.load()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, title=invoice.number, pageCompression=0)
    story = _banner(settings, invoice.is_test)
    story += _header(
        settings,
        "Customer invoice draft",
        [
            ("Invoice number", invoice.number),
            ("Invoice date", invoice.invoice_date.isoformat()),
            ("Due date", invoice.due_date.isoformat() if invoice.due_date else "—"),
            ("Status", invoice.get_status_display()),
            ("Customer reference", invoice.customer_reference or "—"),
        ],
    )
    story.append(
        Paragraph(
            f"<b>Bill to:</b> {_safe(invoice.customer.legal_name)}",
            getSampleStyleSheet()["Normal"],
        )
    )
    if invoice.project_id:
        story.append(
            Paragraph(
                f"<b>Project:</b> {_safe(invoice.project.code)}",
                getSampleStyleSheet()["Normal"],
            )
        )
    story.append(Spacer(1, 4 * mm))
    rows = []
    for line in invoice.lines.select_related("item", "vat_tax"):
        rows.append(
            [
                _safe(line.description or (line.item.name if line.item_id else "—")),
                str(line.quantity),
                f"{line.unit_price}",
                f"{line.vat_amount}",
                f"{line.wht_amount}",
                f"{line.total}",
            ]
        )
    story.append(
        _lines_table(
            ["Description", "Qty", "Unit price", "VAT", "WHT", "Line total"],
            rows,
            [72 * mm, 16 * mm, 25 * mm, 20 * mm, 20 * mm, 27 * mm],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        _total_table(
            [
                ("Subtotal", f"{invoice.currency} {invoice.subtotal}"),
                ("VAT", f"{invoice.currency} {invoice.vat_total}"),
                ("Customer WHT", f"{invoice.currency} {invoice.wht_total}"),
                ("Invoice total", f"{invoice.currency} {invoice.total}"),
                ("Credits / debits", f"{invoice.credited_total} / {invoice.debited_total}"),
                ("Balance", f"{invoice.currency} {invoice.balance}"),
                ("Net receivable after WHT", f"{invoice.currency} {invoice.net_receivable}"),
            ]
        )
    )
    if invoice.notes.strip():
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(f"<b>Notes:</b> {_safe(invoice.notes)}", getSampleStyleSheet()["Normal"])
        )
    document.build(story)
    return buffer.getvalue()


def customer_invoice_pdf(invoice: CustomerInvoice, download: bool = False) -> FileResponse:
    return _response(
        BytesIO(customer_invoice_pdf_bytes(invoice)), f"{invoice.number}.pdf", download
    )


def invoice_note_pdf(note: InvoiceNote, download: bool = False) -> FileResponse:
    settings = InvoiceSettings.load()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, title=note.number, pageCompression=0)
    story = _banner(settings, note.is_test)
    story += _header(
        settings,
        f"{note.get_note_type_display()} — {note.party_name}",
        [
            ("Note number", note.number),
            ("Note date", note.note_date.isoformat()),
            ("Status", note.get_status_display()),
            ("Reason", note.reason),
        ],
    )
    rows = []
    for line in note.lines.select_related("vat_tax"):
        rows.append(
            [
                _safe(line.description),
                str(line.quantity),
                f"{line.unit_price}",
                f"{line.vat_amount}",
                f"{line.total}",
            ]
        )
    story.append(
        _lines_table(
            ["Description", "Qty", "Unit price", "VAT", "Line total"],
            rows,
            [85 * mm, 18 * mm, 28 * mm, 22 * mm, 27 * mm],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        _total_table(
            [
                ("Subtotal", f"{note.currency} {note.subtotal}"),
                ("VAT", f"{note.currency} {note.vat_total}"),
                ("Note total", f"{note.currency} {note.total}"),
            ]
        )
    )
    document.build(story)
    return _response(buffer, f"{note.number}.pdf", download)
