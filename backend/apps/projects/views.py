from __future__ import annotations

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.approvals import ApprovalError, creator_cannot_decide, register_approval
from apps.core.models import create_audit_event
from apps.documents.models import DocumentLink
from apps.documents.services import attach_upload
from apps.projects.costing import cost_summary, dashboard_rows, profitability
from apps.projects.models import (
    ContractRevision,
    CustomerContract,
    Project,
    ProjectBudget,
    ProjectCost,
    ProjectLocation,
    ProjectMilestone,
)
from apps.projects.serializers import (
    ContractRevisionSerializer,
    CustomerContractSerializer,
    ProjectBudgetSerializer,
    ProjectCostSerializer,
    ProjectLocationSerializer,
    ProjectMilestoneSerializer,
    ProjectSerializer,
)
from shared.exceptions import error_response
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet


class ProjectViewSet(MasterDataViewSet):
    queryset = (
        Project.objects.select_related("customer", "project_manager", "department", "cost_centre")
        .prefetch_related("managers")
        .all()
    )
    serializer_class = ProjectSerializer
    search_fields = ("code", "name", "customer__legal_name")

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = (self.request.query_params.get("status") or "").strip()
        if status_filter in Project.Status.values:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=True, methods=["get"])
    def cost_summary(self, request, pk=None):
        return Response(cost_summary(self.get_object()))

    @action(detail=True, methods=["get"])
    def profitability(self, request, pk=None):
        return Response(profitability(self.get_object()))

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def attach(self, request, pk=None):
        if not request.user.has_perm("projects.change_project"):
            raise PermissionDenied("You do not have permission to attach project documents.")
        project = self.get_object()
        document, link = attach_upload(
            upload=request.FILES.get("file"),
            title=request.data.get("title", ""),
            entity_type=DocumentLink.EntityType.PROJECT,
            entity_id=project.pk,
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

    @action(detail=True, methods=["get"])
    def documents(self, request, pk=None):
        project = self.get_object()
        links = DocumentLink.objects.filter(
            entity_type=DocumentLink.EntityType.PROJECT, entity_id=project.pk
        ).select_related("document")
        return Response(
            {
                "count": links.count(),
                "results": [
                    {
                        "id": link.pk,
                        "document": link.document_id,
                        "title": link.document.title,
                        "original_filename": link.document.original_filename,
                        "download_path": f"/api/v1/documents/{link.document_id}/download/",
                        "created_at": link.document.created_at.isoformat(),
                    }
                    for link in links
                ],
            }
        )


class ProjectLocationViewSet(MasterDataViewSet):
    queryset = ProjectLocation.objects.select_related("project").all()
    serializer_class = ProjectLocationSerializer
    search_fields = ("project__code", "name", "address")


class CustomerContractViewSet(MasterDataViewSet):
    queryset = CustomerContract.objects.select_related("project", "customer").all()
    serializer_class = CustomerContractSerializer
    search_fields = ("reference", "project__code", "customer__legal_name")


class ContractRevisionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Revisions are append-only: no update and no delete endpoints."""

    queryset = ContractRevision.objects.select_related("contract").all()
    serializer_class = ContractRevisionSerializer
    search_fields = ("contract__reference", "reason")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class ProjectBudgetViewSet(NoDeleteViewSet):
    queryset = ProjectBudget.objects.select_related("project", "approved_by").prefetch_related(
        "lines"
    )
    serializer_class = ProjectBudgetSerializer
    search_fields = ("project__code", "project__name", "notes")
    ordering_fields = ("project__code", "version", "status", "created_at", "approved_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        project = (self.request.query_params.get("project") or "").strip()
        if project:
            queryset = queryset.filter(project_id=project)
        status_filter = (self.request.query_params.get("status") or "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not request.user.has_perm("projects.approve_projectbudget"):
            raise PermissionDenied("You do not have permission to approve budgets.")
        budget = self.get_object()
        if budget.status == ProjectBudget.Status.APPROVED:
            return error_response(
                "invalid_state", "This budget is already approved.", status.HTTP_409_CONFLICT
            )
        if creator_cannot_decide(request.user, budget.created_by_id):
            return error_response(
                "segregation_of_duties",
                "A budget cannot be approved by the person who raised it.",
                status.HTTP_409_CONFLICT,
            )
        if not budget.lines.exists():
            return error_response(
                "invalid_state", "A budget needs at least one line.", status.HTTP_409_CONFLICT
            )
        try:
            outcome = register_approval(
                document_type="project_budget",
                document_id=budget.pk,
                approver=request.user,
                amount=budget.total_value,
                creators={budget.created_by_id},
            )
        except ApprovalError as exc:
            return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)
        if outcome.final:
            budget.status = ProjectBudget.Status.APPROVED
            budget.approved_by = request.user
            budget.approved_at = timezone.now()
            budget.updated_by = request.user
            budget.save(
                update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
            )
        return Response(ProjectBudgetSerializer(budget).data)


class ProjectCostViewSet(NoDeleteViewSet):
    queryset = ProjectCost.objects.select_related("project", "supplier", "approved_by").all()
    serializer_class = ProjectCostSerializer
    search_fields = ("project__code", "project__name", "description", "reference")
    ordering_fields = ("project__code", "cost_date", "amount", "status", "created_at")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            if not request.user.has_perm("projects.view_projectcost"):
                raise PermissionDenied("You do not have permission to view project costs.")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("project", "status", "category"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        if not request.user.has_perm("projects.add_projectcost"):
            raise PermissionDenied("You do not have permission to add project costs.")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not request.user.has_perm("projects.change_projectcost"):
            raise PermissionDenied("You do not have permission to change project costs.")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        create_audit_event(
            actor=self.request.user,
            action="project_cost.created",
            entity_type="projects.projectcost",
            entity_id=serializer.instance.pk,
            after={
                "project": serializer.instance.project_id,
                "amount": str(serializer.instance.amount),
            },
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not request.user.has_perm("projects.approve_projectcost"):
            raise PermissionDenied("You do not have permission to approve project costs.")
        cost = self.get_object()
        if cost.status == ProjectCost.Status.APPROVED:
            return error_response(
                "invalid_state", "This cost is already approved.", status.HTTP_409_CONFLICT
            )
        if creator_cannot_decide(request.user, cost.created_by_id):
            return error_response(
                "segregation_of_duties",
                "A direct cost cannot be approved by the person who recorded it.",
                status.HTTP_409_CONFLICT,
            )
        try:
            outcome = register_approval(
                document_type="project_cost",
                document_id=cost.pk,
                approver=request.user,
                amount=cost.amount,
                creators={cost.created_by_id},
            )
        except ApprovalError as exc:
            return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)
        if outcome.final:
            cost.status = ProjectCost.Status.APPROVED
            cost.approved_by = request.user
            cost.approved_at = timezone.now()
            cost.updated_by = request.user
            cost.save(
                update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
            )
        return Response(ProjectCostSerializer(cost).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not request.user.has_perm("projects.approve_projectcost"):
            raise PermissionDenied("You do not have permission to reject project costs.")
        cost = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if cost.status == ProjectCost.Status.APPROVED:
            return error_response(
                "invalid_state", "An approved cost cannot be rejected.", status.HTTP_409_CONFLICT
            )
        if not reason:
            return error_response(
                "invalid_request", "A rejection reason is required.", status.HTTP_400_BAD_REQUEST
            )
        cost.status = ProjectCost.Status.REJECTED
        cost.rejection_reason = reason
        cost.updated_by = request.user
        cost.save(update_fields=["status", "rejection_reason", "updated_by", "updated_at"])
        create_audit_event(
            actor=request.user,
            action="project_cost.rejected",
            entity_type="projects.projectcost",
            entity_id=cost.pk,
            after={"reason": reason},
            request=request,
        )
        return Response(ProjectCostSerializer(cost).data)


def _paged(request, rows: list[dict]) -> Response:
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
        size = min(max(int(request.query_params.get("page_size", "25")), 1), 100)
    except ValueError:
        page, size = 1, 25
    start = (page - 1) * size
    return Response({"count": len(rows), "results": rows[start : start + size]})


class ProjectDashboardView(APIView):
    def get(self, request):
        if not request.user.has_perm("projects.view_project"):
            raise PermissionDenied("You do not have permission to view projects.")
        return _paged(request, dashboard_rows())


class ProjectProfitabilityView(APIView):
    def get(self, request):
        if not request.user.has_perm("projects.view_project"):
            raise PermissionDenied("You do not have permission to view projects.")
        rows = []
        for project in Project.objects.all():
            estimate = profitability(project)
            rows.append(
                {
                    "id": project.pk,
                    "code": project.code,
                    "name": project.name,
                    "currency": estimate["currency"],
                    "contract_value": estimate["contract_value"],
                    "actual_cost": estimate["actual_cost"],
                    "open_commitments": estimate["open_commitments"],
                    "estimated_cost_to_complete": estimate["estimated_cost_to_complete"],
                    "estimated_margin": estimate["estimated_margin"],
                    "estimated_margin_percent": estimate["estimated_margin_percent"],
                    "revenue_recognised": estimate["revenue_recognised"],
                }
            )
        return _paged(request, rows)


class ProjectDocumentListView(APIView):
    def get(self, request):
        if not request.user.has_perm("projects.view_project"):
            raise PermissionDenied("You do not have permission to view projects.")
        project_id = request.query_params.get("project")
        links = DocumentLink.objects.filter(entity_type=DocumentLink.EntityType.PROJECT)
        if project_id:
            links = links.filter(entity_id=project_id)
        links = links.select_related("document")
        rows = [
            {
                "id": link.pk,
                "project": link.entity_id,
                "document": link.document_id,
                "title": link.document.title,
                "original_filename": link.document.original_filename,
                "download_path": f"/api/v1/documents/{link.document_id}/download/",
                "created_at": link.document.created_at.isoformat(),
            }
            for link in links
        ]
        return _paged(request, rows)


class ProjectMilestoneViewSet(MasterDataViewSet):
    queryset = ProjectMilestone.objects.select_related("project").all()
    serializer_class = ProjectMilestoneSerializer
    search_fields = ("project__code", "name", "notes")
    ordering_fields = ("project__code", "due_date", "completed_on", "name")

    def get_queryset(self):
        queryset = super().get_queryset()
        project = (self.request.query_params.get("project") or "").strip()
        if project:
            queryset = queryset.filter(project_id=project)
        return queryset
