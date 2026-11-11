"""Organisational structure: departments and cost centres.

Cost centres arrive in Phase 3 (PRJ-04). Their hierarchy is optional because
Q-14b (whether the cost-code structure is hierarchical) is unresolved; a flat
list is valid, and a parent can be added later without a data migration.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from shared.models import CodedModel, UserStampedModel


class Department(UserStampedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "department"
        verbose_name_plural = "departments"

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError({"parent": "A department cannot be its own parent."})


class CostCentre(CodedModel):
    """A cost code used on project commitments (PRJ-04).

    ``parent`` is optional: hierarchical and flat structures are both valid
    until Q-14b is answered. No cost codes are seeded.
    """

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_centres",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "cost centre"
        verbose_name_plural = "cost centres"

    def clean(self) -> None:
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError({"parent": "A cost centre cannot be its own parent."})

        ancestor = self.parent
        seen: set[int] = set()
        while ancestor is not None:
            if ancestor.pk in seen or ancestor.pk == self.pk:
                raise ValidationError({"parent": "Cost centres cannot form a cycle."})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent
