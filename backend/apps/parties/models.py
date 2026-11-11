"""Partner master data: suppliers and customers.

A single ``Party`` table holds both, with flags, because one company can be
both a supplier and a customer, and because contacts, addresses and tax
registrations are identical for either role. The supplier and customer APIs
filter by the relevant flag; neither can see the other's records.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from shared.models import CodedModel, UserStampedModel


class SupplierCategory(CodedModel):
    """Approved supplier categories (MAS-02). No categories are seeded."""

    description = models.TextField(blank=True)


class Party(UserStampedModel):
    code = models.CharField(max_length=32, unique=True)
    legal_name = models.CharField(max_length=200)
    trading_name = models.CharField(max_length=200, blank=True)

    is_supplier = models.BooleanField(default=False)
    is_customer = models.BooleanField(default=False)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Supplier-only attributes (MAS-02). Terms are supplied by the client; no
    # default is invented, and currency defaults to the confirmed reporting
    # currency.
    supplier_category = models.ForeignKey(
        SupplierCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="suppliers",
    )
    payment_terms_days = models.PositiveSmallIntegerField(null=True, blank=True)
    default_currency = models.CharField(max_length=3, default="NGN")
    due_diligence_status = models.CharField(max_length=40, blank=True)

    # Customer-only attributes (MAS-01). Credit control values are client data.
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    credit_hold = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]
        verbose_name = "party"
        verbose_name_plural = "parties"

    def __str__(self) -> str:
        return f"{self.code} — {self.legal_name}"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        self.legal_name = (self.legal_name or "").strip()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if not self.is_supplier and not self.is_customer:
            raise ValidationError("A party must be at least a supplier or a customer.")


class Contact(UserStampedModel):
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="contacts")
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["party__code", "-is_primary", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.party.code})"


class Address(UserStampedModel):
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="addresses")
    label = models.CharField(max_length=60, blank=True)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postcode = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=80, default="Nigeria")
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["party__code", "-is_primary"]

    def __str__(self) -> str:
        return f"{self.line1}, {self.city} ({self.party.code})"


class TaxRegistration(UserStampedModel):
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="tax_registrations")
    scheme = models.CharField(max_length=40)
    number = models.CharField(max_length=60)
    issued_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["party__code", "scheme"]
        constraints = [
            models.UniqueConstraint(
                fields=["party", "scheme", "number"], name="unique_party_tax_registration"
            )
        ]

    def __str__(self) -> str:
        return f"{self.scheme}: {self.number}"


class BankAccount(UserStampedModel):
    """Supplier bank details (MAS-02).

    The full account number is write-only through the API; responses expose only
    the last four digits. Encryption at rest and the audited change workflow
    (W7 audit trail) are not yet implemented and are recorded as open items.
    """

    supplier = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="bank_accounts")
    bank_name = models.CharField(max_length=120)
    account_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=34)
    sort_code = models.CharField(max_length=20, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["supplier__code", "bank_name"]

    def __str__(self) -> str:
        return f"{self.bank_name} ••••{self.account_number[-4:]}"

    @property
    def account_last4(self) -> str:
        return self.account_number[-4:]


class ComplianceDocument(UserStampedModel):
    supplier = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="compliance_documents"
    )
    document_type = models.CharField(max_length=80)
    reference = models.CharField(max_length=80, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="compliance_documents",
    )
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["supplier__code", "document_type"]
        verbose_name = "compliance document"
        verbose_name_plural = "compliance documents"

    def __str__(self) -> str:
        return f"{self.document_type} ({self.supplier.code})"

    def clean(self) -> None:
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            raise ValidationError({"expires_on": "Expiry cannot precede the issue date."})
