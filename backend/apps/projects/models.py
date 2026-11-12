"""Projects and customer contracts (PRJ-01, PRJ-02).

Lifecycle states and transitions are explicit because PRJ-01 requires illegal
transitions to be rejected. The transition table is PROPOSED and needs
management sign-off; it is small and data-driven on purpose.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from shared.models import UserStampedModel


class Project(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        CLOSED = "closed", "Closed"

    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        Status.DRAFT: {Status.ACTIVE},
        Status.ACTIVE: {Status.ON_HOLD, Status.CLOSED},
        Status.ON_HOLD: {Status.ACTIVE, Status.CLOSED},
        Status.CLOSED: set(),
    }

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    customer = models.ForeignKey(
        "parties.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="managed_projects"
    )
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_projects",
    )
    department = models.ForeignKey(
        "organisation.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "project"
        verbose_name_plural = "projects"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date cannot precede the start date."})

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class ProjectLocation(UserStampedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="locations")
    name = models.CharField(max_length=120)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["project__code", "-is_primary", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.project.code})"


class CustomerContract(UserStampedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="contracts")
    customer = models.ForeignKey(
        "parties.Party", on_delete=models.PROTECT, related_name="contracts"
    )
    reference = models.CharField(max_length=80, unique=True)
    value = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    terms = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["project__code", "reference"]
        verbose_name = "customer contract"
        verbose_name_plural = "customer contracts"

    def clean(self) -> None:
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date cannot precede the start date."})

    def __str__(self) -> str:
        return self.reference


class ContractRevision(UserStampedModel):
    """An append-only revision of a contract's value and terms (PRJ-02).

    Applying a revision to the live contract is an approval action in a later
    phase; this table only preserves the history.
    """

    contract = models.ForeignKey(
        CustomerContract, on_delete=models.PROTECT, related_name="revisions"
    )
    revision_number = models.PositiveIntegerField()
    value = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    terms = models.TextField(blank=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["contract__reference", "-revision_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "revision_number"], name="unique_revision_per_contract"
            )
        ]
        verbose_name = "contract revision"
        verbose_name_plural = "contract revisions"

    def clean(self) -> None:
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date cannot precede the start date."})

    def __str__(self) -> str:
        return f"{self.contract.reference} rev {self.revision_number}"


class BudgetCategory(models.TextChoices):
    MATERIALS = "materials", "Materials"
    LABOUR = "labour", "Labour"
    LOGISTICS = "logistics", "Logistics and transport"
    EQUIPMENT = "equipment", "Equipment rental"
    SUBCONTRACT = "subcontract", "Subcontracting"
    ENGINEERING = "engineering", "Engineering services"
    OTHER = "other", "Other direct cost"


class ProjectBudget(UserStampedModel):
    """A versioned project budget (PRJ-03).

    Amounts are client data. A budget is approved by a second person; approval
    is a permission the access administrator grants, because no approval-limit
    policy (D-04) has been signed. Approved budgets are not edited: a new
    version is raised instead, so committed cost can be compared with the
    budget that applied at the time.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="budgets")
    version = models.PositiveIntegerField(default=1)
    currency = models.CharField(max_length=3, default="NGN")
    revision_reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["project__code", "-version"]
        verbose_name = "project budget"
        verbose_name_plural = "project budgets"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version"], name="unique_budget_version_per_project"
            )
        ]
        permissions = [("approve_projectbudget", "Can approve a project budget")]

    def __str__(self) -> str:
        return f"{self.project.code} budget v{self.version}"

    @property
    def total_value(self):
        return sum((line.amount for line in self.lines.all()), start=Decimal("0"))


class BudgetLine(UserStampedModel):
    budget = models.ForeignKey(ProjectBudget, on_delete=models.CASCADE, related_name="lines")
    cost_centre = models.ForeignKey(
        "organisation.CostCentre",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="budget_lines",
    )
    category = models.CharField(
        max_length=16, choices=BudgetCategory.choices, default=BudgetCategory.OTHER
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ["budget", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name="budget_line_amount_non_negative"
            )
        ]

    def __str__(self) -> str:
        return f"{self.budget_id}: {self.description} {self.amount}"


class ProjectCost(UserStampedModel):
    """A direct project cost not already represented by procurement or stock.

    Supplier invoices and project stock issues are deliberately not duplicated
    here: the costing report combines those source documents with the approved
    rows in this table. This prevents the same cost being counted twice.
    """

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual cost capture"
        RENTAL_AGREEMENT = "rental_agreement", "Equipment rental agreement"
        OTHER = "other", "Other direct cost"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="costs")
    cost_date = models.DateField()
    category = models.CharField(max_length=16, choices=BudgetCategory.choices)
    description = models.CharField(max_length=255)
    supplier = models.ForeignKey(
        "parties.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="project_costs",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    reference = models.CharField(max_length=120, blank=True)
    source_type = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["project__code", "-cost_date", "-id"]
        verbose_name = "project cost"
        verbose_name_plural = "project costs"
        permissions = [
            ("approve_projectcost", "Can approve a direct project cost"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="project_cost_amount_positive"
            )
        ]

    def __str__(self) -> str:
        return f"{self.project.code}: {self.description} {self.amount}"


class ProjectMilestone(UserStampedModel):
    """A dated project milestone (PRJ-05). Completion is a recorded date, not
    an invented workflow status."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="milestones")
    name = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["project__code", "due_date", "name"]
        verbose_name = "project milestone"
        verbose_name_plural = "project milestones"

    def __str__(self) -> str:
        return f"{self.project.code}: {self.name}"
