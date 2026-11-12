from __future__ import annotations

from apps.warehousing.models import StorageLocation, Warehouse
from apps.warehousing.serializers import StorageLocationSerializer, WarehouseSerializer
from shared.viewsets import ProtectedMasterDataViewSet


class WarehouseViewSet(ProtectedMasterDataViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    search_fields = ("code", "name", "site_name")


class StorageLocationViewSet(ProtectedMasterDataViewSet):
    queryset = StorageLocation.objects.select_related("warehouse").all()
    serializer_class = StorageLocationSerializer
    search_fields = ("code", "name", "warehouse__code")
