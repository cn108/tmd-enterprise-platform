from __future__ import annotations

from rest_framework import mixins, viewsets

from apps.catalogue.models import (
    CatalogueItem,
    Certificate,
    ItemBatch,
    ItemPrice,
    Manufacturer,
    ProductCategory,
    SerialNumber,
    TechnicalSpecification,
    UnitOfMeasure,
)
from apps.catalogue.serializers import (
    CatalogueItemSerializer,
    CertificateSerializer,
    ItemBatchSerializer,
    ItemPriceSerializer,
    ManufacturerSerializer,
    ProductCategorySerializer,
    SerialNumberSerializer,
    TechnicalSpecificationSerializer,
    UnitOfMeasureSerializer,
)
from shared.permissions import ModelPermission
from shared.viewsets import ProtectedMasterDataViewSet, ProtectedNoDeleteViewSet


class UnitOfMeasureViewSet(ProtectedMasterDataViewSet):
    queryset = UnitOfMeasure.objects.select_related("base_uom").all()
    serializer_class = UnitOfMeasureSerializer
    search_fields = ("code", "name")


class ProductCategoryViewSet(ProtectedMasterDataViewSet):
    queryset = ProductCategory.objects.select_related("parent").all()
    serializer_class = ProductCategorySerializer
    search_fields = ("code", "name")


class ManufacturerViewSet(ProtectedMasterDataViewSet):
    queryset = Manufacturer.objects.all()
    serializer_class = ManufacturerSerializer
    search_fields = ("code", "name", "country")


class CatalogueItemViewSet(ProtectedMasterDataViewSet):
    queryset = CatalogueItem.objects.select_related("category", "uom", "manufacturer").all()
    serializer_class = CatalogueItemSerializer
    search_fields = ("code", "name", "brand", "description")


class ItemPriceViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Price history is append-only: no update and no delete endpoints."""

    queryset = ItemPrice.objects.select_related("item").all()
    serializer_class = ItemPriceSerializer
    permission_classes = [ModelPermission]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class TechnicalSpecificationViewSet(ProtectedNoDeleteViewSet):
    queryset = TechnicalSpecification.objects.select_related("item").all()
    serializer_class = TechnicalSpecificationSerializer


class ItemBatchViewSet(ProtectedNoDeleteViewSet):
    queryset = ItemBatch.objects.select_related("item").all()
    serializer_class = ItemBatchSerializer


class SerialNumberViewSet(ProtectedNoDeleteViewSet):
    queryset = SerialNumber.objects.select_related("item", "batch").all()
    serializer_class = SerialNumberSerializer


class CertificateViewSet(ProtectedNoDeleteViewSet):
    queryset = Certificate.objects.select_related("item", "batch", "serial", "document").all()
    serializer_class = CertificateSerializer
