from __future__ import annotations

from rest_framework import mixins, viewsets

from apps.projects.models import ContractRevision, CustomerContract, Project, ProjectLocation
from apps.projects.serializers import (
    ContractRevisionSerializer,
    CustomerContractSerializer,
    ProjectLocationSerializer,
    ProjectSerializer,
)
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet


class ProjectViewSet(MasterDataViewSet):
    queryset = Project.objects.select_related("customer").prefetch_related("managers").all()
    serializer_class = ProjectSerializer
    search_fields = ("code", "name", "customer__legal_name")


class ProjectLocationViewSet(NoDeleteViewSet):
    queryset = ProjectLocation.objects.select_related("project").all()
    serializer_class = ProjectLocationSerializer


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

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
