"""Equipment register, rental agreements, reservations and utilisation (Phase 9).

The register deliberately has no automatic fixed-asset or inventory
classification. ``asset_classification`` and ``accounting_treatment`` stay
blank until finance approves a policy.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from shared.models import CodedModel, UserStampedModel

ZERO = Decimal("0")


class EquipmentCategory(CodedModel):
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "equipment category"
        verbose_name_plural = "equipment categories"


class Equipment(UserStampedModel):
    class Ownership(models.TextChoices):
        OWNED = "owned", "Owned"
        LEASED_IN = "leased_in", "Leased in"
        THIRD_PARTY = "third_party", "Third party / customer supplied"
        UNKNOWN = "unknown", "Not recorded"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        RENTED = "rented", "On rent"
        MAINTENANCE = "maintenance", "Under maintenance"
        RETIRED = "retired", "Retired"

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        EquipmentCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="equipment",
    )
    description = models.TextField(blank=True)
    specification = models.TextField(blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    identifier = models.CharField(max_length=120, blank=True)
    ownership = models.CharField(
        max_length=16, choices=Ownership.choices, default=Ownership.UNKNOWN
    )
    ownership_reference = models.CharField(max_length=160, blank=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    asset_classification = models.CharField(
        max_length=80,
        blank=True,
        help_text="Finance-approved classification; never inferred by the system.",
    )
    accounting_treatment = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "equipment"
        verbose_name_plural = "equipment register"
        permissions = [
            ("manage_equipment", "Can maintain the equipment register"),
            ("dispatch_equipment", "Can dispatch equipment"),
            ("return_equipment", "Can record equipment returns"),
            ("record_inspection", "Can record equipment inspections"),
            ("manage_maintenance", "Can maintain equipment maintenance records"),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)


class EquipmentRate(UserStampedModel):
    class Basis(models.TextChoices):
        DAILY = "daily", "Per day"
        WEEKLY = "weekly", "Per week"
        MONTHLY = "monthly", "Per month"

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="rates")
    basis = models.CharField(max_length=10, choices=Basis.choices, default=Basis.DAILY)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["equipment", "-effective_from"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="equipment_rate_amount_positive"
            )
        ]

    def clean(self) -> None:
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The rate cannot end before it starts."})


class RentalAgreement(UserStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=24, unique=True)
    customer = models.ForeignKey(
        "parties.Party", on_delete=models.PROTECT, related_name="rental_agreements"
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rental_agreements",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    terms = models.TextField(blank=True)
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
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        verbose_name = "rental agreement"
        verbose_name_plural = "rental agreements"
        permissions = [
            ("approve_rentalagreement", "Can approve a rental agreement"),
            ("dispatch_rental", "Can dispatch equipment under a rental agreement"),
            ("close_rentalagreement", "Can close a rental agreement"),
        ]

    def __str__(self) -> str:
        return self.number

    def clean(self) -> None:
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "The agreement cannot end before it starts."})

    @property
    def total_value(self) -> Decimal:
        return sum((line.line_total for line in self.lines.all()), start=ZERO)


class RentalAgreementLine(UserStampedModel):
    agreement = models.ForeignKey(RentalAgreement, on_delete=models.CASCADE, related_name="lines")
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="rental_lines")
    rate = models.ForeignKey(
        EquipmentRate,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rental_lines",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    rate_amount = models.DecimalField(max_digits=18, decimal_places=2)
    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["agreement", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="rental_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(rate_amount__gte=0), name="rental_line_rate_non_negative"
            ),
        ]

    def clean(self) -> None:
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "The line cannot end before it starts."})
        if self.agreement_id and (
            self.start_date < self.agreement.start_date or self.end_date > self.agreement.end_date
        ):
            raise ValidationError(
                {"start_date": "The line dates must fall inside the agreement period."}
            )

    def save(self, *args, **kwargs):
        days = (self.end_date - self.start_date).days + 1
        self.line_total = (Decimal(days) * Decimal(self.quantity) * self.rate_amount).quantize(
            Decimal("0.01")
        )
        super().save(*args, **kwargs)


class EquipmentReservation(UserStampedModel):
    class Status(models.TextChoices):
        TENTATIVE = "tentative", "Tentative"
        CONFIRMED = "confirmed", "Confirmed"
        CONVERTED = "converted", "Converted to rental"
        CANCELLED = "cancelled", "Cancelled"

    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="reservations")
    agreement = models.ForeignKey(
        RentalAgreement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservations",
    )
    customer = models.ForeignKey(
        "parties.Party", on_delete=models.PROTECT, related_name="equipment_reservations"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TENTATIVE)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["start_date", "equipment"]
        verbose_name = "equipment reservation"
        verbose_name_plural = "equipment reservations"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="equipment_reservation_quantity_positive"
            )
        ]

    def clean(self) -> None:
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "The reservation cannot end before it starts."})


class EquipmentMovement(UserStampedModel):
    class Kind(models.TextChoices):
        DISPATCH = "dispatch", "Dispatch"
        RETURN = "return", "Return"

    class Condition(models.TextChoices):
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        DAMAGED = "damaged", "Damaged"
        UNUSABLE = "unusable", "Unusable"

    number = models.CharField(max_length=24, blank=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="movements")
    agreement = models.ForeignKey(
        RentalAgreement,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    movement_date = models.DateField()
    expected_return_date = models.DateField(null=True, blank=True)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.GOOD)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-movement_date", "-id"]
        verbose_name = "equipment movement"
        verbose_name_plural = "equipment movements"

    def clean(self) -> None:
        if (
            self.kind == self.Kind.DISPATCH
            and self.expected_return_date
            and self.expected_return_date < self.movement_date
        ):
            raise ValidationError(
                {"expected_return_date": "The return date cannot precede dispatch."}
            )


class EquipmentInspection(UserStampedModel):
    class Kind(models.TextChoices):
        PRE_DISPATCH = "pre_dispatch", "Pre-dispatch"
        RETURN = "return", "Return inspection"
        PERIODIC = "periodic", "Periodic inspection"
        DAMAGE = "damage", "Damage inspection"

    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="inspections")
    agreement = models.ForeignKey(
        RentalAgreement,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inspections",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.PERIODIC)
    inspection_date = models.DateField()
    condition = models.CharField(
        max_length=10, choices=EquipmentMovement.Condition.choices, default="good"
    )
    damage_found = models.BooleanField(default=False)
    damage_description = models.TextField(blank=True)
    charge_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["equipment", "-inspection_date", "-id"]
        verbose_name = "equipment inspection"
        verbose_name_plural = "equipment inspections"

    def clean(self) -> None:
        if self.damage_found and not self.damage_description.strip():
            raise ValidationError({"damage_description": "Describe the damage found."})
        if self.charge_amount is not None and self.charge_amount < 0:
            raise ValidationError({"charge_amount": "A charge cannot be negative."})


class EquipmentMaintenance(UserStampedModel):
    class Kind(models.TextChoices):
        PREVENTIVE = "preventive", "Preventive"
        CORRECTIVE = "corrective", "Corrective"
        INSPECTION = "inspection", "Inspection-driven"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="maintenance_records"
    )
    work_order = models.ForeignKey(
        "services.WorkOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="equipment_maintenance",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.PREVENTIVE)
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    description = models.TextField()
    vendor = models.CharField(max_length=160, blank=True)
    cost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-id"]
        verbose_name = "equipment maintenance"
        verbose_name_plural = "equipment maintenance records"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cost__isnull=True) | models.Q(cost__gte=0),
                name="equipment_maintenance_cost_non_negative",
            )
        ]

    def clean(self) -> None:
        if self.completed_date and self.completed_date < self.scheduled_date:
            raise ValidationError(
                {"completed_date": "Completion cannot precede the scheduled date."}
            )
