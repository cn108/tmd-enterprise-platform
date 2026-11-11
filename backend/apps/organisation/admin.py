from django.contrib import admin

from apps.organisation.models import CostCentre, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(CostCentre)
class CostCentreAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "department", "is_active")
    list_filter = ("is_active", "department")
    search_fields = ("code", "name")
    ordering = ("code",)
