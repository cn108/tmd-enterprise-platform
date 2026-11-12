"""Inventory ledger, reservations and stock documents (Phase 5).

The ledger is the source of truth. ``StockMovement`` rows are append-only and
signed: an inbound movement is positive, an outbound movement is negative.
Balances are never stored in a mutable row; they are computed by summing the
ledger, so no endpoint can overwrite a balance.

Valuation follows an explicitly configured method. D-06 (costing method and
GRNI policy) is unresolved, so no method is seeded and the valuation report
refuses to answer until an authorised user records one. The choice is locked
once movements exist, because replaying history under a different method would
change already-reported costs.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from shared.models import UserStampedModel

ZERO = Decimal("0")


class InventoryPolicy(models.Model):
    """The single company inventory policy (D-06, PROPOSED until signed)."""

    class Method(models.TextChoices):
        FIFO = "fifo", "FIFO"
        WEIGHTED_AVERAGE = "weighted_average", "Weighted average"
        SPECIFIC_IDENTIFICATION = "specific_identification", "Specific identification"

    valuation_method = models.CharField(max_length=30, choices=Method.choices, blank=True)
    note = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "inventory policy"
        verbose_name_plural = "inventory policy"
        permissions = [
            ("set_valuation_method", "Can set the inventory valuation method"),
        ]

    def __str__(self) -> str:
        return self.valuation_method or "unconfigured"

    @classmethod
    def load(cls) -> InventoryPolicy:
        policy, _ = cls.objects.get_or_create(pk=1)
        return policy


class StockMovement(models.Model):
    """One immutable, signed quantity and value change."""

    class Type(models.TextChoices):
        RECEIPT = "receipt", "Goods receipt"
        TRANSFER_OUT = "transfer_out", "Transfer out"
        TRANSFER_IN = "transfer_in", "Transfer in"
        ISSUE = "issue", "Issue"
        PROJECT_ISSUE = "project_issue", "Project issue"
        RETURN_IN = "return_in", "Return to stock"
        ADJUSTMENT_IN = "adjustment_in", "Adjustment increase"
        ADJUSTMENT_OUT = "adjustment_out", "Adjustment decrease"
        DAMAGE = "damage", "Damaged stock written off"
        COUNT_GAIN = "count_gain", "Stock count gain"
        COUNT_LOSS = "count_loss", "Stock count loss"

    number = models.CharField(max_length=24, unique=True)
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_movements"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_movements"
    )
    location = models.ForeignKey(
        "warehousing.StorageLocation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    serial = models.ForeignKey(
        "catalogue.SerialNumber",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    value_delta = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    reference = models.CharField(max_length=32, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    movement_date = models.DateField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    goods_receipt_line = models.ForeignKey(
        "procurement.GoodsReceiptLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    stock_receipt = models.ForeignKey(
        "inventory.StockReceipt",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    transfer_line = models.ForeignKey(
        "inventory.StockTransferLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    issue_line = models.ForeignKey(
        "inventory.StockIssueLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    return_line = models.ForeignKey(
        "inventory.StockReturnLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    adjustment_line = models.ForeignKey(
        "inventory.StockAdjustmentLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    damage_line = models.ForeignKey(
        "inventory.StockDamageLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    count_line = models.ForeignKey(
        "inventory.StockCountLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity=0), name="stock_movement_quantity_non_zero"
            ),
            models.UniqueConstraint(
                fields=["goods_receipt_line"],
                condition=models.Q(goods_receipt_line__isnull=False),
                name="one_movement_per_goods_receipt_line",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.number} {self.quantity} {self.item.code}"


class StockLayer(models.Model):
    """A FIFO cost layer created by an inbound movement.

    Layers are created for every inbound movement, whatever method is
    configured, so a method chosen before the first issue has complete history.
    The method itself cannot change after movements exist.
    """

    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_layers"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_layers"
    )
    movement = models.ForeignKey(
        StockMovement, on_delete=models.PROTECT, related_name="created_layers"
    )
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6)
    original_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    remaining_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    received_on = models.DateField()

    class Meta:
        ordering = ["item", "warehouse", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(remaining_quantity__gte=0)
                & models.Q(remaining_quantity__lte=models.F("original_quantity")),
                name="stock_layer_remaining_within_bounds",
            )
        ]

    def __str__(self) -> str:
        return f"{self.item.code}/{self.warehouse.code}: {self.remaining_quantity}"


class StockLayerConsumption(models.Model):
    """Which FIFO layers an outbound movement consumed, and at what cost."""

    layer = models.ForeignKey(StockLayer, on_delete=models.PROTECT, related_name="consumptions")
    movement = models.ForeignKey(
        StockMovement, on_delete=models.PROTECT, related_name="layer_consumptions"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6)
    value = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ["movement", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="layer_consumption_quantity_positive"
            )
        ]

    def __str__(self) -> str:
        return f"{self.layer_id}: {self.quantity} @ {self.unit_cost}"


class StockReservation(UserStampedModel):
    """A claim on stock that reduces availability without moving it."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FULFILLED = "fulfilled", "Fulfilled"
        RELEASED = "released", "Released"

    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="reservations"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="reservations"
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_reservations",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    quantity_fulfilled = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("reserve_stock", "Can reserve stock")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="reservation_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_fulfilled__gte=0)
                & models.Q(quantity_fulfilled__lte=models.F("quantity")),
                name="reservation_fulfilled_within_quantity",
            ),
        ]

    @property
    def quantity_remaining(self) -> Decimal:
        return self.quantity - self.quantity_fulfilled

    def __str__(self) -> str:
        return f"{self.item.code} @ {self.warehouse.code}: {self.quantity}"


class StockReceipt(UserStampedModel):
    """Stock received directly, outside a purchase order (opening or direct)."""

    number = models.CharField(max_length=24, unique=True)
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_receipts"
    )
    supplier = models.ForeignKey(
        "parties.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_receipts",
    )
    received_at = models.DateField()
    reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, related_name="stock_receipts"
    )

    class Meta:
        ordering = ["-received_at", "-id"]
        permissions = [("receive_stock", "Can receive stock into a warehouse")]

    def __str__(self) -> str:
        return self.number


class StockReceiptLine(UserStampedModel):
    receipt = models.ForeignKey(StockReceipt, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_receipt_lines"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6)
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    serial = models.ForeignKey(
        "catalogue.SerialNumber",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["receipt", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="stock_receipt_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="stock_receipt_line_cost_non_negative",
            ),
        ]


class StockTransfer(UserStampedModel):
    """Movement of stock between warehouses or storage locations."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        DISPATCHED = "dispatched", "Dispatched"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    from_warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="transfers_out"
    )
    from_location = models.ForeignKey(
        "warehousing.StorageLocation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    to_warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="transfers_in"
    )
    to_location = models.ForeignKey(
        "warehousing.StorageLocation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("transfer_stock", "Can transfer stock between warehouses")]

    def __str__(self) -> str:
        return self.number


class StockTransferLine(UserStampedModel):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_transfer_lines"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    serial = models.ForeignKey(
        "catalogue.SerialNumber",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["transfer", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="stock_transfer_line_quantity_positive"
            )
        ]


class StockIssue(UserStampedModel):
    """Stock issued to a project or to consumption."""

    number = models.CharField(max_length=24, unique=True)
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_issues",
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_issues",
    )
    recipient = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    issued_at = models.DateTimeField()
    issued_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, related_name="stock_issues"
    )

    class Meta:
        ordering = ["-issued_at", "-id"]
        permissions = [("issue_stock", "Can issue stock")]

    def __str__(self) -> str:
        return self.number


class StockIssueLine(UserStampedModel):
    issue = models.ForeignKey(StockIssue, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_issue_lines"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_issue_lines"
    )
    location = models.ForeignKey(
        "warehousing.StorageLocation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    serial = models.ForeignKey(
        "catalogue.SerialNumber",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    reservation = models.ForeignKey(
        StockReservation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="issue_lines",
    )
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["issue", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="stock_issue_line_quantity_positive"
            )
        ]


class StockReturn(UserStampedModel):
    """Goods returned into stock."""

    number = models.CharField(max_length=24, unique=True)
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_returns",
    )
    notes = models.TextField(blank=True)
    returned_at = models.DateTimeField()
    returned_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, related_name="stock_returns"
    )

    class Meta:
        ordering = ["-returned_at", "-id"]
        permissions = [("return_stock", "Can return stock into a warehouse")]

    def __str__(self) -> str:
        return self.number


class StockReturnLine(UserStampedModel):
    return_document = models.ForeignKey(StockReturn, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_return_lines"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_return_lines"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6)
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    serial = models.ForeignKey(
        "catalogue.SerialNumber",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["return_document", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="stock_return_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0), name="stock_return_line_cost_non_negative"
            ),
        ]


class StockAdjustment(UserStampedModel):
    """A quantity correction with a mandatory reason."""

    number = models.CharField(max_length=24, unique=True)
    reason = models.CharField(max_length=255)
    adjusted_at = models.DateTimeField()
    adjusted_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, related_name="stock_adjustments"
    )

    class Meta:
        ordering = ["-adjusted_at", "-id"]
        permissions = [("adjust_stock", "Can adjust stock quantities")]

    def __str__(self) -> str:
        return self.number


class StockAdjustmentLine(UserStampedModel):
    class Direction(models.TextChoices):
        INCREASE = "increase", "Increase"
        DECREASE = "decrease", "Decrease"

    adjustment = models.ForeignKey(StockAdjustment, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_adjustment_lines"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_adjustment_lines"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    serial = models.ForeignKey(
        "catalogue.SerialNumber",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["adjustment", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="stock_adjustment_line_quantity_positive"
            )
        ]


class StockDamage(UserStampedModel):
    """Damaged stock written out of available inventory, with a reason."""

    number = models.CharField(max_length=24, unique=True)
    reason = models.CharField(max_length=255)
    recorded_at = models.DateTimeField()
    recorded_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, related_name="stock_damages"
    )

    class Meta:
        ordering = ["-recorded_at", "-id"]
        permissions = [("write_off_stock", "Can write off damaged stock")]

    def __str__(self) -> str:
        return self.number


class StockDamageLine(UserStampedModel):
    damage = models.ForeignKey(StockDamage, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_damage_lines"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_damage_lines"
    )
    location = models.ForeignKey(
        "warehousing.StorageLocation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    serial = models.ForeignKey(
        "catalogue.SerialNumber",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["damage", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="stock_damage_line_quantity_positive"
            )
        ]


class StockCount(UserStampedModel):
    """A physical count posted as gain or loss movements against the ledger."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"

    number = models.CharField(max_length=24, unique=True)
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="stock_counts"
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    counted_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_counts",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        permissions = [("count_stock", "Can post stock counts")]

    def __str__(self) -> str:
        return self.number


class StockCountLine(UserStampedModel):
    count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="stock_count_lines"
    )
    batch = models.ForeignKey(
        "catalogue.ItemBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    counted_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    system_quantity = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    variance = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["count", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(counted_quantity__gte=0),
                name="stock_count_line_counted_non_negative",
            ),
            models.UniqueConstraint(fields=["count", "item"], name="unique_item_per_stock_count"),
        ]

    def clean(self) -> None:
        if self.count_id and self.item_id:
            item = self.item
            if not item.is_stock_tracked:
                raise ValidationError({"item": "Only a stock-tracked product can be counted."})


class ReorderLevel(UserStampedModel):
    """The client-supplied level at which a reorder alert is raised."""

    item = models.ForeignKey(
        "catalogue.CatalogueItem", on_delete=models.PROTECT, related_name="reorder_levels"
    )
    warehouse = models.ForeignKey(
        "warehousing.Warehouse", on_delete=models.PROTECT, related_name="reorder_levels"
    )
    minimum_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    reorder_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item__code", "warehouse__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "warehouse"], name="unique_reorder_level_per_item_warehouse"
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_quantity__gte=0) & models.Q(reorder_quantity__gte=0),
                name="reorder_level_quantities_non_negative",
            ),
        ]
