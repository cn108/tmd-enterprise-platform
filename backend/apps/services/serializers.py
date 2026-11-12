from __future__ import annotations

from rest_framework import serializers

from apps.services.models import (
    HseRecord,
    ServiceChecklistItem,
    ServiceContract,
    WorkOrder,
    WorkOrderAssignment,
    WorkOrderProgress,
    WorkOrderReport,
)


class ServiceContractSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True, default="")
    approved_by_email = serializers.CharField(
        source="approved_by.email", read_only=True, default=""
    )

    class Meta:
        model = ServiceContract
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "project",
            "project_code",
            "kind",
            "title",
            "start_date",
            "end_date",
            "value",
            "currency",
            "status",
            "terms",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "created_at",
            "updated_at",
        ]

    def validate_customer(self, value):
        if not value.is_customer or not value.is_active:
            raise serializers.ValidationError("Choose an active customer.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The contract cannot end before it starts."}
            )
        if self.instance and self.instance.status != ServiceContract.Status.DRAFT:
            raise serializers.ValidationError("Only a draft service contract can be edited.")
        return attrs


class WorkOrderAssignmentSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)

    class Meta:
        model = WorkOrderAssignment
        fields = [
            "id",
            "work_order",
            "work_order_number",
            "user",
            "user_email",
            "role",
            "planned_hours",
            "actual_hours",
            "assigned_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["assigned_at", "created_at", "updated_at"]

    def validate_work_order(self, value):
        if value.status in {
            WorkOrder.Status.COMPLETED,
            WorkOrder.Status.ACCEPTED,
            WorkOrder.Status.CANCELLED,
        }:
            raise serializers.ValidationError("Closed work cannot receive assignments.")
        return value


class WorkOrderProgressSerializer(serializers.ModelSerializer):
    reported_by_email = serializers.CharField(
        source="reported_by.email", read_only=True, default=""
    )

    class Meta:
        model = WorkOrderProgress
        fields = [
            "id",
            "work_order",
            "progress_date",
            "percent_complete",
            "notes",
            "labour_hours",
            "materials_used",
            "reported_by",
            "reported_by_email",
            "created_at",
        ]
        read_only_fields = fields


class ServiceChecklistItemSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = ServiceChecklistItem
        fields = [
            "id",
            "work_order",
            "sequence",
            "description",
            "is_required",
            "is_completed",
            "status",
            "completed_by",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["completed_by", "completed_at", "created_at", "updated_at"]

    def get_status(self, obj: ServiceChecklistItem) -> str:
        return "completed" if obj.is_completed else "open"


class HseRecordSerializer(serializers.ModelSerializer):
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)
    recorded_by_email = serializers.CharField(
        source="recorded_by.email", read_only=True, default=""
    )

    class Meta:
        model = HseRecord
        fields = [
            "id",
            "work_order",
            "work_order_number",
            "kind",
            "record_date",
            "description",
            "outcome",
            "recorded_by",
            "recorded_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["recorded_by", "created_at", "updated_at"]


class WorkOrderReportSerializer(serializers.ModelSerializer):
    work_order_number = serializers.CharField(source="work_order.number", read_only=True)
    submitted_by_email = serializers.CharField(
        source="submitted_by.email", read_only=True, default=""
    )
    accepted_by_email = serializers.CharField(
        source="accepted_by.email", read_only=True, default=""
    )

    class Meta:
        model = WorkOrderReport
        fields = [
            "id",
            "work_order",
            "work_order_number",
            "summary",
            "findings",
            "recommendations",
            "completed_on",
            "status",
            "submitted_by",
            "submitted_by_email",
            "submitted_at",
            "accepted_by",
            "accepted_by_email",
            "accepted_at",
            "customer_representative",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "submitted_by",
            "submitted_by_email",
            "submitted_at",
            "accepted_by",
            "accepted_by_email",
            "accepted_at",
            "customer_representative",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

    def validate_work_order(self, value):
        if (
            WorkOrderReport.objects.filter(work_order=value)
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            raise serializers.ValidationError("This work order already has a report.")
        return value

    def validate_summary(self, value):
        if not value.strip():
            raise serializers.ValidationError("A report summary is required.")
        return value


class WorkOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name", read_only=True, default="")
    project_code = serializers.CharField(source="project.code", read_only=True, default="")
    contract_number = serializers.CharField(
        source="service_contract.number", read_only=True, default=""
    )
    supervisor_email = serializers.CharField(source="supervisor.email", read_only=True, default="")
    requested_by_email = serializers.CharField(
        source="requested_by.email", read_only=True, default=""
    )
    assignments = WorkOrderAssignmentSerializer(many=True, read_only=True)
    checklist = ServiceChecklistItemSerializer(many=True, read_only=True)
    report_status = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "number",
            "service_contract",
            "contract_number",
            "project",
            "project_code",
            "customer",
            "customer_name",
            "request_type",
            "priority",
            "status",
            "title",
            "description",
            "site",
            "supervisor",
            "supervisor_email",
            "requested_by",
            "requested_by_email",
            "scheduled_start",
            "scheduled_end",
            "actual_start",
            "actual_end",
            "progress_percent",
            "hse_requirements",
            "notes",
            "assignments",
            "checklist",
            "report_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "actual_start",
            "actual_end",
            "progress_percent",
            "requested_by",
            "requested_by_email",
            "created_at",
            "updated_at",
        ]

    def get_report_status(self, obj: WorkOrder) -> str:
        report = getattr(obj, "completion_report", None)
        return report.status if report else ""

    def validate(self, attrs):
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        if customer is not None and not customer.is_customer:
            raise serializers.ValidationError({"customer": "Choose a customer party."})
        scheduled_start = attrs.get(
            "scheduled_start", getattr(self.instance, "scheduled_start", None)
        )
        scheduled_end = attrs.get("scheduled_end", getattr(self.instance, "scheduled_end", None))
        if scheduled_start and scheduled_end and scheduled_end < scheduled_start:
            raise serializers.ValidationError(
                {"scheduled_end": "Scheduled end cannot precede the start."}
            )
        if self.instance and self.instance.status not in {
            WorkOrder.Status.DRAFT,
            WorkOrder.Status.SCHEDULED,
            WorkOrder.Status.ON_HOLD,
        }:
            raise serializers.ValidationError(
                "This work order is beyond the editable planning states."
            )
        return attrs
