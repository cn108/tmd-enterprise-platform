from __future__ import annotations

from apps.organisation.models import CostCentre, Department
from apps.organisation.serializers import CostCentreSerializer, DepartmentSerializer
from shared.viewsets import ProtectedMasterDataViewSet


class DepartmentViewSet(ProtectedMasterDataViewSet):
    queryset = Department.objects.select_related("parent").all()
    serializer_class = DepartmentSerializer
    search_fields = ("code", "name")


class CostCentreViewSet(ProtectedMasterDataViewSet):
    queryset = CostCentre.objects.select_related("parent", "department").all()
    serializer_class = CostCentreSerializer
    search_fields = ("code", "name", "description")
