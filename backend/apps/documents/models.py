"""Document management (MAS-07, DOC-01, DOC-02).

Files are private: there is no media URL route, and downloads go through an
authenticated endpoint. Categories, retention periods and access rules are
client configuration; no retention period is invented (Q-28 unresolved).

``DocumentLink`` attaches a document to a business record without importing
every domain module here, which keeps this app free of circular imports.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.db import models

from shared.models import CodedModel, UserStampedModel


def document_upload_path(instance: Document, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"documents/{uuid.uuid4().hex}{suffix}"


class DocumentCategory(CodedModel):
    retention_months = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "document category"
        verbose_name_plural = "document categories"


class Document(UserStampedModel):
    category = models.ForeignKey(
        DocumentCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=document_upload_path, max_length=255)
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    version = models.PositiveIntegerField(default=1)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="superseded_by",
    )
    is_private = models.BooleanField(default=True)
    retention_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "document"
        verbose_name_plural = "documents"

    def save(self, *args, **kwargs):
        # Checksum and size are derived from the bytes actually stored, not from
        # anything the client claims.
        if self.file and not self.checksum_sha256:
            digest = hashlib.sha256()
            size = 0
            for chunk in self.file.chunks():
                digest.update(chunk)
                size += len(chunk)
            self.file.seek(0)
            self.checksum_sha256 = digest.hexdigest()
            self.size_bytes = size
            self.original_filename = self.original_filename or Path(self.file.name).name
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class DocumentLink(UserStampedModel):
    class EntityType(models.TextChoices):
        SUPPLIER = "supplier", "Supplier"
        CUSTOMER = "customer", "Customer"
        PROJECT = "project", "Project"
        CONTRACT = "contract", "Customer contract"
        CATALOGUE_ITEM = "catalogue_item", "Catalogue item"
        WAREHOUSE = "warehouse", "Warehouse"
        STORAGE_LOCATION = "storage_location", "Storage location"
        CERTIFICATE = "certificate", "Certificate"
        COMPLIANCE_DOCUMENT = "compliance_document", "Compliance document"
        SUPPLIER_INVOICE = "supplier_invoice", "Supplier invoice"
        WORK_ORDER = "service_work_order", "Engineering / maintenance work order"
        RENTAL_AGREEMENT = "rental_agreement", "Equipment rental agreement"

    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="links")
    entity_type = models.CharField(max_length=32, choices=EntityType.choices)
    entity_id = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["document", "entity_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "entity_type", "entity_id"],
                name="unique_document_link",
            )
        ]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def __str__(self) -> str:
        return f"{self.document_id} → {self.entity_type}:{self.entity_id}"
