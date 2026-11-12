from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.services import views

app_name = "services"

router = DefaultRouter()
router.register("service-contracts", views.ServiceContractViewSet, basename="service-contract")
router.register("work-orders", views.WorkOrderViewSet, basename="work-order")
router.register(
    "work-order-assignments",
    views.WorkOrderAssignmentViewSet,
    basename="work-order-assignment",
)
router.register(
    "work-order-progress",
    views.WorkOrderProgressViewSet,
    basename="work-order-progress",
)
router.register(
    "service-checklists",
    views.ServiceChecklistViewSet,
    basename="service-checklist",
)
router.register("hse-records", views.HseRecordViewSet, basename="hse-record")
router.register("work-order-reports", views.WorkOrderReportViewSet, basename="work-order-report")

urlpatterns = router.urls
