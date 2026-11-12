"""Serializers for invoices, notes, payments and settings."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.core.approvals import approval_state
from apps.core.models import create_audit_event
from apps.documents.models import DocumentLink
from apps.invoicing.models import (
    CustomerInvoice,
    CustomerInvoiceLine,
    InvoiceNote,
    InvoiceNoteLine,
    InvoiceSettings,
    NrsSubmission,
    PaymentAllocation,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
    TaxTreatment,
    money,
    validate_invoice_tax,
)
from apps.invoicing.services import (
    InvoiceConflict,
    duplicate_candidates,
    exact_duplicate,
    mark_duplicate_risk,
    next_invoice_number,
    next_note_number,
    next_payment_number,
    next_supplier_invoice_number,
    recalculate_customer_invoice,
    recalculate_note,
    recalculate_supplier_invoice,
)


def _validate_tax(tax, expected: str, on_date, field: str) -> None:
    try:
        validate_invoice_tax(tax, expected, on_date)
    except DjangoValidationError as exc:
        message = exc.message_dict.get("tax", [str(exc)])[0]
        raise serializers.ValidationError({field: message}) from exc


class SupplierInvoiceLineSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True, default=None)
    order_line_label = serializers.SerializerMethodField()
    receipt_line_label = serializers.SerializerMethodField()
    vat_rate = serializers.DecimalField(
        source="vat_tax.rate", max_digits=7, decimal_places=4, read_only=True, default=None
    )
    wht_rate = serializers.DecimalField(
        source="wht_tax.rate", max_digits=7, decimal_places=4, read_only=True, default=None
    )

    class Meta:
        model = SupplierInvoiceLine
        fields = [
            "id",
            "order_line",
            "order_line_label",
            "receipt_line",
            "receipt_line_label",
            "item",
            "item_code",
            "description",
            "quantity",
            "unit_price",
            "vat_tax",
            "vat_rate",
            "wht_tax",
            "wht_rate",
            "tax_treatment",
            "vat_recoverable",
            "subtotal",
            "vat_amount",
            "vat_recoverable_amount",
            "wht_amount",
            "total",
        ]
        read_only_fields = [
            "id",
            "subtotal",
            "vat_amount",
            "vat_recoverable_amount",
            "wht_amount",
            "total",
        ]

    def get_order_line_label(self, obj) -> str | None:
        if not obj.order_line_id:
            return None
        return f"{obj.order_line.order.number} · {obj.order_line.item.code}"

    def get_receipt_line_label(self, obj) -> str | None:
        if not obj.receipt_line_id:
            return None
        return f"{obj.receipt_line.receipt.number} · {obj.receipt_line.order_line.item.code}"

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value

    def validate(self, attrs):
        invoice = self.context.get("invoice")
        order_line = attrs.get("order_line") or getattr(self.instance, "order_line", None)
        receipt_line = attrs.get("receipt_line") or getattr(self.instance, "receipt_line", None)
        item = attrs.get("item") or getattr(self.instance, "item", None)
        if order_line is not None and invoice is not None and invoice.purchase_order_id:
            if order_line.order_id != invoice.purchase_order_id:
                raise serializers.ValidationError(
                    {"order_line": "The order line belongs to a different purchase order."}
                )
        if receipt_line is not None:
            if order_line is not None and receipt_line.order_line_id != order_line.pk:
                raise serializers.ValidationError(
                    {"receipt_line": "The receipt line belongs to a different order line."}
                )
            if invoice is not None and invoice.purchase_order_id:
                if receipt_line.receipt.order_id != invoice.purchase_order_id:
                    raise serializers.ValidationError(
                        {"receipt_line": "The receipt belongs to a different purchase order."}
                    )
        if item is None and order_line is not None:
            attrs["item"] = order_line.item
        if item is None and receipt_line is not None:
            attrs["item"] = receipt_line.order_line.item
        tax_date = getattr(invoice, "tax_point_date", None) or getattr(
            invoice, "invoice_date", None
        )
        if attrs.get("vat_tax") is not None:
            _validate_tax(attrs["vat_tax"], "vat", tax_date, "vat_tax")
        if attrs.get("wht_tax") is not None:
            _validate_tax(attrs["wht_tax"], "wht", tax_date, "wht_tax")
        treatment = attrs.get("tax_treatment") or getattr(
            self.instance, "tax_treatment", TaxTreatment.TAXABLE
        )
        if treatment != TaxTreatment.TAXABLE and attrs.get("vat_tax") is not None:
            if attrs["vat_tax"].rate != 0:
                raise serializers.ValidationError(
                    {
                        "vat_tax": (
                            "An exempt, zero-rated or out-of-scope line cannot use "
                            "a non-zero VAT rate."
                        )
                    }
                )
        return attrs


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    lines = SupplierInvoiceLineSerializer(many=True)
    journal_entry = serializers.PrimaryKeyRelatedField(read_only=True)
    journal_number = serializers.CharField(
        source="journal_entry.number", read_only=True, default=None
    )
    supplier_name = serializers.CharField(source="supplier.legal_name", read_only=True)
    supplier_email = serializers.EmailField(source="supplier.email", read_only=True, default="")
    purchase_order_number = serializers.CharField(
        source="purchase_order.number", read_only=True, default=None
    )
    approved_by = serializers.SerializerMethodField()
    test_document = serializers.BooleanField(source="is_test", read_only=True)
    payment_status = serializers.CharField(read_only=True)
    balance = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    approvals_required = serializers.SerializerMethodField()
    approvals_recorded = serializers.SerializerMethodField()
    approval_policy = serializers.SerializerMethodField()
    duplicate_warnings = serializers.SerializerMethodField()
    supporting_documents = serializers.SerializerMethodField()

    class Meta:
        model = SupplierInvoice
        fields = [
            "id",
            "number",
            "supplier_invoice_number",
            "supplier",
            "supplier_name",
            "supplier_email",
            "project",
            "purchase_order",
            "purchase_order_number",
            "invoice_date",
            "tax_point_date",
            "due_date",
            "currency",
            "status",
            "match_status",
            "match_exceptions",
            "match_exempt_reason",
            "duplicate_status",
            "duplicate_of",
            "duplicate_override_reason",
            "duplicate_warnings",
            "supporting_documents",
            "subtotal",
            "vat_total",
            "vat_recoverable_total",
            "wht_total",
            "total",
            "credited_total",
            "debited_total",
            "amount_paid",
            "payment_due",
            "balance",
            "payment_status",
            "test_document",
            "notes",
            "submitted_at",
            "approved_by",
            "approved_at",
            "journal_entry",
            "journal_number",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "approvals_required",
            "approvals_recorded",
            "approval_policy",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "number",
            "status",
            "match_status",
            "match_exceptions",
            "duplicate_status",
            "duplicate_of",
            "subtotal",
            "vat_total",
            "vat_recoverable_total",
            "wht_total",
            "total",
            "credited_total",
            "debited_total",
            "amount_paid",
            "payment_due",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]

    def get_approved_by(self, obj) -> str | None:
        return obj.approved_by.email if obj.approved_by else None

    def _approval_state(self, obj: SupplierInvoice) -> dict:
        return approval_state("supplier_invoice", obj.pk, obj.total)

    def get_approvals_required(self, obj: SupplierInvoice) -> int:
        return self._approval_state(obj)["required"]

    def get_approvals_recorded(self, obj: SupplierInvoice) -> int:
        return self._approval_state(obj)["recorded"]

    def get_approval_policy(self, obj: SupplierInvoice) -> str | None:
        return self._approval_state(obj)["policy"]

    def get_duplicate_warnings(self, obj: SupplierInvoice) -> list[dict]:
        if obj.pk is None:
            return []
        return [
            {
                "id": candidate.pk,
                "number": candidate.number,
                "supplier_invoice_number": candidate.supplier_invoice_number,
                "invoice_date": candidate.invoice_date,
                "total": str(candidate.total),
                "status": candidate.status,
            }
            for candidate in duplicate_candidates(
                supplier=obj.supplier,
                supplier_invoice_number=obj.supplier_invoice_number,
                total=obj.total,
                invoice_date=obj.invoice_date,
                exclude_id=obj.pk,
            )
        ]

    def get_supporting_documents(self, obj: SupplierInvoice) -> str:
        if obj.pk is None:
            return ""
        links = DocumentLink.objects.filter(
            entity_type=DocumentLink.EntityType.SUPPLIER_INVOICE,
            entity_id=obj.pk,
        ).select_related("document")
        return "; ".join(
            f"{link.document.title} ({link.document.original_filename})" for link in links
        )

    def validate(self, attrs):
        supplier = attrs.get("supplier") or getattr(self.instance, "supplier", None)
        purchase_order = attrs.get("purchase_order") or getattr(
            self.instance, "purchase_order", None
        )
        number = attrs.get("supplier_invoice_number") or getattr(
            self.instance, "supplier_invoice_number", ""
        )
        if supplier is None:
            raise serializers.ValidationError({"supplier": "Choose a supplier."})
        if not supplier.is_supplier or not supplier.is_active:
            raise serializers.ValidationError({"supplier": "Choose an active supplier."})
        if purchase_order is not None and purchase_order.supplier_id != supplier.pk:
            raise serializers.ValidationError(
                {"purchase_order": "The order belongs to a different supplier."}
            )
        exact = exact_duplicate(
            supplier=supplier,
            supplier_invoice_number=number,
            exclude_id=self.instance.pk if self.instance else None,
        )
        if exact is not None:
            raise serializers.ValidationError(
                {"supplier_invoice_number": (f"This number is already recorded as {exact.number}.")}
            )
        if self.instance and self.instance.status != SupplierInvoice.Status.DRAFT:
            raise serializers.ValidationError(
                "Only a draft supplier invoice can be edited. Cancel and re-enter instead."
            )
        return attrs

    def _make_lines(self, invoice: SupplierInvoice, lines: list[dict]) -> None:
        tax_date = invoice.tax_point_date or invoice.invoice_date
        for payload in lines:
            payload = dict(payload)
            order_line = payload.get("order_line")
            receipt_line = payload.get("receipt_line")
            item = payload.get("item")
            if order_line is not None:
                if invoice.purchase_order_id and order_line.order_id != invoice.purchase_order_id:
                    raise serializers.ValidationError(
                        {"lines": "An order line belongs to a different purchase order."}
                    )
            if receipt_line is not None:
                if (
                    invoice.purchase_order_id
                    and receipt_line.receipt.order_id != invoice.purchase_order_id
                ):
                    raise serializers.ValidationError(
                        {"lines": "A receipt belongs to a different purchase order."}
                    )
                if order_line is not None and receipt_line.order_line_id != order_line.pk:
                    raise serializers.ValidationError(
                        {"lines": "A receipt line belongs to a different order line."}
                    )
            if item is None and order_line is not None:
                item = order_line.item
            if item is None and receipt_line is not None:
                item = receipt_line.order_line.item
            if payload.get("vat_tax") is not None:
                _validate_tax(payload["vat_tax"], "vat", tax_date, "lines")
            if payload.get("wht_tax") is not None:
                _validate_tax(payload["wht_tax"], "wht", tax_date, "lines")
            treatment = payload.get("tax_treatment", TaxTreatment.TAXABLE)
            if treatment != TaxTreatment.TAXABLE and payload.get("vat_tax") is not None:
                if payload["vat_tax"].rate != 0:
                    raise serializers.ValidationError(
                        {
                            "lines": (
                                "An exempt, zero-rated or out-of-scope line cannot use "
                                "a non-zero VAT rate."
                            )
                        }
                    )
            line = SupplierInvoiceLine(invoice=invoice, **{**payload, "item": item})
            line.calculate()
            line.save()
        recalculate_supplier_invoice(invoice)
        mark_duplicate_risk(invoice)

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "Add at least one invoice line."})
        user = self.context["request"].user
        settings = InvoiceSettings.load()
        for calculated in (
            "subtotal",
            "vat_total",
            "vat_recoverable_total",
            "wht_total",
            "total",
            "credited_total",
            "debited_total",
            "amount_paid",
            "payment_due",
        ):
            validated_data.pop(calculated, None)
        invoice = SupplierInvoice.objects.create(
            number=next_supplier_invoice_number(),
            is_test=not settings.can_issue,
            created_by=user,
            updated_by=user,
            **validated_data,
        )
        self._make_lines(invoice, lines)
        create_audit_event(
            actor=user,
            action="supplier_invoice.created",
            entity_type="invoicing.supplierinvoice",
            entity_id=invoice.pk,
            after={"number": invoice.number, "status": invoice.status},
            request=self.context.get("request"),
        )
        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = self.context["request"].user
        instance.save()
        if lines is not None:
            if not lines:
                raise serializers.ValidationError({"lines": "Add at least one invoice line."})
            instance.lines.all().delete()
            self._make_lines(instance, lines)
        else:
            recalculate_supplier_invoice(instance)
            mark_duplicate_risk(instance)
        create_audit_event(
            actor=instance.updated_by,
            action="supplier_invoice.updated",
            entity_type="invoicing.supplierinvoice",
            entity_id=instance.pk,
            after={"number": instance.number, "status": instance.status},
            request=self.context.get("request"),
        )
        return instance


class CustomerInvoiceLineSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True, default=None)
    vat_rate = serializers.DecimalField(
        source="vat_tax.rate", max_digits=7, decimal_places=4, read_only=True, default=None
    )
    wht_rate = serializers.DecimalField(
        source="wht_tax.rate", max_digits=7, decimal_places=4, read_only=True, default=None
    )

    class Meta:
        model = CustomerInvoiceLine
        fields = [
            "id",
            "item",
            "item_code",
            "description",
            "quantity",
            "unit_price",
            "vat_tax",
            "vat_rate",
            "tax_treatment",
            "wht_tax",
            "wht_rate",
            "subtotal",
            "vat_amount",
            "wht_amount",
            "total",
        ]
        read_only_fields = ["id", "subtotal", "vat_amount", "wht_amount", "total"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value

    def validate(self, attrs):
        invoice = self.context.get("invoice")
        tax_date = getattr(invoice, "tax_point_date", None) or getattr(
            invoice, "invoice_date", None
        )
        if attrs.get("vat_tax") is not None:
            _validate_tax(attrs["vat_tax"], "vat", tax_date, "vat_tax")
        if attrs.get("wht_tax") is not None:
            _validate_tax(attrs["wht_tax"], "wht", tax_date, "wht_tax")
        treatment = attrs.get("tax_treatment") or getattr(
            self.instance, "tax_treatment", TaxTreatment.TAXABLE
        )
        if treatment != TaxTreatment.TAXABLE and attrs.get("vat_tax") is not None:
            if attrs["vat_tax"].rate != 0:
                raise serializers.ValidationError(
                    {
                        "vat_tax": (
                            "An exempt, zero-rated or out-of-scope line cannot use "
                            "a non-zero VAT rate."
                        )
                    }
                )
        return attrs


class CustomerInvoiceSerializer(serializers.ModelSerializer):
    lines = CustomerInvoiceLineSerializer(many=True)
    journal_entry = serializers.PrimaryKeyRelatedField(read_only=True)
    journal_number = serializers.CharField(
        source="journal_entry.number", read_only=True, default=None
    )
    customer_name = serializers.CharField(source="customer.legal_name", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True, default="")
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    approved_by = serializers.SerializerMethodField()
    test_document = serializers.BooleanField(source="is_test", read_only=True)
    approvals_required = serializers.SerializerMethodField()
    approvals_recorded = serializers.SerializerMethodField()
    approval_policy = serializers.SerializerMethodField()
    net_receivable = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = CustomerInvoice
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "customer_email",
            "project",
            "project_code",
            "customer_reference",
            "invoice_date",
            "tax_point_date",
            "due_date",
            "currency",
            "status",
            "subtotal",
            "vat_total",
            "wht_total",
            "total",
            "credited_total",
            "debited_total",
            "balance",
            "net_receivable",
            "test_document",
            "notes",
            "submitted_at",
            "approved_by",
            "approved_at",
            "journal_entry",
            "journal_number",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "approvals_required",
            "approvals_recorded",
            "approval_policy",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "number",
            "status",
            "subtotal",
            "vat_total",
            "wht_total",
            "total",
            "credited_total",
            "debited_total",
            "balance",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]

    def get_approved_by(self, obj) -> str | None:
        return obj.approved_by.email if obj.approved_by else None

    def _approval_state(self, obj: CustomerInvoice) -> dict:
        return approval_state("customer_invoice", obj.pk, obj.total)

    def get_approvals_required(self, obj: CustomerInvoice) -> int:
        return self._approval_state(obj)["required"]

    def get_approvals_recorded(self, obj: CustomerInvoice) -> int:
        return self._approval_state(obj)["recorded"]

    def get_approval_policy(self, obj: CustomerInvoice) -> str | None:
        return self._approval_state(obj)["policy"]

    def validate(self, attrs):
        customer = attrs.get("customer") or getattr(self.instance, "customer", None)
        if customer is None:
            raise serializers.ValidationError({"customer": "Choose a customer."})
        if not customer.is_customer or not customer.is_active:
            raise serializers.ValidationError({"customer": "Choose an active customer."})
        if self.instance and self.instance.status != CustomerInvoice.Status.DRAFT:
            raise serializers.ValidationError(
                "Only a draft customer invoice can be edited. Cancel and re-enter instead."
            )
        return attrs

    def _make_lines(self, invoice: CustomerInvoice, lines: list[dict]) -> None:
        tax_date = invoice.tax_point_date or invoice.invoice_date
        for payload in lines:
            if payload.get("vat_tax") is not None:
                _validate_tax(payload["vat_tax"], "vat", tax_date, "lines")
            if payload.get("wht_tax") is not None:
                _validate_tax(payload["wht_tax"], "wht", tax_date, "lines")
            treatment = payload.get("tax_treatment", TaxTreatment.TAXABLE)
            if treatment != TaxTreatment.TAXABLE and payload.get("vat_tax") is not None:
                if payload["vat_tax"].rate != 0:
                    raise serializers.ValidationError(
                        {
                            "lines": (
                                "An exempt, zero-rated or out-of-scope line cannot use "
                                "a non-zero VAT rate."
                            )
                        }
                    )
            line = CustomerInvoiceLine(invoice=invoice, **payload)
            line.calculate()
            line.save()
        recalculate_customer_invoice(invoice)

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "Add at least one invoice line."})
        user = self.context["request"].user
        settings = InvoiceSettings.load()
        try:
            number = next_invoice_number("customer_invoice")
        except InvoiceConflict as exc:
            raise serializers.ValidationError({"number": str(exc)}) from exc
        invoice = CustomerInvoice.objects.create(
            number=number,
            is_test=not settings.can_issue,
            created_by=user,
            updated_by=user,
            **validated_data,
        )
        self._make_lines(invoice, lines)
        create_audit_event(
            actor=user,
            action="customer_invoice.created",
            entity_type="invoicing.customerinvoice",
            entity_id=invoice.pk,
            after={"number": invoice.number, "status": invoice.status},
            request=self.context.get("request"),
        )
        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = self.context["request"].user
        instance.save()
        if lines is not None:
            if not lines:
                raise serializers.ValidationError({"lines": "Add at least one invoice line."})
            instance.lines.all().delete()
            self._make_lines(instance, lines)
        else:
            recalculate_customer_invoice(instance)
        create_audit_event(
            actor=instance.updated_by,
            action="customer_invoice.updated",
            entity_type="invoicing.customerinvoice",
            entity_id=instance.pk,
            after={"number": instance.number, "status": instance.status},
            request=self.context.get("request"),
        )
        return instance


class InvoiceNoteLineSerializer(serializers.ModelSerializer):
    vat_rate = serializers.DecimalField(
        source="vat_tax.rate", max_digits=7, decimal_places=4, read_only=True, default=None
    )

    class Meta:
        model = InvoiceNoteLine
        fields = [
            "id",
            "description",
            "quantity",
            "unit_price",
            "vat_tax",
            "vat_rate",
            "tax_treatment",
            "subtotal",
            "vat_amount",
            "total",
        ]
        read_only_fields = ["id", "subtotal", "vat_amount", "total"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value

    def validate(self, attrs):
        note = self.context.get("note")
        tax_date = getattr(note, "tax_point_date", None) or getattr(note, "note_date", None)
        if attrs.get("vat_tax") is not None:
            _validate_tax(attrs["vat_tax"], "vat", tax_date, "vat_tax")
        treatment = attrs.get("tax_treatment") or getattr(
            self.instance, "tax_treatment", TaxTreatment.TAXABLE
        )
        if treatment != TaxTreatment.TAXABLE and attrs.get("vat_tax") is not None:
            if attrs["vat_tax"].rate != 0:
                raise serializers.ValidationError(
                    {
                        "vat_tax": (
                            "An exempt, zero-rated or out-of-scope line cannot use "
                            "a non-zero VAT rate."
                        )
                    }
                )
        return attrs


class InvoiceNoteSerializer(serializers.ModelSerializer):
    lines = InvoiceNoteLineSerializer(many=True)
    party_kind = serializers.CharField(required=False, allow_blank=True)
    party_name = serializers.CharField(read_only=True)
    test_document = serializers.BooleanField(source="is_test", read_only=True)
    approvals_required = serializers.SerializerMethodField()
    approvals_recorded = serializers.SerializerMethodField()
    approval_policy = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceNote
        fields = [
            "id",
            "number",
            "note_type",
            "party_kind",
            "supplier_invoice",
            "customer_invoice",
            "party_name",
            "note_date",
            "tax_point_date",
            "currency",
            "reason",
            "status",
            "subtotal",
            "vat_total",
            "total",
            "test_document",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "approvals_required",
            "approvals_recorded",
            "approval_policy",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "number",
            "status",
            "subtotal",
            "vat_total",
            "total",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]

    def _approval_state(self, obj: InvoiceNote) -> dict:
        return approval_state("invoice_note", obj.pk, obj.total)

    def get_approvals_required(self, obj: InvoiceNote) -> int:
        return self._approval_state(obj)["required"]

    def get_approvals_recorded(self, obj: InvoiceNote) -> int:
        return self._approval_state(obj)["recorded"]

    def get_approval_policy(self, obj: InvoiceNote) -> str | None:
        return self._approval_state(obj)["policy"]

    def validate(self, attrs):
        supplier_invoice = attrs.get("supplier_invoice") or getattr(
            self.instance, "supplier_invoice", None
        )
        customer_invoice = attrs.get("customer_invoice") or getattr(
            self.instance, "customer_invoice", None
        )
        if (supplier_invoice is None) == (customer_invoice is None):
            raise serializers.ValidationError(
                "Choose exactly one supplier invoice or customer invoice."
            )
        if supplier_invoice is not None:
            attrs["party_kind"] = InvoiceNote.PartyKind.SUPPLIER
            attrs["currency"] = supplier_invoice.currency
        else:
            attrs["party_kind"] = InvoiceNote.PartyKind.CUSTOMER
            attrs["currency"] = customer_invoice.currency
        if self.instance and self.instance.status != InvoiceNote.Status.DRAFT:
            raise serializers.ValidationError("Only a draft note can be edited.")
        if (
            self.instance
            and attrs.get("note_type", self.instance.note_type) != self.instance.note_type
        ):
            raise serializers.ValidationError(
                {"note_type": "The note type cannot change; issue a new note instead."}
            )
        if self.instance:
            if (
                supplier_invoice is not None
                and self.instance.supplier_invoice_id != supplier_invoice.pk
            ):
                raise serializers.ValidationError("The linked invoice cannot change.")
            if (
                customer_invoice is not None
                and self.instance.customer_invoice_id != customer_invoice.pk
            ):
                raise serializers.ValidationError("The linked invoice cannot change.")
        return attrs

    def _make_lines(self, note: InvoiceNote, lines: list[dict]) -> None:
        tax_date = note.tax_point_date or note.note_date
        for payload in lines:
            if payload.get("vat_tax") is not None:
                _validate_tax(payload["vat_tax"], "vat", tax_date, "lines")
            treatment = payload.get("tax_treatment", TaxTreatment.TAXABLE)
            if treatment != TaxTreatment.TAXABLE and payload.get("vat_tax") is not None:
                if payload["vat_tax"].rate != 0:
                    raise serializers.ValidationError(
                        {
                            "lines": (
                                "An exempt, zero-rated or out-of-scope line cannot use "
                                "a non-zero VAT rate."
                            )
                        }
                    )
            line = InvoiceNoteLine(note=note, **payload)
            line.calculate()
            line.save()
        recalculate_note(note)

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "Add at least one note line."})
        user = self.context["request"].user
        settings = InvoiceSettings.load()
        note = InvoiceNote.objects.create(
            number=next_note_number(validated_data["note_type"]),
            is_test=not settings.can_issue,
            created_by=user,
            updated_by=user,
            **validated_data,
        )
        self._make_lines(note, lines)
        create_audit_event(
            actor=user,
            action="invoice_note.created",
            entity_type="invoicing.invoicenote",
            entity_id=note.pk,
            after={"number": note.number, "status": note.status},
            request=self.context.get("request"),
        )
        return note

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = self.context["request"].user
        instance.save()
        if lines is not None:
            if not lines:
                raise serializers.ValidationError({"lines": "Add at least one note line."})
            instance.lines.all().delete()
            self._make_lines(instance, lines)
        else:
            recalculate_note(instance)
        create_audit_event(
            actor=instance.updated_by,
            action="invoice_note.updated",
            entity_type="invoicing.invoicenote",
            entity_id=instance.pk,
            after={"number": instance.number, "status": instance.status},
            request=self.context.get("request"),
        )
        return instance


class SupplierPaymentSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.legal_name", read_only=True)
    test_document = serializers.BooleanField(source="is_test", read_only=True)
    unallocated_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    approvals_required = serializers.SerializerMethodField()
    approvals_recorded = serializers.SerializerMethodField()
    approval_policy = serializers.SerializerMethodField()

    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "number",
            "supplier",
            "supplier_name",
            "payment_date",
            "currency",
            "amount",
            "allocated_amount",
            "unallocated_amount",
            "method",
            "external_reference",
            "bank_account",
            "company_bank_account",
            "status",
            "execution_status",
            "test_document",
            "notes",
            "submitted_at",
            "approved_by",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "approvals_required",
            "approvals_recorded",
            "approval_policy",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "number",
            "allocated_amount",
            "status",
            "execution_status",
            "submitted_at",
            "approved_by",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "rejection_reason",
            "cancelled_at",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]

    def _approval_state(self, obj: SupplierPayment) -> dict:
        return approval_state("payment", obj.pk, obj.amount)

    def get_approvals_required(self, obj: SupplierPayment) -> int:
        return self._approval_state(obj)["required"]

    def get_approvals_recorded(self, obj: SupplierPayment) -> int:
        return self._approval_state(obj)["recorded"]

    def get_approval_policy(self, obj: SupplierPayment) -> str | None:
        return self._approval_state(obj)["policy"]

    def validate(self, attrs):
        supplier = attrs.get("supplier") or getattr(self.instance, "supplier", None)
        if supplier is None or not supplier.is_supplier or not supplier.is_active:
            raise serializers.ValidationError({"supplier": "Choose an active supplier."})
        if attrs.get("amount") is not None and attrs["amount"] <= 0:
            raise serializers.ValidationError({"amount": "Amount must be greater than zero."})
        if self.instance and self.instance.status != SupplierPayment.Status.DRAFT:
            raise serializers.ValidationError("Only a draft payment can be edited.")
        bank_account = attrs.get("bank_account") or getattr(self.instance, "bank_account", None)
        if bank_account is not None and bank_account.supplier_id != supplier.pk:
            raise serializers.ValidationError(
                {"bank_account": "The bank account belongs to a different supplier."}
            )
        company_account = attrs.get(
            "company_bank_account", getattr(self.instance, "company_bank_account", None)
        )
        if company_account is not None:
            currency = attrs.get("currency") or getattr(self.instance, "currency", None)
            if currency and company_account.currency != currency:
                raise serializers.ValidationError(
                    {"company_bank_account": "The company account currency must match the payment."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        settings = InvoiceSettings.load()
        payment = SupplierPayment.objects.create(
            number=next_payment_number(),
            is_test=not settings.can_issue,
            created_by=user,
            updated_by=user,
            **validated_data,
        )
        create_audit_event(
            actor=user,
            action="supplier_payment.created",
            entity_type="invoicing.supplierpayment",
            entity_id=payment.pk,
            after={"number": payment.number, "status": payment.status},
            request=self.context.get("request"),
        )
        return payment


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(
        source="supplier_invoice.supplier_invoice_number", read_only=True
    )

    class Meta:
        model = PaymentAllocation
        fields = ["id", "payment", "supplier_invoice", "invoice_number", "amount", "created_at"]
        read_only_fields = ["id", "created_at"]


class NrsSubmissionSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="customer_invoice.number", read_only=True)

    class Meta:
        model = NrsSubmission
        fields = [
            "id",
            "customer_invoice",
            "invoice_number",
            "status",
            "environment",
            "request_payload",
            "response_payload",
            "error",
            "attempts",
            "is_test",
            "submitted_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvoiceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSettings
        fields = [
            "id",
            "test_mode",
            "company_legal_name",
            "company_address",
            "company_tax_identification_number",
            "company_email",
            "company_phone",
            "company_bank_details",
            "default_currency",
            "require_supplier_match",
            "duplicate_window_days",
            "price_tolerance_percent",
            "quantity_tolerance_percent",
            "nrs_enabled",
            "nrs_environment",
            "activation_checklist",
            "activated_at",
            "activated_by",
            "activation_notes",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "test_mode",
            "activated_at",
            "activated_by",
            "updated_at",
        ]

    def validate_price_tolerance_percent(self, value):
        if value < 0:
            raise serializers.ValidationError("Tolerance cannot be negative.")
        return value

    def validate_quantity_tolerance_percent(self, value):
        if value < 0:
            raise serializers.ValidationError("Tolerance cannot be negative.")
        return value


class MatchCheckSerializer(serializers.Serializer):
    purchase_order = serializers.IntegerField(required=False, allow_null=True)
    supplier = serializers.IntegerField(required=False, allow_null=True)


class InvoiceEmailSerializer(serializers.Serializer):
    to = serializers.EmailField()
    cc = serializers.CharField(required=False, allow_blank=True, max_length=500)
    message = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class PaymentAllocationRequestSerializer(serializers.Serializer):
    supplier_invoice = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return money(value)
