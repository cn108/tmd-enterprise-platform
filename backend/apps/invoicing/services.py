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
    invoice.balance = money(invoice.total - invoice.credited_total + invoice.debited_total)
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
            "balance",
            "updated_at",
        ]
    )
    return invoice


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
    "approve_customer_invoice",
    "approve_note",
    "approve_payment",
    "approve_supplier_invoice",
    "cancel_customer_invoice",
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
    "recalculate_customer_invoice",
    "recalculate_note",
    "recalculate_supplier_invoice",
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
]
