from __future__ import annotations

from rest_framework import serializers

from apps.leasing.models import (
    Equipment,
    EquipmentCategory,
    EquipmentInspection,
    EquipmentMaintenance,
    EquipmentMovement,
    EquipmentRate,
    EquipmentReservation,
    RentalAgreement,
    RentalAgreementLine,
)
from apps.leasing.workflows import LeasingConflict, check_availability


class EquipmentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentCategory
        fields = ["id", "code", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class EquipmentRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentRate
        fields = [
            "id",
            "equipment",
            "basis",
            "amount",
            "currency",
            "effective_from",
            "effective_to",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("effective_from", getattr(self.instance, "effective_from", None))
        end = attrs.get("effective_to", getattr(self.instance, "effective_to", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"effective_to": "The rate cannot end before it starts."}
            )
        return attrs


class EquipmentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    open_maintenance = serializers.SerializerMethodField()
    active_rental = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = [
            "id",
            "code",
            "name",
            "category",
            "category_name",
            "description",
            "specification",
            "serial_number",
            "identifier",
            "ownership",
            "ownership_reference",
            "location",
            "status",
            "asset_classification",
            "accounting_treatment",
            "is_active",
            "notes",
            "open_maintenance",
            "active_rental",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_open_maintenance(self, obj: Equipment) -> int:
        return obj.maintenance_records.filter(
            status__in=[
                EquipmentMaintenance.Status.PLANNED,
                EquipmentMaintenance.Status.IN_PROGRESS,
            ]
        ).count()

    def get_active_rental(self, obj: Equipment) -> str:
        line = (
            obj.rental_lines.filter(
                agreement__status__in=[
                    RentalAgreement.Status.APPROVED,
                    RentalAgreement.Status.ACTIVE,
                ]
            )
            .select_related("agreement")
            .first()
        )
        return line.agreement.number if line else ""

    def validate_code(self, value):
        return (value or "").strip().upper()


class RentalAgreementLineSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source="equipment.code", read_only=True)
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)

    class Meta:
        model = RentalAgreementLine
        fields = [
            "id",
            "equipment",
            "equipment_code",
            "equipment_name",
            "rate",
            "start_date",
            "end_date",
            "quantity",
            "rate_amount",
            "line_total",
        ]
        read_only_fields = ["line_total"]

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "The line cannot end before it starts."})
        equipment = attrs.get("equipment")
        if equipment is not None and equipment.status == Equipment.Status.RETIRED:
            raise serializers.ValidationError({"equipment": "Retired equipment cannot be rented."})
        return attrs


class RentalAgreementSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True, default="")
    lines = RentalAgreementLineSerializer(many=True)
    total_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    approved_by_email = serializers.CharField(
        source="approved_by.email", read_only=True, default=""
    )

    class Meta:
        model = RentalAgreement
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "project",
            "project_code",
            "start_date",
            "end_date",
            "currency",
            "status",
            "terms",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "closed_at",
            "total_value",
            "lines",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "closed_at",
            "total_value",
            "created_at",
            "updated_at",
        ]

    def validate_customer(self, value):
        if not value.is_customer or not value.is_active:
            raise serializers.ValidationError("Choose an active customer.")
        return value

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("An agreement needs at least one equipment line.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The agreement cannot end before it starts."}
            )
        if self.instance and self.instance.status not in {
            RentalAgreement.Status.DRAFT,
            RentalAgreement.Status.SUBMITTED,
        }:
            raise serializers.ValidationError("Only a draft or submitted agreement can be edited.")
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        agreement = RentalAgreement.objects.create(**validated_data)
        for line in lines:
            RentalAgreementLine.objects.create(agreement=agreement, **line)
        return agreement

    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                RentalAgreementLine.objects.create(agreement=instance, **line)
        return instance


class EquipmentReservationSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source="equipment.code", read_only=True)
    customer_name = serializers.CharField(source="customer.legal_name", read_only=True)
    agreement_number = serializers.CharField(source="agreement.number", read_only=True, default="")

    class Meta:
        model = EquipmentReservation
        fields = [
            "id",
            "equipment",
            "equipment_code",
            "agreement",
            "agreement_number",
            "customer",
            "customer_name",
            "start_date",
            "end_date",
            "quantity",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_customer(self, value):
        if not value.is_customer or not value.is_active:
            raise serializers.ValidationError("Choose an active customer.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        equipment = attrs.get("equipment")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The reservation cannot end before it starts."}
            )
        status_value = attrs.get("status", getattr(self.instance, "status", "tentative"))
        if equipment and status_value == EquipmentReservation.Status.CONFIRMED:
            try:
                check_availability(
                    equipment,
                    start,
                    end,
                    exclude_reservation=self.instance,
                )
            except LeasingConflict as exc:
                raise serializers.ValidationError({"equipment": str(exc)}) from exc
        return attrs


class EquipmentMovementSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source="equipment.code", read_only=True)
    agreement_number = serializers.CharField(source="agreement.number", read_only=True, default="")

    class Meta:
        model = EquipmentMovement
        fields = [
            "id",
            "number",
            "equipment",
            "equipment_code",
            "agreement",
            "agreement_number",
            "kind",
            "movement_date",
            "expected_return_date",
            "condition",
            "handled_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["number", "handled_by", "created_at", "updated_at"]

    def validate(self, attrs):
        kind = attrs.get("kind")
        if kind == EquipmentMovement.Kind.DISPATCH and not attrs.get("agreement"):
            raise serializers.ValidationError(
                {"agreement": "A dispatch must be linked to a rental agreement."}
            )
        if attrs.get("expected_return_date") and attrs.get("movement_date"):
            if attrs["expected_return_date"] < attrs["movement_date"]:
                raise serializers.ValidationError(
                    {"expected_return_date": "The return date cannot precede dispatch."}
                )
        return attrs


class EquipmentInspectionSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source="equipment.code", read_only=True)
    inspection_type = serializers.CharField(source="kind", read_only=True)

    class Meta:
        model = EquipmentInspection
        fields = [
            "id",
            "equipment",
            "equipment_code",
            "agreement",
            "kind",
            "inspection_type",
            "inspection_date",
            "condition",
            "damage_found",
            "damage_description",
            "charge_amount",
            "inspected_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["inspected_by", "created_at", "updated_at"]

    def validate(self, attrs):
        damage = attrs.get("damage_found", getattr(self.instance, "damage_found", False))
        description = attrs.get(
            "damage_description", getattr(self.instance, "damage_description", "")
        )
        if damage and not description.strip():
            raise serializers.ValidationError({"damage_description": "Describe the damage found."})
        return attrs


class EquipmentMaintenanceSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source="equipment.code", read_only=True)

    class Meta:
        model = EquipmentMaintenance
        fields = [
            "id",
            "equipment",
            "equipment_code",
            "work_order",
            "kind",
            "scheduled_date",
            "completed_date",
            "status",
            "description",
            "vendor",
            "cost",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["completed_date", "created_at", "updated_at"]

    def validate(self, attrs):
        scheduled = attrs.get("scheduled_date", getattr(self.instance, "scheduled_date", None))
        completed = attrs.get("completed_date", getattr(self.instance, "completed_date", None))
        if scheduled and completed and completed < scheduled:
            raise serializers.ValidationError(
                {"completed_date": "Completion cannot precede the scheduled date."}
            )
        return attrs
