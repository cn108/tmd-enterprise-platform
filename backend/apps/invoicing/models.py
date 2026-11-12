"""Phase 7 invoices, notes, payments and NRS adapter state.

Stage 7A deliberately keeps every created document in test mode. The settings
record is the activation gate: production issuance and ledger posting require an
explicit Stage 7B checklist, a recorded Finance Controller review and management
authorisation. No company legal details, tax rates or bank credentials are
seeded here.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models

from shared.models import TimeStampedModel, UserStampedModel

ZERO = Decimal("0")
MONEY = Decimal("0.01")


class TaxTreatment(models.TextChoices):
    TAXABLE = "taxable", "Taxable"
    ZERO_RATED = "zero_rated", "Zero-rated"
    EXEMPT = "exempt", "Exempt"
    OUT_OF_SCOPE = "out_of_scope", "Out of scope"


def money(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(MONEY, rounding=ROUND_HALF_UP)


def tax_amount(net: Decimal, tax) -> Decimal:
    if tax is None:
        return ZERO
    return money(Decimal(net) * Decimal(tax.rate) / Decimal("100"))


class InvoiceSettings(TimeStampedModel):
    """Singleton activation and presentation settings.

    ``test_mode`` starts true and is not writable through ordinary invoice
    endpoints. Activation is a separate, audited management action.
    """

    test_mode = models.BooleanField(default=True)
    company_legal_name = models.CharField(max_length=200, blank=True)
    company_address = models.TextField(blank=True)
    company_tax_identification_number = models.CharField(max_length=80, blank=True)
    company_email = models.EmailField(blank=True)
    company_phone = models.CharField(max_length=40, blank=True)
    company_bank_details = models.TextField(blank=True)
    default_currency = models.CharField(max_length=3, default="NGN")
    require_supplier_match = models.BooleanField(default=True)
    duplicate_window_days = models.PositiveSmallIntegerField(default=7)
    price_tolerance_percent = models.DecimalField(max_digits=7, decimal_places=4, default=ZERO)
    quantity_tolerance_percent = models.DecimalField(max_digits=7, decimal_places=4, default=ZERO)
    nrs_enabled = models.BooleanField(default=False)
    nrs_environment = models.CharField(max_length=20, blank=True)
    activation_checklist = models.JSONField(default=dict, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    activation_notes = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "invoice settings"
        verbose_name_plural = "invoice settings"
        permissions = [
            ("manage_invoicesettings", "Can manage invoice settings and activation"),
            ("post_supplierinvoice", "Can post a supplier invoice to the ledger"),
            ("post_customerinvoice", "Can post a customer invoice to the ledger"),
            ("submit_nrs", "Can submit an invoice to the NRS adapter"),
        ]

    def __str__(self) -> str:
        return "Invoice settings"

    @classmethod
    def load(cls) -> InvoiceSettings:
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    @property
    def can_issue(self) -> bool:
        return self.activated_at is not None and not self.test_mode


class SupplierInvoice(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class MatchStatus(models.TextChoices):
        UNMATCHED = "unmatched", "Unmatched"
        MATCHED = "matched", "Matched"
        EXCEPTION = "exception", "Exception"
        EXEMPT = "exempt", "Exempt"

    class DuplicateStatus(models.TextChoices):
        CLEAR = "clear", "Clear"
        SUSPECTED = "suspected", "Suspected"
        CONFIRMED = "confirmed", "Confirmed duplicate"

    number = models.CharField(max_length=24, unique=True)
    supplier_invoice_number = models.CharField(max_length=80)
    supplier_invoice_number_normalized = models.CharField(max_length=80, editable=False)
    supplier = models.ForeignKey("parties.Party", on_delete=models.PROTECT, related_name="invoices")
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
    )
    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
    )
    invoice_date = models.DateField()
    tax_point_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    match_status = models.CharField(
        max_length=10, choices=MatchStatus.choices, default=MatchStatus.UNMATCHED
    )
    duplicate_status = models.CharField(
        max_length=10, choices=DuplicateStatus.choices, default=DuplicateStatus.CLEAR
    )
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="duplicates"
    )
    duplicate_override_reason = models.CharField(max_length=255, blank=True)
    match_exempt_reason = models.CharField(max_length=255, blank=True)
    match_exceptions = models.JSONField(default=list, blank=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_recoverable_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    wht_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    credited_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    debited_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    payment_due = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    is_test = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
    )

    class Meta:
        ordering = ["-invoice_date", "-id"]
        permissions = [
            ("approve_supplierinvoice", "Can approve a supplier invoice"),
            ("cancel_supplierinvoice", "Can cancel a supplier invoice"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "supplier_invoice_number_normalized"],
                name="unique_supplier_invoice_number_normalized",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0)
                & models.Q(vat_total__gte=0)
                & models.Q(wht_total__gte=0)
                & models.Q(total__gte=0),
                name="supplier_invoice_totals_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    def save(self, *args, **kwargs):
        self.supplier_invoice_number = (self.supplier_invoice_number or "").strip().upper()
        self.supplier_invoice_number_normalized = "".join(
            character for character in self.supplier_invoice_number if character.isalnum()
        )
        super().save(*args, **kwargs)

    @property
    def balance(self) -> Decimal:
        return max(self.payment_due - self.amount_paid, ZERO)

    @property
    def payment_status(self) -> str:
        if self.amount_paid <= ZERO:
            return "unpaid"
        if self.balance <= ZERO:
            return "paid"
        return "part_paid"


class SupplierInvoiceLine(UserStampedModel):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoice_lines",
    )
    receipt_line = models.ForeignKey(
        "procurement.GoodsReceiptLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoice_lines",
    )
    item = models.ForeignKey(
        "catalogue.CatalogueItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoice_lines",
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    vat_tax = models.ForeignKey(
        "core.TaxConfiguration",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    wht_tax = models.ForeignKey(
        "core.TaxConfiguration",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    tax_treatment = models.CharField(
        max_length=12, choices=TaxTreatment.choices, default=TaxTreatment.TAXABLE
    )
    vat_recoverable = models.BooleanField(default=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_recoverable_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    wht_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["invoice", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="supplier_invoice_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="supplier_invoice_line_price_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice.number} line {self.pk}"

    def calculate(self) -> None:
        self.subtotal = money(Decimal(self.quantity) * Decimal(self.unit_price))
        self.vat_amount = (
            tax_amount(self.subtotal, self.vat_tax)
            if self.tax_treatment == TaxTreatment.TAXABLE
            else ZERO
        )
        self.vat_recoverable_amount = self.vat_amount if self.vat_recoverable else ZERO
        self.wht_amount = tax_amount(self.subtotal, self.wht_tax)
        self.total = money(self.subtotal + self.vat_amount)


class CustomerInvoice(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    customer = models.ForeignKey(
        "parties.Party", on_delete=models.PROTECT, related_name="customer_invoices"
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_invoices",
    )
    customer_reference = models.CharField(max_length=80, blank=True)
    invoice_date = models.DateField()
    tax_point_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    wht_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    credited_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    debited_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    is_test = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_invoices",
    )

    class Meta:
        ordering = ["-invoice_date", "-id"]
        permissions = [
            ("approve_customerinvoice", "Can approve a customer invoice"),
            ("cancel_customerinvoice", "Can cancel a customer invoice"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0)
                & models.Q(vat_total__gte=0)
                & models.Q(total__gte=0),
                name="customer_invoice_totals_non_negative",
            )
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def amount_due(self) -> Decimal:
        return max(self.balance, ZERO)

    @property
    def net_receivable(self) -> Decimal:
        return max(self.balance - self.wht_total, ZERO)


class CustomerInvoiceLine(UserStampedModel):
    invoice = models.ForeignKey(CustomerInvoice, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        "catalogue.CatalogueItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_invoice_lines",
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    vat_tax = models.ForeignKey(
        "core.TaxConfiguration",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    tax_treatment = models.CharField(
        max_length=12, choices=TaxTreatment.choices, default=TaxTreatment.TAXABLE
    )
    wht_tax = models.ForeignKey(
        "core.TaxConfiguration",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    wht_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["invoice", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="customer_invoice_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="customer_invoice_line_price_non_negative",
            ),
        ]

    def calculate(self) -> None:
        self.subtotal = money(Decimal(self.quantity) * Decimal(self.unit_price))
        self.vat_amount = (
            tax_amount(self.subtotal, self.vat_tax)
            if self.tax_treatment == TaxTreatment.TAXABLE
            else ZERO
        )
        self.wht_amount = tax_amount(self.subtotal, self.wht_tax)
        self.total = money(self.subtotal + self.vat_amount)


class InvoiceNote(UserStampedModel):
    class NoteType(models.TextChoices):
        CREDIT = "credit", "Credit note"
        DEBIT = "debit", "Debit note"

    class PartyKind(models.TextChoices):
        SUPPLIER = "supplier", "Supplier"
        CUSTOMER = "customer", "Customer"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    note_type = models.CharField(max_length=8, choices=NoteType.choices)
    party_kind = models.CharField(max_length=10, choices=PartyKind.choices)
    supplier_invoice = models.ForeignKey(
        SupplierInvoice,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoice_notes",
    )
    customer_invoice = models.ForeignKey(
        CustomerInvoice,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoice_notes",
    )
    note_date = models.DateField()
    tax_point_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    is_test = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-note_date", "-id"]
        permissions = [
            ("approve_invoicenote", "Can approve a credit or debit note"),
            ("cancel_invoicenote", "Can cancel a credit or debit note"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(party_kind="supplier", supplier_invoice__isnull=False)
                    & models.Q(customer_invoice__isnull=True)
                )
                | (
                    models.Q(party_kind="customer", customer_invoice__isnull=False)
                    & models.Q(supplier_invoice__isnull=True)
                ),
                name="invoice_note_has_one_party_invoice",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0)
                & models.Q(vat_total__gte=0)
                & models.Q(total__gte=0),
                name="invoice_note_totals_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def party_name(self) -> str:
        if self.supplier_invoice_id:
            return self.supplier_invoice.supplier.legal_name
        if self.customer_invoice_id:
            return self.customer_invoice.customer.legal_name
        return ""


class InvoiceNoteLine(UserStampedModel):
    note = models.ForeignKey(InvoiceNote, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    vat_tax = models.ForeignKey(
        "core.TaxConfiguration",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    tax_treatment = models.CharField(
        max_length=12, choices=TaxTreatment.choices, default=TaxTreatment.TAXABLE
    )
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    vat_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["note", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="invoice_note_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="invoice_note_line_price_non_negative",
            ),
        ]

    def calculate(self) -> None:
        self.subtotal = money(Decimal(self.quantity) * Decimal(self.unit_price))
        self.vat_amount = (
            tax_amount(self.subtotal, self.vat_tax)
            if self.tax_treatment == TaxTreatment.TAXABLE
            else ZERO
        )
        self.total = money(self.subtotal + self.vat_amount)


class SupplierPayment(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        RECORDED = "recorded", "Recorded"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CHEQUE = "cheque", "Cheque"
        CASH = "cash", "Cash"
        OTHER = "other", "Other"

    class ExecutionStatus(models.TextChoices):
        NOT_EXECUTED = "not_executed", "Not executed — recording only"
        RECORDED = "recorded", "Recorded externally"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    supplier = models.ForeignKey(
        "parties.Party", on_delete=models.PROTECT, related_name="supplier_payments"
    )
    payment_date = models.DateField()
    currency = models.CharField(max_length=3, default="NGN")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    method = models.CharField(max_length=16, choices=Method.choices)
    external_reference = models.CharField(max_length=120, blank=True)
    bank_account = models.ForeignKey(
        "parties.BankAccount",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    company_bank_account = models.ForeignKey(
        "banking.BankAccount",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supplier_payments",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    execution_status = models.CharField(
        max_length=14, choices=ExecutionStatus.choices, default=ExecutionStatus.NOT_EXECUTED
    )
    is_test = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    recorded_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supplier_payments",
    )

    class Meta:
        ordering = ["-payment_date", "-id"]
        permissions = [
            ("approve_payment", "Can approve a supplier payment"),
            ("record_payment", "Can record an externally executed payment"),
            ("allocate_payment", "Can allocate a payment to invoices"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="supplier_payment_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="supplier_payment_allocated_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def unallocated_amount(self) -> Decimal:
        return max(self.amount - self.allocated_amount, ZERO)


class PaymentAllocation(UserStampedModel):
    payment = models.ForeignKey(
        SupplierPayment, on_delete=models.CASCADE, related_name="allocations"
    )
    supplier_invoice = models.ForeignKey(
        SupplierInvoice, on_delete=models.PROTECT, related_name="payment_allocations"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ["payment", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "supplier_invoice"], name="unique_payment_invoice_allocation"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payment_allocation_amount_positive"
            ),
        ]


class NrsSubmission(UserStampedModel):
    class Status(models.TextChoices):
        DISABLED = "disabled", "Disabled — feature flag off"
        QUEUED = "queued", "Queued for adapter"
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    customer_invoice = models.OneToOneField(
        CustomerInvoice, on_delete=models.PROTECT, related_name="nrs_submission"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DISABLED)
    environment = models.CharField(max_length=20, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_test = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("submit_nrs", "Can submit an invoice to the NRS adapter")]

    def __str__(self) -> str:
        return f"NRS {self.customer_invoice.number}: {self.status}"


class IdempotencyRecord(TimeStampedModel):
    """Replay protection for payment recording and financial posting."""

    scope = models.CharField(max_length=40)
    key = models.CharField(max_length=120)
    response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["scope", "key"], name="unique_idempotency_scope_key")
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.key}"


def validate_invoice_tax(tax, expected_type: str, on_date=None) -> None:
    if tax is not None and tax.tax_type != expected_type:
        raise ValidationError({"tax": f"This line expects a {expected_type.upper()} tax code."})
    if tax is not None and on_date is not None and not tax.is_effective(on_date):
        raise ValidationError(
            {"tax": f"Tax code {tax.code} is not effective on {on_date.isoformat()}."}
        )
