"""Warehouses and storage locations (MAS-06).

Warehouses are standalone records with a free-text site name because D-02 (the
office/warehouse/site structure) is unresolved. Nothing here assumes a
hierarchy: a site name is a label, not a foreign key to an unapproved structure.
"""

from __future__ import annotations

from django.db import models

from shared.models import CodedModel, UserStampedModel


class Warehouse(CodedModel):
    site_name = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "warehouse"
        verbose_name_plural = "warehouses"


class StorageLocation(UserStampedModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="locations")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["warehouse__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "code"], name="unique_location_code_per_warehouse"
            )
        ]

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.warehouse.code}/{self.code}"
