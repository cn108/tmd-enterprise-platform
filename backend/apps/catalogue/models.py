"""Catalogue master data (MAS-03, MAS-04).

Products and services share one table so a SKU cannot be duplicated across the
two kinds, and so price history and specifications have one owner. Traceability
flags (batch, serial, expiry) are per item and default to off because Q-17
(which items need them) is unresolved: the safe default tracks nothing.

Nothing here sets a tax rate, a price, a category or a unit conversion. Those
are client data; tax codes themselves arrive with MAS-05.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from shared.models import CodedModel, UserStampedModel


class UnitOfMeasure(CodedModel):
    """A unit, optionally converted to a base unit (Q-14).

    Conversion is optional because the client has not yet said whether
    conversions are needed. A factor without a base unit, or a base unit without
    a factor, is rejected rather than guessed.
    """

    base_uom = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="conversions",
    )
    conversion_factor = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "unit of measure"
        verbose_name_plural = "units of measure"

    def clean(self) -> None:
        if self.base_uom_id is not None and self.base_uom_id == self.pk:
            raise ValidationError({"base_uom": "A unit cannot be its own base unit."})
        if (self.base_uom_id is None) != (self.conversion_factor is None):
            raise ValidationError(
                {"conversion_factor": "A conversion needs both a base unit and a factor."}
            )
        if self.conversion_factor is not None and self.conversion_factor <= 0:
            raise ValidationError({"conversion_factor": "The factor must be greater than zero."})


class ProductCategory(CodedModel):
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )


class Manufacturer(CodedModel):
    website = models.URLField(blank=True)
    country = models.CharField(max_length=80, blank=True)


class CatalogueItem(CodedModel):
    class Kind(models.TextChoices):
        PRODUCT = "product", "Product"
        SERVICE = "service", "Service"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ProductCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="items",
    )
    uom = models.ForeignKey(
        UnitOfMeasure,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="items",
    )
    manufacturer = models.ForeignKey(
        Manufacturer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="items",
    )
    brand = models.CharField(max_length=120, blank=True)
    specification_summary = models.TextField(blank=True)
    tax_classification = models.CharField(max_length=80, blank=True)
    tracks_batches = models.BooleanField(default=False)
    tracks_serials = models.BooleanField(default=False)
    tracks_expiry = models.BooleanField(default=False)
    preferred_suppliers = models.ManyToManyField(
        "parties.Party", blank=True, related_name="preferred_items"
    )

    class Meta:
        ordering = ["code"]
        verbose_name = "catalogue item"
        verbose_name_plural = "catalogue items"

    def clean(self) -> None:
        if self.kind == self.Kind.SERVICE and (
            self.tracks_batches or self.tracks_serials or self.tracks_expiry
        ):
            raise ValidationError("A service cannot track batches, serial numbers or expiry.")

    @property
    def is_stock_tracked(self) -> bool:
        return self.kind == self.Kind.PRODUCT

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class ItemPrice(UserStampedModel):
    """Effective-dated price history (MAS-03).

    A new price is a new row; existing rows are never edited so historical
    documents can keep the price that applied when they were raised.
    """

    item = models.ForeignKey(CatalogueItem, on_delete=models.PROTECT, related_name="prices")
    currency = models.CharField(max_length=3, default="NGN")
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    source_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["item__code", "-effective_from"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="price_effective_to_after_from",
            )
        ]

    def clean(self) -> None:
        if self.amount is not None and self.amount < Decimal("0"):
            raise ValidationError({"amount": "A price cannot be negative."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the start date."})


class TechnicalSpecification(UserStampedModel):
    item = models.ForeignKey(
        CatalogueItem, on_delete=models.PROTECT, related_name="technical_specifications"
    )
    name = models.CharField(max_length=120)
    value = models.CharField(max_length=255)
    unit = models.CharField(max_length=40, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["item__code", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["item", "name"], name="unique_specification_per_item")
        ]


class ItemBatch(UserStampedModel):
    """A manufacturer batch/lot recorded against an item (Q-17).

    Stock quantities and balances do not live here; this is the traceability
    record that Phase 5 movements will reference.
    """

    item = models.ForeignKey(CatalogueItem, on_delete=models.PROTECT, related_name="batches")
    batch_number = models.CharField(max_length=80)
    manufactured_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["item__code", "batch_number"]
        constraints = [
            models.UniqueConstraint(fields=["item", "batch_number"], name="unique_batch_per_item")
        ]

    def clean(self) -> None:
        if self.manufactured_on and self.expires_on and self.expires_on < self.manufactured_on:
            raise ValidationError({"expires_on": "Expiry cannot precede manufacture."})

    def __str__(self) -> str:
        return f"{self.item.code}/{self.batch_number}"


class SerialNumber(UserStampedModel):
    item = models.ForeignKey(CatalogueItem, on_delete=models.PROTECT, related_name="serials")
    serial = models.CharField(max_length=120)
    batch = models.ForeignKey(
        ItemBatch,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="serials",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item__code", "serial"]
        constraints = [
            models.UniqueConstraint(fields=["item", "serial"], name="unique_serial_per_item")
        ]

    def __str__(self) -> str:
        return f"{self.item.code}/{self.serial}"


class Certificate(UserStampedModel):
    """A certificate attached to an item, batch or serial, with its document."""

    item = models.ForeignKey(
        CatalogueItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="certificates",
    )
    batch = models.ForeignKey(
        ItemBatch,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="certificates",
    )
    serial = models.ForeignKey(
        SerialNumber,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="certificates",
    )
    document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates",
    )
    certificate_type = models.CharField(max_length=80)
    issuer = models.CharField(max_length=120, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_on", "certificate_type"]

    def clean(self) -> None:
        if not any([self.item_id, self.batch_id, self.serial_id]):
            raise ValidationError("A certificate must reference an item, batch or serial number.")
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            raise ValidationError({"expires_on": "Expiry cannot precede the issue date."})

    def __str__(self) -> str:
        return f"{self.certificate_type} ({self.issuer or 'unissued'})"
