from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.parties import views

app_name = "parties"

router = DefaultRouter()
router.register("supplier-categories", views.SupplierCategoryViewSet, basename="supplier-category")
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("contacts", views.ContactViewSet, basename="contact")
router.register("addresses", views.AddressViewSet, basename="address")
router.register("tax-registrations", views.TaxRegistrationViewSet, basename="tax-registration")
router.register("bank-accounts", views.BankAccountViewSet, basename="bank-account")
router.register(
    "compliance-documents", views.ComplianceDocumentViewSet, basename="compliance-document"
)

urlpatterns = router.urls
