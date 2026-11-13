from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from apps.core.models import create_audit_event
from apps.documents.models import DocumentLink
from apps.documents.services import attach_upload
from apps.services.models import (
    HseRecord,
    ServiceChecklistItem,
    ServiceContract,
    WorkOrder,
    WorkOrderAssignment,
    WorkOrderProgress,
    WorkOrderReport,
)
from apps.services.serializers import (
    HseRecordSerializer,
    ServiceChecklistItemSerializer,
    ServiceContractSerializer,
    WorkOrderAssignmentSerializer,
    WorkOrderProgressSerializer,
    WorkOrderReportSerializer,
    WorkOrderSerializer,
)
from apps.services.workflows import (
    ServiceConflict,
    accept_work_order,
    activate_contract,
    assign_person,
    complete_work_order,
    create_contract_number,
    create_work_order_number,
    schedule_work_order,
    start_work_order,
    submit_report,
    update_progress,
)
from shared.exceptions import error_response
from shared.viewsets import NoDeleteViewSet

User = get_user_model()


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


def _conflict(exc: ServiceConflict) -> Response:
    return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)


class ServicePermissionMixin:
    view_permission = ""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in SAFE_METHODS and self.view_permission:
            _require(request, self.view_permission)


class ServiceContractViewSet(ServicePermissionMixin, NoDeleteViewSet):
    view_permission = "services.view_servicecontract"
    queryset = ServiceContract.objects.select_related("customer", "project", "approved_by").all()
    serializer_class = ServiceContractSerializer
    search_fields = ("number", "title", "customer__legal_name", "project__code")

    def create(self, request, *args, **kwargs):
        _require(request, "services.add_servicecontract")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "services.change_servicecontract")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            number=create_contract_number(),
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        _require(request, "services.approve_servicecontract")
        try:
            contract = activate_contract(self.get_object(), request.user)
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(contract).data)


class WorkOrderViewSet(ServicePermissionMixin, NoDeleteViewSet):
    view_permission = "services.view_workorder"
    queryset = (
        WorkOrder.objects.select_related(
            "service_contract", "project", "customer", "supervisor", "requested_by"
        )
        .prefetch_related("assignments", "checklist")
        .all()
    )
    serializer_class = WorkOrderSerializer
    search_fields = ("number", "title", "site", "project__code", "customer__legal_name")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("status", "project", "request_type", "priority", "supervisor"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "services.add_workorder")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "services.change_workorder")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            number=create_work_order_number(),
            requested_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        _require(request, "services.change_workorder")
        try:
            work_order = schedule_work_order(
                self.get_object(),
                request.user,
                start=request.data.get("scheduled_start") or None,
                end=request.data.get("scheduled_end") or None,
            )
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        _require(request, "services.change_workorder")
        try:
            work_order = start_work_order(
                self.get_object(), request.user, started_on=request.data.get("actual_start") or None
            )
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=["post"])
    def progress(self, request, pk=None):
        _require(request, "services.change_workorder")
        try:
            percent = int(request.data.get("percent_complete", 0))
        except (TypeError, ValueError):
            return error_response(
                "invalid_request", "Progress must be a number.", status.HTTP_400_BAD_REQUEST
            )
        try:
            work_order = update_progress(
                self.get_object(),
                request.user,
                percent=percent,
                notes=(request.data.get("notes") or "").strip(),
                labour_hours=request.data.get("labour_hours") or None,
                materials_used=(request.data.get("materials_used") or "").strip(),
            )
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=["post"])
    def hold(self, request, pk=None):
        _require(request, "services.change_workorder")
        work_order = self.get_object()
        if work_order.status != WorkOrder.Status.IN_PROGRESS:
            return error_response(
                "invalid_state", "Only work in progress can be held.", status.HTTP_409_CONFLICT
            )
        work_order.status = WorkOrder.Status.ON_HOLD
        work_order.updated_by = request.user
        work_order.save(update_fields=["status", "updated_by", "updated_at"])
        create_audit_event(
            actor=request.user,
            action="work_order.held",
            entity_type="services.workorder",
            entity_id=work_order.pk,
            after={"status": work_order.status},
            request=request,
        )
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        _require(request, "services.change_workorder")
        work_order = self.get_object()
        if work_order.status != WorkOrder.Status.ON_HOLD:
            return error_response(
                "invalid_state", "Only on-hold work can be resumed.", status.HTTP_409_CONFLICT
            )
        work_order.status = WorkOrder.Status.IN_PROGRESS
        work_order.updated_by = request.user
        work_order.save(update_fields=["status", "updated_by", "updated_at"])
        create_audit_event(
            actor=request.user,
            action="work_order.resumed",
            entity_type="services.workorder",
            entity_id=work_order.pk,
            after={"status": work_order.status},
            request=request,
        )
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        _require(request, "services.assign_workorder")
        user_id = request.data.get("user")
        user = User.objects.filter(pk=user_id).first() if user_id else None
        if user is None:
            return error_response(
                "not_found", "Choose an employee to assign.", status.HTTP_404_NOT_FOUND
            )
        try:
            assignment = assign_person(
                self.get_object(),
                request.user,
                user=user,
                role=(request.data.get("role") or "").strip(),
                planned_hours=request.data.get("planned_hours") or None,
            )
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(
            WorkOrderAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        _require(request, "services.complete_workorder")
        try:
            work_order = complete_work_order(self.get_object(), request.user)
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        _require(request, "services.accept_workorder")
        try:
            work_order = accept_work_order(
                self.get_object(),
                request.user,
                representative=(request.data.get("customer_representative") or "").strip(),
            )
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(work_order).data)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def attach(self, request, pk=None):
        _require(request, "services.change_workorder")
        work_order = self.get_object()
        document, link = attach_upload(
            upload=request.FILES.get("file"),
            title=request.data.get("title", ""),
            entity_type=DocumentLink.EntityType.WORK_ORDER,
            entity_id=work_order.pk,
            user=request.user,
            request=request,
        )
        return Response(
            {
                "id": link.pk,
                "document": document.pk,
                "title": document.title,
                "original_filename": document.original_filename,
                "download_path": f"/api/v1/documents/{document.pk}/download/",
            },
            status=status.HTTP_201_CREATED,
        )


class WorkOrderAssignmentViewSet(ServicePermissionMixin, NoDeleteViewSet):
    view_permission = "services.view_workorderassignment"
    queryset = WorkOrderAssignment.objects.select_related("work_order", "user").all()
    serializer_class = WorkOrderAssignmentSerializer
    search_fields = ("work_order__number", "user__email", "role")

    def create(self, request, *args, **kwargs):
        _require(request, "services.assign_workorder")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            assigned_at=timezone.now(),
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class WorkOrderProgressViewSet(ServicePermissionMixin, viewsets.ReadOnlyModelViewSet):
    view_permission = "services.view_workorderprogress"
    queryset = WorkOrderProgress.objects.select_related("work_order", "reported_by").all()
    serializer_class = WorkOrderProgressSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        work_order = self.request.query_params.get("work_order")
        if work_order:
            queryset = queryset.filter(work_order_id=work_order)
        return queryset


class ServiceChecklistViewSet(ServicePermissionMixin, NoDeleteViewSet):
    view_permission = "services.view_servicechecklistitem"
    queryset = ServiceChecklistItem.objects.select_related("work_order", "completed_by").all()
    serializer_class = ServiceChecklistItemSerializer
    search_fields = ("work_order__number", "description")

    def create(self, request, *args, **kwargs):
        _require(request, "services.change_workorder")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "services.change_workorder")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        _require(request, "services.change_workorder")
        item = self.get_object()
        if item.work_order.status in {
            WorkOrder.Status.COMPLETED,
            WorkOrder.Status.ACCEPTED,
            WorkOrder.Status.CANCELLED,
        }:
            return error_response(
                "invalid_state", "This work order is closed.", status.HTTP_409_CONFLICT
            )
        item.is_completed = True
        item.completed_by = request.user
        item.completed_at = timezone.now()
        item.updated_by = request.user
        item.save(
            update_fields=[
                "is_completed",
                "completed_by",
                "completed_at",
                "updated_by",
                "updated_at",
            ]
        )
        return Response(self.get_serializer(item).data)


class HseRecordViewSet(ServicePermissionMixin, NoDeleteViewSet):
    view_permission = "services.view_hserecord"
    queryset = HseRecord.objects.select_related("work_order", "recorded_by").all()
    serializer_class = HseRecordSerializer
    search_fields = ("work_order__number", "description")

    def create(self, request, *args, **kwargs):
        _require(request, "services.change_workorder")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            recorded_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class WorkOrderReportViewSet(ServicePermissionMixin, NoDeleteViewSet):
    view_permission = "services.view_workorderreport"
    queryset = WorkOrderReport.objects.select_related(
        "work_order", "submitted_by", "accepted_by"
    ).all()
    serializer_class = WorkOrderReportSerializer
    search_fields = ("work_order__number", "summary")

    def create(self, request, *args, **kwargs):
        _require(request, "services.change_workorder")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "services.change_workorder")
        report = self.get_object()
        if report.status == WorkOrderReport.Status.ACCEPTED:
            return error_response(
                "invalid_state", "An accepted report cannot be edited.", status.HTTP_409_CONFLICT
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "services.change_workorder")
        try:
            report = submit_report(self.get_object(), request.user)
        except ServiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "services.complete_workorder")
        report = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if report.status != WorkOrderReport.Status.SUBMITTED or not reason:
            return error_response(
                "invalid_state",
                "A submitted report and a reason are required.",
                status.HTTP_409_CONFLICT,
            )
        report.status = WorkOrderReport.Status.REJECTED
        report.rejection_reason = reason
        report.updated_by = request.user
        report.save(update_fields=["status", "rejection_reason", "updated_by", "updated_at"])
        return Response(self.get_serializer(report).data)
