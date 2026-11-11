from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.parties.models import (
    Address,
    BankAccount,
    ComplianceDocument,
    Contact,
    Party,
    SupplierCategory,
    TaxRegistration,
)
from shared.serializers import CodedSerializerMixin


class SupplierCategorySerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = SupplierCategory
        fields = ["id", "code", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class SupplierSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    is_customer = serializers.BooleanField(read_only=True)

    class Meta:
        model = Party
        fields = [
            "id",
            "code",
            "legal_name",
            "trading_name",
            "supplier_category",
            "payment_terms_days",
            "default_currency",
            "due_diligence_status",
            "email",
            "phone",
            "website",
            "notes",
            "is_active",
            "is_customer",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "is_customer"]

    def create(self, validated_data):
        validated_data["is_supplier"] = True
        return super().create(validated_data)


class CustomerSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    is_supplier = serializers.BooleanField(read_only=True)

    class Meta:
        model = Party
        fields = [
            "id",
            "code",
            "legal_name",
            "trading_name",
            "payment_terms_days",
            "default_currency",
            "credit_limit",
            "credit_hold",
            "email",
            "phone",
            "website",
            "notes",
            "is_active",
            "is_supplier",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "is_supplier"]

    def create(self, validated_data):
        validated_data["is_customer"] = True
        return super().create(validated_data)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = [
            "id",
            "party",
            "name",
            "role",
            "email",
            "phone",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "party",
            "label",
            "line1",
            "line2",
            "city",
            "state",
            "postcode",
            "country",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class TaxRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRegistration
        fields = [
            "id",
            "party",
            "scheme",
            "number",
            "issued_on",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class BankAccountSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(write_only=True, required=False)
    masked_account = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "supplier",
            "bank_name",
            "account_name",
            "account_number",
            "masked_account",
            "sort_code",
            "currency",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_masked_account(self, obj: BankAccount) -> str:
        return f"••••{obj.account_last4}"

    def validate_supplier(self, value: Party):
        if not value.is_supplier:
            raise serializers.ValidationError("Bank accounts belong to suppliers.")
        return value

    def validate(self, attrs):
        if not self.instance and not attrs.get("account_number"):
            raise serializers.ValidationError(
                {"account_number": "An account number is required when creating a bank account."}
            )
        return attrs


class ComplianceDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceDocument
        fields = [
            "id",
            "supplier",
            "document_type",
            "reference",
            "issued_on",
            "expires_on",
            "document",
            "is_verified",
            "verified_by",
            "verified_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["verified_by", "verified_at", "created_at", "updated_at"]

    def validate_supplier(self, value: Party):
        if not value.is_supplier:
            raise serializers.ValidationError("Compliance documents belong to suppliers.")
        return value

    def validate(self, attrs):
        issued = attrs.get("issued_on") or getattr(self.instance, "issued_on", None)
        expires = attrs.get("expires_on") or getattr(self.instance, "expires_on", None)
        if issued and expires and expires < issued:
            raise serializers.ValidationError(
                {"expires_on": "Expiry cannot precede the issue date."}
            )
        if attrs.get("is_verified") and not attrs.get("verified_at"):
            attrs["verified_at"] = timezone.now()
            attrs["verified_by"] = self.context["request"].user
        return attrs
