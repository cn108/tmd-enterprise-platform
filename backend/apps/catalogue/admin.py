from django.contrib import admin

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


@admin.register(CatalogueItem)
class CatalogueItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "category", "uom", "is_active")
    list_filter = ("kind", "is_active", "tracks_batches", "tracks_serials")
    search_fields = ("code", "name", "brand")
    filter_horizontal = ("preferred_suppliers",)
    ordering = ("code",)


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "base_uom", "conversion_factor", "is_active")


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "is_active")


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "country", "is_active")


@admin.register(ItemPrice)
class ItemPriceAdmin(admin.ModelAdmin):
    list_display = ("item", "amount", "currency", "effective_from", "effective_to")
    search_fields = ("item__code",)


@admin.register(TechnicalSpecification)
class TechnicalSpecificationAdmin(admin.ModelAdmin):
    list_display = ("item", "name", "value", "unit")
    search_fields = ("item__code", "name")


@admin.register(ItemBatch)
class ItemBatchAdmin(admin.ModelAdmin):
    list_display = ("item", "batch_number", "manufactured_on", "expires_on")
    search_fields = ("item__code", "batch_number")


@admin.register(SerialNumber)
class SerialNumberAdmin(admin.ModelAdmin):
    list_display = ("item", "serial", "batch", "is_active")
    search_fields = ("item__code", "serial")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_type", "issuer", "item", "batch", "serial", "expires_on")
    search_fields = ("certificate_type", "issuer", "reference")
