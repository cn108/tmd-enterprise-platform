from __future__ import annotations

from apps.parties.models import (
    Address,
    BankAccount,
    ComplianceDocument,
    Contact,
    Party,
    SupplierCategory,
    TaxRegistration,
)
from apps.parties.serializers import (
    AddressSerializer,
    BankAccountSerializer,
    ComplianceDocumentSerializer,
    ContactSerializer,
    CustomerSerializer,
    SupplierCategorySerializer,
    SupplierSerializer,
    TaxRegistrationSerializer,
)
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet


class SupplierCategoryViewSet(MasterDataViewSet):
    queryset = SupplierCategory.objects.all()
    serializer_class = SupplierCategorySerializer
    search_fields = ("code", "name")


class SupplierViewSet(MasterDataViewSet):
    queryset = Party.objects.filter(is_supplier=True).select_related("supplier_category")
    serializer_class = SupplierSerializer
    search_fields = ("code", "legal_name", "trading_name", "email")


class CustomerViewSet(MasterDataViewSet):
    queryset = Party.objects.filter(is_customer=True)
    serializer_class = CustomerSerializer
    search_fields = ("code", "legal_name", "trading_name", "email")


class ContactViewSet(NoDeleteViewSet):
    queryset = Contact.objects.select_related("party").all()
    serializer_class = ContactSerializer


class AddressViewSet(NoDeleteViewSet):
    queryset = Address.objects.select_related("party").all()
    serializer_class = AddressSerializer


class TaxRegistrationViewSet(NoDeleteViewSet):
    queryset = TaxRegistration.objects.select_related("party").all()
    serializer_class = TaxRegistrationSerializer


class BankAccountViewSet(NoDeleteViewSet):
    queryset = BankAccount.objects.select_related("supplier").all()
    serializer_class = BankAccountSerializer


class ComplianceDocumentViewSet(NoDeleteViewSet):
    queryset = ComplianceDocument.objects.select_related("supplier", "document").all()
    serializer_class = ComplianceDocumentSerializer
