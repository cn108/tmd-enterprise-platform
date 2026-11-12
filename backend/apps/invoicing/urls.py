from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.invoicing import views

app_name = "invoicing"

router = DefaultRouter()
router.register("supplier-invoices", views.SupplierInvoiceViewSet, basename="supplier-invoice")
router.register("customer-invoices", views.CustomerInvoiceViewSet, basename="customer-invoice")
router.register("invoice-notes", views.InvoiceNoteViewSet, basename="invoice-note")
router.register("supplier-payments", views.SupplierPaymentViewSet, basename="supplier-payment")
router.register("invoice-settings", views.InvoiceSettingsViewSet, basename="invoice-settings")
router.register("nrs-submissions", views.NrsSubmissionViewSet, basename="nrs-submission")

urlpatterns = router.urls
