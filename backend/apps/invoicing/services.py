"""Invoice lifecycle, duplicate checks, matching, notes and payment allocation.

Every mutation is transactional and audited. The service layer is the authority:
serializers provide shapes, but they cannot bypass matching, approval arithmetic,
payment limits or the Stage 7B activation gate.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import AccountingSettings
from apps.core.approvals import ApprovalError, register_approval
from apps.core.models import ApprovalRecord, NumberingScheme, TaxProfile, create_audit_event
from apps.core.numbering import NumberingError, allocate_document_number
from apps.invoicing.exceptions import InvoiceConflict
from apps.invoicing.models import (
    ZERO,
    CustomerInvoice,
    CustomerReceipt,
    CustomerReceiptAllocation,
    IdempotencyRecord,
    InvoiceNote,
    InvoiceSettings,
    NrsSubmission,
    PaymentAllocation,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
    money,
    validate_invoice_tax,
)
from apps.invoicing.nrs import build_payload, get_adapter
from apps.procurement.numbering import next_number

ACTIVATION_GATES = (
    "management_roles_approved",
    "chart_and_mappings_approved",
    "opening_balances_loaded",
    "bank_and_inventory_opening_loaded",
    "vat_and_wht_reviewed",
    "numbering_and_rounding_approved",
    "company_legal_details_recorded",
    "posting_rules_approved",
    "finance_review_recorded",
    "management_go_live_authorised",
)


def _audit(actor, action: str, invoice, after=None, before=None, request=None) -> None:
    create_audit_event(
        actor=actor,
        action=action,
        entity_type=invoice._meta.label_lower,
        entity_id=invoice.pk,
        before=before or {},
        after=after or {},
        request=request,
    )


def _normalise_number(value: str) -> str:
    return "".join(character for character in (value or "").upper() if character.isalnum())


def recalculate_supplier_invoice(invoice: SupplierInvoice) -> SupplierInvoice:
    lines = list(invoice.lines.all())
    invoice.subtotal = money(sum((line.subtotal for line in lines), ZERO))
    invoice.vat_total = money(sum((line.vat_amount for line in lines), ZERO))
    invoice.vat_recoverable_total = money(
        sum((line.vat_recoverable_amount for line in lines), ZERO)
    )
    invoice.wht_total = money(sum((line.wht_amount for line in lines), ZERO))
    invoice.total = money(invoice.subtotal + invoice.vat_total)
    invoice.credited_total = money(
        sum(
            (
                note.total
                for note in invoice.invoice_notes.filter(
                    note_type=InvoiceNote.NoteType.CREDIT,
                    status=InvoiceNote.Status.APPROVED,
                )
            ),
            ZERO,
        )
    )
    invoice.debited_total = money(
        sum(
            (
                note.total
                for note in invoice.invoice_notes.filter(
                    note_type=InvoiceNote.NoteType.DEBIT,
                    status=InvoiceNote.Status.APPROVED,
                )
            ),
            ZERO,
        )
    )
    invoice.amount_paid = money(
        sum((allocation.amount for allocation in invoice.payment_allocations.all()), ZERO)
    )
    invoice.payment_due = money(
        invoice.total - invoice.wht_total - invoice.credited_total + invoice.debited_total
    )
    if invoice.payment_due < ZERO:
        raise InvoiceConflict("Approved notes exceed the invoice payable value.")
    invoice.save(
        update_fields=[
            "subtotal",
            "vat_total",
            "vat_recoverable_total",
            "wht_total",
            "total",
            "credited_total",
            "debited_total",
            "amount_paid",
            "payment_due",
            "updated_at",
        ]
    )
    return invoice


def recalculate_customer_invoice(invoice: CustomerInvoice) -> CustomerInvoice:
    lines = list(invoice.lines.all())
    invoice.subtotal = money(sum((line.subtotal for line in lines), ZERO))
    invoice.vat_total = money(sum((line.vat_amount for line in lines), ZERO))
    invoice.wht_total = money(sum((line.wht_amount for line in lines), ZERO))
    invoice.total = money(invoice.subtotal + invoice.vat_total)
    invoice.credited_total = money(
        sum(
            (
                note.total
                for note in invoice.invoice_notes.filter(
                    note_type=InvoiceNote.NoteType.CREDIT,
                    status=InvoiceNote.Status.APPROVED,
                )
            ),
            ZERO,
        )
    )
    invoice.debited_total = money(
        sum(
            (
                note.total
                for note in invoice.invoice_notes.filter(
                    note_type=InvoiceNote.NoteType.DEBIT,
                    status=InvoiceNote.Status.APPROVED,
                )
            ),
            ZERO,
        )
    )
    invoice.amount_paid = money(
        sum(
            (
                allocation.amount
                for allocation in invoice.receipt_allocations.filter(
                    is_reversed=False,
                    receipt__status__in=[
                        CustomerReceipt.Status.RECORDED,
                        CustomerReceipt.Status.SUBMITTED,
                        CustomerReceipt.Status.APPROVED,
                        CustomerReceipt.Status.POSTED,
                    ],
                )
            ),
            ZERO,
        )
    )
    invoice.balance = money(
        invoice.total
        - invoice.credited_total
        + invoice.debited_total
        - invoice.amount_paid
    )
    if invoice.balance < ZERO:
        raise InvoiceConflict("Approved notes exceed the customer invoice value.")
    invoice.save(
        update_fields=[
            "subtotal",
            "vat_total",
            "wht_total",
            "total",
            "credited_total",
            "debited_total",
            "amount_paid",
            "balance",
            "updated_at",
        ]
    )
    return invoice


def _validate_customer_receipt_allocation(
    receipt: CustomerReceipt,
    invoice: CustomerInvoice,
    amount,
    already_allocated,
) -> Decimal:
    amount = money(amount)
    if amount <= ZERO:
        raise InvoiceConflict("An allocation must be greater than zero.")
    if invoice.customer_id != receipt.customer_id:
        raise InvoiceConflict("The invoice belongs to a different customer.")
    if invoice.currency != receipt.currency:
        raise InvoiceConflict("The receipt and invoice currencies must match.")
    if invoice.status != CustomerInvoice.Status.APPROVED:
        raise InvoiceConflict("Only an approved customer invoice can receive a receipt.")
    available_receipt = money(receipt.amount - already_allocated)
    if amount > available_receipt:
        raise InvoiceConflict("The allocation exceeds the unapplied receipt amount.")
    if amount > max(invoice.balance, ZERO):
        raise InvoiceConflict("The allocation exceeds the invoice balance.")
    return amount


@transaction.atomic
def record_customer_receipt(
    *,
    customer,
    receipt_date,
    currency,
    amount,
    method,
    external_reference,
    notes,
    company_bank_account,
    allocations,
    user,
) -> CustomerReceipt:
    amount = money(amount)
    if amount <= ZERO:
        raise InvoiceConflict("A customer receipt must be greater than zero.")
    if not customer.is_customer or not customer.is_active:
        raise InvoiceConflict("Choose an active customer.")
    settings = InvoiceSettings.load()
    receipt = CustomerReceipt.objects.create(
        number=next_number("RCT"),
        customer=customer,
        receipt_date=receipt_date,
        currency=currency,
        amount=amount,
        method=method,
        external_reference=external_reference,
        notes=notes,
        company_bank_account=company_bank_account,
        is_test=not settings.can_issue,
        created_by=user,
        updated_by=user,
    )
    allocated = ZERO
    seen: set[int] = set()
    for payload in allocations:
        invoice = (
            CustomerInvoice.objects.select_for_update()
            .filter(pk=payload["invoice"].pk)
            .first()
        )
        if invoice is None:
            raise InvoiceConflict("Unknown customer invoice.")
        if invoice.pk in seen:
            raise InvoiceConflict("Each invoice may appear only once on a receipt.")
        seen.add(invoice.pk)
        value = _validate_customer_receipt_allocation(
            receipt, invoice, payload["amount"], allocated
        )
        CustomerReceiptAllocation.objects.create(
            receipt=receipt,
            invoice=invoice,
            amount=value,
            created_by=user,
            updated_by=user,
        )
        allocated = money(allocated + value)
        recalculate_customer_invoice(invoice)
    receipt.allocated_amount = allocated
    receipt.save(update_fields=["allocated_amount", "updated_at"])
    create_audit_event(
        actor=user,
        action="customer_receipt.recorded",
        entity_type="invoicing.customerreceipt",
        entity_id=receipt.pk,
        after={
            "number": receipt.number,
            "amount": str(receipt.amount),
            "allocated": str(receipt.allocated_amount),
        },
    )
    from apps.banking.services import sync_customer_receipt

    sync_customer_receipt(receipt)
    return receipt


@transaction.atomic
def allocate_customer_receipt(receipt_id, invoice, amount, user) -> CustomerReceiptAllocation:
    receipt = CustomerReceipt.objects.select_for_update().filter(pk=receipt_id).first()
    if receipt is None:
        raise InvoiceConflict("Unknown customer receipt.")
    if receipt.status != CustomerReceipt.Status.RECORDED:
        raise InvoiceConflict("A cancelled receipt cannot be allocated.")
    invoice = CustomerInvoice.objects.select_for_update().filter(pk=invoice.pk).first()
    if invoice is None:
        raise InvoiceConflict("Unknown customer invoice.")
    if CustomerReceiptAllocation.objects.filter(
        receipt=receipt, invoice=invoice, is_reversed=False
    ).exists():
        raise InvoiceConflict("This invoice already has an allocation on the receipt.")
    value = _validate_customer_receipt_allocation(
        receipt, invoice, amount, receipt.allocated_amount
    )
    allocation = CustomerReceiptAllocation.objects.create(
        receipt=receipt,
        invoice=invoice,
        amount=value,
        created_by=user,
        updated_by=user,
    )
    receipt.allocated_amount = money(receipt.allocated_amount + value)
    receipt.save(update_fields=["allocated_amount", "updated_at"])
    recalculate_customer_invoice(invoice)
    create_audit_event(
        actor=user,
        action="customer_receipt.allocated",
        entity_type="invoicing.customerreceipt",
        entity_id=receipt.pk,
        after={"invoice": invoice.number, "amount": str(value)},
    )
    return allocation


@transaction.atomic
def reverse_customer_receipt_allocation(
    allocation: CustomerReceiptAllocation, user, reason: str
) -> CustomerReceiptAllocation:
    allocation = (
        CustomerReceiptAllocation.objects.select_for_update()
        .select_related("receipt", "invoice")
        .get(pk=allocation.pk)
    )
    receipt = CustomerReceipt.objects.select_for_update().get(pk=allocation.receipt_id)
    invoice = CustomerInvoice.objects.select_for_update().get(pk=allocation.invoice_id)
    if receipt.status != CustomerReceipt.Status.RECORDED:
        raise InvoiceConflict("An allocation can be reversed only before the receipt is submitted.")
    if allocation.is_reversed:
        raise InvoiceConflict("This allocation is already reversed.")
    if not reason.strip():
        raise InvoiceConflict("A reversal reason is required.")
    allocation.is_reversed = True
    allocation.reversed_by = user
    allocation.reversed_at = timezone.now()
    allocation.reversal_reason = reason.strip()
    allocation.updated_by = user
    allocation.save(
        update_fields=[
            "is_reversed",
            "reversed_by",
            "reversed_at",
            "reversal_reason",
            "updated_by",
            "updated_at",
        ]
    )
    receipt.allocated_amount = money(
        sum(
            (
                item.amount
                for item in receipt.allocations.filter(is_reversed=False)
            ),
            ZERO,
        )
    )
    receipt.save(update_fields=["allocated_amount", "updated_at"])
    recalculate_customer_invoice(invoice)
    create_audit_event(
        actor=user,
        action="customer_receipt.allocation_reversed",
        entity_type="invoicing.customerreceipt",
        entity_id=receipt.pk,
        after={"invoice": invoice.number, "amount": str(allocation.amount), "reason": reason},
    )
    return allocation


def submit_customer_receipt(receipt: CustomerReceipt, user) -> CustomerReceipt:
    receipt = CustomerReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status != CustomerReceipt.Status.RECORDED:
        raise InvoiceConflict("Only a recorded receipt can be submitted for approval.")
    receipt.status = CustomerReceipt.Status.SUBMITTED
    receipt.submitted_at = timezone.now()
    receipt.updated_by = user
    receipt.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
    create_audit_event(
        actor=user,
        action="customer_receipt.submitted",
        entity_type="invoicing.customerreceipt",
        entity_id=receipt.pk,
        after={"status": receipt.status},
    )
    return receipt


def approve_customer_receipt(receipt: CustomerReceipt, approver, notes: str = ""):
    receipt = CustomerReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status != CustomerReceipt.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted receipt can be approved.")
    if receipt.created_by_id == approver.pk:
        raise InvoiceConflict("A receipt cannot be approved by its creator.")
    try:
        outcome = register_approval(
            document_type="customer_receipt",
            document_id=receipt.pk,
            approver=approver,
            amount=receipt.amount,
            creators={receipt.created_by_id},
            notes=notes,
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    if outcome.final:
        receipt.status = CustomerReceipt.Status.APPROVED
        receipt.approved_by = approver
        receipt.approved_at = timezone.now()
        receipt.updated_by = approver
        receipt.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "updated_by",
                "updated_at",
            ]
        )
    create_audit_event(
        actor=approver,
        action="customer_receipt.approved",
        entity_type="invoicing.customerreceipt",
        entity_id=receipt.pk,
        after={"status": receipt.status, "approvals_recorded": outcome.recorded},
    )
    return receipt


def reject_customer_receipt(receipt: CustomerReceipt, approver, reason: str) -> CustomerReceipt:
    receipt = CustomerReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status != CustomerReceipt.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted receipt can be rejected.")
    if not reason.strip():
        raise InvoiceConflict("A rejection reason is required.")
    receipt.status = CustomerReceipt.Status.REJECTED
    receipt.rejection_reason = reason.strip()
    receipt.updated_by = approver
    receipt.save(
        update_fields=["status", "rejection_reason", "updated_by", "updated_at"]
    )
    create_audit_event(
        actor=approver,
        action="customer_receipt.rejected",
        entity_type="invoicing.customerreceipt",
        entity_id=receipt.pk,
        after={"status": receipt.status, "reason": reason},
    )
    return receipt


@transaction.atomic
def cancel_customer_receipt(receipt: CustomerReceipt, user, reason: str) -> CustomerReceipt:
    receipt = CustomerReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status == CustomerReceipt.Status.CANCELLED:
        raise InvoiceConflict("This receipt is already cancelled.")
    if receipt.status not in {
        CustomerReceipt.Status.RECORDED,
        CustomerReceipt.Status.APPROVED,
        CustomerReceipt.Status.POSTED,
    }:
        raise InvoiceConflict(
            "Only a recorded, approved or posted receipt can be cancelled."
        )
    if not reason.strip():
        raise InvoiceConflict("A cancellation reason is required.")
    from apps.banking.models import BankTransaction

    bank_transaction = BankTransaction.objects.filter(
        source_type=BankTransaction.Source.CUSTOMER_RECEIPT,
        source_id=receipt.pk,
    ).first()
    if (
        bank_transaction is not None
        and bank_transaction.status == BankTransaction.Status.RECONCILED
    ):
        raise InvoiceConflict(
            "This receipt is linked to a reconciled bank transaction. "
            "Reverse the reconciliation match before cancelling the receipt."
        )
    invoice_ids = list(receipt.allocations.values_list("invoice_id", flat=True))
    reversal = None
    if receipt.status == CustomerReceipt.Status.POSTED:
        if receipt.journal_entry_id is None:
            raise InvoiceConflict(
                "The receipt is marked posted but has no journal. Inspect it before cancelling."
            )
        from apps.accounting.services import Conflict as AccountingConflict
        from apps.accounting.services import reverse_journal
        from apps.invoicing.posting import _period_for_date

        today = timezone.localdate()
        try:
            reversal = reverse_journal(
                receipt.journal_entry,
                user,
                reason.strip(),
                period=_period_for_date(today, "receipt reversal"),
                journal_date=today,
            )
        except AccountingConflict as exc:
            raise InvoiceConflict(str(exc)) from exc
    receipt.status = CustomerReceipt.Status.CANCELLED
    receipt.reversal_entry = reversal
    receipt.cancelled_at = timezone.now()
    receipt.cancel_reason = reason
    receipt.updated_by = user
    receipt.save(
        update_fields=[
            "status",
            "reversal_entry",
            "cancelled_at",
            "cancel_reason",
            "updated_by",
            "updated_at",
        ]
    )
    for invoice in CustomerInvoice.objects.select_for_update().filter(pk__in=invoice_ids):
        recalculate_customer_invoice(invoice)
    create_audit_event(
        actor=user,
        action="customer_receipt.cancelled",
        entity_type="invoicing.customerreceipt",
        entity_id=receipt.pk,
        after={"number": receipt.number, "reason": reason},
    )
    from apps.banking.services import sync_customer_receipt

    sync_customer_receipt(receipt)
    return receipt


def customer_statement_data(customer, start: date, end: date) -> dict:
    """Customer ledger presentation built from approved invoices, notes and receipts."""
    if start > end:
        raise InvoiceConflict("The statement start date must be before the end date.")
    entries: list[dict] = []
    invoices = CustomerInvoice.objects.filter(
        customer=customer,
        status=CustomerInvoice.Status.APPROVED,
        invoice_date__lte=end,
    )
    for invoice in invoices:
        entries.append(
            {
                "date": invoice.invoice_date,
                "type": "Invoice",
                "reference": invoice.number,
                "debit": invoice.total,
                "credit": ZERO,
                "detail": invoice.customer_reference,
            }
        )
    notes = InvoiceNote.objects.filter(
        customer_invoice__customer=customer,
        status=InvoiceNote.Status.APPROVED,
        note_date__lte=end,
    )
    for note in notes:
        is_credit = note.note_type == InvoiceNote.NoteType.CREDIT
        entries.append(
            {
                "date": note.note_date,
                "type": "Credit note" if is_credit else "Debit note",
                "reference": note.number,
                "debit": ZERO if is_credit else note.total,
                "credit": note.total if is_credit else ZERO,
                "detail": note.reason,
            }
        )
    receipts = CustomerReceipt.objects.filter(
        customer=customer,
        status__in=[
            CustomerReceipt.Status.RECORDED,
            CustomerReceipt.Status.SUBMITTED,
            CustomerReceipt.Status.APPROVED,
            CustomerReceipt.Status.POSTED,
        ],
        receipt_date__lte=end,
    )
    for receipt in receipts:
        entries.append(
            {
                "date": receipt.receipt_date,
                "type": "Receipt",
                "reference": receipt.number,
                "debit": ZERO,
                "credit": receipt.amount,
                "detail": receipt.external_reference,
            }
        )
    entries.sort(key=lambda item: (item["date"], item["reference"]))
    opening = ZERO
    rows = []
    running = ZERO
    for entry in entries:
        if entry["date"] < start:
            opening = money(opening + entry["debit"] - entry["credit"])
            continue
        running = money(running + entry["debit"] - entry["credit"])
        rows.append({**entry, "balance": money(opening + running)})
    outstanding = sum(
        (
            invoice.balance
            for invoice in invoices
            if invoice.balance > ZERO
        ),
        ZERO,
    )
    return {
        "customer": customer,
        "start": start,
        "end": end,
        "opening": money(opening),
        "rows": rows,
        "closing": money(opening + running),
        "outstanding": money(outstanding),
        "unapplied": money(
            sum(
                (receipt.unallocated_amount for receipt in receipts),
                ZERO,
            )
        ),
    }


def recalculate_note(note: InvoiceNote) -> InvoiceNote:
    lines = list(note.lines.all())
    note.subtotal = money(sum((line.subtotal for line in lines), ZERO))
    note.vat_total = money(sum((line.vat_amount for line in lines), ZERO))
    note.total = money(note.subtotal + note.vat_total)
    note.save(update_fields=["subtotal", "vat_total", "total", "updated_at"])
    return note


def validate_line_tax_dates(invoice) -> None:
    """Re-check effective tax dates at submission, not only at entry."""

    tax_date = (
        getattr(invoice, "tax_point_date", None)
        or getattr(invoice, "invoice_date", None)
        or getattr(invoice, "note_date", None)
    )
    for line in invoice.lines.select_related("vat_tax"):
        try:
            validate_invoice_tax(line.vat_tax, "vat", tax_date)
            if hasattr(line, "wht_tax"):
                validate_invoice_tax(line.wht_tax, "wht", tax_date)
        except ValidationError as exc:
            raise InvoiceConflict(
                str(exc.message_dict.get("tax", ["Invalid tax date."])[0])
            ) from exc


def duplicate_candidates(
    *,
    supplier,
    supplier_invoice_number: str,
    total,
    invoice_date: date,
    exclude_id: int | None = None,
    window_days: int | None = None,
) -> list[SupplierInvoice]:
    settings = InvoiceSettings.load()
    window = settings.duplicate_window_days if window_days is None else window_days
    queryset = SupplierInvoice.objects.filter(supplier=supplier).exclude(pk=exclude_id)
    normalised = _normalise_number(supplier_invoice_number)
    exact = queryset.filter(supplier_invoice_number_normalized=normalised)
    nearest = queryset.filter(
        total=total,
        invoice_date__gte=invoice_date - timedelta(days=window),
        invoice_date__lte=invoice_date + timedelta(days=window),
    )
    return list((exact | nearest).distinct().order_by("invoice_date", "id"))


def exact_duplicate(
    *, supplier, supplier_invoice_number: str, exclude_id: int | None = None
) -> SupplierInvoice | None:
    return (
        SupplierInvoice.objects.filter(
            supplier=supplier,
            supplier_invoice_number_normalized=_normalise_number(supplier_invoice_number),
        )
        .exclude(pk=exclude_id)
        .first()
    )


def mark_duplicate_risk(invoice: SupplierInvoice) -> SupplierInvoice:
    candidates = duplicate_candidates(
        supplier=invoice.supplier,
        supplier_invoice_number=invoice.supplier_invoice_number,
        total=invoice.total,
        invoice_date=invoice.invoice_date,
        exclude_id=invoice.pk,
    )
    exact = exact_duplicate(
        supplier=invoice.supplier,
        supplier_invoice_number=invoice.supplier_invoice_number,
        exclude_id=invoice.pk,
    )
    invoice.duplicate_status = (
        SupplierInvoice.DuplicateStatus.CONFIRMED
        if exact
        else (
            SupplierInvoice.DuplicateStatus.SUSPECTED
            if candidates
            else SupplierInvoice.DuplicateStatus.CLEAR
        )
    )
    invoice.duplicate_of = exact or (candidates[0] if candidates else None)
    invoice.save(update_fields=["duplicate_status", "duplicate_of", "updated_at"])
    return invoice


def evaluate_supplier_match(invoice: SupplierInvoice) -> tuple[str, list[str]]:
    settings = InvoiceSettings.load()
    exceptions: list[str] = []
    if invoice.purchase_order_id is None:
        if invoice.match_exempt_reason.strip():
            return SupplierInvoice.MatchStatus.EXEMPT, []
        return (
            SupplierInvoice.MatchStatus.EXCEPTION,
            ["No purchase order is linked; record an exemption reason or link the order."],
        )
    order = invoice.purchase_order
    if order.supplier_id != invoice.supplier_id:
        exceptions.append("The purchase order belongs to a different supplier.")
    if order.status not in {
        order.Status.APPROVED,
        order.Status.ISSUED,
        order.Status.PARTIALLY_RECEIVED,
        order.Status.RECEIVED,
        order.Status.CLOSED,
    }:
        exceptions.append("The purchase order has not been approved.")
    for line in invoice.lines.select_related(
        "order_line", "receipt_line", "receipt_line__schedule", "item"
    ):
        if line.order_line_id is None:
            exceptions.append(f"Line {line.pk} is not linked to a purchase-order line.")
            continue
        if line.order_line.order_id != order.pk:
            exceptions.append(f"Line {line.pk} belongs to another order.")
            continue
        if line.receipt_line_id is None:
            if line.item_id and line.item.kind == "service":
                continue
            exceptions.append(f"Line {line.pk} has no accepted goods receipt.")
            continue
        if line.receipt_line.order_line_id != line.order_line_id:
            exceptions.append(f"Line {line.pk} receipt does not match its order line.")
            continue
        already = (
            SupplierInvoiceLine.objects.filter(
                receipt_line=line.receipt_line,
                invoice__status__in=[
                    SupplierInvoice.Status.SUBMITTED,
                    SupplierInvoice.Status.APPROVED,
                ],
            )
            .exclude(invoice=invoice)
            .aggregate(total=Sum("quantity"))
            .get("total")
            or ZERO
        )
        accepted = line.receipt_line.quantity_accepted
        allowed = accepted * (
            Decimal("1") + Decimal(settings.quantity_tolerance_percent) / Decimal("100")
        )
        if already + line.quantity > allowed:
            exceptions.append(
                f"Line {line.pk} exceeds accepted quantity: "
                f"{already + line.quantity} invoiced against {accepted} accepted."
            )
        price_allowed = line.order_line.unit_price * (
            Decimal("1") + Decimal(settings.price_tolerance_percent) / Decimal("100")
        )
        if line.unit_price > price_allowed:
            exceptions.append(f"Line {line.pk} unit price exceeds the order price tolerance.")
    return (
        (SupplierInvoice.MatchStatus.MATCHED, [])
        if not exceptions
        else (SupplierInvoice.MatchStatus.EXCEPTION, exceptions)
    )


def submit_supplier_invoice(invoice: SupplierInvoice, actor) -> SupplierInvoice:
    if invoice.status != SupplierInvoice.Status.DRAFT:
        raise InvoiceConflict("Only a draft supplier invoice can be submitted.")
    if not invoice.lines.exists():
        raise InvoiceConflict("A supplier invoice needs at least one line.")
    validate_line_tax_dates(invoice)
    recalculate_supplier_invoice(invoice)
    duplicate = exact_duplicate(
        supplier=invoice.supplier,
        supplier_invoice_number=invoice.supplier_invoice_number,
        exclude_id=invoice.pk,
    )
    if duplicate is not None:
        invoice.duplicate_status = SupplierInvoice.DuplicateStatus.CONFIRMED
        invoice.duplicate_of = duplicate
        invoice.save(update_fields=["duplicate_status", "duplicate_of", "updated_at"])
        raise InvoiceConflict(
            f"Duplicate invoice: {duplicate.supplier_invoice_number} is already recorded "
            f"as {duplicate.number}."
        )
    mark_duplicate_risk(invoice)
    if invoice.duplicate_status == SupplierInvoice.DuplicateStatus.SUSPECTED:
        if not invoice.duplicate_override_reason.strip():
            raise InvoiceConflict(
                "A possible duplicate was found. Record an override reason before submitting."
            )
    settings = InvoiceSettings.load()
    match_status, exceptions = evaluate_supplier_match(invoice)
    invoice.match_status = match_status
    invoice.match_exceptions = exceptions
    if settings.require_supplier_match and match_status == SupplierInvoice.MatchStatus.EXCEPTION:
        invoice.save(update_fields=["match_status", "match_exceptions", "updated_at"])
        raise InvoiceConflict("Invoice matching failed: " + " ".join(exceptions))
    invoice.status = SupplierInvoice.Status.SUBMITTED
    invoice.submitted_at = timezone.now()
    invoice.save(
        update_fields=[
            "status",
            "submitted_at",
            "match_status",
            "match_exceptions",
            "duplicate_status",
            "duplicate_of",
            "updated_at",
        ]
    )
    _audit(actor, "supplier_invoice.submitted", invoice, after={"status": invoice.status})
    return invoice


def approve_supplier_invoice(
    invoice: SupplierInvoice, approver, notes: str = ""
) -> SupplierInvoice:
    if invoice.status != SupplierInvoice.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted supplier invoice can be approved.")
    if invoice.created_by_id == approver.pk:
        raise InvoiceConflict("A supplier invoice cannot be approved by its creator.")
    try:
        outcome = register_approval(
            document_type="supplier_invoice",
            document_id=invoice.pk,
            approver=approver,
            amount=invoice.total,
            creators={invoice.created_by_id},
            notes=notes,
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    if not outcome.final:
        return invoice
    invoice.status = SupplierInvoice.Status.APPROVED
    invoice.approved_by = approver
    invoice.approved_at = timezone.now()
    invoice.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    _audit(approver, "supplier_invoice.approved", invoice, after={"status": invoice.status})
    return invoice


def reject_supplier_invoice(invoice: SupplierInvoice, approver, reason: str) -> SupplierInvoice:
    if invoice.status != SupplierInvoice.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted supplier invoice can be rejected.")
    if invoice.created_by_id == approver.pk:
        raise InvoiceConflict("A supplier invoice cannot be rejected by its creator.")
    if not reason.strip():
        raise InvoiceConflict("A rejection reason is required.")
    try:
        register_approval(
            document_type="supplier_invoice",
            document_id=invoice.pk,
            approver=approver,
            amount=invoice.total,
            creators={invoice.created_by_id},
            decision=ApprovalRecord.Decision.REJECTED,
            notes=reason.strip(),
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    invoice.status = SupplierInvoice.Status.REJECTED
    invoice.rejection_reason = reason.strip()
    invoice.save(update_fields=["status", "rejection_reason", "updated_at"])
    _audit(approver, "supplier_invoice.rejected", invoice, after={"status": invoice.status})
    return invoice


def cancel_supplier_invoice(invoice: SupplierInvoice, actor, reason: str) -> SupplierInvoice:
    if invoice.status == SupplierInvoice.Status.CANCELLED:
        raise InvoiceConflict("This supplier invoice is already cancelled.")
    if not reason.strip():
        raise InvoiceConflict("A cancellation reason is required.")
    if invoice.status == SupplierInvoice.Status.APPROVED and invoice.amount_paid > ZERO:
        raise InvoiceConflict("An invoice with payment allocations cannot be cancelled.")
    before = {"status": invoice.status}
    invoice.status = SupplierInvoice.Status.CANCELLED
    invoice.cancelled_at = timezone.now()
    invoice.cancel_reason = reason.strip()
    invoice.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    _audit(
        actor,
        "supplier_invoice.cancelled",
        invoice,
        before=before,
        after={"status": invoice.status},
    )
    return invoice


def submit_customer_invoice(invoice: CustomerInvoice, actor) -> CustomerInvoice:
    if invoice.status != CustomerInvoice.Status.DRAFT:
        raise InvoiceConflict("Only a draft customer invoice can be submitted.")
    if not invoice.lines.exists():
        raise InvoiceConflict("A customer invoice needs at least one line.")
    validate_line_tax_dates(invoice)
    recalculate_customer_invoice(invoice)
    invoice.status = CustomerInvoice.Status.SUBMITTED
    invoice.submitted_at = timezone.now()
    invoice.save(update_fields=["status", "submitted_at", "updated_at"])
    _audit(actor, "customer_invoice.submitted", invoice, after={"status": invoice.status})
    return invoice


def approve_customer_invoice(
    invoice: CustomerInvoice, approver, notes: str = ""
) -> CustomerInvoice:
    if invoice.status != CustomerInvoice.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted customer invoice can be approved.")
    if invoice.created_by_id == approver.pk:
        raise InvoiceConflict("A customer invoice cannot be approved by its creator.")
    try:
        outcome = register_approval(
            document_type="customer_invoice",
            document_id=invoice.pk,
            approver=approver,
            amount=invoice.total,
            creators={invoice.created_by_id},
            notes=notes,
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    if not outcome.final:
        return invoice
    invoice.status = CustomerInvoice.Status.APPROVED
    invoice.approved_by = approver
    invoice.approved_at = timezone.now()
    invoice.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    _audit(approver, "customer_invoice.approved", invoice, after={"status": invoice.status})
    return invoice


def reject_customer_invoice(invoice: CustomerInvoice, approver, reason: str) -> CustomerInvoice:
    if invoice.status != CustomerInvoice.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted customer invoice can be rejected.")
    if invoice.created_by_id == approver.pk:
        raise InvoiceConflict("A customer invoice cannot be rejected by its creator.")
    if not reason.strip():
        raise InvoiceConflict("A rejection reason is required.")
    try:
        register_approval(
            document_type="customer_invoice",
            document_id=invoice.pk,
            approver=approver,
            amount=invoice.total,
            creators={invoice.created_by_id},
            decision=ApprovalRecord.Decision.REJECTED,
            notes=reason.strip(),
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    invoice.status = CustomerInvoice.Status.REJECTED
    invoice.rejection_reason = reason.strip()
    invoice.save(update_fields=["status", "rejection_reason", "updated_at"])
    _audit(approver, "customer_invoice.rejected", invoice, after={"status": invoice.status})
    return invoice


def cancel_customer_invoice(invoice: CustomerInvoice, actor, reason: str) -> CustomerInvoice:
    if invoice.status == CustomerInvoice.Status.CANCELLED:
        raise InvoiceConflict("This customer invoice is already cancelled.")
    if not reason.strip():
        raise InvoiceConflict("A cancellation reason is required.")
    if invoice.receipt_allocations.filter(is_reversed=False).exclude(
        receipt__status=CustomerReceipt.Status.CANCELLED
    ).exists():
        raise InvoiceConflict(
            "This invoice has active receipt allocations. Reverse them before "
            "cancelling the invoice so receipt and invoice balances stay consistent."
        )
    before = {"status": invoice.status}
    invoice.status = CustomerInvoice.Status.CANCELLED
    invoice.cancelled_at = timezone.now()
    invoice.cancel_reason = reason.strip()
    invoice.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    _audit(
        actor,
        "customer_invoice.cancelled",
        invoice,
        before=before,
        after={"status": invoice.status},
    )
    return invoice


def submit_note(note: InvoiceNote, actor) -> InvoiceNote:
    if note.status != InvoiceNote.Status.DRAFT:
        raise InvoiceConflict("Only a draft note can be submitted.")
    if not note.lines.exists():
        raise InvoiceConflict("A credit or debit note needs at least one line.")
    validate_line_tax_dates(note)
    recalculate_note(note)
    note.status = InvoiceNote.Status.SUBMITTED
    note.submitted_at = timezone.now()
    note.save(update_fields=["status", "submitted_at", "updated_at"])
    _audit(actor, "invoice_note.submitted", note, after={"status": note.status})
    return note


def _invoice_for_note(note: InvoiceNote):
    return note.supplier_invoice or note.customer_invoice


def approve_note(note: InvoiceNote, approver, notes: str = "") -> InvoiceNote:
    if note.status != InvoiceNote.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted note can be approved.")
    if note.created_by_id == approver.pk:
        raise InvoiceConflict("A credit or debit note cannot be approved by its creator.")
    invoice = _invoice_for_note(note)
    if invoice is None:
        raise InvoiceConflict("The note has no linked invoice.")
    if invoice.status != invoice.Status.APPROVED:
        raise InvoiceConflict("The linked invoice must be approved before its note.")
    if note.note_type == InvoiceNote.NoteType.CREDIT:
        remaining = invoice.total - invoice.credited_total + invoice.debited_total
        if note.total > remaining:
            raise InvoiceConflict("The credit note exceeds the remaining invoice value.")
    try:
        outcome = register_approval(
            document_type="invoice_note",
            document_id=note.pk,
            approver=approver,
            amount=note.total,
            creators={note.created_by_id},
            notes=notes,
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    if not outcome.final:
        return note
    note.status = InvoiceNote.Status.APPROVED
    note.approved_by = approver
    note.approved_at = timezone.now()
    note.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    if isinstance(invoice, SupplierInvoice):
        recalculate_supplier_invoice(invoice)
    else:
        recalculate_customer_invoice(invoice)
    _audit(approver, "invoice_note.approved", note, after={"status": note.status})
    return note


def reject_note(note: InvoiceNote, approver, reason: str) -> InvoiceNote:
    if note.status != InvoiceNote.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted note can be rejected.")
    if note.created_by_id == approver.pk:
        raise InvoiceConflict("A note cannot be rejected by its creator.")
    if not reason.strip():
        raise InvoiceConflict("A rejection reason is required.")
    try:
        register_approval(
            document_type="invoice_note",
            document_id=note.pk,
            approver=approver,
            amount=note.total,
            creators={note.created_by_id},
            decision=ApprovalRecord.Decision.REJECTED,
            notes=reason.strip(),
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    note.status = InvoiceNote.Status.REJECTED
    note.rejection_reason = reason.strip()
    note.save(update_fields=["status", "rejection_reason", "updated_at"])
    _audit(approver, "invoice_note.rejected", note, after={"status": note.status})
    return note


def cancel_note(note: InvoiceNote, actor, reason: str) -> InvoiceNote:
    if note.status == InvoiceNote.Status.CANCELLED:
        raise InvoiceConflict("This note is already cancelled.")
    if note.status == InvoiceNote.Status.APPROVED:
        raise InvoiceConflict("An approved note is corrected by another note, not cancelled.")
    if not reason.strip():
        raise InvoiceConflict("A cancellation reason is required.")
    before = {"status": note.status}
    note.status = InvoiceNote.Status.CANCELLED
    note.cancelled_at = timezone.now()
    note.cancel_reason = reason.strip()
    note.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    _audit(actor, "invoice_note.cancelled", note, before=before, after={"status": note.status})
    return note


def submit_payment(payment: SupplierPayment, actor) -> SupplierPayment:
    if payment.status != SupplierPayment.Status.DRAFT:
        raise InvoiceConflict("Only a draft payment can be submitted.")
    if payment.amount <= ZERO:
        raise InvoiceConflict("A payment amount must be greater than zero.")
    payment.status = SupplierPayment.Status.SUBMITTED
    payment.submitted_at = timezone.now()
    payment.save(update_fields=["status", "submitted_at", "updated_at"])
    _audit(actor, "supplier_payment.submitted", payment, after={"status": payment.status})
    return payment


def approve_payment(payment: SupplierPayment, approver, notes: str = "") -> SupplierPayment:
    if payment.status != SupplierPayment.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted payment can be approved.")
    if payment.created_by_id == approver.pk:
        raise InvoiceConflict("A payment cannot be approved by its creator.")
    try:
        outcome = register_approval(
            document_type="payment",
            document_id=payment.pk,
            approver=approver,
            amount=payment.amount,
            creators={payment.created_by_id},
            notes=notes,
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    if not outcome.final:
        return payment
    payment.status = SupplierPayment.Status.APPROVED
    payment.approved_by = approver
    payment.approved_at = timezone.now()
    payment.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    _audit(approver, "supplier_payment.approved", payment, after={"status": payment.status})
    return payment


def reject_payment(payment: SupplierPayment, approver, reason: str) -> SupplierPayment:
    if payment.status != SupplierPayment.Status.SUBMITTED:
        raise InvoiceConflict("Only a submitted payment can be rejected.")
    if payment.created_by_id == approver.pk:
        raise InvoiceConflict("A payment cannot be rejected by its creator.")
    if not reason.strip():
        raise InvoiceConflict("A rejection reason is required.")
    try:
        register_approval(
            document_type="payment",
            document_id=payment.pk,
            approver=approver,
            amount=payment.amount,
            creators={payment.created_by_id},
            decision=ApprovalRecord.Decision.REJECTED,
            notes=reason.strip(),
            actor=approver,
        )
    except ApprovalError as exc:
        raise InvoiceConflict(str(exc)) from exc
    payment.status = SupplierPayment.Status.REJECTED
    payment.rejection_reason = reason.strip()
    payment.save(update_fields=["status", "rejection_reason", "updated_at"])
    _audit(approver, "supplier_payment.rejected", payment, after={"status": payment.status})
    return payment


def _response_for_payment(payment: SupplierPayment) -> dict:
    return {
        "id": payment.pk,
        "number": payment.number,
        "status": payment.status,
        "execution_status": payment.execution_status,
    }


@transaction.atomic
def record_payment(
    payment: SupplierPayment, actor, idempotency_key: str = ""
) -> tuple[SupplierPayment, bool]:
    """Record an externally executed payment; never execute a bank transfer."""

    locked = SupplierPayment.objects.select_for_update().get(pk=payment.pk)
    if idempotency_key:
        existing = (
            IdempotencyRecord.objects.select_for_update()
            .filter(scope=f"supplier_payment.record:{payment.pk}", key=idempotency_key)
            .first()
        )
        if existing is not None:
            return locked, True
    if locked.status != SupplierPayment.Status.APPROVED:
        raise InvoiceConflict("Only an approved payment can be recorded.")
    locked.status = SupplierPayment.Status.RECORDED
    locked.execution_status = SupplierPayment.ExecutionStatus.RECORDED
    locked.recorded_by = actor
    locked.recorded_at = timezone.now()
    locked.save(
        update_fields=[
            "status",
            "execution_status",
            "recorded_by",
            "recorded_at",
            "updated_at",
        ]
    )
    if idempotency_key:
        IdempotencyRecord.objects.create(
            scope=f"supplier_payment.record:{payment.pk}",
            key=idempotency_key,
            response=_response_for_payment(locked),
        )
    # A recorded payment is an expectation in the banking workspace, not proof
    # that the bank has cleared it. Matching remains a separate control step.
    from apps.banking.services import sync_supplier_payment

    sync_supplier_payment(locked)
    _audit(actor, "supplier_payment.recorded", locked, after={"status": locked.status})
    return locked, False


@transaction.atomic
def allocate_payment(
    payment: SupplierPayment, invoice: SupplierInvoice, amount, actor
) -> PaymentAllocation:
    payment = SupplierPayment.objects.select_for_update().get(pk=payment.pk)
    invoice = SupplierInvoice.objects.select_for_update().get(pk=invoice.pk)
    if payment.status != SupplierPayment.Status.RECORDED:
        raise InvoiceConflict("A payment must be recorded before it is allocated.")
    if invoice.status != SupplierInvoice.Status.APPROVED:
        raise InvoiceConflict("Only an approved supplier invoice can receive a payment.")
    if payment.supplier_id != invoice.supplier_id:
        raise InvoiceConflict("The payment and invoice belong to different suppliers.")
    if payment.currency != invoice.currency:
        raise InvoiceConflict("The payment and invoice currencies differ.")
    value = money(amount)
    if value <= ZERO:
        raise InvoiceConflict("An allocation amount must be greater than zero.")
    existing = PaymentAllocation.objects.filter(payment=payment, supplier_invoice=invoice).first()
    previous = existing.amount if existing else ZERO
    other_allocations = (
        PaymentAllocation.objects.filter(payment=payment)
        .exclude(pk=existing.pk if existing else None)
        .aggregate(total=Sum("amount"))
        .get("total")
        or ZERO
    )
    if other_allocations + value > payment.amount:
        raise InvoiceConflict("The allocation exceeds the unallocated payment amount.")
    invoice_other = (
        PaymentAllocation.objects.filter(supplier_invoice=invoice)
        .exclude(pk=existing.pk if existing else None)
        .aggregate(total=Sum("amount"))
        .get("total")
        or ZERO
    )
    if invoice_other + value > invoice.payment_due:
        raise InvoiceConflict("The allocation exceeds the invoice balance.")
    if existing:
        existing.amount = value
        existing.updated_by = actor
        existing.save(update_fields=["amount", "updated_by", "updated_at"])
        allocation = existing
    else:
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            supplier_invoice=invoice,
            amount=value,
            created_by=payment.created_by,
            updated_by=actor,
        )
    payment.allocated_amount = money(
        sum(
            (allocation.amount for allocation in PaymentAllocation.objects.filter(payment=payment)),
            ZERO,
        )
    )
    payment.save(update_fields=["allocated_amount", "updated_at"])
    recalculate_supplier_invoice(invoice)
    _audit(
        actor,
        "supplier_payment.allocated",
        payment,
        after={"invoice": invoice.pk, "amount": str(value), "previous": str(previous)},
    )
    return allocation


def cancel_payment(payment: SupplierPayment, actor, reason: str) -> SupplierPayment:
    if payment.status in {SupplierPayment.Status.CANCELLED}:
        raise InvoiceConflict("This payment is already cancelled.")
    if payment.allocations.exists():
        raise InvoiceConflict("Remove payment allocations before cancelling.")
    if not reason.strip():
        raise InvoiceConflict("A cancellation reason is required.")
    before = {"status": payment.status}
    payment.status = SupplierPayment.Status.CANCELLED
    payment.execution_status = SupplierPayment.ExecutionStatus.CANCELLED
    payment.cancelled_at = timezone.now()
    payment.cancel_reason = reason.strip()
    payment.save(
        update_fields=[
            "status",
            "execution_status",
            "cancelled_at",
            "cancel_reason",
            "updated_at",
        ]
    )
    _audit(
        actor,
        "supplier_payment.cancelled",
        payment,
        before=before,
        after={"status": payment.status},
    )
    return payment


def post_invoice(invoice, actor, idempotency_key: str = ""):
    """Post an approved invoice to the ledger through the activation gate."""

    from apps.invoicing.posting import post_invoice as post

    return post(invoice, actor, idempotency_key)


def post_supplier_payment(payment, actor, idempotency_key: str = ""):
    """Post a recorded supplier payment through the same activation gate."""

    from apps.invoicing.posting import post_supplier_payment as post

    return post(payment, actor, idempotency_key)


def post_customer_receipt(receipt, actor, idempotency_key: str = ""):
    """Post an approved customer receipt through the same activation gate."""

    from apps.invoicing.posting import post_customer_receipt as post

    return post(receipt, actor, idempotency_key)


def activation_blockers(settings: InvoiceSettings, checklist: dict) -> list[str]:
    blockers = [
        gate.replace("_", " ") for gate in ACTIVATION_GATES if not bool(checklist.get(gate))
    ]
    accounting = AccountingSettings.objects.filter(pk=1).first()
    if accounting is None or accounting.posting_reviewed_at is None:
        blockers.append("finance controller posting review")
    if not settings.company_legal_name.strip():
        blockers.append("company legal name")
    if not settings.company_tax_identification_number.strip():
        blockers.append("company tax identification number")
    scheme = NumberingScheme.objects.filter(
        document_type="customer_invoice", is_active=True
    ).first()
    if scheme is None or scheme.review_status != "reviewed":
        blockers.append("approved customer-invoice numbering scheme")
    profile = TaxProfile.objects.order_by("id").first()
    if profile is None or profile.review_status != "reviewed":
        blockers.append("reviewed tax profile")
    if settings.nrs_enabled and not settings.nrs_environment.strip():
        blockers.append("NRS environment")
    return blockers


@transaction.atomic
def activate_invoices(settings: InvoiceSettings, actor, checklist: dict, notes: str):
    if not notes.strip():
        raise InvoiceConflict("Record the activation rationale.")
    blockers = activation_blockers(settings, checklist)
    if blockers:
        raise InvoiceConflict("Activation is blocked: " + ", ".join(blockers) + ".")
    settings.activation_checklist = checklist
    settings.activation_notes = notes.strip()
    settings.test_mode = False
    settings.activated_at = timezone.now()
    settings.activated_by = actor
    settings.updated_by = actor
    settings.save()
    _audit(actor, "invoice_settings.activated", settings, after={"test_mode": False})
    return settings


def nrs_payload(invoice: CustomerInvoice) -> dict:
    return build_payload(invoice)


@transaction.atomic
def submit_to_nrs(invoice: CustomerInvoice, actor) -> NrsSubmission:
    settings = InvoiceSettings.load()
    submission, _ = NrsSubmission.objects.get_or_create(
        customer_invoice=invoice,
        defaults={"is_test": invoice.is_test},
    )
    submission.request_payload = nrs_payload(invoice)
    submission.environment = settings.nrs_environment
    submission.attempts += 1
    result = get_adapter(settings).submit(invoice)
    if result.status == "disabled":
        submission.status = NrsSubmission.Status.DISABLED
        submission.error = result.message
        submission.save()
        return submission
    if not invoice.is_test and not settings.can_issue:
        submission.status = NrsSubmission.Status.FAILED
        submission.error = "Production invoice issuance is not activated."
        submission.save()
        return submission
    submission.status = NrsSubmission.Status.QUEUED
    submission.error = result.message
    submission.response_payload = result.response
    submission.save()
    _audit(actor, "customer_invoice.nrs_queued", invoice, after={"status": submission.status})
    return submission


def next_invoice_number(document_type: str) -> str:
    try:
        return allocate_document_number(document_type)
    except NumberingError as exc:
        raise InvoiceConflict(str(exc)) from exc


def next_note_number(note_type: str) -> str:
    return next_number("CN" if note_type == InvoiceNote.NoteType.CREDIT else "DN")


def next_supplier_invoice_number() -> str:
    return next_number("SI")


def next_payment_number() -> str:
    return next_number("PAY")


def safe_create(callback):
    try:
        return callback()
    except IntegrityError as exc:
        raise InvoiceConflict("That record already exists.") from exc


def ensure_line_tax(tax, expected: str) -> None:
    validate_invoice_tax(tax, expected)


# Kept as a named export for tests and callers that need the calculation.
def line_total(quantity, unit_price) -> Decimal:
    return money(Decimal(quantity) * Decimal(unit_price))


# Re-export for serializer convenience without importing models directly.
__all__ = [
    "ACTIVATION_GATES",
    "InvoiceConflict",
    "activate_invoices",
    "activation_blockers",
    "allocate_payment",
    "allocate_customer_receipt",
    "reverse_customer_receipt_allocation",
    "submit_customer_receipt",
    "approve_customer_receipt",
    "reject_customer_receipt",
    "approve_customer_invoice",
    "approve_note",
    "approve_payment",
    "approve_supplier_invoice",
    "cancel_customer_invoice",
    "cancel_customer_receipt",
    "cancel_note",
    "cancel_payment",
    "cancel_supplier_invoice",
    "duplicate_candidates",
    "evaluate_supplier_match",
    "exact_duplicate",
    "mark_duplicate_risk",
    "next_invoice_number",
    "next_note_number",
    "next_payment_number",
    "next_supplier_invoice_number",
    "post_invoice",
    "post_supplier_payment",
    "post_customer_receipt",
    "recalculate_customer_invoice",
    "recalculate_note",
    "recalculate_supplier_invoice",
    "record_customer_receipt",
    "record_payment",
    "reject_customer_invoice",
    "reject_note",
    "reject_payment",
    "reject_supplier_invoice",
    "submit_customer_invoice",
    "submit_note",
    "submit_payment",
    "submit_supplier_invoice",
    "submit_to_nrs",
    "customer_statement_data",
]
