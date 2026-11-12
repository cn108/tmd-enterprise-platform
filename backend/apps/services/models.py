"""Engineering, maintenance, inspection and service work orders (Phase 9).

A work order is the operational record. It does not recognise revenue or post
costs. Labour hours and material notes are recorded against the work, while
approved direct project costs remain the costing source of truth.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from shared.models import UserStampedModel

ZERO = 0


class ServiceContract(UserStampedModel):
    class Kind(models.TextChoices):
        ENGINEERING = "engineering", "Engineering services"
        MAINTENANCE = "maintenance", "Maintenance contract"
        INSPECTION = "inspection", "Inspection contract"
        OTHER = "other", "Other service contract"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    customer = models.ForeignKey(
        "parties.Party", on_delete=models.PROTECT, related_name="service_contracts"
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="service_contracts",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.ENGINEERING)
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    terms = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        verbose_name = "service contract"
        verbose_name_plural = "service contracts"
        permissions = [
            ("approve_servicecontract", "Can approve a service contract"),
        ]

    def __str__(self) -> str:
        return self.number

    def clean(self) -> None:
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The contract cannot end before it starts."})


class WorkOrder(UserStampedModel):
    class RequestType(models.TextChoices):
        ENGINEERING_REQUEST = "engineering_request", "Engineering request"
        PREVENTIVE_MAINTENANCE = "preventive_maintenance", "Preventive maintenance"
        CORRECTIVE_MAINTENANCE = "corrective_maintenance", "Corrective maintenance"
        INSPECTION = "inspection", "Inspection assignment"
        INSTALLATION = "installation", "Installation"
        OTHER = "other", "Other service"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        EMERGENCY = "emergency", "Emergency"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In progress"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        ACCEPTED = "accepted", "Accepted by customer"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    service_contract = models.ForeignKey(
        ServiceContract,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="work_orders",
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="work_orders",
    )
    customer = models.ForeignKey(
        "parties.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="work_orders",
    )
    request_type = models.CharField(
        max_length=24, choices=RequestType.choices, default=RequestType.ENGINEERING_REQUEST
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    site = models.CharField(max_length=200, blank=True)
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supervised_work_orders",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_work_orders",
    )
    scheduled_start = models.DateField(null=True, blank=True)
    scheduled_end = models.DateField(null=True, blank=True)
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    hse_requirements = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "work order"
        verbose_name_plural = "work orders"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(progress_percent__gte=0) & models.Q(progress_percent__lte=100),
                name="work_order_progress_range",
            )
        ]
        permissions = [
            ("assign_workorder", "Can assign people to a work order"),
            ("complete_workorder", "Can complete a work order"),
            ("accept_workorder", "Can record customer acceptance"),
        ]

    def __str__(self) -> str:
        return f"{self.number} — {self.title}"

    def clean(self) -> None:
        if (
            self.scheduled_start
            and self.scheduled_end
            and self.scheduled_end < self.scheduled_start
        ):
            raise ValidationError({"scheduled_end": "Scheduled end cannot precede the start."})
        if self.actual_start and self.actual_end and self.actual_end < self.actual_start:
            raise ValidationError({"actual_end": "Actual end cannot precede the start."})


class WorkOrderAssignment(UserStampedModel):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="work_assignments"
    )
    role = models.CharField(max_length=80, blank=True)
    planned_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["work_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "user"], name="unique_work_order_assignee"
            ),
            models.CheckConstraint(
                condition=models.Q(planned_hours__isnull=True) | models.Q(planned_hours__gte=0),
                name="work_assignment_planned_hours_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(actual_hours__isnull=True) | models.Q(actual_hours__gte=0),
                name="work_assignment_actual_hours_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.work_order.number}: {self.user.email}"


class WorkOrderProgress(UserStampedModel):
    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="progress_updates"
    )
    progress_date = models.DateField()
    percent_complete = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)
    labour_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    materials_used = models.TextField(blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["work_order", "-progress_date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(percent_complete__gte=0) & models.Q(percent_complete__lte=100),
                name="work_progress_range",
            ),
            models.CheckConstraint(
                condition=models.Q(labour_hours__isnull=True) | models.Q(labour_hours__gte=0),
                name="work_progress_hours_non_negative",
            ),
        ]


class ServiceChecklistItem(UserStampedModel):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="checklist")
    sequence = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=255)
    is_required = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["work_order", "sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "sequence"], name="unique_checklist_sequence"
            )
        ]


class HseRecord(UserStampedModel):
    class Kind(models.TextChoices):
        TOOLBOX_TALK = "toolbox_talk", "Toolbox talk"
        PERMIT_TO_WORK = "permit_to_work", "Permit to work"
        INSPECTION = "inspection", "HSE inspection"
        INCIDENT = "incident", "Incident"
        PPE_CHECK = "ppe_check", "PPE check"
        OTHER = "other", "Other HSE record"

    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        SATISFACTORY = "satisfactory", "Satisfactory"
        ACTION_REQUIRED = "action_required", "Action required"
        CLOSED = "closed", "Closed"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="hse_records")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    record_date = models.DateField()
    description = models.TextField()
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.OPEN)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["work_order", "-record_date", "-id"]


class WorkOrderReport(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted by customer"
        REJECTED = "rejected", "Rejected"

    work_order = models.OneToOneField(
        WorkOrder, on_delete=models.PROTECT, related_name="completion_report"
    )
    summary = models.TextField()
    findings = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    completed_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    customer_representative = models.CharField(max_length=160, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "work order report"
        verbose_name_plural = "work order reports"

    def __str__(self) -> str:
        return f"{self.work_order.number} completion report"
