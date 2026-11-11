"""State transitions and receipt arithmetic for procurement.

Views handle permissions; this module handles the rules that must hold no matter
who calls it, so they cannot be bypassed by a different endpoint later.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.procurement.models import (
    ZERO,
    DeliverySchedule,
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseRequest,
    RequestForQuotation,
    SupplierQuote,
)

from .numbering import next_number


class StateConflict(Exception):
    """A request is valid but the record is not in a state that allows it."""


def submit_request(request: PurchaseRequest) -> PurchaseRequest:
    if request.status != PurchaseRequest.Status.DRAFT:
        raise StateConflict("Only a draft request can be submitted.")
    if not request.lines.exists():
        raise StateConflict("A request needs at least one line before it is submitted.")
    request.status = PurchaseRequest.Status.SUBMITTED
    request.submitted_at = timezone.now()
    request.save(update_fields=["status", "submitted_at", "updated_at"])
    return request


def approve_request(request: PurchaseRequest, approver) -> PurchaseRequest:
    if request.status != PurchaseRequest.Status.SUBMITTED:
        raise StateConflict("Only a submitted request can be approved.")
    if request.requester_id == approver.pk:
        raise StateConflict("A request cannot be approved by its own requester.")
    request.status = PurchaseRequest.Status.APPROVED
    request.approved_by = approver
    request.approved_at = timezone.now()
    request.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return request


def reject_request(request: PurchaseRequest, approver, reason: str) -> PurchaseRequest:
    if request.status != PurchaseRequest.Status.SUBMITTED:
        raise StateConflict("Only a submitted request can be rejected.")
    if request.requester_id == approver.pk:
        raise StateConflict("A request cannot be rejected by its own requester.")
    if not reason.strip():
        raise StateConflict("A rejection reason is required.")
    request.status = PurchaseRequest.Status.REJECTED
    request.approved_by = approver
    request.approved_at = timezone.now()
    request.rejection_reason = reason.strip()
    request.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    return request


def open_rfq(request: PurchaseRequest, rfq: RequestForQuotation) -> RequestForQuotation:
    if request.status != PurchaseRequest.Status.APPROVED:
        raise StateConflict("Quotations can only be raised against an approved request.")
    return rfq


def issue_rfq(rfq: RequestForQuotation) -> RequestForQuotation:
    if rfq.status != RequestForQuotation.Status.DRAFT:
        raise StateConflict("Only a draft RFQ can be issued.")
    if not rfq.invitations.exists():
        raise StateConflict("Invite at least one supplier before issuing the RFQ.")
    rfq.status = RequestForQuotation.Status.ISSUED
    rfq.issued_at = timezone.now()
    rfq.save(update_fields=["status", "issued_at", "updated_at"])
    return rfq


def validate_quote(quote: SupplierQuote, lines) -> None:
    if quote.rfq.status != RequestForQuotation.Status.ISSUED:
        raise StateConflict("Quotations are only accepted against an issued RFQ.")
    if not quote.rfq.invitations.filter(supplier=quote.supplier).exists():
        raise StateConflict("This supplier was not invited to the RFQ.")
    request_line_quantities = {line.pk: line.quantity for line in quote.rfq.request.lines.all()}
    for line in lines:
        if line.request_line_id not in request_line_quantities:
            raise StateConflict("The quoted line is not on this RFQ's request.")
        if line.quantity > request_line_quantities[line.request_line_id]:
            raise StateConflict("A quotation cannot exceed the requested quantity.")


def select_supplier(rfq: RequestForQuotation, quote: SupplierQuote, reason: str):
    if rfq.status != RequestForQuotation.Status.ISSUED:
        raise StateConflict("Suppliers are selected on an issued RFQ.")
    if quote.rfq_id != rfq.pk:
        raise StateConflict("The quotation belongs to a different RFQ.")
    if not reason.strip():
        raise StateConflict("A selection reason is required.")


def submit_order(order: PurchaseOrder) -> PurchaseOrder:
    if order.status != PurchaseOrder.Status.DRAFT:
        raise StateConflict("Only a draft order can be submitted.")
    if not order.lines.exists():
        raise StateConflict("An order needs at least one line.")
    order.status = PurchaseOrder.Status.SUBMITTED
    order.submitted_at = timezone.now()
    order.save(update_fields=["status", "submitted_at", "updated_at"])
    return order


def approve_order(order: PurchaseOrder, approver) -> PurchaseOrder:
    if order.status != PurchaseOrder.Status.SUBMITTED:
        raise StateConflict("Only a submitted order can be approved.")
    if order.request.requester_id == approver.pk:
        raise StateConflict("The requester cannot approve the resulting order.")
    order.status = PurchaseOrder.Status.APPROVED
    order.approved_by = approver
    order.approved_at = timezone.now()
    order.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return order


def issue_order(order: PurchaseOrder) -> PurchaseOrder:
    if order.status != PurchaseOrder.Status.APPROVED:
        raise StateConflict("Only an approved order can be issued.")
    order.status = PurchaseOrder.Status.ISSUED
    order.issued_at = timezone.now()
    order.save(update_fields=["status", "issued_at", "updated_at"])
    return order


def close_order(order: PurchaseOrder, actor, reason: str) -> PurchaseOrder:
    if order.status in {PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.SUBMITTED}:
        raise StateConflict("An unapproved order cannot be closed.")
    if order.status == PurchaseOrder.Status.CLOSED:
        raise StateConflict("This order is already closed.")
    if not reason.strip():
        raise StateConflict("A closure reason is required.")
    order.status = PurchaseOrder.Status.CLOSED
    order.closed_at = timezone.now()
    order.close_reason = reason.strip()
    order.updated_by = actor
    order.save(update_fields=["status", "closed_at", "close_reason", "updated_by", "updated_at"])
    return order


def _decide_order_status(order: PurchaseOrder) -> None:
    # Re-query rather than trusting a prefetched relation: the quantities were
    # just changed through separate model instances.
    from apps.procurement.models import PurchaseOrderLine

    lines = list(PurchaseOrderLine.objects.filter(order=order))
    if lines and all(line.quantity_accepted >= line.quantity for line in lines):
        order.status = PurchaseOrder.Status.RECEIVED
    elif any(line.quantity_accepted > ZERO for line in lines):
        order.status = PurchaseOrder.Status.PARTIALLY_RECEIVED
    order.save(update_fields=["status", "updated_at"])


@transaction.atomic
def receive_goods(order: PurchaseOrder, actor, received_at, lines_data, notes: str = ""):
    """Record a delivery. Rejected and damaged units never count as received."""
    if order.status not in {
        PurchaseOrder.Status.ISSUED,
        PurchaseOrder.Status.PARTIALLY_RECEIVED,
    }:
        raise StateConflict("Goods can only be received against an issued open order.")
    if not lines_data:
        raise StateConflict("A goods receipt needs at least one line.")

    receipt = GoodsReceiptNote.objects.create(
        number=next_number("GRN"),
        order=order,
        received_at=received_at,
        notes=notes,
        received_by=actor,
        created_by=actor,
        updated_by=actor,
    )

    for entry in lines_data:
        schedule: DeliverySchedule = entry["schedule"]
        order_line = entry["order_line"]
        delivered = entry["quantity_delivered"]
        accepted = entry.get("quantity_accepted", ZERO)
        rejected = entry.get("quantity_rejected", ZERO)
        damaged = entry.get("quantity_damaged", ZERO)

        if schedule.order_line_id != order_line.pk:
            raise StateConflict("The schedule belongs to a different order line.")
        if delivered <= ZERO:
            raise StateConflict("Delivered quantity must be greater than zero.")
        if accepted + rejected + damaged > delivered:
            raise StateConflict("Accepted, rejected and damaged cannot exceed delivered.")
        if schedule.quantity_delivered + delivered > schedule.quantity:
            raise StateConflict("The schedule does not have that much quantity outstanding.")
        if (
            order_line.quantity_accepted
            + order_line.quantity_rejected
            + order_line.quantity_damaged
            + delivered
            > order_line.quantity
        ):
            raise StateConflict("This delivery would over-receive the ordered quantity.")
        if (rejected or damaged) and not entry.get("rejection_reason", "").strip():
            raise StateConflict("Rejected or damaged goods need a reason.")

        GoodsReceiptLine.objects.create(
            receipt=receipt,
            schedule=schedule,
            order_line=order_line,
            quantity_delivered=delivered,
            quantity_accepted=accepted,
            quantity_rejected=rejected,
            quantity_damaged=damaged,
            rejection_reason=entry.get("rejection_reason", ""),
            created_by=actor,
            updated_by=actor,
        )

        schedule.quantity_delivered += delivered
        schedule.save(update_fields=["quantity_delivered", "updated_at"])

        order_line.quantity_accepted += accepted
        order_line.quantity_rejected += rejected
        order_line.quantity_damaged += damaged
        order_line.updated_by = actor
        order_line.save(
            update_fields=[
                "quantity_accepted",
                "quantity_rejected",
                "quantity_damaged",
                "updated_by",
                "updated_at",
            ]
        )

    _decide_order_status(order)

    # Accepted quantities for warehouse destinations enter the stock ledger.
    # Direct project/other-location deliveries stay procurement facts.
    from apps.inventory.services import post_goods_receipt

    post_goods_receipt(receipt)
    return receipt


def schedule_total(order_line) -> Decimal:
    return sum((row.quantity for row in order_line.schedules.all()), ZERO)
