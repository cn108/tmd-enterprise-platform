from __future__ import annotations

from rest_framework import serializers

from apps.catalogue.models import CatalogueItem, UnitOfMeasure
from apps.organisation.models import CostCentre
from apps.parties.models import Party
from apps.procurement.models import (
    DeliverySchedule,
    Destination,
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    RequestForQuotation,
    RfqSupplier,
    SupplierQuote,
    SupplierQuoteLine,
    SupplierSelection,
)
from apps.procurement.services import schedule_total
from apps.projects.models import Project
from apps.warehousing.models import Warehouse


class DestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = [
            "id",
            "kind",
            "project",
            "warehouse",
            "location_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        project = attrs.get("project", getattr(self.instance, "project", None))
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        location = (attrs.get("location_name") or "").strip()

        if kind == Destination.Kind.PROJECT:
            if project is None:
                raise serializers.ValidationError({"project": "Choose a project."})
            if project.status == Project.Status.CLOSED:
                raise serializers.ValidationError({"project": "The project is closed."})
        elif project is not None:
            raise serializers.ValidationError(
                {"project": "Only a project destination takes a project."}
            )

        if kind == Destination.Kind.WAREHOUSE:
            if warehouse is None:
                raise serializers.ValidationError({"warehouse": "Choose a warehouse."})
            if not warehouse.is_active:
                raise serializers.ValidationError({"warehouse": "The warehouse is inactive."})
        elif warehouse is not None:
            raise serializers.ValidationError(
                {"warehouse": "Only a warehouse destination takes a warehouse."}
            )

        if kind == Destination.Kind.OTHER and not location:
            raise serializers.ValidationError({"location_name": "Name the authorised location."})
        if kind != Destination.Kind.OTHER and location:
            raise serializers.ValidationError(
                {"location_name": "Only an other-location destination takes a name."}
            )
        return attrs


class PurchaseRequestLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseRequestLine
        fields = [
            "id",
            "item",
            "description",
            "quantity",
            "uom",
            "cost_centre",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class PurchaseRequestSerializer(serializers.ModelSerializer):
    lines = PurchaseRequestLineSerializer(many=True)
    requester = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequest
        fields = [
            "id",
            "number",
            "requester",
            "department",
            "destination",
            "justification",
            "required_by",
            "status",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "submitted_at",
            "approved_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

    def get_requester(self, obj: PurchaseRequest) -> str:
        return obj.requester.email

    def get_approved_by(self, obj: PurchaseRequest) -> str | None:
        return obj.approved_by.email if obj.approved_by else None

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "Add at least one line."})
        from .numbering import next_number

        request = PurchaseRequest.objects.create(
            number=next_number("PR"),
            requester=self.context["request"].user,
            **validated_data,
        )
        for line in lines:
            PurchaseRequestLine.objects.create(request=request, **line)
        return request


class RfqSupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = RfqSupplier
        fields = ["id", "rfq", "supplier", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_supplier(self, value: Party):
        if not value.is_supplier:
            raise serializers.ValidationError("Only a supplier can be invited.")
        if not value.is_active:
            raise serializers.ValidationError("The supplier is inactive.")
        return value


class RequestForQuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestForQuotation
        fields = [
            "id",
            "number",
            "request",
            "status",
            "due_date",
            "issued_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["number", "status", "issued_at", "created_at", "updated_at"]

    def validate_request(self, value: PurchaseRequest):
        if value.status != PurchaseRequest.Status.APPROVED:
            raise serializers.ValidationError("Only an approved request can be quoted.")
        return value

    def create(self, validated_data):
        from .numbering import next_number

        return RequestForQuotation.objects.create(number=next_number("RFQ"), **validated_data)


class SupplierQuoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierQuoteLine
        fields = ["id", "request_line", "quantity", "unit_price", "lead_time_days"]


class SupplierQuoteSerializer(serializers.ModelSerializer):
    lines = SupplierQuoteLineSerializer(many=True)

    class Meta:
        model = SupplierQuote
        fields = [
            "id",
            "number",
            "rfq",
            "supplier",
            "reference",
            "received_at",
            "currency",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["number", "created_at", "updated_at"]

    def validate_supplier(self, value: Party):
        if not value.is_supplier:
            raise serializers.ValidationError("Quotations come from suppliers.")
        return value

    def create(self, validated_data):
        from .numbering import next_number
        from .services import StateConflict, validate_quote

        lines = validated_data.pop("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "A quotation needs at least one line."})
        quote = SupplierQuote(number=next_number("QT"), **validated_data)
        try:
            validate_quote(quote, [SupplierQuoteLine(**line) for line in lines])
        except StateConflict as exc:
            raise serializers.ValidationError(str(exc)) from exc
        quote.save()
        for line in lines:
            SupplierQuoteLine.objects.create(quote=quote, **line)
        return quote


class SupplierSelectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierSelection
        fields = ["id", "rfq", "quote", "reason", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        if attrs["quote"].rfq_id != attrs["rfq"].pk:
            raise serializers.ValidationError({"quote": "The quotation belongs to another RFQ."})
        if SupplierSelection.objects.filter(rfq=attrs["rfq"]).exists():
            raise serializers.ValidationError({"rfq": "A supplier is already selected."})
        if not attrs.get("reason", "").strip():
            raise serializers.ValidationError({"reason": "A selection reason is required."})
        return attrs


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id",
            "item",
            "description",
            "quantity",
            "unit_price",
            "uom",
            "cost_centre",
            "quantity_accepted",
            "quantity_rejected",
            "quantity_damaged",
        ]
        read_only_fields = ["quantity_accepted", "quantity_rejected", "quantity_damaged"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class PurchaseOrderSerializer(serializers.ModelSerializer):
    lines = PurchaseOrderLineSerializer(many=True, required=False)
    selection = serializers.PrimaryKeyRelatedField(
        queryset=SupplierSelection.objects.select_related("quote", "rfq"),
        write_only=True,
        required=False,
    )
    total_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    approved_by = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "number",
            "supplier",
            "request",
            "rfq",
            "selection",
            "destination",
            "currency",
            "status",
            "submitted_at",
            "approved_by",
            "approved_at",
            "issued_at",
            "closed_at",
            "close_reason",
            "total_value",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "submitted_at",
            "approved_at",
            "issued_at",
            "closed_at",
            "close_reason",
            "created_at",
            "updated_at",
        ]

    def get_approved_by(self, obj: PurchaseOrder) -> str | None:
        return obj.approved_by.email if obj.approved_by else None

    def create(self, validated_data):
        from .numbering import next_number

        selection = validated_data.pop("selection", None)
        lines = validated_data.pop("lines", [])

        if validated_data["request"].status != PurchaseRequest.Status.APPROVED:
            raise serializers.ValidationError({"request": "An order needs an approved request."})

        if selection is not None:
            quote = selection.quote
            if validated_data["supplier"].pk != quote.supplier_id:
                raise serializers.ValidationError(
                    {"supplier": "The supplier does not match the selected quotation."}
                )
            if validated_data.get("rfq") and validated_data["rfq"].pk != selection.rfq_id:
                raise serializers.ValidationError({"rfq": "The RFQ does not match the selection."})
            validated_data["rfq"] = selection.rfq
            if not lines:
                lines = [
                    {
                        "item": line.request_line.item,
                        "request_line": line.request_line,
                        "description": line.request_line.description,
                        "quantity": line.quantity,
                        "unit_price": line.unit_price,
                        "uom": line.request_line.uom,
                        "cost_centre": line.request_line.cost_centre,
                    }
                    for line in quote.lines.select_related("request_line")
                ]

        if not lines:
            raise serializers.ValidationError({"lines": "An order needs at least one line."})

        order = PurchaseOrder.objects.create(number=next_number("PO"), **validated_data)
        for line in lines:
            PurchaseOrderLine.objects.create(order=order, **line)
        return order


class DeliveryScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverySchedule
        fields = [
            "id",
            "order_line",
            "due_date",
            "quantity",
            "destination",
            "quantity_delivered",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["quantity_delivered", "created_at", "updated_at"]

    def validate(self, attrs):
        order_line = attrs["order_line"]
        quantity = attrs["quantity"]
        if quantity <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
        already = schedule_total(order_line)
        if already + quantity > order_line.quantity:
            raise serializers.ValidationError(
                {"quantity": "Schedules cannot exceed the ordered quantity."}
            )
        return attrs


class GoodsReceiptLineSerializer(serializers.Serializer):
    schedule = serializers.PrimaryKeyRelatedField(queryset=DeliverySchedule.objects.all())
    order_line = serializers.PrimaryKeyRelatedField(queryset=PurchaseOrderLine.objects.all())
    quantity_delivered = serializers.DecimalField(max_digits=18, decimal_places=4)
    quantity_accepted = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=0
    )
    quantity_rejected = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=0
    )
    quantity_damaged = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=0
    )
    rejection_reason = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )


class GoodsReceiptCreateSerializer(serializers.Serializer):
    received_at = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = GoodsReceiptLineSerializer(many=True)


class GoodsReceiptLineReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceiptLine
        fields = [
            "id",
            "schedule",
            "order_line",
            "quantity_delivered",
            "quantity_accepted",
            "quantity_rejected",
            "quantity_damaged",
            "rejection_reason",
        ]


class GoodsReceiptNoteSerializer(serializers.ModelSerializer):
    lines = GoodsReceiptLineReadSerializer(many=True, read_only=True)
    received_by = serializers.SerializerMethodField()

    class Meta:
        model = GoodsReceiptNote
        fields = ["id", "number", "order", "received_at", "notes", "received_by", "lines"]

    def get_received_by(self, obj: GoodsReceiptNote) -> str:
        return obj.received_by.email


class ItemReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogueItem
        fields = ["id", "code", "name"]


class UnitReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ["id", "code", "name"]


class CostCentreReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostCentre
        fields = ["id", "code", "name"]


class WarehouseReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name"]
