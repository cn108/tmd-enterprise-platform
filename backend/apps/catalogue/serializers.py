from __future__ import annotations

from datetime import date

from rest_framework import serializers

from apps.catalogue.models import (
    CatalogueItem,
    Certificate,
    ItemBatch,
    ItemPrice,
    Manufacturer,
    ProductCategory,
    SerialNumber,
    TechnicalSpecification,
    UnitOfMeasure,
)
from shared.serializers import CodedSerializerMixin


class UnitOfMeasureSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = [
            "id",
            "code",
            "name",
            "base_uom",
            "conversion_factor",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        base = attrs.get("base_uom", getattr(self.instance, "base_uom", None))
        factor = attrs.get("conversion_factor", getattr(self.instance, "conversion_factor", None))
        if base is not None and factor is None:
            raise serializers.ValidationError({"conversion_factor": "A conversion needs a factor."})
        if factor is not None and base is None:
            raise serializers.ValidationError({"base_uom": "A factor needs a base unit."})
        if factor is not None and factor <= 0:
            raise serializers.ValidationError(
                {"conversion_factor": "The factor must be greater than zero."}
            )
        return attrs


class ProductCategorySerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "code", "name", "parent", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class ManufacturerSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = [
            "id",
            "code",
            "name",
            "website",
            "country",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CatalogueItemSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    is_stock_tracked = serializers.BooleanField(read_only=True)

    class Meta:
        model = CatalogueItem
        fields = [
            "id",
            "code",
            "name",
            "kind",
            "description",
            "category",
            "uom",
            "manufacturer",
            "brand",
            "specification_summary",
            "tax_classification",
            "tracks_batches",
            "tracks_serials",
            "tracks_expiry",
            "preferred_suppliers",
            "is_stock_tracked",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "is_stock_tracked"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        tracks = any(
            attrs.get(field, getattr(self.instance, field, False))
            for field in ("tracks_batches", "tracks_serials", "tracks_expiry")
        )
        if kind == CatalogueItem.Kind.SERVICE and tracks:
            raise serializers.ValidationError(
                "A service cannot track batches, serial numbers or expiry."
            )
        return attrs


class ItemPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPrice
        fields = [
            "id",
            "item",
            "currency",
            "amount",
            "effective_from",
            "effective_to",
            "source_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        item = attrs.get("item", getattr(self.instance, "item", None))
        start = attrs.get("effective_from", getattr(self.instance, "effective_from", None))
        end = attrs.get("effective_to", getattr(self.instance, "effective_to", None))

        if start and end and end < start:
            raise serializers.ValidationError(
                {"effective_to": "The end date cannot precede the start date."}
            )

        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        if amount is not None and amount < 0:
            raise serializers.ValidationError({"amount": "A price cannot be negative."})

        if item and start:
            existing = ItemPrice.objects.filter(item=item)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            this_end = end or date.max
            for other in existing:
                other_end = other.effective_to or date.max
                if start <= other_end and other.effective_from <= this_end:
                    raise serializers.ValidationError(
                        {"effective_from": "This price period overlaps an existing price."}
                    )
        return attrs


class TechnicalSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicalSpecification
        fields = [
            "id",
            "item",
            "name",
            "value",
            "unit",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ItemBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemBatch
        fields = [
            "id",
            "item",
            "batch_number",
            "manufactured_on",
            "expires_on",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        manufactured = attrs.get("manufactured_on", getattr(self.instance, "manufactured_on", None))
        expires = attrs.get("expires_on", getattr(self.instance, "expires_on", None))
        if manufactured and expires and expires < manufactured:
            raise serializers.ValidationError({"expires_on": "Expiry cannot precede manufacture."})
        return attrs


class SerialNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = SerialNumber
        fields = [
            "id",
            "item",
            "serial",
            "batch",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        item = attrs.get("item", getattr(self.instance, "item", None))
        batch = attrs.get("batch", getattr(self.instance, "batch", None))
        if batch is not None and item is not None and batch.item_id != item.pk:
            raise serializers.ValidationError({"batch": "The batch belongs to a different item."})
        return attrs


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = [
            "id",
            "item",
            "batch",
            "serial",
            "document",
            "certificate_type",
            "issuer",
            "reference",
            "issued_on",
            "expires_on",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        item = attrs.get("item", getattr(self.instance, "item", None))
        batch = attrs.get("batch", getattr(self.instance, "batch", None))
        serial_number = attrs.get("serial", getattr(self.instance, "serial", None))

        if not any([item, batch, serial_number]):
            raise serializers.ValidationError(
                "A certificate must reference an item, batch or serial number."
            )
        if batch and item and batch.item_id != item.pk:
            raise serializers.ValidationError({"batch": "The batch belongs to a different item."})
        if serial_number and item and serial_number.item_id != item.pk:
            raise serializers.ValidationError(
                {"serial": "The serial number belongs to a different item."}
            )

        issued = attrs.get("issued_on", getattr(self.instance, "issued_on", None))
        expires = attrs.get("expires_on", getattr(self.instance, "expires_on", None))
        if issued and expires and expires < issued:
            raise serializers.ValidationError(
                {"expires_on": "Expiry cannot precede the issue date."}
            )
        return attrs
