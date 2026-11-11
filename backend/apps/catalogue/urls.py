from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.catalogue import views

app_name = "catalogue"

router = DefaultRouter()
router.register("catalogue-items", views.CatalogueItemViewSet, basename="catalogue-item")
router.register("product-categories", views.ProductCategoryViewSet, basename="product-category")
router.register("units-of-measure", views.UnitOfMeasureViewSet, basename="unit-of-measure")
router.register("manufacturers", views.ManufacturerViewSet, basename="manufacturer")
router.register("item-prices", views.ItemPriceViewSet, basename="item-price")
router.register(
    "technical-specifications",
    views.TechnicalSpecificationViewSet,
    basename="technical-specification",
)
router.register("item-batches", views.ItemBatchViewSet, basename="item-batch")
router.register("serial-numbers", views.SerialNumberViewSet, basename="serial-number")
router.register("certificates", views.CertificateViewSet, basename="certificate")

urlpatterns = router.urls
