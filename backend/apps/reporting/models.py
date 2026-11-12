"""Reporting access control and export records.

Report reads are not anonymous and financial reports are not available to every
signed-in employee. The permissions below are attached to a real model so they
are managed through the same role bundles as every other capability.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from shared.models import TimeStampedModel


class ReportExport(TimeStampedModel):
    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        PDF = "pdf", "PDF"

    report_name = models.CharField(max_length=60)
    export_format = models.CharField(max_length=3, choices=Format.choices)
    parameters = models.JSONField(default=dict, blank=True)
    exported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="report_exports",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "report export"
        verbose_name_plural = "report exports"
        permissions = [
            ("view_reporting", "Can view operational reports"),
            ("view_financialreporting", "Can view financial reports and dashboards"),
            ("export_reporting", "Can export reports"),
        ]

    def __str__(self) -> str:
        return f"{self.report_name} ({self.export_format})"
