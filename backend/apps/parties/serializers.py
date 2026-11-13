from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.parties.models import (
    Address,
    BankAccount,
    BankAccountChangeRequest,
    ComplianceDocument,
    Contact,
    Party,
    SupplierCategory,
    TaxRegistration,
)
from shared.serializers import CodedSerializerMixin


def _tax_number(party: Party) -> str:
    """The active TIN registration, or the first active registration as shown on the record."""
    registrations = [item for item in party.tax_registrations.all() if item.is_active]
    for item in registrations:
        if item.scheme.strip().upper() == "TIN":
            return item.number
    return registrations[0].number if registrations else ""


def _region(party: Party) -> str:
    addresses = list(party.addresses.all())
    primary = next(
        (item for item in addresses if item.is_primary),
        addresses[0] if addresses else None,
    )
    if primary is None:
        return ""
    return primary.state or primary.city


class SupplierCategorySerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = SupplierCategory
        fields = ["id", "code", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class SupplierSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    is_customer = serializers.BooleanField(read_only=True)
    tin = serializers.SerializerMethodField()
    region = serializers.SerializerMethodField()

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
            "tin",
            "region",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "is_customer", "tin", "region"]

    def get_tin(self, obj: Party) -> str:
        return _tax_number(obj)

    def get_region(self, obj: Party) -> str:
        return _region(obj)

    def create(self, validated_data):
        validated_data["is_supplier"] = True
        return super().create(validated_data)


class CustomerSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    is_supplier = serializers.BooleanField(read_only=True)
    region = serializers.SerializerMethodField()

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
            "region",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "is_supplier", "region"]

    def get_region(self, obj: Party) -> str:
        return _region(obj)

    def validate_credit_limit(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Credit limit cannot be negative.")
        return value

    def create(self, validated_data):
        validated_data["is_customer"] = True
        return super().create(validated_data)


class ContactSerializer(serializers.ModelSerializer):
    party_code = serializers.CharField(source="party.code", read_only=True)

    class Meta:
        model = Contact
        fields = [
            "id",
            "party",
            "party_code",
            "name",
            "role",
            "email",
            "phone",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class PartyOptionSerializer(serializers.ModelSerializer):
    """All parties, for relationship master data that serves either role."""

    class Meta:
        model = Party
        fields = ["id", "code", "legal_name", "is_supplier", "is_customer", "is_active"]


class AddressSerializer(serializers.ModelSerializer):
    party_code = serializers.CharField(source="party.code", read_only=True)

    class Meta:
        model = Address
        fields = [
            "id",
            "party",
            "party_code",
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
    party_code = serializers.CharField(source="party.code", read_only=True)

    class Meta:
        model = TaxRegistration
        fields = [
            "id",
            "party",
            "party_code",
            "scheme",
            "number",
            "issued_on",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class BankAccountSerializer(serializers.ModelSerializer):
    """Read-only view of an approved account; never exposes the ciphertext."""

    masked_account = serializers.CharField(read_only=True)
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.legal_name", read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "supplier",
            "supplier_code",
            "supplier_name",
            "bank_name",
            "account_name",
            "masked_account",
            "sort_code",
            "currency",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BankAccountChangeRequestSerializer(serializers.ModelSerializer):
    proposed_account_number = serializers.CharField(write_only=True, trim_whitespace=True)
    proposed_masked_account = serializers.CharField(
        source="masked_proposed_account", read_only=True
    )
    requested_by = serializers.SerializerMethodField()
    reviewed_by = serializers.SerializerMethodField()
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)

    class Meta:
        model = BankAccountChangeRequest
        fields = [
            "id",
            "supplier",
            "supplier_code",
            "bank_account",
            "proposed_bank_name",
            "proposed_account_name",
            "proposed_account_number",
            "proposed_masked_account",
            "proposed_sort_code",
            "proposed_currency",
            "reason",
            "status",
            "requested_by",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "created_at",
            "updated_at",
        ]

    def get_requested_by(self, obj: BankAccountChangeRequest) -> str | None:
        return obj.created_by.email if obj.created_by else None

    def get_reviewed_by(self, obj: BankAccountChangeRequest) -> str | None:
        return obj.reviewed_by.email if obj.reviewed_by else None

    def validate_supplier(self, value: Party):
        if not value.is_supplier:
            raise serializers.ValidationError("Bank accounts belong to suppliers.")
        return value

    def validate(self, attrs):
        supplier = attrs.get("supplier")
        account = attrs.get("bank_account")
        if account is not None and supplier is not None and account.supplier_id != supplier.pk:
            raise serializers.ValidationError(
                {"bank_account": "The bank account belongs to a different supplier."}
            )
        if not attrs.get("proposed_account_number"):
            raise serializers.ValidationError(
                {"proposed_account_number": "An account number is required."}
            )
        return attrs

    def create(self, validated_data):
        raw = validated_data.pop("proposed_account_number")
        change = BankAccountChangeRequest(**validated_data)
        change.set_proposed_account_number(raw)
        change.save()
        return change


class BankAccountDecisionSerializer(serializers.Serializer):
    review_note = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )


class ComplianceDocumentSerializer(serializers.ModelSerializer):
    party_code = serializers.CharField(source="supplier.code", read_only=True)

    class Meta:
        model = ComplianceDocument
        fields = [
            "id",
            "supplier",
            "party_code",
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
