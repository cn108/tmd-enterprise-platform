"""General ledger, journals, periods and posting rules (Phase 6).

D-05 (chart of accounts, financial year and posting matrix) is unresolved, so
nothing here seeds an account, a rule, a fiscal year or a retained-earnings
mapping. Accounts and posting rules carry an explicit approval recorded by a
different user, and posting refuses any account that has not been approved.

Posted journals are immutable at the API layer: there is no update or delete
route, and corrections are separate reversing or adjusting journals.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from shared.models import CodedModel, TimeStampedModel, UserStampedModel

ZERO = Decimal("0")


class Account(CodedModel):
    class Type(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    class NormalBalance(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    account_type = models.CharField(max_length=12, choices=Type.choices)
    normal_balance = models.CharField(max_length=6, choices=NormalBalance.choices)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    description = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "account"
        verbose_name_plural = "accounts"
        permissions = [
            ("manage_accounts", "Can maintain the chart of accounts"),
            ("approve_account", "Can approve a chart-of-accounts entry"),
        ]

    @property
    def is_approved(self) -> bool:
        return self.approved_at is not None

    def clean(self) -> None:
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError({"parent": "An account cannot be its own parent."})
        ancestor = self.parent
        seen: set[int] = set()
        while ancestor is not None:
            if ancestor.pk in seen or ancestor.pk == self.pk:
                raise ValidationError({"parent": "Accounts cannot form a cycle."})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent


class AccountRole(CodedModel):
    """A stable accounting role; the accountant maps it to a real account."""

    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "account role"
        verbose_name_plural = "account roles"

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class AccountRoleMapping(UserStampedModel):
    """An effective-dated mapping from a role to an approved account."""

    role = models.ForeignKey(AccountRole, on_delete=models.PROTECT, related_name="mappings")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="role_mappings")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["role__code", "-effective_from"]
        verbose_name = "account role mapping"
        verbose_name_plural = "account role mappings"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "effective_from"], name="unique_role_mapping_start"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="role_mapping_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.role.code} → {self.account.code}"

    def clean(self) -> None:
        if self.account_id and not self.account.is_approved:
            raise ValidationError({"account": "The mapped account must be approved first."})
        if self.account_id and not self.account.is_active:
            raise ValidationError({"account": "The mapped account must be active."})


class FiscalYear(UserStampedModel):
    """A client-supplied financial year; no year or period is seeded (D-05)."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "fiscal year"
        verbose_name_plural = "fiscal years"
        permissions = [("manage_fiscalyears", "Can maintain fiscal years")]

    def __str__(self) -> str:
        return f"{self.code} ({self.start_date} – {self.end_date})"

    def clean(self) -> None:
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date cannot precede the start date."})


class AccountingPeriod(UserStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="periods")
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reopen_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "accounting period"
        verbose_name_plural = "accounting periods"
        constraints = [
            models.UniqueConstraint(
                fields=["fiscal_year", "name"], name="unique_period_name_per_year"
            )
        ]
        permissions = [
            ("manage_periods", "Can maintain accounting periods"),
            ("close_period", "Can close an accounting period"),
            ("reopen_period", "Can reopen a closed accounting period"),
        ]

    def __str__(self) -> str:
        return f"{self.fiscal_year.code}/{self.name}"

    def clean(self) -> None:
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date cannot precede the start date."})
        if (
            self.start_date < self.fiscal_year.start_date
            or self.end_date > self.fiscal_year.end_date
        ):
            raise ValidationError("A period must fall inside its fiscal year.")
        overlap = AccountingPeriod.objects.filter(
            fiscal_year_id=self.fiscal_year_id,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
        ).exclude(pk=self.pk)
        if overlap.exists():
            raise ValidationError("Accounting periods cannot overlap.")


class JournalEntry(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        POSTED = "posted", "Posted"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual journal"
        ADJUSTMENT = "adjustment", "Adjustment"
        OPENING_BALANCE = "opening_balance", "Opening balances"
        REVERSAL = "reversal", "Reversal"
        PERIOD_CLOSE = "period_close", "Period close"
        EVENT = "event", "Financial event"

    number = models.CharField(max_length=24, unique=True)
    journal_date = models.DateField()
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="journals")
    description = models.CharField(max_length=255)
    source_type = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    total_debit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    total_credit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    reversal_of = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    posting_rule = models.ForeignKey(
        "accounting.PostingRule",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journals",
    )
    event_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-journal_date", "-id"]
        verbose_name = "journal entry"
        verbose_name_plural = "journal entries"
        constraints = [
            models.UniqueConstraint(
                fields=["posting_rule", "event_reference"],
                condition=models.Q(posting_rule__isnull=False) & ~models.Q(event_reference=""),
                name="unique_event_reference_per_rule",
            )
        ]
        permissions = [
            ("create_journal", "Can create and submit journal entries"),
            ("approve_journal", "Can approve journal entries"),
            ("post_journal", "Can post journal entries"),
            ("reverse_journal", "Can reverse posted journal entries"),
        ]

    def __str__(self) -> str:
        return self.number


class JournalLine(models.Model):
    journal = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    line_number = models.PositiveSmallIntegerField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    description = models.CharField(max_length=255, blank=True)
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    party = models.ForeignKey(
        "parties.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    item = models.ForeignKey(
        "catalogue.CatalogueItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )

    class Meta:
        ordering = ["journal", "line_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["journal", "line_number"], name="unique_line_number_per_journal"
            ),
            models.CheckConstraint(
                condition=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="journal_line_amounts_non_negative",
            ),
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0) & models.Q(credit=0))
                | (models.Q(credit__gt=0) & models.Q(debit=0)),
                name="journal_line_has_one_side",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.journal_id}: {self.account_id} Dr {self.debit} Cr {self.credit}"


class OpeningBalance(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"

    number = models.CharField(max_length=24, unique=True)
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="opening_balances"
    )
    period = models.ForeignKey(
        AccountingPeriod, on_delete=models.PROTECT, related_name="opening_balances"
    )
    as_of_date = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    posted_journal = models.OneToOneField(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="opening_balance",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "opening balance"
        verbose_name_plural = "opening balances"
        constraints = [
            models.UniqueConstraint(fields=["fiscal_year"], name="one_opening_balance_per_year")
        ]
        permissions = [
            ("manage_openingbalance", "Can maintain opening balances"),
        ]

    def __str__(self) -> str:
        return self.number


class OpeningBalanceLine(models.Model):
    opening_balance = models.ForeignKey(
        OpeningBalance, on_delete=models.CASCADE, related_name="lines"
    )
    line_number = models.PositiveSmallIntegerField()
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="opening_balance_lines"
    )
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    description = models.CharField(max_length=255, blank=True)
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["opening_balance", "line_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["opening_balance", "line_number"],
                name="unique_opening_line_number",
            ),
            models.CheckConstraint(
                condition=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="opening_line_amounts_non_negative",
            ),
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0) & models.Q(credit=0))
                | (models.Q(credit__gt=0) & models.Q(debit=0)),
                name="opening_line_has_one_side",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.opening_balance_id}: {self.account_id}"


class PostingRule(UserStampedModel):
    """A client-approved mapping from event amounts to debit/credit accounts."""

    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "posting rule"
        verbose_name_plural = "posting rules"
        permissions = [
            ("manage_postingrules", "Can maintain posting rules"),
            ("approve_postingrule", "Can approve a posting rule"),
        ]

    def __str__(self) -> str:
        return self.code

    @property
    def is_approved(self) -> bool:
        return self.approved_at is not None


class PostingRuleLine(models.Model):
    class Direction(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    rule = models.ForeignKey(PostingRule, on_delete=models.CASCADE, related_name="lines")
    line_number = models.PositiveSmallIntegerField()
    account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="posting_rule_lines",
    )
    account_role = models.ForeignKey(
        AccountRole,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="posting_rule_lines",
    )
    direction = models.CharField(max_length=6, choices=Direction.choices)
    amount_key = models.CharField(max_length=60)

    class Meta:
        ordering = ["rule", "line_number"]
        constraints = [
            models.UniqueConstraint(fields=["rule", "line_number"], name="unique_rule_line_number"),
            models.CheckConstraint(
                condition=(models.Q(account__isnull=False, account_role__isnull=True))
                | (models.Q(account__isnull=True, account_role__isnull=False)),
                name="posting_rule_line_has_one_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rule_id}: {self.direction} {self.amount_key}"


class FinancialEvent(TimeStampedModel):
    """An outbox entry for a financial event awaiting rule configuration."""

    class Code(models.TextChoices):
        E02 = "E-02", "Goods received before invoice"
        E04 = "E-04", "Stock issued to a project"
        E16 = "E-16", "Stock adjustment, count or damage"
        E21 = "E-21", "Opening balances"
        E22 = "E-22", "Period reopen adjustment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending configuration"
        POSTED = "posted", "Posted"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    code = models.CharField(max_length=8, choices=Code.choices)
    source_type = models.CharField(max_length=60)
    source_id = models.PositiveBigIntegerField()
    event_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    description = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=8, blank=True)
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    party = models.ForeignKey(
        "parties.Party", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    journal = models.OneToOneField(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="financial_event",
    )
    error = models.CharField(max_length=255, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "financial event"
        verbose_name_plural = "financial events"
        constraints = [
            models.UniqueConstraint(
                fields=["code", "source_type", "source_id"],
                name="unique_financial_event_source",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.source_type}:{self.source_id} ({self.status})"


class AccountingSettings(models.Model):
    """The one configuration the engine cannot derive: retained earnings."""

    retained_earnings_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    posting_reviewed_at = models.DateTimeField(null=True, blank=True)
    posting_reviewed_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    posting_review_notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "identity.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "accounting settings"
        verbose_name_plural = "accounting settings"
        permissions = [
            ("configure_accounting", "Can configure retained earnings and closing"),
        ]

    def __str__(self) -> str:
        return "Accounting settings"

    @classmethod
    def load(cls) -> AccountingSettings:
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
