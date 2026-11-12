from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.projects.models import (
    BudgetLine,
    ContractRevision,
    CustomerContract,
    Project,
    ProjectBudget,
    ProjectCost,
    ProjectLocation,
    ProjectMilestone,
)


class ProjectSerializer(serializers.ModelSerializer):
    project_manager_email = serializers.CharField(
        source="project_manager.email", read_only=True, default=""
    )
    department_code = serializers.CharField(source="department.code", read_only=True, default="")
    cost_centre_code = serializers.CharField(
        source="cost_centre.code", read_only=True, default=""
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "code",
            "name",
            "customer",
            "managers",
            "project_manager",
            "project_manager_email",
            "department",
            "department_code",
            "cost_centre",
            "cost_centre_code",
            "status",
            "start_date",
            "end_date",
            "actual_completion_date",
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
    project_code = serializers.CharField(source="project.code", read_only=True)

    class Meta:
        model = ProjectLocation
        fields = [
            "id",
            "project",
            "project_code",
            "name",
            "address",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CustomerContractSerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source="project.code", read_only=True)
    customer_name = serializers.CharField(source="customer.legal_name", read_only=True)

    class Meta:
        model = CustomerContract
        fields = [
            "id",
            "project",
            "project_code",
            "customer",
            "customer_name",
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
    contract_reference = serializers.CharField(source="contract.reference", read_only=True)

    class Meta:
        model = ContractRevision
        fields = [
            "id",
            "contract",
            "contract_reference",
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


class BudgetLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetLine
        fields = ["id", "cost_centre", "category", "description", "amount"]

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("A budget line cannot be negative.")
        return value


class ProjectBudgetSerializer(serializers.ModelSerializer):
    lines = BudgetLineSerializer(many=True)
    total_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True)
    approved_by = serializers.SerializerMethodField()
    approvals_required = serializers.SerializerMethodField()
    approvals_recorded = serializers.SerializerMethodField()
    approval_policy = serializers.SerializerMethodField()

    class Meta:
        model = ProjectBudget
        fields = [
            "id",
            "project",
            "project_code",
            "version",
            "currency",
            "revision_reason",
            "notes",
            "status",
            "total_value",
            "approved_by",
            "approved_at",
            "approvals_required",
            "approvals_recorded",
            "approval_policy",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "version",
            "status",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        # The version is assigned server-side, so the unique-together check
        # cannot run against the client payload.
        validators: list = []

    def get_approved_by(self, obj: ProjectBudget) -> str | None:
        return obj.approved_by.email if obj.approved_by else None

    def _state(self, obj: ProjectBudget) -> dict:
        from apps.core.approvals import approval_state

        return approval_state("project_budget", obj.pk, obj.total_value)

    def get_approvals_required(self, obj: ProjectBudget) -> int:
        return self._state(obj)["required"]

    def get_approvals_recorded(self, obj: ProjectBudget) -> int:
        return self._state(obj)["recorded"]

    def get_approval_policy(self, obj: ProjectBudget) -> str | None:
        return self._state(obj)["policy"]

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("A budget needs at least one line.")
        return value

    def validate(self, attrs):
        if self.instance and self.instance.status == ProjectBudget.Status.APPROVED:
            raise serializers.ValidationError(
                "An approved budget cannot be edited; raise a new version instead."
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        project = validated_data["project"]
        latest = ProjectBudget.objects.filter(project=project).order_by("-version").first()
        budget = ProjectBudget.objects.create(
            version=(latest.version + 1) if latest else 1, **validated_data
        )
        for line in lines:
            BudgetLine.objects.create(budget=budget, **line)
        return budget

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                BudgetLine.objects.create(budget=instance, **line)
        return instance


class ProjectCostSerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source="project.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.legal_name", read_only=True, default="")
    approved_by_email = serializers.CharField(
        source="approved_by.email", read_only=True, default=""
    )

    class Meta:
        model = ProjectCost
        fields = [
            "id",
            "project",
            "project_code",
            "cost_date",
            "category",
            "description",
            "supplier",
            "supplier_name",
            "amount",
            "currency",
            "reference",
            "source_type",
            "source_id",
            "status",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "rejection_reason",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "rejection_reason",
            "source_type",
            "source_id",
            "created_at",
            "updated_at",
        ]

    def validate_supplier(self, value):
        if value is not None and (not value.is_supplier or not value.is_active):
            raise serializers.ValidationError("Choose an active supplier.")
        return value

    def validate(self, attrs):
        if self.instance and self.instance.status != ProjectCost.Status.DRAFT:
            raise serializers.ValidationError("Only a draft direct cost can be edited.")
        return attrs


class ProjectMilestoneSerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source="project.code", read_only=True)

    class Meta:
        model = ProjectMilestone
        fields = [
            "id",
            "project",
            "project_code",
            "name",
            "due_date",
            "completed_on",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
