"""Banking, statement reconciliation and petty cash (Phase 8).

The module records what the company knows about its bank accounts and what the
bank reported. It never derives a bank balance from an unapproved statement,
never posts to the ledger, and never executes a payment or transfer. Those
operations remain behind the Stage 7B activation controls.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from shared.models import UserStampedModel

ZERO = Decimal("0")


class BankingSettings(models.Model):
    """Configurable matching tolerances; zero is the conservative baseline."""

    amount_tolerance = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    date_tolerance_days = models.PositiveSmallIntegerField(default=0)
    auto_suggest_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "banking settings"
        verbose_name_plural = "banking settings"
        permissions = [
            ("manage_bankingsettings", "Can manage banking matching settings"),
        ]

    def __str__(self) -> str:
        return "Banking settings"

    @classmethod
    def load(cls) -> BankingSettings:
        record, _ = cls.objects.get_or_create(pk=1)
        return record


class BankAccount(UserStampedModel):
    class Classification(models.TextChoices):
        OPERATING = "operating", "Operating account"
        SAVINGS = "savings", "Savings account"
        TRUST = "trust", "Trust / project account"
        CALL_DEPOSIT = "call_deposit", "Call deposit"
        OTHER = "other", "Other"

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    bank_name = models.CharField(max_length=160)
    branch = models.CharField(max_length=160, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    account_last4 = models.CharField(max_length=4, blank=True)
    sort_code = models.CharField(max_length=20, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    classification = models.CharField(
        max_length=20, choices=Classification.choices, default=Classification.OPERATING
    )
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    opening_balance_date = models.DateField(null=True, blank=True)
    gl_account = models.ForeignKey(
        "accounting.Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bank_accounts",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "bank account"
        verbose_name_plural = "bank accounts"
        permissions = [
            ("manage_bankaccounts", "Can maintain company bank accounts"),
            ("import_bankstatement", "Can import bank statements"),
            ("match_banktransaction", "Can match statement lines"),
            ("approve_reconciliation", "Can approve bank reconciliations"),
            ("manage_pettycash", "Can maintain petty cash"),
            ("approve_cashvoucher", "Can approve cash vouchers"),
            ("manage_banktransfer", "Can maintain inter-account transfers"),
            ("approve_banktransfer", "Can approve inter-account transfers"),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    @property
    def masked_account(self) -> str:
        return f"••••{self.account_last4}" if self.account_last4 else ""


class BankStatement(UserStampedModel):
    class Status(models.TextChoices):
        IMPORTED = "imported", "Imported"
        IN_RECONCILIATION = "in_reconciliation", "In reconciliation"
        RECONCILED = "reconciled", "Reconciled"
        ARCHIVED = "archived", "Archived"

    number = models.CharField(max_length=24, unique=True)
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="statements"
    )
    reference = models.CharField(max_length=120, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    currency = models.CharField(max_length=3, default="NGN")
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.IMPORTED)
    source_file = models.FileField(upload_to="bank-statements/%Y/%m/", blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    file_sha256 = models.CharField(max_length=64, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    imported_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        verbose_name = "bank statement"
        verbose_name_plural = "bank statements"
        constraints = [
            models.UniqueConstraint(
                fields=["bank_account", "file_sha256"],
                condition=~models.Q(file_sha256=""),
                name="unique_statement_file_per_account",
            )
        ]

    def __str__(self) -> str:
        return self.number

    def clean(self) -> None:
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "The period cannot end before it starts."})


class StatementLine(models.Model):
    class Status(models.TextChoices):
        UNMATCHED = "unmatched", "Unmatched"
        MATCHED = "matched", "Matched"
        PARTIALLY_MATCHED = "partially_matched", "Partially matched"
        EXCLUDED = "excluded", "Excluded from reconciliation"

    class DuplicateStatus(models.TextChoices):
        CLEAR = "clear", "Clear"
        SUSPECTED = "suspected", "Suspected duplicate"
        CONFIRMED = "confirmed", "Confirmed duplicate"

    class Classification(models.TextChoices):
        UNCLASSIFIED = "unclassified", "Unclassified"
        BANK_CHARGE = "bank_charge", "Bank charge"
        INTEREST = "interest", "Interest"
        UNIDENTIFIED_RECEIPT = "unidentified_receipt", "Unidentified receipt"
        UNIDENTIFIED_PAYMENT = "unidentified_payment", "Unidentified payment"
        TRANSFER = "transfer", "Transfer"
        OTHER = "other", "Other"

    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name="lines")
    line_number = models.PositiveIntegerField()
    value_date = models.DateField()
    description = models.CharField(max_length=500)
    reference = models.CharField(max_length=160, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    external_id = models.CharField(max_length=120, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.UNMATCHED)
    duplicate_status = models.CharField(
        max_length=10, choices=DuplicateStatus.choices, default=DuplicateStatus.CLEAR
    )
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="duplicates"
    )
    classification = models.CharField(
        max_length=24,
        choices=Classification.choices,
        default=Classification.UNCLASSIFIED,
    )
    exclusion_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["statement", "line_number"]
        verbose_name = "statement line"
        verbose_name_plural = "statement lines"
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "line_number"], name="unique_line_per_statement"
            ),
            models.UniqueConstraint(
                fields=["statement", "fingerprint"],
                condition=~models.Q(fingerprint=""),
                name="unique_line_fingerprint_per_statement",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.statement.number} line {self.line_number}"

    @property
    def matched_amount(self) -> Decimal:
        return sum((match.amount for match in self.matches.filter(status="confirmed")), start=ZERO)

    @property
    def remaining_amount(self) -> Decimal:
        return abs(self.amount) - self.matched_amount


class BankTransaction(UserStampedModel):
    """A company-side expected or recorded bank movement.

    The statement line is the bank's record; this row is the company's expected
    record (for example a recorded supplier payment). Matching links the two.
    """

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual expectation"
        SUPPLIER_PAYMENT = "supplier_payment", "Supplier payment"
        CUSTOMER_RECEIPT = "customer_receipt", "Customer receipt"
        TRANSFER = "transfer", "Inter-account transfer"
        BANK_CHARGE = "bank_charge", "Bank charge"
        INTEREST = "interest", "Interest"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        EXPECTED = "expected", "Expected"
        RECORDED = "recorded", "Recorded"
        RECONCILED = "reconciled", "Reconciled"
        VOID = "void", "Void"

    number = models.CharField(max_length=24, blank=True)
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="transactions"
    )
    transaction_date = models.DateField()
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=160, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    source_type = models.CharField(max_length=24, choices=Source.choices, default=Source.MANUAL)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    external_reference = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EXPECTED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        verbose_name = "bank transaction"
        verbose_name_plural = "bank transactions"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount=0), name="bank_transaction_amount_non_zero"
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id"],
                condition=models.Q(source_id__isnull=False) & ~models.Q(source_type="transfer"),
                name="unique_bank_transaction_source",
            ),
        ]

    def __str__(self) -> str:
        return self.number or f"{self.bank_account.code} {self.transaction_date}"

    @property
    def matched_amount(self) -> Decimal:
        return sum((match.amount for match in self.matches.filter(status="confirmed")), start=ZERO)

    @property
    def remaining_amount(self) -> Decimal:
        return abs(self.amount) - self.matched_amount


class Reconciliation(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class PostingStatus(models.TextChoices):
        BLOCKED = "blocked", "Blocked — Stage 7B not authorised"
        NOT_REQUIRED = "not_required", "No posting required"
        PENDING = "pending", "Pending accounting review"

    number = models.CharField(max_length=24, unique=True)
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="reconciliations"
    )
    statement = models.OneToOneField(
        BankStatement, on_delete=models.PROTECT, related_name="reconciliation"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    statement_opening_balance = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    statement_closing_balance = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    posting_status = models.CharField(
        max_length=14, choices=PostingStatus.choices, default=PostingStatus.BLOCKED
    )
    posting_blocker = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        verbose_name = "bank reconciliation"
        verbose_name_plural = "bank reconciliations"
        permissions = [
            ("submit_reconciliation", "Can submit a bank reconciliation"),
            ("approve_reconciliation", "Can approve a bank reconciliation"),
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def unmatched_count(self) -> int:
        return self.statement.lines.filter(
            status__in=[StatementLine.Status.UNMATCHED, StatementLine.Status.PARTIALLY_MATCHED]
        ).count()

    @property
    def excluded_count(self) -> int:
        return self.statement.lines.filter(status=StatementLine.Status.EXCLUDED).count()

    @property
    def difference(self):
        if self.statement_closing_balance is None:
            return None
        controls = (
            self.matches.filter(status=ReconciliationMatch.Status.CONFIRMED).aggregate(
                total=models.Sum("amount")
            )["total"]
            or ZERO
        )
        return self.statement_closing_balance - controls


class ReconciliationMatch(UserStampedModel):
    class MatchType(models.TextChoices):
        ONE_TO_ONE = "one_to_one", "One statement line to one transaction"
        ONE_TO_MANY = "one_to_many", "One statement line split across transactions"
        MANY_TO_ONE = "many_to_one", "Many statement lines to one transaction"
        MANUAL = "manual", "Manual override"

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    reconciliation = models.ForeignKey(
        Reconciliation, on_delete=models.CASCADE, related_name="matches"
    )
    statement_line = models.ForeignKey(
        StatementLine, on_delete=models.PROTECT, related_name="matches"
    )
    bank_transaction = models.ForeignKey(
        BankTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="matches",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    match_type = models.CharField(
        max_length=16, choices=MatchType.choices, default=MatchType.MANUAL
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    matched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    matched_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["reconciliation", "statement_line", "id"]
        verbose_name = "reconciliation match"
        verbose_name_plural = "reconciliation matches"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="reconciliation_match_amount_positive"
            ),
            models.UniqueConstraint(
                fields=["reconciliation", "statement_line", "bank_transaction"],
                condition=models.Q(bank_transaction__isnull=False),
                name="unique_reconciliation_match_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reconciliation.number}: {self.amount}"


class BankTransfer(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        RECORDED = "recorded", "Recorded internally"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    from_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="outgoing_transfers"
    )
    to_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="incoming_transfers"
    )
    transfer_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    recorded_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-transfer_date", "-id"]
        verbose_name = "bank transfer"
        verbose_name_plural = "bank transfers"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="bank_transfer_amount_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(from_account=models.F("to_account")),
                name="bank_transfer_accounts_differ",
            ),
        ]

    def __str__(self) -> str:
        return self.number


class CashAccount(UserStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    currency = models.CharField(max_length=3, default="NGN")
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    imprest_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "cash account"
        verbose_name_plural = "cash accounts"

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)


class CashVoucher(UserStampedModel):
    class Kind(models.TextChoices):
        EXPENSE = "expense", "Petty cash expense"
        RECEIPT = "receipt", "Cash receipt"
        REPLENISHMENT = "replenishment", "Replenishment"
        PAYMENT = "payment", "Cash payment"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        RECORDED = "recorded", "Recorded"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    cash_account = models.ForeignKey(CashAccount, on_delete=models.PROTECT, related_name="vouchers")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.EXPENSE)
    voucher_date = models.DateField()
    payee = models.CharField(max_length=200)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    receipt_reference = models.CharField(max_length=120, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    recorded_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-voucher_date", "-id"]
        verbose_name = "cash voucher"
        verbose_name_plural = "cash vouchers"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="cash_voucher_amount_positive"
            )
        ]

    def __str__(self) -> str:
        return self.number


class PettyCashReplenishment(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        RECORDED = "recorded", "Recorded"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    cash_account = models.ForeignKey(
        CashAccount, on_delete=models.PROTECT, related_name="replenishments"
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="petty_cash_replenishments"
    )
    replenishment_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    recorded_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-replenishment_date", "-id"]
        verbose_name = "petty cash replenishment"
        verbose_name_plural = "petty cash replenishments"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="petty_cash_replenishment_amount_positive",
            )
        ]

    def __str__(self) -> str:
        return self.number
