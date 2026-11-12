from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.procurement import views

app_name = "procurement"

router = DefaultRouter()
router.register("destinations", views.DestinationViewSet, basename="destination")
router.register("purchase-requests", views.PurchaseRequestViewSet, basename="purchase-request")
router.register(
    "purchase-request-lines", views.PurchaseRequestLineViewSet, basename="purchase-request-line"
)
router.register("rfqs", views.RequestForQuotationViewSet, basename="rfq")
router.register("rfq-suppliers", views.RfqSupplierViewSet, basename="rfq-supplier")
router.register("supplier-quotes", views.SupplierQuoteViewSet, basename="supplier-quote")
router.register(
    "supplier-selections", views.SupplierSelectionViewSet, basename="supplier-selection"
)
router.register("purchase-orders", views.PurchaseOrderViewSet, basename="purchase-order")
router.register(
    "purchase-order-lines",
    views.PurchaseOrderLineViewSet,
    basename="purchase-order-line",
)
router.register("delivery-schedules", views.DeliveryScheduleViewSet, basename="delivery-schedule")
router.register("goods-receipts", views.GoodsReceiptNoteViewSet, basename="goods-receipt")
router.register(
    "goods-receipt-lines", views.GoodsReceiptLineViewSet, basename="goods-receipt-line"
)

urlpatterns = router.urls
