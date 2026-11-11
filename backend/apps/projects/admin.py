from django.contrib import admin

from apps.projects.models import ContractRevision, CustomerContract, Project, ProjectLocation


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "customer", "status", "start_date", "end_date")
    list_filter = ("status",)
    search_fields = ("code", "name", "customer__legal_name")
    filter_horizontal = ("managers",)
    ordering = ("code",)


@admin.register(ProjectLocation)
class ProjectLocationAdmin(admin.ModelAdmin):
    list_display = ("project", "name", "is_primary", "is_active")
    list_filter = ("is_primary", "is_active")
    search_fields = ("project__code", "name")


@admin.register(CustomerContract)
class CustomerContractAdmin(admin.ModelAdmin):
    list_display = ("reference", "project", "customer", "value", "currency", "is_active")
    search_fields = ("reference", "project__code", "customer__legal_name")


@admin.register(ContractRevision)
class ContractRevisionAdmin(admin.ModelAdmin):
    list_display = ("contract", "revision_number", "value", "currency", "start_date")
    search_fields = ("contract__reference",)
