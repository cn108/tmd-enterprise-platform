"""Procurement lifecycle (Phase 4).

The state machine is explicit because every step is auditable: a request is
drafted, submitted, approved or rejected; a quotation is raised against an
approved request; a purchase order is approved, issued, received against and
closed.

No approval threshold is encoded. D-04 (limits) and D-14 (approval route) are
unanswered, so approval requires a permission, the approver must differ from the
requester, and every decision records who and when. Configuring a permission
without a policy is fail-closed: nobody can approve until it is granted.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from shared.models import UserStampedModel

ZERO = Decimal("0")


class DocumentSequence(models.Model):
    """Year-scoped counter behind human-readable document numbers (M-01)."""

    kind = models.CharField(max_length=8)
    year = models.PositiveSmallIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "year"], name="unique_sequence_per_kind_year")
        ]

    def __str__(self) -> str:
        return f"{self.kind}-{self.year}: {self.last_number}"


class Destination(UserStampedModel):
    """Where goods must go: a project, a warehouse, or an authorised location."""

    class Kind(models.TextChoices):
        PROJECT = "project", "Direct project delivery"
        WAREHOUSE = "warehouse", "Company warehouse"
        OTHER = "other", "Other authorised location"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    location_name = models.CharField(max_length=120, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["kind", "id"]

    def clean(self) -> None:
        targets = {
            self.Kind.PROJECT: self.project_id,
            self.Kind.WAREHOUSE: self.warehouse_id,
            self.Kind.OTHER: self.location_name.strip() or None,
        }
        if not targets[self.kind]:
            raise ValidationError("The chosen destination type needs its target.")
        if self.kind != self.Kind.PROJECT and self.project_id:
            raise ValidationError({"project": "Only a project destination takes a project."})
        if self.kind != self.Kind.WAREHOUSE and self.warehouse_id:
            raise ValidationError({"warehouse": "Only a warehouse destination takes a warehouse."})
        if self.kind != self.Kind.OTHER and self.location_name:
            raise ValidationError(
                {"location_name": "Only an other-location destination takes a name."}
            )

    def __str__(self) -> str:
        if self.kind == self.Kind.PROJECT and self.project_id:
            return f"Project {self.project.code}"
        if self.kind == self.Kind.WAREHOUSE and self.warehouse_id:
            return f"Warehouse {self.warehouse.code}"
        return self.location_name or "Unnamed location"


class PurchaseRequest(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    number = models.CharField(max_length=24, unique=True)
    requester = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, related_name="purchase_requests"
    )
    department = models.ForeignKey(
        "organisation.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    destination = models.ForeignKey(
        Destination, on_delete=models.PROTECT, related_name="purchase_requests"
    )
    justification = models.TextField(blank=True)
    required_by = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("approve_purchaserequest", "Can approve purchase requests")]

    def __str__(self) -> str:
        return self.number


class PurchaseRequestLine(UserStampedModel):
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="request_lines"
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom = models.ForeignKey(
        "catalogue.UnitOfMeasure",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="request_lines",
    )

    class Meta:
        ordering = ["request", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="request_line_quantity_positive"
            )
        ]


class RequestForQuotation(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        CLOSED = "closed", "Closed"

    number = models.CharField(max_length=24, unique=True)
    request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name="rfqs")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.number


class RfqSupplier(UserStampedModel):
    rfq = models.ForeignKey(
        RequestForQuotation, on_delete=models.CASCADE, related_name="invitations"
    )
    supplier = models.ForeignKey(
        "parties.Party", on_delete=models.PROTECT, related_name="rfq_invitations"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rfq", "supplier"], name="unique_rfq_supplier")
        ]


class SupplierQuote(UserStampedModel):
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.PROTECT, related_name="quotes")
    supplier = models.ForeignKey("parties.Party", on_delete=models.PROTECT, related_name="quotes")
    number = models.CharField(max_length=24, unique=True)
    reference = models.CharField(max_length=80, blank=True)
    received_at = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="NGN")

    class Meta:
        ordering = ["rfq", "supplier__code"]
        constraints = [
            models.UniqueConstraint(fields=["rfq", "supplier"], name="unique_quote_per_supplier")
        ]


class SupplierQuoteLine(UserStampedModel):
    quote = models.ForeignKey(SupplierQuote, on_delete=models.CASCADE, related_name="lines")
    request_line = models.ForeignKey(
        PurchaseRequestLine, on_delete=models.PROTECT, related_name="quote_lines"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    lead_time_days = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["quote", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="quote_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="quote_line_price_non_negative"
            ),
        ]


class SupplierSelection(UserStampedModel):
    rfq = models.OneToOneField(
        RequestForQuotation, on_delete=models.PROTECT, related_name="selection"
    )
    quote = models.ForeignKey(SupplierQuote, on_delete=models.PROTECT, related_name="selections")
    reason = models.CharField(max_length=255)

    class Meta:
        permissions = [("select_supplier", "Can select a supplier for a quotation")]

    def clean(self) -> None:
        if self.quote_id and self.rfq_id and self.quote.rfq_id != self.rfq_id:
            raise ValidationError({"quote": "The quotation belongs to a different RFQ."})


class PurchaseOrder(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        ISSUED = "issued", "Issued"
        PARTIALLY_RECEIVED = "partially_received", "Partially received"
        RECEIVED = "received", "Received"
        CLOSED = "closed", "Closed"

    number = models.CharField(max_length=24, unique=True)
    supplier = models.ForeignKey("parties.Party", on_delete=models.PROTECT, related_name="orders")
    request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name="orders")
    rfq = models.ForeignKey(
        RequestForQuotation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, related_name="orders")
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("approve_purchaseorder", "Can approve purchase orders")]

    def __str__(self) -> str:
        return self.number

    @property
    def total_value(self) -> Decimal:
        return sum((line.quantity * line.unit_price for line in self.lines.all()), ZERO)


class PurchaseOrderLine(UserStampedModel):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    request_line = models.ForeignKey(
        PurchaseRequestLine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="order_lines"
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=6, default=ZERO)
    uom = models.ForeignKey(
        "catalogue.UnitOfMeasure",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    quantity_accepted = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    quantity_rejected = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    quantity_damaged = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="order_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="order_line_price_non_negative"
            ),
        ]

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.quantity_accepted


class DeliverySchedule(UserStampedModel):
    order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.CASCADE, related_name="schedules"
    )
    due_date = models.DateField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, related_name="schedules")
    quantity_delivered = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)

    class Meta:
        ordering = ["order_line", "due_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="schedule_quantity_positive"
            )
        ]


class GoodsReceiptNote(UserStampedModel):
    number = models.CharField(max_length=24, unique=True)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    received_at = models.DateField()
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, related_name="goods_receipts"
    )

    class Meta:
        ordering = ["-received_at", "-id"]

    def __str__(self) -> str:
        return self.number


class GoodsReceiptLine(UserStampedModel):
    receipt = models.ForeignKey(GoodsReceiptNote, on_delete=models.CASCADE, related_name="lines")
    schedule = models.ForeignKey(
        DeliverySchedule, on_delete=models.PROTECT, related_name="receipt_lines"
    )
    order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines"
    )
    quantity_delivered = models.DecimalField(max_digits=18, decimal_places=4)
    quantity_accepted = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    quantity_rejected = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    quantity_damaged = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    rejection_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["receipt", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_delivered__gt=0),
                name="receipt_line_delivered_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_accepted__gte=0)
                & models.Q(quantity_rejected__gte=0)
                & models.Q(quantity_damaged__gte=0),
                name="receipt_line_quantities_non_negative",
            ),
        ]
