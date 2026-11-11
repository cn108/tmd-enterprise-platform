"""Shared model building blocks for master data.

Every master record carries its own audit columns (M-08) and a stable code.
Nothing here encodes a business policy: codes, names and limits are supplied by
the client, never seeded.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserStampedModel(TimeStampedModel):
    """Audit columns for master data (M-08).

    ``SET_NULL`` keeps history when a user is offboarded; user rows are never
    hard-deleted anyway (ADM-01).
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class CodedModel(UserStampedModel):
    """A coded master record with an active flag (M-05).

    Codes are normalised to upper case so that ``fin`` and ``FIN`` cannot both
    exist as different records.
    """

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)
