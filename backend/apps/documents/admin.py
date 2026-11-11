from django.contrib import admin

from apps.documents.models import Document, DocumentCategory, DocumentLink


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "retention_months", "is_active")
    search_fields = ("code", "name")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "original_filename", "size_bytes", "version", "created_at")
    list_filter = ("category", "is_private")
    search_fields = ("title", "original_filename")
    readonly_fields = ("checksum_sha256", "size_bytes", "mime_type", "original_filename")


@admin.register(DocumentLink)
class DocumentLinkAdmin(admin.ModelAdmin):
    list_display = ("document", "entity_type", "entity_id")
    list_filter = ("entity_type",)
