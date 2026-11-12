"""Stage 7A invoice, matching, note, payment and activation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.catalogue.models import CatalogueItem
from apps.core.models import ApprovalPolicy, TaxConfiguration
from apps.documents.models import Document
from apps.identity.models import User
from apps.invoicing.models import (
    CustomerInvoice,
    InvoiceSettings,
    NrsSubmission,
    PaymentAllocation,
    SupplierInvoice,
    SupplierPayment,
)
from apps.parties.models import Party
from apps.procurement.models import (
    DeliverySchedule,
    Destination,
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
)
from apps.warehousing.models import Warehouse

pytestmark = pytest.mark.django_db


def test_invoice_creation_rolls_back_when_line_creation_fails(
    client_for, creator, supplier, monkeypatch
):
    from rest_framework import serializers as drf_serializers

    from apps.invoicing.serializers import SupplierInvoiceSerializer

    def fail_after_header(self, invoice, lines):
        raise drf_serializers.ValidationError({"lines": "Simulated line failure."})

    monkeypatch.setattr(SupplierInvoiceSerializer, "_make_lines", fail_after_header)
    before = SupplierInvoice.objects.count()
    response = client_for(creator).post(
        "/api/v1/supplier-invoices/",
        {
            "supplier": supplier.pk,
            "supplier_invoice_number": "ROLLBACK-TEST-1",
            "invoice_date": "2026-01-05",
            "due_date": "2026-02-04",
            "currency": "NGN",
            "lines": [{"description": "Test line", "quantity": "1", "unit_price": "100.00"}],
        },
        format="json",
    )
    assert response.status_code == 400, response.content
    assert SupplierInvoice.objects.count() == before


def make_user(email: str) -> User:
    return User.objects.create_superuser(
        email=email, full_name=email.split("@")[0], password="Tmd-Test-Pass-2026!"
    )


@pytest.fixture
def creator():
    return make_user("invoice.creator@example.com")


@pytest.fixture
def approver():
    return make_user("invoice.approver@example.com")


@pytest.fixture
def second_approver():
    return make_user("invoice.approver2@example.com")


@pytest.fixture
def client_for():
    def build(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return build


@pytest.fixture
def supplier():
    return Party.objects.create(code="SUP-P7", legal_name="Phase Seven Supplies", is_supplier=True)


@pytest.fixture
def customer():
    return Party.objects.create(code="CUS-P7", legal_name="Phase Seven Customer", is_customer=True)


@pytest.fixture
def vat():
    return TaxConfiguration.objects.create(
        code="VAT-TEST",
        name="Test VAT",
        tax_type=TaxConfiguration.TaxType.VAT,
        rate=Decimal("7.5000"),
        effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def wht():
    return TaxConfiguration.objects.create(
        code="WHT-TEST",
        name="Test WHT",
        tax_type=TaxConfiguration.TaxType.WHT,
        rate=Decimal("5.0000"),
        effective_from=date(2026, 1, 1),
    )


def seed():
    call_command("apply_provisional_governance")


def pdf_bytes(response) -> bytes:
    return b"".join(response.streaming_content)


def supplier_invoice_payload(supplier, lines, number="SUP-INV-001", **extra):
    return {
        "supplier": supplier.pk,
        "supplier_invoice_number": number,
        "invoice_date": "2026-11-12",
        "currency": "NGN",
        "lines": lines,
        **extra,
    }


def line_payload(**extra):
    payload = {
        "description": "Cable supply",
        "quantity": "2.0000",
        "unit_price": "100.000000",
    }
    payload.update(extra)
    return payload


def create_supplier_invoice(client, supplier, lines, number="SUP-INV-001", **extra):
    response = client.post(
        "/api/v1/supplier-invoices/",
        supplier_invoice_payload(supplier, lines, number, **extra),
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def create_customer_invoice(client, customer, lines, **extra):
    response = client.post(
        "/api/v1/customer-invoices/",
        {
            "customer": customer.pk,
            "invoice_date": "2026-11-12",
            "currency": "NGN",
            "lines": lines,
            **extra,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def test_supplier_invoice_calculates_vat_wht_and_stays_test(client_for, supplier, vat, wht):
    seed()
    client = client_for(make_user("tax.calc@example.com"))

    body = create_supplier_invoice(
        client,
        supplier,
        [line_payload(vat_tax=vat.pk, wht_tax=wht.pk)],
    )

    assert body["subtotal"] == "200.00"
    assert body["vat_total"] == "15.00"
    assert body["wht_total"] == "10.00"
    assert body["total"] == "215.00"
    assert body["payment_due"] == "205.00"
    assert body["test_document"] is True
    assert body["status"] == "draft"


def test_duplicate_supplier_invoice_number_is_rejected_even_with_punctuation(
    client_for, supplier, vat
):
    seed()
    client = client_for(make_user("duplicate@example.com"))
    create_supplier_invoice(client, supplier, [line_payload()], number="INV/2026/001")

    response = client.post(
        "/api/v1/supplier-invoices/",
        supplier_invoice_payload(supplier, [line_payload()], number="INV-2026-001"),
        format="json",
    )

    assert response.status_code == 400, response.content
    assert "already recorded" in response.json()["error"]["details"]["supplier_invoice_number"][0]


def test_near_duplicate_is_flagged_and_requires_override(client_for, supplier):
    seed()
    client = client_for(make_user("near.duplicate@example.com"))
    create_supplier_invoice(client, supplier, [line_payload()], number="NEAR-001")

    second = create_supplier_invoice(client, supplier, [line_payload()], number="NEAR-002")
    assert second["duplicate_status"] == "suspected"
    assert second["duplicate_warnings"]
    response = client.post(f"/api/v1/supplier-invoices/{second['id']}/submit/")
    assert response.status_code == 409
    assert "possible duplicate" in response.json()["error"]["message"].lower()


def test_creator_cannot_approve_and_independent_approval_works(client_for, supplier, approver, vat):
    seed()
    creator = make_user("creator.approval@example.com")
    creator_client = client_for(creator)
    body = create_supplier_invoice(
        creator_client,
        supplier,
        [line_payload()],
        match_exempt_reason="Service invoice without a purchase order.",
    )
    assert creator_client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/").status_code == 200
    own = creator_client.post(f"/api/v1/supplier-invoices/{body['id']}/approve/")
    assert own.status_code == 409

    approver_client = client_for(approver)
    approved = approver_client.post(f"/api/v1/supplier-invoices/{body['id']}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"


def test_five_million_invoice_needs_two_distinct_approvers(
    client_for, supplier, approver, second_approver
):
    seed()
    creator = make_user("high.value.creator@example.com")
    creator_client = client_for(creator)
    body = create_supplier_invoice(
        creator_client,
        supplier,
        [line_payload(quantity="1", unit_price="5000000")],
        match_exempt_reason="Direct service contract.",
    )
    assert creator_client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/").status_code == 200

    first = client_for(approver).post(f"/api/v1/supplier-invoices/{body['id']}/approve/")
    assert first.status_code == 200, first.content
    assert first.json()["status"] == "submitted"
    assert first.json()["approvals_recorded"] == 1

    second = client_for(second_approver).post(f"/api/v1/supplier-invoices/{body['id']}/approve/")
    assert second.status_code == 200, second.content
    assert second.json()["status"] == "approved"
    assert second.json()["approvals_recorded"] == 2


def make_order_and_receipt(supplier, user, accepted="5"):
    item = CatalogueItem.objects.create(code="ITEM-P7", name="Cable", kind="product")
    destination = Destination.objects.create(
        kind=Destination.Kind.WAREHOUSE,
        warehouse=Warehouse.objects.create(code="WH-P7", name="Stores"),
    )
    request = PurchaseRequest.objects.create(
        number="PR-P7-1", requester=user, destination=destination
    )
    order = PurchaseOrder.objects.create(
        number="PO-P7-1",
        supplier=supplier,
        request=request,
        destination=destination,
        status=PurchaseOrder.Status.ISSUED,
    )
    order_line = PurchaseOrderLine.objects.create(
        order=order,
        item=item,
        quantity=Decimal("10"),
        unit_price=Decimal("100"),
        quantity_accepted=Decimal(accepted),
    )
    schedule = DeliverySchedule.objects.create(
        order_line=order_line,
        due_date=date(2026, 11, 1),
        quantity=Decimal("10"),
        destination=destination,
    )
    receipt = GoodsReceiptNote.objects.create(
        number="GRN-P7-1", order=order, received_at=date(2026, 11, 2), received_by=user
    )
    receipt_line = GoodsReceiptLine.objects.create(
        receipt=receipt,
        schedule=schedule,
        order_line=order_line,
        quantity_delivered=Decimal(accepted),
        quantity_accepted=Decimal(accepted),
    )
    return order, order_line, receipt_line


def test_matching_blocks_over_invoicing_and_accepts_matched_line(client_for, supplier):
    seed()
    user = make_user("match.creator@example.com")
    client = client_for(user)
    order, order_line, receipt_line = make_order_and_receipt(supplier, user)

    over = create_supplier_invoice(
        client,
        supplier,
        [
            line_payload(
                quantity="6",
                unit_price="100",
                order_line=order_line.pk,
                receipt_line=receipt_line.pk,
            )
        ],
        number="SUP-MATCH-1",
        purchase_order=order.pk,
    )
    response = client.post(f"/api/v1/supplier-invoices/{over['id']}/submit/")
    assert response.status_code == 409, response.content
    assert "exceeds accepted quantity" in response.json()["error"]["message"]

    matched = create_supplier_invoice(
        client,
        supplier,
        [
            line_payload(
                quantity="5",
                unit_price="100",
                order_line=order_line.pk,
                receipt_line=receipt_line.pk,
            )
        ],
        number="SUP-MATCH-2",
        purchase_order=order.pk,
    )
    accepted = client.post(f"/api/v1/supplier-invoices/{matched['id']}/submit/")
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["match_status"] == "matched"


def test_customer_invoice_draft_approval_and_test_pdf(client_for, customer, approver, vat):
    seed()
    creator = make_user("customer.invoice@example.com")
    body = create_customer_invoice(
        client_for(creator),
        customer,
        [line_payload(quantity="1", unit_price="1000", vat_tax=vat.pk)],
    )
    assert body["status"] == "draft"
    assert body["test_document"] is True
    client = client_for(creator)
    submitted = client.post(f"/api/v1/customer-invoices/{body['id']}/submit/")
    assert submitted.status_code == 200, submitted.content
    approved = client_for(approver).post(f"/api/v1/customer-invoices/{body['id']}/approve/")
    assert approved.status_code == 200, approved.content

    pdf = client.get(f"/api/v1/customer-invoices/{body['id']}/pdf/")
    assert pdf.status_code == 200
    assert pdf["Content-Type"] == "application/pdf"
    content = pdf_bytes(pdf)
    assert content.startswith(b"%PDF")
    assert b"TEST DOCUMENT" in content


def test_approved_customer_invoice_can_be_emailed_to_the_test_mailbox(
    client_for, customer, approver, vat, settings, mailoutbox
):
    seed()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "Tico McDon Limited <tmdtico@gmail.com>"
    settings.INVOICE_EMAIL_TEST_RECIPIENT = "tmdtico@gmail.com"
    creator = make_user("customer.email@example.com")
    client = client_for(creator)
    body = create_customer_invoice(
        client,
        customer,
        [line_payload(quantity="1", unit_price="1000", vat_tax=vat.pk)],
    )
    client.post(f"/api/v1/customer-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/customer-invoices/{body['id']}/approve/")

    response = client.post(
        f"/api/v1/customer-invoices/{body['id']}/email/",
        {"to": "tmdtico@gmail.com", "cc": "", "message": "Please find the invoice attached."},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["to"] == "tmdtico@gmail.com"
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.from_email == "Tico McDon Limited <tmdtico@gmail.com>"
    assert message.to == ["tmdtico@gmail.com"]
    assert message.attachments[0][0] == f"{body['number']}.pdf"
    assert message.attachments[0][1].startswith(b"%PDF")


def test_test_invoice_email_is_limited_to_the_company_test_mailbox(
    client_for, customer, approver, vat, settings, mailoutbox
):
    seed()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.INVOICE_EMAIL_TEST_RECIPIENT = "tmdtico@gmail.com"
    creator = make_user("customer.email.safety@example.com")
    client = client_for(creator)
    body = create_customer_invoice(
        client,
        customer,
        [line_payload(quantity="1", unit_price="1000", vat_tax=vat.pk)],
    )
    client.post(f"/api/v1/customer-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/customer-invoices/{body['id']}/approve/")

    external = client.post(
        f"/api/v1/customer-invoices/{body['id']}/email/",
        {"to": "customer@example.com"},
        format="json",
    )
    assert external.status_code == 409
    assert "test document" in external.json()["error"]["message"].lower()
    assert len(mailoutbox) == 0

    draft = create_customer_invoice(
        client,
        customer,
        [line_payload(quantity="1", unit_price="500")],
    )
    response = client.post(
        f"/api/v1/customer-invoices/{draft['id']}/email/",
        {"to": "tmdtico@gmail.com"},
        format="json",
    )
    assert response.status_code == 409
    assert "approved" in response.json()["error"]["message"].lower()


def test_approved_supplier_invoice_can_be_emailed(
    client_for, supplier, approver, settings, mailoutbox
):
    seed()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.INVOICE_EMAIL_TEST_RECIPIENT = "tmdtico@gmail.com"
    creator = make_user("supplier.email@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload()],
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")

    response = client.post(
        f"/api/v1/supplier-invoices/{invoice['id']}/email/",
        {"to": "tmdtico@gmail.com"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert len(mailoutbox) == 1
    assert mailoutbox[0].attachments[0][0] == f"{invoice['number']}.pdf"


def test_only_an_authorised_user_can_email_an_invoice(
    client_for, customer, approver, vat, settings, mailoutbox
):
    seed()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.INVOICE_EMAIL_TEST_RECIPIENT = "tmdtico@gmail.com"
    creator = make_user("customer.email.permission@example.com")
    client = client_for(creator)
    body = create_customer_invoice(
        client,
        customer,
        [line_payload(quantity="1", unit_price="100", vat_tax=vat.pk)],
    )
    client.post(f"/api/v1/customer-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/customer-invoices/{body['id']}/approve/")

    viewer = User.objects.create_user(
        email="customer.email.viewer@example.com", full_name="Invoice Viewer"
    )
    viewer.user_permissions.add(Permission.objects.get(codename="view_customerinvoice"))
    viewer_client = client_for(viewer)
    denied = viewer_client.post(
        f"/api/v1/customer-invoices/{body['id']}/email/",
        {"to": "tmdtico@gmail.com"},
        format="json",
    )
    assert denied.status_code == 403
    assert len(mailoutbox) == 0

    viewer.user_permissions.add(Permission.objects.get(codename="email_customerinvoice"))
    allowed = client_for(User.objects.get(pk=viewer.pk)).post(
        f"/api/v1/customer-invoices/{body['id']}/email/",
        {"to": "tmdtico@gmail.com"},
        format="json",
    )
    assert allowed.status_code == 200, allowed.content
    assert len(mailoutbox) == 1


def test_credit_note_reduces_payment_due_after_approval(client_for, supplier, approver):
    seed()
    creator = make_user("note.creator@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")

    note = client.post(
        "/api/v1/invoice-notes/",
        {
            "note_type": "credit",
            "supplier_invoice": invoice["id"],
            "note_date": "2026-11-13",
            "reason": "Price correction",
            "lines": [{"description": "Credit", "quantity": "1", "unit_price": "20"}],
        },
        format="json",
    )
    assert note.status_code == 201, note.content
    note_id = note.json()["id"]
    assert client.post(f"/api/v1/invoice-notes/{note_id}/submit/").status_code == 200
    approved = client_for(approver).post(f"/api/v1/invoice-notes/{note_id}/approve/")
    assert approved.status_code == 200, approved.content

    refreshed = client.get(f"/api/v1/supplier-invoices/{invoice['id']}/").json()
    assert refreshed["credited_total"] == "20.00"
    assert refreshed["payment_due"] == "80.00"


def test_payment_recording_allocation_and_idempotency(client_for, supplier, approver):
    seed()
    creator = make_user("payment.creator@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")

    payment = client.post(
        "/api/v1/supplier-payments/",
        {
            "supplier": supplier.pk,
            "payment_date": "2026-11-14",
            "currency": "NGN",
            "amount": "60",
            "method": "bank_transfer",
            "external_reference": "BANK-REF-1",
        },
        format="json",
    )
    assert payment.status_code == 201, payment.content
    payment_id = payment.json()["id"]
    assert client.post(f"/api/v1/supplier-payments/{payment_id}/submit/").status_code == 200
    assert (
        client_for(approver).post(f"/api/v1/supplier-payments/{payment_id}/approve/").status_code
        == 200
    )

    recorded = client.post(
        f"/api/v1/supplier-payments/{payment_id}/record/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="payment-record-1",
    )
    assert recorded.status_code == 200, recorded.content
    replay = client.post(
        f"/api/v1/supplier-payments/{payment_id}/record/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="payment-record-1",
    )
    assert replay.status_code == 200
    assert replay["Idempotency-Replayed"] == "true"

    allocation = client.post(
        f"/api/v1/supplier-payments/{payment_id}/allocate/",
        {"supplier_invoice": invoice["id"], "amount": "60"},
        format="json",
    )
    assert allocation.status_code == 201, allocation.content
    refreshed = client.get(f"/api/v1/supplier-invoices/{invoice['id']}/").json()
    assert refreshed["amount_paid"] == "60.00"
    assert refreshed["payment_status"] == "part_paid"

    over = client.post(
        f"/api/v1/supplier-payments/{payment_id}/allocate/",
        {"supplier_invoice": invoice["id"], "amount": "110"},
        format="json",
    )
    assert over.status_code == 409


def test_nrs_is_disabled_and_activation_posting_are_blocked(
    client_for, customer, approver, supplier
):
    seed()
    creator = make_user("gate.creator@example.com")
    client = client_for(creator)
    customer_invoice = create_customer_invoice(
        client, customer, [line_payload(quantity="1", unit_price="100")]
    )
    client.post(f"/api/v1/customer-invoices/{customer_invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/customer-invoices/{customer_invoice['id']}/approve/")

    nrs = client.post(f"/api/v1/customer-invoices/{customer_invoice['id']}/submit-nrs/")
    assert nrs.status_code == 409
    submission = NrsSubmission.objects.get(customer_invoice_id=customer_invoice["id"])
    assert submission.status == NrsSubmission.Status.DISABLED

    settings = client.get("/api/v1/invoice-settings/").json()[0]
    assert settings["test_mode"] is True
    activation = client.post(
        f"/api/v1/invoice-settings/{settings['id']}/activate/",
        {"activation_checklist": {}, "notes": "Not approved."},
        format="json",
    )
    assert activation.status_code == 409
    assert InvoiceSettings.load().test_mode is True

    supplier_invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-POST-1",
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{supplier_invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{supplier_invoice['id']}/approve/")
    posting = client.post(f"/api/v1/supplier-invoices/{supplier_invoice['id']}/post/")
    assert posting.status_code == 409
    assert "Stage 7B" in posting.json()["error"]["message"]


def test_cancelled_invoice_preserves_number_and_blocks_reuse(client_for, supplier):
    seed()
    client = client_for(make_user("cancel.creator@example.com"))
    body = create_supplier_invoice(client, supplier, [line_payload()], number="SUP-CANCEL-1")
    cancelled = client.post(
        f"/api/v1/supplier-invoices/{body['id']}/cancel/",
        {"reason": "Wrong supplier document."},
        format="json",
    )
    assert cancelled.status_code == 200
    assert SupplierInvoice.objects.filter(pk=body["id"], status="cancelled").exists()

    retry = client.post(
        "/api/v1/supplier-invoices/",
        supplier_invoice_payload(supplier, [line_payload()], number="SUP-CANCEL-1"),
        format="json",
    )
    assert retry.status_code == 400


def test_payment_allocation_records_are_immutable_through_service_limits(
    client_for, supplier, approver
):
    seed()
    creator = make_user("allocation.creator@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")
    payment = SupplierPayment.objects.create(
        number="PAY-TEST-1",
        supplier=supplier,
        payment_date=date(2026, 11, 14),
        amount=Decimal("100"),
        method=SupplierPayment.Method.BANK_TRANSFER,
        status=SupplierPayment.Status.RECORDED,
        execution_status=SupplierPayment.ExecutionStatus.RECORDED,
        created_by=creator,
        updated_by=creator,
    )
    response = client.post(
        f"/api/v1/supplier-payments/{payment.pk}/allocate/",
        {"supplier_invoice": invoice["id"], "amount": "100"},
        format="json",
    )
    assert response.status_code == 201, response.content
    assert PaymentAllocation.objects.filter(payment=payment).count() == 1
    invoice_row = SupplierInvoice.objects.get(pk=invoice["id"])
    assert invoice_row.amount_paid == Decimal("100.00")
    assert invoice_row.payment_status == "paid"


def test_invoice_policy_bands_were_seeded_without_assigning_controller():
    seed()
    assert ApprovalPolicy.objects.filter(document_type="supplier_invoice").count() == 2
    assert ApprovalPolicy.objects.filter(document_type="payment").count() == 2
    assert ApprovalPolicy.objects.filter(document_type="invoice_note").count() == 2
    assert InvoiceSettings.load().test_mode is True
    assert not User.objects.filter(groups__name="Finance Controller").exists()


def test_supplier_invoice_pdf_has_test_banner(client_for, supplier):
    seed()
    client = client_for(make_user("pdf.creator@example.com"))
    body = create_supplier_invoice(client, supplier, [line_payload()])
    pdf = client.get(f"/api/v1/supplier-invoices/{body['id']}/pdf/")
    assert pdf.status_code == 200
    content = pdf_bytes(pdf)
    assert content.startswith(b"%PDF")
    assert b"TEST DOCUMENT" in content


def test_customer_invoice_number_uses_configured_scheme(client_for, customer):
    seed()
    body = create_customer_invoice(
        client_for(make_user("number.creator@example.com")),
        customer,
        [line_payload(quantity="1", unit_price="10")],
    )
    assert body["number"].startswith("INV-2026-")
    assert CustomerInvoice.objects.filter(number=body["number"]).exists()


def test_expired_tax_code_is_rejected(client_for, supplier):
    seed()
    expired = TaxConfiguration.objects.create(
        code="VAT-EXPIRED",
        name="Expired VAT",
        tax_type=TaxConfiguration.TaxType.VAT,
        rate=Decimal("7.5000"),
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
    )
    response = client_for(make_user("expired.tax@example.com")).post(
        "/api/v1/supplier-invoices/",
        supplier_invoice_payload(supplier, [line_payload(vat_tax=expired.pk)]),
        format="json",
    )
    assert response.status_code == 400
    assert "not effective" in response.content.decode().lower()


def test_tax_point_date_controls_effective_tax_rate(client_for, supplier):
    seed()
    future = TaxConfiguration.objects.create(
        code="VAT-FUTURE",
        name="Future VAT",
        tax_type=TaxConfiguration.TaxType.VAT,
        rate=Decimal("7.5000"),
        effective_from=date(2027, 1, 1),
    )
    client = client_for(make_user("tax.point@example.com"))
    response = client.post(
        "/api/v1/supplier-invoices/",
        supplier_invoice_payload(
            supplier,
            [line_payload(vat_tax=future.pk)],
            tax_point_date="2027-01-02",
        ),
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["vat_total"] == "15.00"


def test_zero_rated_exempt_and_recoverable_vat_are_distinct(client_for, supplier, vat):
    seed()
    client = client_for(make_user("vat.treatment@example.com"))
    zero = TaxConfiguration.objects.create(
        code="VAT-ZERO",
        name="Zero VAT",
        tax_type=TaxConfiguration.TaxType.VAT,
        rate=Decimal("0"),
        effective_from=date(2026, 1, 1),
    )
    zero_invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(vat_tax=zero.pk, tax_treatment="zero_rated")],
        number="VAT-ZERO-1",
    )
    assert zero_invoice["vat_total"] == "0.00"
    assert zero_invoice["lines"][0]["vat_amount"] == "0.00"

    exempt = client.post(
        "/api/v1/supplier-invoices/",
        supplier_invoice_payload(
            supplier,
            [line_payload(vat_tax=vat.pk, tax_treatment="exempt")],
            number="VAT-EXEMPT-1",
        ),
        format="json",
    )
    assert exempt.status_code == 400
    assert "non-zero vat rate" in exempt.content.decode().lower()

    non_recoverable = create_supplier_invoice(
        client,
        supplier,
        [line_payload(vat_tax=vat.pk, vat_recoverable=False)],
        number="VAT-NONREC-1",
    )
    assert non_recoverable["vat_total"] == "15.00"
    assert non_recoverable["vat_recoverable_total"] == "0.00"
    assert non_recoverable["lines"][0]["vat_recoverable_amount"] == "0.00"


def test_customer_wht_is_withheld_by_customer_and_reduces_net_receivable(client_for, customer, wht):
    seed()
    body = create_customer_invoice(
        client_for(make_user("customer.wht@example.com")),
        customer,
        [line_payload(quantity="1", unit_price="200", wht_tax=wht.pk)],
    )
    assert body["wht_total"] == "10.00"
    assert body["balance"] == "200.00"
    assert body["net_receivable"] == "190.00"


def test_invoicing_reads_and_pdfs_require_model_view_permission(client_for, supplier):
    seed()
    owner = make_user("permission.owner@example.com")
    invoice = create_supplier_invoice(
        client_for(owner), supplier, [line_payload()], match_exempt_reason="Service."
    )
    viewer = User.objects.create_user(
        email="permission.viewer@example.com",
        password="Tmd-Test-Pass-2026!",
        full_name="No invoicing access",
    )
    client = client_for(viewer)

    assert client.get("/api/v1/supplier-invoices/").status_code == 403
    assert client.get(f"/api/v1/supplier-invoices/{invoice['id']}/").status_code == 403
    assert client.get(f"/api/v1/supplier-invoices/{invoice['id']}/pdf/").status_code == 403
    assert client.get("/api/v1/customer-invoices/").status_code == 403
    assert client.get("/api/v1/invoice-notes/").status_code == 403
    assert client.get("/api/v1/supplier-payments/").status_code == 403
    assert client.get("/api/v1/invoice-settings/").status_code == 403
    assert client.get("/api/v1/nrs-submissions/").status_code == 403
    assert client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/").status_code == 403


def test_supporting_document_can_be_attached_and_is_visible(client_for, supplier):
    seed()
    user = make_user("attachment.owner@example.com")
    client = client_for(user)
    invoice = create_supplier_invoice(client, supplier, [line_payload()])
    document = Document.objects.create(
        title="Supplier delivery note",
        file=SimpleUploadedFile("delivery.txt", b"signed delivery note"),
        created_by=user,
        updated_by=user,
    )
    attached = client.post(
        f"/api/v1/supplier-invoices/{invoice['id']}/attach-document/",
        {"document": document.pk},
        format="json",
    )
    assert attached.status_code == 201, attached.content
    refreshed = client.get(f"/api/v1/supplier-invoices/{invoice['id']}/").json()
    assert "Supplier delivery note" in refreshed["supporting_documents"]
    replay = client.post(
        f"/api/v1/supplier-invoices/{invoice['id']}/attach-document/",
        {"document": document.pk},
        format="json",
    )
    assert replay.status_code == 200


def test_pdf_escapes_markup_in_free_text(client_for, supplier):
    seed()
    client = client_for(make_user("pdf.escape@example.com"))
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(description="<b>Cable & fittings</b>")],
        number="PDF-ESCAPE-1",
        notes="<script>alert('x')</script> & delivery note",
    )
    response = client.get(f"/api/v1/supplier-invoices/{invoice['id']}/pdf/")
    assert response.status_code == 200
    assert pdf_bytes(response).startswith(b"%PDF")


def test_partial_deliveries_can_be_invoiced_across_split_receipts(client_for, supplier):
    seed()
    user = make_user("split.receipt@example.com")
    client = client_for(user)
    order, order_line, first_receipt = make_order_and_receipt(supplier, user, accepted="3")
    second_receipt = GoodsReceiptLine.objects.create(
        receipt=GoodsReceiptNote.objects.create(
            number="GRN-P7-2", order=order, received_at=date(2026, 11, 3), received_by=user
        ),
        schedule=first_receipt.schedule,
        order_line=order_line,
        quantity_delivered=Decimal("2"),
        quantity_accepted=Decimal("2"),
    )
    body = create_supplier_invoice(
        client,
        supplier,
        [
            line_payload(
                quantity="3",
                unit_price="100",
                order_line=order_line.pk,
                receipt_line=first_receipt.pk,
            ),
            line_payload(
                quantity="2",
                unit_price="100",
                order_line=order_line.pk,
                receipt_line=second_receipt.pk,
            ),
        ],
        number="SUP-SPLIT-1",
        purchase_order=order.pk,
    )
    submitted = client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["match_status"] == "matched"


def test_approved_supplier_invoice_cannot_be_edited(client_for, supplier, approver):
    seed()
    creator = make_user("approved.edit@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")
    edited = client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/",
        {"supplier_invoice_number": "CHANGED-AFTER-APPROVAL"},
        format="json",
    )
    assert edited.status_code == 400
    assert "draft" in str(edited.json()).lower()


def test_debit_note_increases_and_credit_note_cannot_exceed_remaining_value(
    client_for, supplier, approver
):
    seed()
    creator = make_user("debit.note@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")
    debit = client.post(
        "/api/v1/invoice-notes/",
        {
            "note_type": "debit",
            "supplier_invoice": invoice["id"],
            "note_date": "2026-11-13",
            "reason": "Additional delivery",
            "lines": [{"description": "Extra", "quantity": "1", "unit_price": "10"}],
        },
        format="json",
    )
    assert debit.status_code == 201, debit.content
    debit_id = debit.json()["id"]
    client.post(f"/api/v1/invoice-notes/{debit_id}/submit/")
    assert (
        client_for(approver).post(f"/api/v1/invoice-notes/{debit_id}/approve/").status_code == 200
    )
    assert (
        client.get(f"/api/v1/supplier-invoices/{invoice['id']}/").json()["payment_due"] == "110.00"
    )

    credit = client.post(
        "/api/v1/invoice-notes/",
        {
            "note_type": "credit",
            "supplier_invoice": invoice["id"],
            "note_date": "2026-11-14",
            "reason": "Excess credit test",
            "lines": [{"description": "Credit", "quantity": "1", "unit_price": "111"}],
        },
        format="json",
    )
    credit_id = credit.json()["id"]
    client.post(f"/api/v1/invoice-notes/{credit_id}/submit/")
    rejected = client_for(approver).post(f"/api/v1/invoice-notes/{credit_id}/approve/")
    assert rejected.status_code == 409
    assert "exceeds" in rejected.json()["error"]["message"].lower()


def test_one_payment_can_be_allocated_across_multiple_invoices(client_for, supplier, approver):
    seed()
    creator = make_user("multi.allocation@example.com")
    client = client_for(creator)
    invoices = []
    for index in (1, 2):
        invoice = create_supplier_invoice(
            client,
            supplier,
            [line_payload(quantity="1", unit_price="100" if index == 1 else "200")],
            number=f"MULTI-{index}",
            match_exempt_reason="Service.",
        )
        client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
        client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")
        invoices.append(invoice)
    payment = client.post(
        "/api/v1/supplier-payments/",
        {
            "supplier": supplier.pk,
            "payment_date": "2026-11-15",
            "currency": "NGN",
            "amount": "150",
            "method": "bank_transfer",
        },
        format="json",
    )
    payment_id = payment.json()["id"]
    client.post(f"/api/v1/supplier-payments/{payment_id}/submit/")
    client_for(approver).post(f"/api/v1/supplier-payments/{payment_id}/approve/")
    client.post(f"/api/v1/supplier-payments/{payment_id}/record/", {}, format="json")
    for invoice, amount in zip(invoices, ("60", "40"), strict=True):
        response = client.post(
            f"/api/v1/supplier-payments/{payment_id}/allocate/",
            {"supplier_invoice": invoice["id"], "amount": amount},
            format="json",
        )
        assert response.status_code == 201, response.content
    refreshed_payment = client.get(f"/api/v1/supplier-payments/{payment_id}/").json()
    assert refreshed_payment["allocated_amount"] == "100.00"
    assert refreshed_payment["unallocated_amount"] == "50.00"


def test_vat_rounding_boundary_uses_decimal_half_up(client_for, supplier, vat):
    seed()
    body = create_supplier_invoice(
        client_for(make_user("rounding@example.com")),
        supplier,
        [line_payload(quantity="1", unit_price="0.10", vat_tax=vat.pk)],
        number="ROUND-1",
    )
    assert body["subtotal"] == "0.10"
    assert body["vat_total"] == "0.01"
    assert body["total"] == "0.11"


def test_tax_rate_must_be_a_percentage_and_dates_must_be_ordered(client_for):
    seed()
    client = client_for(make_user("tax.config@example.com"))
    base = {
        "name": "Invalid tax",
        "tax_type": "vat",
        "effective_from": "2026-01-01",
    }
    for code, rate in (("TAX-BAD-HIGH", "101"), ("TAX-BAD-LOW", "-1")):
        response = client.post(
            "/api/v1/governance/tax-configuration/",
            {**base, "code": code, "rate": rate},
            format="json",
        )
        assert response.status_code == 400
        assert "rate" in response.json()["error"]["details"]
    reversed_dates = client.post(
        "/api/v1/governance/tax-configuration/",
        {
            **base,
            "code": "TAX-BAD-DATE",
            "rate": "7.5",
            "effective_to": "2025-12-31",
        },
        format="json",
    )
    assert reversed_dates.status_code == 400
    assert "effective_to" in reversed_dates.json()["error"]["details"]
