from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.core.models import (
    ApprovalPolicy,
    ApprovalRecord,
    AuditEvent,
    NumberingScheme,
    PolicyDecision,
    TaxConfiguration,
    TaxProfile,
)


class PolicyDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDecision
        fields = [
            "id",
            "code",
            "version",
            "title",
            "status",
            "effective_from",
            "review_date",
            "owner",
            "summary",
            "configuration",
            "notes",
            "approved_at",
            "created_at",
        ]
        read_only_fields = fields


class ApprovalPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalPolicy
        fields = [
            "id",
            "code",
            "document_type",
            "version",
            "min_amount",
            "max_amount",
            "required_approvals",
            "required_role",
            "effective_from",
            "effective_to",
            "is_active",
            "notes",
        ]
        read_only_fields = fields


class ApprovalRecordSerializer(serializers.ModelSerializer):
    approver_email = serializers.CharField(source="approver.email", read_only=True)

    class Meta:
        model = ApprovalRecord
        fields = [
            "id",
            "document_type",
            "document_id",
            "approver",
            "approver_email",
            "decision",
            "amount",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "occurred_at",
            "actor",
            "actor_email",
            "action",
            "entity_type",
            "entity_id",
            "before",
            "after",
            "metadata",
            "request_id",
            "previous_hash",
            "hash",
        ]
        read_only_fields = fields


class TaxConfigurationSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        rate = attrs.get("rate", getattr(self.instance, "rate", None))
        if rate is not None and not Decimal("0") <= rate <= Decimal("100"):
            raise serializers.ValidationError({"rate": "The tax rate must be between 0 and 100."})
        effective_from = attrs.get("effective_from", getattr(self.instance, "effective_from", None))
        effective_to = attrs.get("effective_to", getattr(self.instance, "effective_to", None))
        if effective_from and effective_to and effective_to < effective_from:
            raise serializers.ValidationError(
                {"effective_to": "The end date cannot be before the start date."}
            )
        return attrs

    class Meta:
        model = TaxConfiguration
        fields = [
            "id",
            "code",
            "name",
            "tax_type",
            "rate",
            "jurisdiction",
            "registration_number",
            "effective_from",
            "effective_to",
            "review_status",
            "reviewed_by",
            "reviewed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["reviewed_by", "reviewed_at", "created_at", "updated_at"]


class TaxProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxProfile
        fields = [
            "id",
            "legal_name",
            "tax_identification_number",
            "vat_registered",
            "nrs_status",
            "nrs_environment",
            "review_status",
            "reviewed_by",
            "reviewed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["reviewed_by", "reviewed_at", "created_at", "updated_at"]


class NumberingSchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberingScheme
        fields = [
            "id",
            "document_type",
            "prefix",
            "padding",
            "reset_yearly",
            "next_value",
            "is_active",
            "review_status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
