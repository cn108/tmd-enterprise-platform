from django.contrib import admin

from apps.parties.models import (
    Address,
    BankAccount,
    ComplianceDocument,
    Contact,
    Party,
    SupplierCategory,
    TaxRegistration,
)


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ("code", "legal_name", "is_supplier", "is_customer", "is_active")
    list_filter = ("is_supplier", "is_customer", "is_active", "supplier_category")
    search_fields = ("code", "legal_name", "trading_name")
    ordering = ("code",)


@admin.register(SupplierCategory)
class SupplierCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("party", "name", "role", "is_primary")
    search_fields = ("party__code", "name")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("party", "line1", "city", "is_primary")
    search_fields = ("party__code", "line1", "city")


@admin.register(TaxRegistration)
class TaxRegistrationAdmin(admin.ModelAdmin):
    list_display = ("party", "scheme", "number", "is_active")
    search_fields = ("party__code", "scheme", "number")


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("supplier", "bank_name", "account_last4", "is_active")
    exclude = ("account_number",)
    search_fields = ("supplier__code", "bank_name")


@admin.register(ComplianceDocument)
class ComplianceDocumentAdmin(admin.ModelAdmin):
    list_display = ("supplier", "document_type", "expires_on", "is_verified")
    list_filter = ("is_verified",)
    search_fields = ("supplier__code", "document_type")
