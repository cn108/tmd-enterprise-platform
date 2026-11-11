from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.warehousing import views

app_name = "warehousing"

router = DefaultRouter()
router.register("warehouses", views.WarehouseViewSet, basename="warehouse")
router.register("storage-locations", views.StorageLocationViewSet, basename="storage-location")

urlpatterns = router.urls
