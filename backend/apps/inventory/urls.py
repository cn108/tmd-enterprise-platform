from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.inventory import views

app_name = "inventory"

router = DefaultRouter()
router.register("stock-movements", views.StockMovementViewSet, basename="stock-movement")
router.register("stock-receipts", views.StockReceiptViewSet, basename="stock-receipt")
router.register("stock-transfers", views.StockTransferViewSet, basename="stock-transfer")
router.register("stock-issues", views.StockIssueViewSet, basename="stock-issue")
router.register("stock-returns", views.StockReturnViewSet, basename="stock-return")
router.register("stock-adjustments", views.StockAdjustmentViewSet, basename="stock-adjustment")
router.register("stock-damages", views.StockDamageViewSet, basename="stock-damage")
router.register("stock-counts", views.StockCountViewSet, basename="stock-count")
router.register("stock-reservations", views.StockReservationViewSet, basename="stock-reservation")
router.register("reorder-levels", views.ReorderLevelViewSet, basename="reorder-level")

urlpatterns = [
    path("inventory-policy/", views.InventoryPolicyView.as_view(), name="inventory-policy"),
    path("stock-balances/", views.StockBalanceView.as_view(), name="stock-balances"),
    path(
        "inventory-valuation/",
        views.InventoryValuationView.as_view(),
        name="inventory-valuation",
    ),
    path("reorder-alerts/", views.ReorderAlertView.as_view(), name="reorder-alerts"),
    *router.urls,
]
