"""Governance records: provisional policy, approvals, tax configuration and audit.

None of these tables asserts that a provisional policy is a signed company
accounting record. A policy carries its version, owner, effective date and
review status; an unreviewed policy is configuration, not approval to post.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from shared.models import TimeStampedModel, UserStampedModel

ZERO = Decimal("0")


class PolicyDecision(TimeStampedModel):
    """A recorded policy choice, including provisional choices.

    Rows are versioned and are not edited in place: a changed policy is a new
    version so a decision made under an older version remains explainable.
    """

    class Status(models.TextChoices):
        PROVISIONAL = "provisional", "Provisional — requires professional review"
        CONFIRMED = "confirmed", "Confirmed"
        SUPERSEDED = "superseded", "Superseded"
        REJECTED = "rejected", "Rejected"

    code = models.CharField(max_length=20)
    version = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROVISIONAL)
    effective_from = models.DateField()
    review_date = models.DateField(null=True, blank=True)
    owner = models.CharField(max_length=120, blank=True)
    summary = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["code", "-effective_from"]
        verbose_name = "policy decision"
        verbose_name_plural = "policy decisions"
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="unique_policy_code_version")
        ]

    def __str__(self) -> str:
        return f"{self.code} v{self.version} ({self.status})"


class ApprovalPolicy(TimeStampedModel):
    """An amount band that decides how many independent approvals are needed."""

    class DocumentType(models.TextChoices):
        PURCHASE_REQUEST = "purchase_request", "Purchase request"
        PURCHASE_ORDER = "purchase_order", "Purchase order"
        PROJECT_BUDGET = "project_budget", "Project budget"
        SUPPLIER_INVOICE = "supplier_invoice", "Supplier invoice"
        PAYMENT = "payment", "Payment"
        CUSTOMER_INVOICE = "customer_invoice", "Customer invoice"
        INVOICE_NOTE = "invoice_note", "Credit or debit note"
        STOCK_ADJUSTMENT = "stock_adjustment", "Stock adjustment"
        JOURNAL = "journal", "Journal"

    code = models.CharField(max_length=40, unique=True)
    document_type = models.CharField(max_length=24, choices=DocumentType.choices)
    version = models.CharField(max_length=20, default="1")
    min_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    max_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    required_approvals = models.PositiveSmallIntegerField(default=1)
    required_role = models.ForeignKey(
        "auth.Group",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["document_type", "min_amount"]
        verbose_name = "approval policy"
        verbose_name_plural = "approval policies"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_amount__gte=0), name="approval_min_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(required_approvals__gte=1),
                name="approval_required_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(max_amount__isnull=True)
                | models.Q(max_amount__gt=models.F("min_amount")),
                name="approval_band_max_above_min",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.document_type})"


class ApprovalRecord(models.Model):
    """One person's independent decision on one document."""

    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    policy = models.ForeignKey(
        ApprovalPolicy, null=True, blank=True, on_delete=models.PROTECT, related_name="records"
    )
    document_type = models.CharField(max_length=24, choices=ApprovalPolicy.DocumentType.choices)
    document_id = models.PositiveBigIntegerField()
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approval_records"
    )
    decision = models.CharField(max_length=10, choices=Decision.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_type", "document_id", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "document_id", "approver"],
                name="one_approval_decision_per_person",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document_type}:{self.document_id} {self.decision} by {self.approver_id}"


class AuditEvent(models.Model):
    """An append-only, hash-chained record of a sensitive action."""

    occurred_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    previous_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "audit event"
        verbose_name_plural = "audit events"
        permissions = [("view_audit", "Can read the audit trail")]

    def __str__(self) -> str:
        return f"{self.id} {self.action} {self.entity_type}:{self.entity_id}"


class TaxConfiguration(UserStampedModel):
    """A configurable tax rate; no rate is seeded by the application."""

    class TaxType(models.TextChoices):
        VAT = "vat", "VAT"
        WHT = "wht", "Withholding tax"
        OTHER = "other", "Other"

    class ReviewStatus(models.TextChoices):
        PROVISIONAL = "provisional", "Provisional — requires tax review"
        REVIEWED = "reviewed", "Reviewed"
        REJECTED = "rejected", "Rejected"

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    tax_type = models.CharField(max_length=10, choices=TaxType.choices)
    rate = models.DecimalField(max_digits=7, decimal_places=4)
    jurisdiction = models.CharField(max_length=80, default="Nigeria")
    registration_number = models.CharField(max_length=80, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    review_status = models.CharField(
        max_length=12, choices=ReviewStatus.choices, default=ReviewStatus.PROVISIONAL
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["tax_type", "code"]
        verbose_name = "tax configuration"
        verbose_name_plural = "tax configuration"

    def __str__(self) -> str:
        return f"{self.code} {self.rate}%"

    def is_effective(self, on_date) -> bool:
        return self.effective_from <= on_date and (
            self.effective_to is None or on_date <= self.effective_to
        )


class TaxProfile(TimeStampedModel):
    """Company tax identity; values are entered by the reviewer, never seeded."""

    class NrsStatus(models.TextChoices):
        NOT_REGISTERED = "not_registered", "Not registered"
        ONBOARDING = "onboarding", "Onboarding"
        REGISTERED = "registered", "Registered"
        LIVE = "live", "Live"

    legal_name = models.CharField(max_length=200)
    tax_identification_number = models.CharField(max_length=80, blank=True)
    vat_registered = models.BooleanField(default=False)
    nrs_status = models.CharField(
        max_length=16, choices=NrsStatus.choices, default=NrsStatus.NOT_REGISTERED
    )
    nrs_environment = models.CharField(max_length=20, blank=True)
    review_status = models.CharField(
        max_length=12,
        choices=TaxConfiguration.ReviewStatus.choices,
        default=TaxConfiguration.ReviewStatus.PROVISIONAL,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "tax profile"
        verbose_name_plural = "tax profile"

    def __str__(self) -> str:
        return self.legal_name


class NumberingScheme(TimeStampedModel):
    """Configurable sequential document numbering; no invoice format is seeded."""

    document_type = models.CharField(max_length=24, unique=True)
    prefix = models.CharField(max_length=16)
    padding = models.PositiveSmallIntegerField(default=6)
    reset_yearly = models.BooleanField(default=True)
    next_value = models.PositiveIntegerField(default=1)
    last_allocated_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    review_status = models.CharField(
        max_length=12,
        choices=TaxConfiguration.ReviewStatus.choices,
        default=TaxConfiguration.ReviewStatus.PROVISIONAL,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["document_type"]
        verbose_name = "numbering scheme"
        verbose_name_plural = "numbering schemes"

    def __str__(self) -> str:
        return f"{self.document_type}: {self.prefix}"


def _json_default(value):
    return str(value)


def _audit_payload(
    *, actor_id, action, entity_type, entity_id, before, after, metadata, occurred_at
) -> str:
    return json.dumps(
        {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before": before,
            "after": after,
            "metadata": metadata,
            "occurred_at": occurred_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def create_audit_event(
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id,
    before: dict | None = None,
    after: dict | None = None,
    metadata: dict | None = None,
    request=None,
) -> AuditEvent:
    """Append an audit event, chaining it to the previous hash.

    The service is deliberately the only writer. A database trigger installed
    by migration refuses UPDATE and DELETE on the table, so a caller cannot
    rewrite history even through the ORM.
    """

    before = before or {}
    after = after or {}
    metadata = metadata or {}
    previous = AuditEvent.objects.order_by("-id").first()
    previous_hash = previous.hash if previous else ""
    ip_address = None
    request_id = ""
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR") or None
        request_id = getattr(request, "request_id", "") or ""
    now = timezone.now()
    payload = _audit_payload(
        actor_id=getattr(actor, "pk", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        metadata=metadata,
        occurred_at=now,
    )
    digest = hashlib.sha256(f"{previous_hash}{payload}".encode()).hexdigest()
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else "",
        before=before,
        after=after,
        metadata=metadata,
        ip_address=ip_address,
        request_id=request_id,
        previous_hash=previous_hash,
        hash=digest,
    )
