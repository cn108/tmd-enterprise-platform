from django.contrib import admin

from apps.procurement.models import (
    DeliverySchedule,
    Destination,
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    RequestForQuotation,
    RfqSupplier,
    SupplierQuote,
    SupplierQuoteLine,
    SupplierSelection,
)


class PurchaseRequestLineInline(admin.TabularInline):
    model = PurchaseRequestLine
    extra = 0


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "requester", "destination", "status", "required_by")
    list_filter = ("status",)
    search_fields = ("number", "justification")
    inlines = [PurchaseRequestLineInline]


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("kind", "project", "warehouse", "location_name")


@admin.register(RequestForQuotation)
class RequestForQuotationAdmin(admin.ModelAdmin):
    list_display = ("number", "request", "status", "due_date")
    list_filter = ("status",)


@admin.register(RfqSupplier)
class RfqSupplierAdmin(admin.ModelAdmin):
    list_display = ("rfq", "supplier")


class SupplierQuoteLineInline(admin.TabularInline):
    model = SupplierQuoteLine
    extra = 0


@admin.register(SupplierQuote)
class SupplierQuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "rfq", "supplier", "currency")
    inlines = [SupplierQuoteLineInline]


@admin.register(SupplierSelection)
class SupplierSelectionAdmin(admin.ModelAdmin):
    list_display = ("rfq", "quote", "reason")


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0
    readonly_fields = ("quantity_accepted", "quantity_rejected", "quantity_damaged")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "supplier", "request", "status", "issued_at")
    list_filter = ("status",)
    inlines = [PurchaseOrderLineInline]


@admin.register(DeliverySchedule)
class DeliveryScheduleAdmin(admin.ModelAdmin):
    list_display = ("order_line", "due_date", "quantity", "destination", "quantity_delivered")


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0


@admin.register(GoodsReceiptNote)
class GoodsReceiptNoteAdmin(admin.ModelAdmin):
    list_display = ("number", "order", "received_at", "received_by")
    inlines = [GoodsReceiptLineInline]
