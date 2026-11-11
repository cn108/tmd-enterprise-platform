from __future__ import annotations

from rest_framework import serializers

from apps.projects.models import ContractRevision, CustomerContract, Project, ProjectLocation


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "code",
            "name",
            "customer",
            "managers",
            "status",
            "start_date",
            "end_date",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_customer(self, value):
        if value is not None and not value.is_customer:
            raise serializers.ValidationError("The selected party is not a customer.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The end date cannot precede the start date."}
            )

        requested = attrs.get("status")
        if self.instance is None:
            if requested and requested != Project.Status.DRAFT:
                raise serializers.ValidationError(
                    {"status": "New projects start as draft; transitions are then validated."}
                )
            return attrs

        current = self.instance.status
        if requested and requested != current:
            allowed = Project.ALLOWED_TRANSITIONS[current]
            if requested not in allowed:
                raise serializers.ValidationError(
                    {"status": f"Cannot move a {current} project to {requested}."}
                )
        return attrs


class ProjectLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLocation
        fields = [
            "id",
            "project",
            "name",
            "address",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CustomerContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerContract
        fields = [
            "id",
            "project",
            "customer",
            "reference",
            "value",
            "currency",
            "start_date",
            "end_date",
            "terms",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_customer(self, value):
        if not value.is_customer:
            raise serializers.ValidationError("The selected party is not a customer.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The end date cannot precede the start date."}
            )
        return attrs


class ContractRevisionSerializer(serializers.ModelSerializer):
    revision_number = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = ContractRevision
        fields = [
            "id",
            "contract",
            "revision_number",
            "value",
            "currency",
            "start_date",
            "end_date",
            "terms",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        # The unique-together validator would make the auto-assigned revision
        # number mandatory; numbering and duplicates are handled in create().
        validators: list = []

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The end date cannot precede the start date."}
            )
        return attrs

    def create(self, validated_data):
        contract = validated_data["contract"]
        if "revision_number" not in validated_data:
            latest = (
                ContractRevision.objects.filter(contract=contract)
                .order_by("-revision_number")
                .first()
            )
            validated_data["revision_number"] = (latest.revision_number + 1) if latest else 1
        elif ContractRevision.objects.filter(
            contract=contract, revision_number=validated_data["revision_number"]
        ).exists():
            raise serializers.ValidationError(
                {"revision_number": "This revision number already exists for the contract."}
            )
        return super().create(validated_data)
