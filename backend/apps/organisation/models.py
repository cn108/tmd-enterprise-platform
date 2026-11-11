"""Organisational structure.

Only departments exist in this phase because user scoping needs them. Offices,
warehouses and projects arrive with master data in Phase 3, once D-02 is
answered.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class Department(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
