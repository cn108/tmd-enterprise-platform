from django.contrib import admin

from apps.warehousing.models import StorageLocation, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "site_name", "is_active")
    search_fields = ("code", "name", "site_name")


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "code", "name", "is_active")
    list_filter = ("warehouse", "is_active")
    search_fields = ("warehouse__code", "code")
