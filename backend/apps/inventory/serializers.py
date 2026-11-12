from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.catalogue.models import CatalogueItem, ItemBatch, SerialNumber
from apps.inventory.models import (
    InventoryPolicy,
    ReorderLevel,
    StockAdjustment,
    StockAdjustmentLine,
    StockCount,
    StockCountLine,
    StockDamage,
    StockDamageLine,
    StockIssue,
    StockIssueLine,
    StockMovement,
    StockReceipt,
    StockReceiptLine,
    StockReservation,
    StockReturn,
    StockReturnLine,
    StockTransfer,
    StockTransferLine,
)
from apps.organisation.models import CostCentre
from apps.parties.models import Party
from apps.projects.models import Project
from apps.warehousing.models import StorageLocation, Warehouse

MIN_QUANTITY = Decimal("0.0001")


class InventoryPolicySerializer(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    configured = serializers.SerializerMethodField()

    class Meta:
        model = InventoryPolicy
        fields = [
            "valuation_method",
            "note",
            "approved_by",
            "approved_at",
            "configured",
            "updated_at",
        ]

    def get_approved_by(self, obj: InventoryPolicy) -> str | None:
        return obj.approved_by.email if obj.approved_by else None

    def get_configured(self, obj: InventoryPolicy) -> bool:
        return bool(obj.valuation_method)


class StockMovementSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True, default=None)
    serial_number = serializers.CharField(source="serial.serial", read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "number",
            "movement_type",
            "item",
            "item_code",
            "item_name",
            "warehouse",
            "warehouse_code",
            "location",
            "batch",
            "batch_number",
            "serial",
            "serial_number",
            "quantity",
            "unit_cost",
            "value_delta",
            "project",
            "cost_centre",
            "reference",
            "reason",
            "movement_date",
            "occurred_at",
        ]
        read_only_fields = fields


class StockReceiptLineSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)

    class Meta:
        model = StockReceiptLine
        fields = ["id", "item", "item_code", "quantity", "unit_cost", "batch", "serial"]


class StockReceiptSerializer(serializers.ModelSerializer):
    lines = StockReceiptLineSerializer(many=True, read_only=True)
    received_by = serializers.SerializerMethodField()
    warehouse_code = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()

    class Meta:
        model = StockReceipt
        fields = [
            "id",
            "number",
            "warehouse",
            "warehouse_code",
            "supplier",
            "supplier_name",
            "received_at",
            "reference",
            "notes",
            "received_by",
            "lines",
            "created_at",
        ]

    def get_received_by(self, obj: StockReceipt) -> str:
        return obj.received_by.email

    def get_warehouse_code(self, obj: StockReceipt) -> str | None:
        return obj.warehouse.code if obj.warehouse_id else None

    def get_supplier_name(self, obj: StockReceipt) -> str | None:
        return obj.supplier.legal_name if obj.supplier_id else None


class StockReceiptLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CatalogueItem.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=MIN_QUANTITY)
    unit_cost = serializers.DecimalField(max_digits=18, decimal_places=6, min_value=Decimal("0"))
    batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemBatch.objects.all(), required=False, allow_null=True
    )
    serial = serializers.PrimaryKeyRelatedField(
        queryset=SerialNumber.objects.all(), required=False, allow_null=True
    )


class StockReceiptCreateSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Party.objects.all(), required=False, allow_null=True
    )
    received_at = serializers.DateField()
    reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockReceiptLineInputSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("A receipt needs at least one line.")
        return value


class StockTransferLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockTransferLine
        fields = ["id", "item", "quantity", "batch", "serial", "unit_cost", "value"]


class StockTransferSerializer(serializers.ModelSerializer):
    lines = StockTransferLineSerializer(many=True, read_only=True)
    from_warehouse_code = serializers.CharField(source="from_warehouse.code", read_only=True)
    to_warehouse_code = serializers.CharField(source="to_warehouse.code", read_only=True)

    class Meta:
        model = StockTransfer
        fields = [
            "id",
            "number",
            "from_warehouse",
            "from_warehouse_code",
            "from_location",
            "to_warehouse",
            "to_warehouse_code",
            "to_location",
            "notes",
            "status",
            "dispatched_at",
            "received_at",
            "lines",
            "created_at",
        ]


class StockTransferLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CatalogueItem.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=MIN_QUANTITY)
    batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemBatch.objects.all(), required=False, allow_null=True
    )
    serial = serializers.PrimaryKeyRelatedField(
        queryset=SerialNumber.objects.all(), required=False, allow_null=True
    )


class StockTransferCreateSerializer(serializers.Serializer):
    from_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    from_location = serializers.PrimaryKeyRelatedField(
        queryset=StorageLocation.objects.all(), required=False, allow_null=True
    )
    to_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    to_location = serializers.PrimaryKeyRelatedField(
        queryset=StorageLocation.objects.all(), required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockTransferLineInputSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("A transfer needs at least one line.")
        return value


class StockIssueLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockIssueLine
        fields = [
            "id",
            "item",
            "warehouse",
            "location",
            "quantity",
            "batch",
            "serial",
            "reservation",
            "unit_cost",
            "value",
        ]


class StockIssueSerializer(serializers.ModelSerializer):
    lines = StockIssueLineSerializer(many=True, read_only=True)
    issued_by = serializers.SerializerMethodField()
    project_code = serializers.SerializerMethodField()

    class Meta:
        model = StockIssue
        fields = [
            "id",
            "number",
            "project",
            "project_code",
            "cost_centre",
            "recipient",
            "notes",
            "issued_at",
            "issued_by",
            "lines",
        ]

    def get_issued_by(self, obj: StockIssue) -> str:
        return obj.issued_by.email

    def get_project_code(self, obj: StockIssue) -> str | None:
        return obj.project.code if obj.project_id else None


class StockIssueLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CatalogueItem.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    location = serializers.PrimaryKeyRelatedField(
        queryset=StorageLocation.objects.all(), required=False, allow_null=True
    )
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=MIN_QUANTITY)
    batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemBatch.objects.all(), required=False, allow_null=True
    )
    serial = serializers.PrimaryKeyRelatedField(
        queryset=SerialNumber.objects.all(), required=False, allow_null=True
    )
    reservation = serializers.PrimaryKeyRelatedField(
        queryset=StockReservation.objects.all(), required=False, allow_null=True
    )


class StockIssueCreateSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    cost_centre = serializers.PrimaryKeyRelatedField(
        queryset=CostCentre.objects.all(), required=False, allow_null=True
    )
    recipient = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockIssueLineInputSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("An issue needs at least one line.")
        return value


class StockReturnLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockReturnLine
        fields = ["id", "item", "warehouse", "quantity", "unit_cost", "batch", "serial"]


class StockReturnSerializer(serializers.ModelSerializer):
    lines = StockReturnLineSerializer(many=True, read_only=True)
    returned_by = serializers.SerializerMethodField()

    class Meta:
        model = StockReturn
        fields = [
            "id",
            "number",
            "project",
            "notes",
            "returned_at",
            "returned_by",
            "lines",
        ]

    def get_returned_by(self, obj: StockReturn) -> str:
        return obj.returned_by.email


class StockReturnLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CatalogueItem.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=MIN_QUANTITY)
    unit_cost = serializers.DecimalField(max_digits=18, decimal_places=6, min_value=Decimal("0"))
    batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemBatch.objects.all(), required=False, allow_null=True
    )
    serial = serializers.PrimaryKeyRelatedField(
        queryset=SerialNumber.objects.all(), required=False, allow_null=True
    )


class StockReturnCreateSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockReturnLineInputSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("A return needs at least one line.")
        return value


class StockAdjustmentLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockAdjustmentLine
        fields = [
            "id",
            "item",
            "warehouse",
            "quantity",
            "direction",
            "unit_cost",
            "value",
            "batch",
            "serial",
        ]


class StockAdjustmentSerializer(serializers.ModelSerializer):
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)
    adjusted_by = serializers.SerializerMethodField()

    class Meta:
        model = StockAdjustment
        fields = [
            "id",
            "number",
            "reason",
            "adjusted_at",
            "adjusted_by",
            "lines",
        ]

    def get_adjusted_by(self, obj: StockAdjustment) -> str:
        return obj.adjusted_by.email


class StockAdjustmentLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CatalogueItem.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=MIN_QUANTITY)
    direction = serializers.ChoiceField(choices=StockAdjustmentLine.Direction.choices)
    unit_cost = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
    )
    batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemBatch.objects.all(), required=False, allow_null=True
    )
    serial = serializers.PrimaryKeyRelatedField(
        queryset=SerialNumber.objects.all(), required=False, allow_null=True
    )


class StockAdjustmentCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
    lines = StockAdjustmentLineInputSerializer(many=True)

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("An adjustment needs a reason.")
        return value

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("An adjustment needs at least one line.")
        return value


class StockDamageLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockDamageLine
        fields = [
            "id",
            "item",
            "warehouse",
            "location",
            "quantity",
            "batch",
            "serial",
            "unit_cost",
            "value",
        ]


class StockDamageSerializer(serializers.ModelSerializer):
    lines = StockDamageLineSerializer(many=True, read_only=True)
    recorded_by = serializers.SerializerMethodField()

    class Meta:
        model = StockDamage
        fields = ["id", "number", "reason", "recorded_at", "recorded_by", "lines"]

    def get_recorded_by(self, obj: StockDamage) -> str:
        return obj.recorded_by.email


class StockDamageLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CatalogueItem.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    location = serializers.PrimaryKeyRelatedField(
        queryset=StorageLocation.objects.all(), required=False, allow_null=True
    )
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=MIN_QUANTITY)
    batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemBatch.objects.all(), required=False, allow_null=True
    )
    serial = serializers.PrimaryKeyRelatedField(
        queryset=SerialNumber.objects.all(), required=False, allow_null=True
    )


class StockDamageCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
    lines = StockDamageLineInputSerializer(many=True)

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("A damage record needs a reason.")
        return value

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("A damage record needs at least one line.")
        return value


class StockCountLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockCountLine
        fields = [
            "id",
            "item",
            "batch",
            "counted_quantity",
            "system_quantity",
            "variance",
            "unit_cost",
        ]


class StockCountSerializer(serializers.ModelSerializer):
    lines = StockCountLineSerializer(many=True, read_only=True)
    counted_by = serializers.SerializerMethodField()
    posted_by = serializers.SerializerMethodField()
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = StockCount
        fields = [
            "id",
            "number",
            "warehouse",
            "warehouse_code",
            "notes",
            "status",
            "counted_by",
            "posted_at",
            "posted_by",
            "lines",
            "created_at",
        ]

    def get_counted_by(self, obj: StockCount) -> str | None:
        return obj.counted_by.email if obj.counted_by else None

    def get_posted_by(self, obj: StockCount) -> str | None:
        return obj.posted_by.email if obj.posted_by else None


class StockCountLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=CatalogueItem.objects.all())
    batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemBatch.objects.all(), required=False, allow_null=True
    )
    counted_quantity = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0")
    )
    unit_cost = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
    )


class StockCountCreateSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockCountLineInputSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("A stock count needs at least one line.")
        return value


class StockReservationSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    quantity_remaining = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = StockReservation
        fields = [
            "id",
            "item",
            "item_code",
            "warehouse",
            "warehouse_code",
            "project",
            "quantity",
            "quantity_fulfilled",
            "quantity_remaining",
            "status",
            "reference",
            "notes",
            "created_at",
        ]
        read_only_fields = ["quantity_fulfilled", "status", "created_at"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("A reservation needs a positive quantity.")
        return value


class ReorderLevelSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = ReorderLevel
        fields = [
            "id",
            "item",
            "item_code",
            "warehouse",
            "warehouse_code",
            "minimum_quantity",
            "reorder_quantity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
