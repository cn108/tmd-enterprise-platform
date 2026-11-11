"""Projects and customer contracts (PRJ-01, PRJ-02).

Lifecycle states and transitions are explicit because PRJ-01 requires illegal
transitions to be rejected. The transition table is PROPOSED and needs
management sign-off; it is small and data-driven on purpose.
"""

from __future__ import annotations

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
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
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
