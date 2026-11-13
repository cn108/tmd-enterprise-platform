"""Phase 7 API surface: invoices, notes, payments, NRS state and settings."""

from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from apps.core.models import create_audit_event
from apps.documents.models import Document, DocumentLink
from apps.invoicing.emailing import (
    InvoiceEmailDeliveryError,
    InvoiceEmailError,
    send_customer_invoice_email,
    send_supplier_invoice_email,
)
from apps.invoicing.models import (
    CustomerInvoice,
    CustomerReceipt,
    CustomerReceiptAllocation,
    InvoiceNote,
    InvoiceSettings,
    NrsSubmission,
    SupplierInvoice,
    SupplierPayment,
    money,
)
from apps.invoicing.pdf import (
    customer_invoice_pdf,
    customer_statement_pdf,
    invoice_note_pdf,
    supplier_invoice_pdf,
)
from apps.invoicing.serializers import (
    CustomerInvoiceSerializer,
    CustomerReceiptAllocationRequestSerializer,
    CustomerReceiptAllocationSerializer,
    CustomerReceiptSerializer,
    InvoiceEmailSerializer,
    InvoiceNoteSerializer,
    InvoiceSettingsSerializer,
    NrsSubmissionSerializer,
    PaymentAllocationRequestSerializer,
    PaymentAllocationSerializer,
    SupplierInvoiceSerializer,
    SupplierPaymentSerializer,
)
from apps.invoicing.services import (
    InvoiceConflict,
    activate_invoices,
    allocate_customer_receipt,
    allocate_payment,
    approve_customer_invoice,
    approve_customer_receipt,
    approve_note,
    approve_payment,
    approve_supplier_invoice,
    cancel_customer_invoice,
    cancel_customer_receipt,
    cancel_note,
    cancel_payment,
    cancel_supplier_invoice,
    duplicate_candidates,
    post_customer_receipt,
    post_invoice,
    post_supplier_payment,
    record_payment,
    reject_customer_invoice,
    reject_customer_receipt,
    reject_note,
    reject_payment,
    reject_supplier_invoice,
    reverse_customer_receipt_allocation,
    submit_customer_invoice,
    submit_customer_receipt,
    submit_note,
    submit_payment,
    submit_supplier_invoice,
    submit_to_nrs,
)
from shared.exceptions import error_response

MANAGE_SETTINGS = "invoicing.manage_invoicesettings"


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


def _conflict(exc: InvoiceConflict) -> Response:
    return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)


class InvoiceViewPermissionMixin:
    """Require the model view permission for every safe read, including PDFs."""

    view_permission = ""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in SAFE_METHODS and self.view_permission:
            _require(request, self.view_permission)


class SupplierInvoiceViewSet(InvoiceViewPermissionMixin, viewsets.ModelViewSet):
    view_permission = "invoicing.view_supplierinvoice"
    queryset = SupplierInvoice.objects.select_related(
        "supplier", "purchase_order"
    ).prefetch_related("lines")
    serializer_class = SupplierInvoiceSerializer
    search_fields = (
        "number",
        "supplier_invoice_number",
        "supplier__legal_name",
        "purchase_order__number",
    )
    ordering_fields = ("number", "invoice_date", "due_date", "total", "status", "created_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("status", "supplier", "purchase_order", "match_status", "duplicate_status"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "invoicing.add_supplierinvoice")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "invoicing.change_supplierinvoice")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Invoices are cancelled, never deleted; the number record is preserved.",
            status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "invoicing.change_supplierinvoice")
        try:
            invoice = submit_supplier_invoice(self.get_object(), request.user)
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "invoicing.approve_supplierinvoice")
        try:
            invoice = approve_supplier_invoice(
                self.get_object(), request.user, (request.data.get("notes") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "invoicing.approve_supplierinvoice")
        try:
            invoice = reject_supplier_invoice(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        _require(request, "invoicing.cancel_supplierinvoice")
        try:
            invoice = cancel_supplier_invoice(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        _require(request, "invoicing.post_supplierinvoice")
        key = (
            request.headers.get("Idempotency-Key")
            or request.data.get("idempotency_key")
            or f"invoice-post-supplier-{pk}"
        ).strip()
        try:
            invoice = self.get_object()
            journal, replayed = post_invoice(invoice, request.user, key)
        except InvoiceConflict as exc:
            return _conflict(exc)
        response = Response(
            {
                "detail": f"{invoice.number} posted to {journal.number}.",
                "journal_entry": journal.pk,
                "journal_number": journal.number,
            }
        )
        if replayed:
            response["Idempotency-Replayed"] = "true"
        return response

    @action(detail=True, methods=["post"], url_path="attach-document")
    def attach_document(self, request, pk=None):
        _require(request, "invoicing.change_supplierinvoice")
        invoice = self.get_object()
        document = Document.objects.filter(pk=request.data.get("document")).first()
        if document is None:
            return error_response("not_found", "Unknown document.", status.HTTP_404_NOT_FOUND)
        link, created = DocumentLink.objects.get_or_create(
            document=document,
            entity_type=DocumentLink.EntityType.SUPPLIER_INVOICE,
            entity_id=invoice.pk,
            defaults={"created_by": request.user, "updated_by": request.user},
        )
        if created:
            create_audit_event(
                actor=request.user,
                action="supplier_invoice.document_attached",
                entity_type="invoicing.supplierinvoice",
                entity_id=invoice.pk,
                after={"document": document.pk, "title": document.title},
                request=request,
            )
        return Response(
            {"id": link.pk, "document": document.pk, "title": document.title},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        return supplier_invoice_pdf(invoice, download=request.query_params.get("download") == "1")

    @action(detail=True, methods=["post"])
    def email(self, request, pk=None):
        _require(request, "invoicing.view_supplierinvoice")
        _require(request, "invoicing.email_supplierinvoice")
        payload = InvoiceEmailSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = send_supplier_invoice_email(
                self.get_object(),
                payload.validated_data["to"],
                payload.validated_data.get("cc", ""),
                payload.validated_data.get("message", ""),
                request.user,
                request=request,
            )
        except InvoiceEmailDeliveryError as exc:
            return error_response(
                "email_delivery_failed", str(exc), status.HTTP_502_BAD_GATEWAY
            )
        except InvoiceEmailError as exc:
            return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)
        return Response(result)

    @action(detail=False, methods=["get"], url_path="check-duplicate")
    def check_duplicate(self, request):
        _require(request, "invoicing.view_supplierinvoice")
        from apps.parties.models import Party

        supplier = Party.objects.filter(pk=request.query_params.get("supplier")).first()
        if supplier is None:
            return error_response(
                "invalid_request", "Supply a valid supplier.", status.HTTP_400_BAD_REQUEST
            )
        try:
            total = money(request.query_params.get("total") or "0")
            from datetime import date

            invoice_date = date.fromisoformat(
                request.query_params.get("invoice_date") or "1900-01-01"
            )
        except ValueError:
            return error_response(
                "invalid_request", "Supply a valid date and total.", status.HTTP_400_BAD_REQUEST
            )
        candidates = duplicate_candidates(
            supplier=supplier,
            supplier_invoice_number=request.query_params.get("supplier_invoice_number") or "",
            total=total,
            invoice_date=invoice_date,
        )
        return Response(
            {
                "candidates": [
                    {
                        "id": item.pk,
                        "number": item.number,
                        "supplier_invoice_number": item.supplier_invoice_number,
                        "invoice_date": item.invoice_date,
                        "total": str(item.total),
                        "status": item.status,
                    }
                    for item in candidates
                ]
            }
        )


class CustomerInvoiceViewSet(InvoiceViewPermissionMixin, viewsets.ModelViewSet):
    view_permission = "invoicing.view_customerinvoice"
    queryset = CustomerInvoice.objects.select_related("customer", "project").prefetch_related(
        "lines"
    )
    serializer_class = CustomerInvoiceSerializer
    search_fields = ("number", "customer_reference", "customer__legal_name", "project__code")
    ordering_fields = ("number", "invoice_date", "due_date", "total", "status", "created_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("status", "customer", "project"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "invoicing.add_customerinvoice")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "invoicing.change_customerinvoice")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Invoices are cancelled, never deleted; the number record is preserved.",
            status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "invoicing.change_customerinvoice")
        try:
            invoice = submit_customer_invoice(self.get_object(), request.user)
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "invoicing.approve_customerinvoice")
        try:
            invoice = approve_customer_invoice(
                self.get_object(), request.user, (request.data.get("notes") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "invoicing.approve_customerinvoice")
        try:
            invoice = reject_customer_invoice(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        _require(request, "invoicing.cancel_customerinvoice")
        try:
            invoice = cancel_customer_invoice(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        _require(request, "invoicing.post_customerinvoice")
        key = (
            request.headers.get("Idempotency-Key")
            or request.data.get("idempotency_key")
            or f"invoice-post-customer-{pk}"
        ).strip()
        try:
            invoice = self.get_object()
            journal, replayed = post_invoice(invoice, request.user, key)
        except InvoiceConflict as exc:
            return _conflict(exc)
        response = Response(
            {
                "detail": f"{invoice.number} posted to {journal.number}.",
                "journal_entry": journal.pk,
                "journal_number": journal.number,
            }
        )
        if replayed:
            response["Idempotency-Replayed"] = "true"
        return response

    @action(detail=True, methods=["post"], url_path="submit-nrs")
    def submit_nrs(self, request, pk=None):
        _require(request, "invoicing.submit_nrs")
        submission = submit_to_nrs(self.get_object(), request.user)
        if submission.status == NrsSubmission.Status.DISABLED:
            return error_response(
                "invalid_state",
                "NRS integration is disabled by the feature flag.",
                status.HTTP_409_CONFLICT,
            )
        if submission.status == NrsSubmission.Status.FAILED:
            return error_response("invalid_state", submission.error, status.HTTP_409_CONFLICT)
        return Response(NrsSubmissionSerializer(submission).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        return customer_invoice_pdf(invoice, download=request.query_params.get("download") == "1")

    @action(detail=True, methods=["post"])
    def email(self, request, pk=None):
        _require(request, "invoicing.view_customerinvoice")
        _require(request, "invoicing.email_customerinvoice")
        payload = InvoiceEmailSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = send_customer_invoice_email(
                self.get_object(),
                payload.validated_data["to"],
                payload.validated_data.get("cc", ""),
                payload.validated_data.get("message", ""),
                request.user,
                request=request,
            )
        except InvoiceEmailDeliveryError as exc:
            return error_response(
                "email_delivery_failed", str(exc), status.HTTP_502_BAD_GATEWAY
            )
        except InvoiceEmailError as exc:
            return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)
        return Response(result)


class InvoiceNoteViewSet(InvoiceViewPermissionMixin, viewsets.ModelViewSet):
    view_permission = "invoicing.view_invoicenote"
    queryset = InvoiceNote.objects.select_related(
        "supplier_invoice__supplier", "customer_invoice__customer"
    ).prefetch_related("lines")
    serializer_class = InvoiceNoteSerializer
    search_fields = (
        "number",
        "reason",
        "supplier_invoice__supplier__legal_name",
        "customer_invoice__customer__legal_name",
    )
    ordering_fields = ("number", "note_date", "total", "status", "created_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("status", "note_type", "party_kind"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "invoicing.add_invoicenote")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "invoicing.change_invoicenote")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Notes are cancelled, never deleted; the number record is preserved.",
            status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "invoicing.change_invoicenote")
        try:
            note = submit_note(self.get_object(), request.user)
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "invoicing.approve_invoicenote")
        try:
            note = approve_note(
                self.get_object(), request.user, (request.data.get("notes") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "invoicing.approve_invoicenote")
        try:
            note = reject_note(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        _require(request, "invoicing.cancel_invoicenote")
        try:
            note = cancel_note(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        note = self.get_object()
        return invoice_note_pdf(note, download=request.query_params.get("download") == "1")


class CustomerReceiptViewSet(InvoiceViewPermissionMixin, viewsets.ModelViewSet):
    view_permission = "invoicing.view_customerreceipt"
    queryset = CustomerReceipt.objects.select_related(
        "customer", "company_bank_account", "journal_entry", "reversal_entry"
    ).prefetch_related(
        "allocations__invoice"
    )
    serializer_class = CustomerReceiptSerializer
    search_fields = ("number", "customer__legal_name", "external_reference")
    ordering_fields = ("number", "receipt_date", "amount", "status", "created_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("status", "customer"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "invoicing.add_customerreceipt")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return error_response(
            "invalid_state",
            "A recorded receipt is changed by allocation or cancellation, not by editing it.",
            status.HTTP_409_CONFLICT,
        )

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Receipts are cancelled, never deleted; the number record is preserved.",
            status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        _require(request, "invoicing.allocate_customerreceipt")
        receipt = self.get_object()
        payload = CustomerReceiptAllocationRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        invoice = CustomerInvoice.objects.filter(pk=payload.validated_data["invoice"]).first()
        if invoice is None:
            return error_response(
                "not_found", "Unknown customer invoice.", status.HTTP_404_NOT_FOUND
            )
        try:
            allocation = allocate_customer_receipt(
                receipt.pk, invoice, payload.validated_data["amount"], request.user
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(
            {
                "id": allocation.pk,
                "invoice": invoice.pk,
                "invoice_number": invoice.number,
                "amount": str(allocation.amount),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        _require(request, "invoicing.cancel_customerreceipt")
        try:
            receipt = cancel_customer_receipt(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(receipt).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "invoicing.change_customerreceipt")
        try:
            receipt = submit_customer_receipt(self.get_object(), request.user)
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(receipt).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "invoicing.approve_customerreceipt")
        try:
            receipt = approve_customer_receipt(
                self.get_object(), request.user, (request.data.get("notes") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(receipt).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "invoicing.approve_customerreceipt")
        try:
            receipt = reject_customer_receipt(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(receipt).data)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        _require(request, "invoicing.post_customerreceipt")
        key = (
            request.headers.get("Idempotency-Key")
            or request.data.get("idempotency_key")
            or f"receipt-post-{pk}"
        ).strip()
        try:
            receipt = self.get_object()
            journal, replayed = post_customer_receipt(receipt, request.user, key)
        except InvoiceConflict as exc:
            return _conflict(exc)
        receipt.refresh_from_db()
        return Response(
            {
                "detail": f"{receipt.number} posted to {journal.number}.",
                "journal_entry": journal.pk,
                "journal_number": journal.number,
                "replayed": replayed,
                "receipt": self.get_serializer(receipt).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="reverse-allocation")
    def reverse_allocation(self, request, pk=None):
        _require(request, "invoicing.allocate_customerreceipt")
        receipt = self.get_object()
        allocation = receipt.allocations.filter(pk=request.data.get("allocation")).first()
        if allocation is None:
            return error_response(
                "not_found", "Unknown allocation on this receipt.", status.HTTP_404_NOT_FOUND
            )
        try:
            reverse_customer_receipt_allocation(
                allocation, request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        receipt = self.get_queryset().get(pk=receipt.pk)
        return Response(self.get_serializer(receipt).data)

    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        receipt = self.get_object()
        return customer_statement_pdf(receipt, download=request.query_params.get("download") == "1")


class CustomerReceiptAllocationViewSet(InvoiceViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only allocation register used by the receipt reversal control."""

    view_permission = "invoicing.view_customerreceipt"
    queryset = CustomerReceiptAllocation.objects.select_related(
        "receipt", "invoice"
    ).order_by("-id")
    serializer_class = CustomerReceiptAllocationSerializer
    search_fields = ("receipt__number", "invoice__number")

    def get_queryset(self):
        queryset = super().get_queryset()
        receipt = (self.request.query_params.get("receipt") or "").strip()
        if receipt:
            queryset = queryset.filter(receipt_id=receipt)
        reversed_value = (self.request.query_params.get("is_reversed") or "").strip()
        if reversed_value in {"true", "false"}:
            queryset = queryset.filter(is_reversed=reversed_value == "true")
        return queryset


class SupplierPaymentViewSet(InvoiceViewPermissionMixin, viewsets.ModelViewSet):
    view_permission = "invoicing.view_supplierpayment"
    queryset = SupplierPayment.objects.select_related("supplier").prefetch_related("allocations")
    serializer_class = SupplierPaymentSerializer
    search_fields = ("number", "supplier__legal_name", "external_reference")
    ordering_fields = ("number", "payment_date", "amount", "status", "created_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("status", "supplier"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "invoicing.add_supplierpayment")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "invoicing.change_supplierpayment")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Payments are cancelled, never deleted.",
            status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "invoicing.change_supplierpayment")
        try:
            payment = submit_payment(self.get_object(), request.user)
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "invoicing.approve_payment")
        try:
            payment = approve_payment(
                self.get_object(), request.user, (request.data.get("notes") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "invoicing.approve_payment")
        try:
            payment = reject_payment(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=["post"])
    def record(self, request, pk=None):
        _require(request, "invoicing.record_payment")
        key = (
            request.headers.get("Idempotency-Key") or request.data.get("idempotency_key") or ""
        ).strip()
        try:
            payment, replayed = record_payment(self.get_object(), request.user, key)
        except InvoiceConflict as exc:
            return _conflict(exc)
        response = Response(self.get_serializer(payment).data)
        if replayed:
            response["Idempotency-Replayed"] = "true"
        return response

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        _require(request, "invoicing.post_supplierpayment")
        key = (
            request.headers.get("Idempotency-Key")
            or request.data.get("idempotency_key")
            or f"payment-post-{pk}"
        ).strip()
        try:
            journal, replayed = post_supplier_payment(self.get_object(), request.user, key)
        except InvoiceConflict as exc:
            return _conflict(exc)
        payment = self.get_object()
        response = Response(
            {
                "detail": f"{payment.number} posted to {journal.number}.",
                "journal_entry": journal.pk,
                "journal_number": journal.number,
                "status": payment.status,
            }
        )
        if replayed:
            response["Idempotency-Replayed"] = "true"
        return response

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        _require(request, "invoicing.allocate_payment")
        payload = PaymentAllocationRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        invoice = SupplierInvoice.objects.filter(
            pk=payload.validated_data["supplier_invoice"]
        ).first()
        if invoice is None:
            return error_response(
                "not_found", "Unknown supplier invoice.", status.HTTP_404_NOT_FOUND
            )
        try:
            allocation = allocate_payment(
                self.get_object(), invoice, payload.validated_data["amount"], request.user
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(
            PaymentAllocationSerializer(allocation).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        _require(request, "invoicing.change_supplierpayment")
        try:
            payment = cancel_payment(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(payment).data)


class InvoiceSettingsViewSet(InvoiceViewPermissionMixin, viewsets.GenericViewSet):
    view_permission = "invoicing.view_invoicesettings"
    queryset = InvoiceSettings.objects.all()
    serializer_class = InvoiceSettingsSerializer

    def list(self, request):
        return Response([self.get_serializer(InvoiceSettings.load()).data])

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(InvoiceSettings.load()).data)

    def partial_update(self, request, pk=None):
        _require(request, MANAGE_SETTINGS)
        settings = InvoiceSettings.load()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        _require(request, MANAGE_SETTINGS)
        checklist = request.data.get("activation_checklist") or {}
        notes = (request.data.get("notes") or "").strip()
        try:
            settings = activate_invoices(InvoiceSettings.load(), request.user, checklist, notes)
        except InvoiceConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(settings).data)


class NrsSubmissionViewSet(InvoiceViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    view_permission = "invoicing.view_nrssubmission"
    queryset = NrsSubmission.objects.select_related("customer_invoice")
    serializer_class = NrsSubmissionSerializer
    search_fields = ("customer_invoice__number", "status")
