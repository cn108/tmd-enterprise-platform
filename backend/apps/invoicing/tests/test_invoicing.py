"""Stage 7A invoice, matching, note, payment and activation tests."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountRole,
    AccountRoleMapping,
    FiscalYear,
    JournalEntry,
)
from apps.banking.models import BankAccount, BankTransaction
from apps.catalogue.models import CatalogueItem
from apps.core.models import ApprovalPolicy, TaxConfiguration
from apps.documents.models import Document
from apps.identity.models import User
from apps.invoicing.models import (
    CustomerInvoice,
    CustomerReceipt,
    CustomerReceiptAllocation,
    IdempotencyRecord,
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


def make_clerk(email: str) -> User:
    """A non-administrator holding every business permission.

    Administrative accounts (superusers) are exempt from the creator/approver
    separation, so the separation tests need an ordinary account: they prove the
    control that still applies to everyone else.
    """

    user = User.objects.create_user(
        email=email, full_name=email.split("@")[0], password="Tmd-Test-Pass-2026!"
    )
    user.user_permissions.add(*Permission.objects.all())
    return user


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


def activate_live_invoices(actor):
    settings = InvoiceSettings.load()
    settings.test_mode = False
    settings.activated_at = timezone.now()
    settings.activated_by = actor
    settings.activation_notes = "Posting test activation."
    settings.save(
        update_fields=[
            "test_mode",
            "activated_at",
            "activated_by",
            "activation_notes",
            "updated_at",
        ]
    )


def configure_invoice_posting(actor):
    """Create approved UAT accounts and the mappings required by posting tests."""

    definitions = {
        "AP_CONTROL": ("2100-POST", "liability", "credit"),
        "AR_CONTROL": ("1100-POST", "asset", "debit"),
        "INVENTORY": ("1200-POST", "asset", "debit"),
        "PROJECT_COST": ("1300-POST", "asset", "debit"),
        "COST_OF_SALES": ("5000-POST", "expense", "debit"),
        "INPUT_TAX": ("1400-POST", "asset", "debit"),
        "OUTPUT_TAX": ("2200-POST", "liability", "credit"),
        "REVENUE": ("4000-POST", "income", "credit"),
        "BANK": ("1010-POST", "asset", "debit"),
        "CASH": ("1000-POST", "asset", "debit"),
        "SUPPLIER_ADVANCES": ("1250-POST", "asset", "debit"),
        "CUSTOMER_ADVANCES": ("2150-POST", "liability", "credit"),
    }
    now = timezone.now()
    for role_code, (code, account_type, normal_balance) in definitions.items():
        account = Account.objects.create(
            code=code,
            name=f"Posting test {role_code}",
            account_type=account_type,
            normal_balance=normal_balance,
            approved_at=now,
            created_by=actor,
            updated_by=actor,
        )
        AccountRoleMapping.objects.create(
            role=AccountRole.objects.get(code=role_code),
            account=account,
            effective_from=date(2026, 1, 1),
            approved_at=now,
            approved_by=actor,
            created_by=actor,
            updated_by=actor,
        )

    year = FiscalYear.objects.create(
        code="FY26-POST",
        name="2026 posting test",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    AccountingPeriod.objects.create(
        fiscal_year=year,
        name="November 2026",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 30),
    )


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
    creator = make_clerk("creator.approval@example.com")
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


def test_administrator_approves_their_own_invoice_in_one_decision(client_for, supplier, vat):
    seed()
    administrator = make_user("administrator@example.com")
    client = client_for(administrator)
    body = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="5000000")],
        match_exempt_reason="Direct service contract.",
    )
    assert client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/").status_code == 200

    approved = client.post(f"/api/v1/supplier-invoices/{body['id']}/approve/")

    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"
    assert approved.json()["approvals_recorded"] == 1


def test_five_million_invoice_needs_two_distinct_approvers(
    client_for, supplier, approver, second_approver
):
    seed()
    creator = make_clerk("high.value.creator@example.com")
    creator_client = client_for(creator)
    body = create_supplier_invoice(
        creator_client,
        supplier,
        [line_payload(quantity="1", unit_price="5000000")],
        match_exempt_reason="Direct service contract.",
    )
    assert creator_client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/").status_code == 200

    first = client_for(make_clerk("high.value.first@example.com")).post(
        f"/api/v1/supplier-invoices/{body['id']}/approve/"
    )
    assert first.status_code == 200, first.content
    assert first.json()["status"] == "submitted"
    assert first.json()["approvals_recorded"] == 1

    second = client_for(make_clerk("high.value.second@example.com")).post(
        f"/api/v1/supplier-invoices/{body['id']}/approve/"
    )
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
    assert b"TEST DOCUMENT" not in content


def test_approved_customer_invoice_can_be_emailed_to_the_test_mailbox(
    client_for, customer, approver, vat, settings, mailoutbox
):
    seed()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "Tico McDon Limited <finance@example.test>"
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
        {"to": "finance@example.test", "cc": "", "message": "Please find the invoice attached."},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["to"] == "finance@example.test"
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.from_email == "Tico McDon Limited <finance@example.test>"
    assert message.to == ["finance@example.test"]
    assert message.attachments[0][0] == f"{body['number']}.pdf"
    assert message.attachments[0][1].startswith(b"%PDF")


def test_approved_test_invoice_can_be_emailed_to_an_external_customer(
    client_for, customer, approver, vat, settings, mailoutbox
):
    seed()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
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
    assert external.status_code == 200, external.content
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["customer@example.com"]

    draft = create_customer_invoice(
        client,
        customer,
        [line_payload(quantity="1", unit_price="500")],
    )
    response = client.post(
        f"/api/v1/customer-invoices/{draft['id']}/email/",
        {"to": "finance@example.test"},
        format="json",
    )
    assert response.status_code == 409
    assert "approved" in response.json()["error"]["message"].lower()


def test_approved_supplier_invoice_can_be_emailed(
    client_for, supplier, approver, settings, mailoutbox
):
    seed()
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
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
        {"to": "finance@example.test"},
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
        {"to": "finance@example.test"},
        format="json",
    )
    assert denied.status_code == 403
    assert len(mailoutbox) == 0

    viewer.user_permissions.add(Permission.objects.get(codename="email_customerinvoice"))
    allowed = client_for(User.objects.get(pk=viewer.pk)).post(
        f"/api/v1/customer-invoices/{body['id']}/email/",
        {"to": "finance@example.test"},
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


def _approved_customer_invoice(client, client_for, customer, approver, amount, reference=""):
    invoice = create_customer_invoice(
        client,
        customer,
        [line_payload(quantity="1", unit_price=str(amount))],
        customer_reference=reference,
    )
    assert client.post(f"/api/v1/customer-invoices/{invoice['id']}/submit/").status_code == 200
    assert (
        client_for(approver).post(f"/api/v1/customer-invoices/{invoice['id']}/approve/").status_code
        == 200
    )
    return invoice


def test_customer_receipt_allocates_partial_and_multiple_invoices(client_for, customer, approver):
    seed()
    creator = make_user("receipt.creator@example.com")
    client = client_for(creator)
    first = _approved_customer_invoice(client, client_for, customer, approver, 100, "PO-1")
    second = _approved_customer_invoice(client, client_for, customer, approver, 50, "PO-2")

    response = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "currency": "NGN",
            "amount": "120",
            "method": "bank_transfer",
            "external_reference": "BANK-RCT-1",
            "lines": [
                {"invoice": first["id"], "amount": "70"},
                {"invoice": second["id"], "amount": "30"},
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["allocated_amount"] == "100.00"
    assert body["unallocated_amount"] == "20.00"
    assert body["status"] == "recorded"
    assert body["test_document"] is True
    assert len(body["allocations"]) == 2

    refreshed = client.get(f"/api/v1/customer-invoices/{first['id']}/").json()
    assert refreshed["amount_paid"] == "70.00"
    assert refreshed["balance"] == "30.00"
    assert refreshed["payment_status"] == "part_paid"
    second_row = client.get(f"/api/v1/customer-invoices/{second['id']}/").json()
    assert second_row["balance"] == "20.00"

    statement = client.get(f"/api/v1/customer-receipts/{body['id']}/statement/")
    assert statement.status_code == 200
    assert statement["Content-Type"] == "application/pdf"
    assert pdf_bytes(statement).startswith(b"%PDF")


def test_customer_receipt_rejects_over_allocation_and_wrong_customer(
    client_for, customer, approver
):
    seed()
    creator = make_user("receipt.guard@example.com")
    client = client_for(creator)
    invoice = _approved_customer_invoice(client, client_for, customer, approver, 100)
    other = Party.objects.create(code="CUS-OTHER", legal_name="Other Customer", is_customer=True)

    response = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "50",
            "method": "cash",
            "lines": [{"invoice": invoice["id"], "amount": "60"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert CustomerReceipt.objects.count() == 0

    response = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": other.pk,
            "receipt_date": "2026-11-20",
            "amount": "50",
            "method": "cash",
            "lines": [{"invoice": invoice["id"], "amount": "10"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert CustomerReceipt.objects.count() == 0


def test_customer_receipt_cancellation_restores_invoice_balance(client_for, customer, approver):
    seed()
    creator = make_user("receipt.cancel@example.com")
    client = client_for(creator)
    invoice = _approved_customer_invoice(client, client_for, customer, approver, 100)
    receipt = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "40",
            "method": "bank_transfer",
            "lines": [{"invoice": invoice["id"], "amount": "40"}],
        },
        format="json",
    ).json()

    assert client.post(f"/api/v1/customer-receipts/{receipt['id']}/cancel/", {}).status_code == 409
    cancelled = client.post(
        f"/api/v1/customer-receipts/{receipt['id']}/cancel/",
        {"reason": "Incorrect bank reference"},
        format="json",
    )
    assert cancelled.status_code == 200, cancelled.content
    assert cancelled.json()["status"] == "cancelled"
    refreshed = client.get(f"/api/v1/customer-invoices/{invoice['id']}/").json()
    assert refreshed["amount_paid"] == "0.00"
    assert refreshed["balance"] == "100.00"

    allocation = client.post(
        f"/api/v1/customer-receipts/{receipt['id']}/allocate/",
        {"invoice": invoice["id"], "amount": "10"},
        format="json",
    )
    assert allocation.status_code == 409


def test_customer_receipt_allocates_unapplied_funds_later(client_for, customer, approver):
    seed()
    creator = make_user("receipt.later@example.com")
    client = client_for(creator)
    invoice = _approved_customer_invoice(client, client_for, customer, approver, 100)
    receipt = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "100",
            "method": "bank_transfer",
        },
        format="json",
    ).json()
    assert receipt["allocated_amount"] == "0.00"

    allocated = client.post(
        f"/api/v1/customer-receipts/{receipt['id']}/allocate/",
        {"invoice": invoice["id"], "amount": "60"},
        format="json",
    )
    assert allocated.status_code == 201, allocated.content
    refreshed = client.get(f"/api/v1/customer-invoices/{invoice['id']}/").json()
    assert refreshed["amount_paid"] == "60.00"
    assert refreshed["balance"] == "40.00"


def test_customer_receipt_cannot_allocate_a_draft_invoice(client_for, customer):
    seed()
    creator = make_user("receipt.draft@example.com")
    client = client_for(creator)
    invoice = create_customer_invoice(
        client, customer, [line_payload(quantity="1", unit_price="100")]
    )
    response = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "100",
            "method": "cash",
            "lines": [{"invoice": invoice["id"], "amount": "100"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert CustomerReceipt.objects.count() == 0


def test_activated_supplier_invoice_posts_a_balanced_ledger_journal(
    client_for, supplier, approver, vat
):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.supplier@example.com")
    client = client_for(creator)
    body = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100", vat_tax=vat.pk)],
        number="SUP-POST-ACTIVE-1",
        match_exempt_reason="Service.",
    )
    assert body["test_document"] is False
    client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{body['id']}/approve/")

    posted = client.post(f"/api/v1/supplier-invoices/{body['id']}/post/")
    assert posted.status_code == 200, posted.content
    journal = JournalEntry.objects.get(pk=posted.json()["journal_entry"])
    assert journal.status == JournalEntry.Status.POSTED
    assert journal.total_debit == Decimal("107.50")
    assert journal.total_credit == Decimal("107.50")
    balances = {
        line.account.code: (line.debit, line.credit)
        for line in journal.lines.select_related("account")
    }
    assert balances["2100-POST"] == (Decimal("0.00"), Decimal("107.50"))
    assert balances["5000-POST"] == (Decimal("100.00"), Decimal("0.00"))
    assert balances["1400-POST"] == (Decimal("7.50"), Decimal("0.00"))
    assert SupplierInvoice.objects.get(pk=body["id"]).journal_entry_id == journal.pk

    replay = client.post(f"/api/v1/supplier-invoices/{body['id']}/post/")
    assert replay.status_code == 200
    assert replay["Idempotency-Replayed"] == "true"
    assert replay.json()["journal_entry"] == journal.pk
    assert JournalEntry.objects.filter(pk=journal.pk).count() == 1


def test_recorded_supplier_payment_posts_and_replays_idempotently(client_for, supplier, approver):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.payment@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-PAY-POST-1",
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")
    invoice_post = client.post(f"/api/v1/supplier-invoices/{invoice['id']}/post/")
    assert invoice_post.status_code == 200, invoice_post.content

    payment = client.post(
        "/api/v1/supplier-payments/",
        {
            "supplier": supplier.pk,
            "payment_date": "2026-11-15",
            "currency": "NGN",
            "amount": "100",
            "method": "bank_transfer",
            "external_reference": "PAY-POST-1",
        },
        format="json",
    )
    assert payment.status_code == 201, payment.content
    payment_id = payment.json()["id"]
    client.post(f"/api/v1/supplier-payments/{payment_id}/submit/")
    client_for(approver).post(f"/api/v1/supplier-payments/{payment_id}/approve/")
    recorded = client.post(f"/api/v1/supplier-payments/{payment_id}/record/", {}, format="json")
    assert recorded.status_code == 200, recorded.content
    allocation = client.post(
        f"/api/v1/supplier-payments/{payment_id}/allocate/",
        {"supplier_invoice": invoice["id"], "amount": "60"},
        format="json",
    )
    assert allocation.status_code == 201, allocation.content

    posted = client.post(f"/api/v1/supplier-payments/{payment_id}/post/")
    assert posted.status_code == 200, posted.content
    journal = JournalEntry.objects.get(pk=posted.json()["journal_entry"])
    balances = {
        line.account.code: (line.debit, line.credit)
        for line in journal.lines.select_related("account")
    }
    assert balances["2100-POST"] == (Decimal("60.00"), Decimal("0.00"))
    assert balances["1250-POST"] == (Decimal("40.00"), Decimal("0.00"))
    assert balances["1010-POST"] == (Decimal("0.00"), Decimal("100.00"))
    assert SupplierPayment.objects.get(pk=payment_id).journal_entry_id == journal.pk

    replay = client.post(f"/api/v1/supplier-payments/{payment_id}/post/")
    assert replay.status_code == 200
    assert replay["Idempotency-Replayed"] == "true"
    assert replay.json()["journal_entry"] == journal.pk
    assert JournalEntry.objects.filter(pk=journal.pk).count() == 1


def test_activated_customer_invoice_posts_receivable_revenue_and_output_vat(
    client_for, customer, approver, vat
):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.customer@example.com")
    client = client_for(creator)
    body = create_customer_invoice(
        client,
        customer,
        [line_payload(quantity="1", unit_price="100", vat_tax=vat.pk)],
    )
    assert body["test_document"] is False
    client.post(f"/api/v1/customer-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/customer-invoices/{body['id']}/approve/")

    posted = client.post(f"/api/v1/customer-invoices/{body['id']}/post/")
    assert posted.status_code == 200, posted.content
    journal = JournalEntry.objects.get(pk=posted.json()["journal_entry"])
    balances = {
        line.account.code: (line.debit, line.credit)
        for line in journal.lines.select_related("account")
    }
    assert balances["1100-POST"] == (Decimal("107.50"), Decimal("0.00"))
    assert balances["4000-POST"] == (Decimal("0.00"), Decimal("100.00"))
    assert balances["2200-POST"] == (Decimal("0.00"), Decimal("7.50"))


def test_wht_invoice_posting_requires_an_approved_treatment(
    client_for, supplier, approver, vat, wht
):
    seed()
    activate_live_invoices(approver)
    creator = make_user("posting.wht@example.com")
    client = client_for(creator)
    body = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100", vat_tax=vat.pk, wht_tax=wht.pk)],
        number="SUP-POST-WHT-1",
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{body['id']}/approve/")

    posted = client.post(f"/api/v1/supplier-invoices/{body['id']}/post/")
    assert posted.status_code == 409
    assert "WHT" in posted.json()["error"]["message"]
    assert not JournalEntry.objects.exists()


def test_foreign_currency_invoice_posting_remains_blocked(client_for, supplier, approver):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.fx@example.com")
    client = client_for(creator)
    body = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-POST-FX-1",
        match_exempt_reason="Service.",
        currency="USD",
    )
    client.post(f"/api/v1/supplier-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{body['id']}/approve/")

    posted = client.post(f"/api/v1/supplier-invoices/{body['id']}/post/")
    assert posted.status_code == 409
    assert "Foreign-currency" in posted.json()["error"]["message"]
    assert not JournalEntry.objects.exists()


def test_posting_refuses_gross_invoice_when_an_approved_note_exists(client_for, supplier, approver):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.note@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-POST-NOTE-1",
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
    client.post(f"/api/v1/invoice-notes/{note_id}/submit/")
    approved = client_for(approver).post(f"/api/v1/invoice-notes/{note_id}/approve/")
    assert approved.status_code == 200, approved.content

    posted = client.post(f"/api/v1/supplier-invoices/{invoice['id']}/post/")
    assert posted.status_code == 409
    assert "approved credit or debit notes" in posted.json()["error"]["message"]
    assert not JournalEntry.objects.exists()


def test_posting_refuses_gross_invoice_when_an_approved_debit_note_exists(
    client_for, supplier, approver
):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.debit.note@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-POST-DEBIT-NOTE-1",
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")
    note = client.post(
        "/api/v1/invoice-notes/",
        {
            "note_type": "debit",
            "supplier_invoice": invoice["id"],
            "note_date": "2026-11-13",
            "reason": "Additional works",
            "lines": [{"description": "Debit", "quantity": "1", "unit_price": "20"}],
        },
        format="json",
    )
    assert note.status_code == 201, note.content
    note_id = note.json()["id"]
    client.post(f"/api/v1/invoice-notes/{note_id}/submit/")
    approved = client_for(approver).post(f"/api/v1/invoice-notes/{note_id}/approve/")
    assert approved.status_code == 200, approved.content

    posted = client.post(f"/api/v1/supplier-invoices/{invoice['id']}/post/")
    assert posted.status_code == 409
    assert "approved credit or debit notes" in posted.json()["error"]["message"]
    assert not JournalEntry.objects.exists()


def test_posting_refuses_a_missing_account_mapping(client_for, customer, approver):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    AccountRoleMapping.objects.all().delete()
    creator = make_user("posting.mapping@example.com")
    client = client_for(creator)
    body = create_customer_invoice(client, customer, [line_payload()])
    client.post(f"/api/v1/customer-invoices/{body['id']}/submit/")
    client_for(approver).post(f"/api/v1/customer-invoices/{body['id']}/approve/")

    posted = client.post(f"/api/v1/customer-invoices/{body['id']}/post/")
    assert posted.status_code == 409
    assert "REVENUE" in posted.json()["error"]["message"]
    assert not JournalEntry.objects.exists()


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


def test_supplier_invoice_pdf_carries_no_test_banner(client_for, supplier):
    seed()
    client = client_for(make_user("pdf.creator@example.com"))
    body = create_supplier_invoice(client, supplier, [line_payload()])
    pdf = client.get(f"/api/v1/supplier-invoices/{body['id']}/pdf/")
    assert pdf.status_code == 200
    content = pdf_bytes(pdf)
    assert content.startswith(b"%PDF")
    assert b"TEST DOCUMENT" not in content


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


def test_supplier_payment_can_be_rejected_and_cancelled(client_for, supplier, approver):
    seed()
    creator = make_user("payment.lifecycle@example.com")
    client = client_for(creator)
    payload = {
        "supplier": supplier.pk,
        "payment_date": "2026-11-16",
        "currency": "NGN",
        "amount": "75",
        "method": "bank_transfer",
    }
    rejected_payment = client.post("/api/v1/supplier-payments/", payload, format="json")
    assert rejected_payment.status_code == 201, rejected_payment.content
    rejected_id = rejected_payment.json()["id"]
    client.post(f"/api/v1/supplier-payments/{rejected_id}/submit/")
    rejected = client_for(approver).post(
        f"/api/v1/supplier-payments/{rejected_id}/reject/",
        {"reason": "Incorrect supplier reference."},
        format="json",
    )
    assert rejected.status_code == 200, rejected.content
    payment = SupplierPayment.objects.get(pk=rejected_id)
    assert payment.status == SupplierPayment.Status.REJECTED
    assert payment.rejection_reason == "Incorrect supplier reference."
    assert client.post(f"/api/v1/supplier-payments/{rejected_id}/record/", {}).status_code == 409

    cancelled_payment = client.post(
        "/api/v1/supplier-payments/",
        {**payload, "external_reference": "CANCEL-1"},
        format="json",
    )
    assert cancelled_payment.status_code == 201, cancelled_payment.content
    cancelled_id = cancelled_payment.json()["id"]
    client.post(f"/api/v1/supplier-payments/{cancelled_id}/submit/")
    client_for(approver).post(f"/api/v1/supplier-payments/{cancelled_id}/approve/")
    cancelled = client.post(
        f"/api/v1/supplier-payments/{cancelled_id}/cancel/",
        {"reason": "Duplicate payment instruction."},
        format="json",
    )
    assert cancelled.status_code == 200, cancelled.content
    payment = SupplierPayment.objects.get(pk=cancelled_id)
    assert payment.status == SupplierPayment.Status.CANCELLED
    assert payment.execution_status == SupplierPayment.ExecutionStatus.CANCELLED
    assert payment.cancel_reason == "Duplicate payment instruction."


def test_allocated_payment_cannot_be_cancelled(client_for, supplier, approver):
    seed()
    creator = make_user("payment.cancel.allocated@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-CANCEL-ALLOC-1",
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")
    payment = client.post(
        "/api/v1/supplier-payments/",
        {
            "supplier": supplier.pk,
            "payment_date": "2026-11-16",
            "currency": "NGN",
            "amount": "100",
            "method": "bank_transfer",
        },
        format="json",
    )
    payment_id = payment.json()["id"]
    client.post(f"/api/v1/supplier-payments/{payment_id}/submit/")
    client_for(approver).post(f"/api/v1/supplier-payments/{payment_id}/approve/")
    client.post(f"/api/v1/supplier-payments/{payment_id}/record/", {}, format="json")
    allocation = client.post(
        f"/api/v1/supplier-payments/{payment_id}/allocate/",
        {"supplier_invoice": invoice["id"], "amount": "100"},
        format="json",
    )
    assert allocation.status_code == 201, allocation.content

    response = client.post(
        f"/api/v1/supplier-payments/{payment_id}/cancel/",
        {"reason": "Attempted cancellation."},
        format="json",
    )
    assert response.status_code == 409
    assert "allocations" in response.json()["error"]["message"]
    assert SupplierPayment.objects.get(pk=payment_id).status == SupplierPayment.Status.RECORDED


def test_failed_posting_transaction_rolls_back_journal_and_receipt(
    client_for, supplier, approver, monkeypatch
):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.rollback@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-POST-ROLLBACK-1",
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")

    from apps.invoicing import posting

    def fail_receipt(*args, **kwargs):
        raise RuntimeError("Simulated receipt failure.")

    monkeypatch.setattr(posting, "_remember_post", fail_receipt)
    with pytest.raises(RuntimeError, match="Simulated receipt failure"):
        posting.post_invoice(
            SupplierInvoice.objects.get(pk=invoice["id"]), approver, "rollback-key-1"
        )

    stored = SupplierInvoice.objects.get(pk=invoice["id"])
    assert stored.journal_entry_id is None
    assert not JournalEntry.objects.exists()
    assert not IdempotencyRecord.objects.filter(
        scope=f"invoice.post:supplier:{invoice['id']}"
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_posting_requests_create_exactly_one_journal(client_for, supplier, approver):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("posting.concurrent@example.com")
    client = client_for(creator)
    invoice = create_supplier_invoice(
        client,
        supplier,
        [line_payload(quantity="1", unit_price="100")],
        number="SUP-POST-CONCURRENT-1",
        match_exempt_reason="Service.",
    )
    client.post(f"/api/v1/supplier-invoices/{invoice['id']}/submit/")
    client_for(approver).post(f"/api/v1/supplier-invoices/{invoice['id']}/approve/")

    barrier = threading.Barrier(2)

    def post_once():
        close_old_connections()
        thread_client = APIClient()
        thread_client.force_authenticate(user=approver)
        barrier.wait(timeout=10)
        response = thread_client.post(
            f"/api/v1/supplier-invoices/{invoice['id']}/post/",
            format="json",
        )
        result = {
            "status": response.status_code,
            "body": response.json(),
            "replayed": response.headers.get("Idempotency-Replayed") == "true",
        }
        close_old_connections()
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: post_once(), range(2)))

    assert [row["status"] for row in results] == [200, 200]
    journal_ids = {row["body"]["journal_entry"] for row in results}
    assert len(journal_ids) == 1
    assert sum(1 for row in results if row["replayed"]) == 1
    assert JournalEntry.objects.filter(pk__in=journal_ids).count() == 1
    assert SupplierInvoice.objects.get(pk=invoice["id"]).journal_entry_id == next(iter(journal_ids))


def _bank_account_for_receipts(actor):
    account = Account.objects.get(code="1010-POST")
    return BankAccount.objects.create(
        code="BANK-RCPT",
        name="Receipt collection account",
        bank_name="UAT Bank",
        gl_account=account,
        created_by=actor,
        updated_by=actor,
    )


def _post_customer_invoice(client, invoice):
    response = client.post(f"/api/v1/customer-invoices/{invoice['id']}/post/")
    assert response.status_code == 200, response.content
    return response.json()


def test_customer_receipt_approval_separation_and_threshold(
    client_for, customer, approver, second_approver
):
    seed()
    creator = make_clerk("receipt.threshold@example.com")
    client = client_for(creator)
    invoice = _approved_customer_invoice(client, client_for, customer, approver, 100)
    ApprovalPolicy.objects.create(
        code="RCPT-UAT-2",
        document_type="customer_receipt",
        min_amount=0,
        required_approvals=2,
        effective_from=date(2026, 1, 1),
    )
    receipt = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "100",
            "method": "bank_transfer",
            "lines": [{"invoice": invoice["id"], "amount": "100"}],
        },
        format="json",
    ).json()
    assert client.post(f"/api/v1/customer-receipts/{receipt['id']}/submit/").status_code == 200
    assert client.post(f"/api/v1/customer-receipts/{receipt['id']}/approve/").status_code == 409
    first = client_for(make_clerk("receipt.first@example.com")).post(
        f"/api/v1/customer-receipts/{receipt['id']}/approve/", format="json"
    )
    assert first.status_code == 200
    assert first.json()["status"] == "submitted"
    assert first.json()["approvals_required"] == 2
    assert first.json()["approvals_recorded"] == 1
    final = client_for(make_clerk("receipt.second@example.com")).post(
        f"/api/v1/customer-receipts/{receipt['id']}/approve/", format="json"
    )
    assert final.status_code == 200
    assert final.json()["status"] == "approved"
    assert final.json()["approval_policy"] == "RCPT-UAT-2"


def test_customer_receipt_posts_allocated_and_unapplied_funds_once(
    client_for, customer, approver, second_approver
):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    creator = make_user("receipt.post@example.com")
    client = client_for(creator)
    bank = _bank_account_for_receipts(approver)
    first = _approved_customer_invoice(client, client_for, customer, approver, 100, "PO-1")
    second = _approved_customer_invoice(client, client_for, customer, approver, 50, "PO-2")
    _post_customer_invoice(client, first)
    _post_customer_invoice(client, second)
    receipt = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "120",
            "method": "bank_transfer",
            "company_bank_account": bank.pk,
            "external_reference": "BANK-RCPT-1",
        },
        format="json",
    )
    assert receipt.status_code == 201, receipt.content
    body = receipt.json()
    assert body["allocated_amount"] == "0.00"
    for invoice, amount in ((first, "70"), (second, "30")):
        allocated_later = client.post(
            f"/api/v1/customer-receipts/{body['id']}/allocate/",
            {"invoice": invoice["id"], "amount": amount},
            format="json",
        )
        assert allocated_later.status_code == 201, allocated_later.content
    early = client_for(second_approver).post(
        f"/api/v1/customer-receipts/{body['id']}/post/", format="json"
    )
    assert early.status_code == 409
    client.post(f"/api/v1/customer-receipts/{body['id']}/submit/")
    approved = client_for(approver).post(
        f"/api/v1/customer-receipts/{body['id']}/approve/", format="json"
    )
    assert approved.status_code == 200, approved.content

    posted = client_for(second_approver).post(
        f"/api/v1/customer-receipts/{body['id']}/post/", format="json"
    )
    assert posted.status_code == 200, posted.content
    result = posted.json()
    assert result["receipt"]["status"] == "posted"
    assert result["receipt"]["journal_number"]
    journal = JournalEntry.objects.get(pk=result["journal_entry"])
    lines = {line.account.code: line for line in journal.lines.select_related("account")}
    assert lines["1010-POST"].debit == Decimal("120.00")
    assert lines["1100-POST"].credit == Decimal("100.00")
    assert lines["2150-POST"].credit == Decimal("20.00")
    assert journal.total_debit == journal.total_credit == Decimal("120.00")

    replay = client_for(second_approver).post(
        f"/api/v1/customer-receipts/{body['id']}/post/", format="json"
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["journal_entry"] == result["journal_entry"]
    assert (
        JournalEntry.objects.filter(
            event_reference=f"invoicing.customerreceipt:{body['id']}"
        ).count()
        == 1
    )

    transaction = BankTransaction.objects.get(
        source_type=BankTransaction.Source.CUSTOMER_RECEIPT, source_id=body["id"]
    )
    assert transaction.amount == Decimal("120.00")
    assert transaction.status == BankTransaction.Status.RECORDED
    assert transaction.matches.count() == 0

    cancelled = client.post(
        f"/api/v1/customer-receipts/{body['id']}/cancel/",
        {"reason": "UAT posting reversal"},
        format="json",
    )
    assert cancelled.status_code == 200, cancelled.content
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["reversal_journal_number"]
    reversal = JournalEntry.objects.get(pk=journal.reversal.pk)
    assert reversal.total_debit == reversal.total_credit == Decimal("120.00")
    transaction.refresh_from_db()
    assert transaction.status == BankTransaction.Status.VOID
    for invoice in (first, second):
        balance = client.get(f"/api/v1/customer-invoices/{invoice['id']}/").json()
        assert balance["amount_paid"] == "0.00"


def test_receipt_allocation_reversal_duplicate_and_invoice_cancellation(
    client_for, customer, approver
):
    seed()
    creator = make_user("receipt.allocation.reverse@example.com")
    client = client_for(creator)
    invoice = _approved_customer_invoice(client, client_for, customer, approver, 100)
    receipt = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "100",
            "method": "bank_transfer",
            "lines": [{"invoice": invoice["id"], "amount": "60"}],
        },
        format="json",
    ).json()
    allocation_id = receipt["allocations"][0]["id"]
    blocked = client.post(
        f"/api/v1/customer-invoices/{invoice['id']}/cancel/",
        {"reason": "Customer cancellation"},
        format="json",
    )
    assert blocked.status_code == 409
    assert "receipt allocations" in blocked.json()["error"]["message"]

    duplicate = client.post(
        f"/api/v1/customer-receipts/{receipt['id']}/allocate/",
        {"invoice": invoice["id"], "amount": "10"},
        format="json",
    )
    assert duplicate.status_code == 409
    over = client.post(
        f"/api/v1/customer-receipts/{receipt['id']}/allocate/",
        {"invoice": invoice["id"], "amount": "50"},
        format="json",
    )
    assert over.status_code == 409

    reversed_response = client.post(
        f"/api/v1/customer-receipts/{receipt['id']}/reverse-allocation/",
        {"allocation": allocation_id, "reason": "Applied to wrong invoice"},
        format="json",
    )
    assert reversed_response.status_code == 200, reversed_response.content
    assert reversed_response.json()["allocations"][0]["is_reversed"] is True
    refreshed = client.get(f"/api/v1/customer-invoices/{invoice['id']}/").json()
    assert refreshed["amount_paid"] == "0.00"
    assert refreshed["balance"] == "100.00"
    assert (
        client.post(
            f"/api/v1/customer-receipts/{receipt['id']}/reverse-allocation/",
            {"allocation": allocation_id, "reason": "Again"},
            format="json",
        ).status_code
        == 409
    )

    reallocated = client.post(
        f"/api/v1/customer-receipts/{receipt['id']}/allocate/",
        {"invoice": invoice["id"], "amount": "40"},
        format="json",
    )
    assert reallocated.status_code == 201, reallocated.content
    assert (
        client.post(
            f"/api/v1/customer-invoices/{invoice['id']}/cancel/",
            {"reason": "Customer cancellation"},
            format="json",
        ).status_code
        == 409
    )
    current = CustomerReceiptAllocation.objects.filter(
        receipt_id=receipt["id"], is_reversed=False
    ).get()
    assert (
        client.post(
            f"/api/v1/customer-receipts/{receipt['id']}/reverse-allocation/",
            {"allocation": current.pk, "reason": "Final reversal"},
            format="json",
        ).status_code
        == 200
    )
    cancelled = client.post(
        f"/api/v1/customer-invoices/{invoice['id']}/cancel/",
        {"reason": "Customer cancellation"},
        format="json",
    )
    assert cancelled.status_code == 200, cancelled.content


@pytest.mark.django_db(transaction=True)
def test_concurrent_receipt_allocations_create_one_allocation(client_for, customer, approver):
    seed()
    creator = make_user("receipt.concurrent@example.com")
    client = client_for(creator)
    invoice = _approved_customer_invoice(client, client_for, customer, approver, 100)
    receipt = client.post(
        "/api/v1/customer-receipts/",
        {
            "customer": customer.pk,
            "receipt_date": "2026-11-20",
            "amount": "100",
            "method": "bank_transfer",
        },
        format="json",
    ).json()
    barrier = threading.Barrier(2)

    def allocate_once():
        close_old_connections()
        thread_client = APIClient()
        thread_client.force_authenticate(user=creator)
        barrier.wait(timeout=10)
        response = thread_client.post(
            f"/api/v1/customer-receipts/{receipt['id']}/allocate/",
            {"invoice": invoice["id"], "amount": "60"},
            format="json",
        )
        close_old_connections()
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: allocate_once(), range(2)))

    assert sorted(statuses) == [201, 409]
    assert (
        CustomerReceiptAllocation.objects.filter(
            receipt_id=receipt["id"], is_reversed=False
        ).count()
        == 1
    )
    refreshed = client.get(f"/api/v1/customer-invoices/{invoice['id']}/").json()
    assert refreshed["amount_paid"] == "60.00"


def test_supplier_payment_creates_an_unreconciled_bank_expectation(client_for, supplier, approver):
    seed()
    activate_live_invoices(approver)
    configure_invoice_posting(approver)
    bank = _bank_account_for_receipts(approver)
    creator = make_user("payment.bank.link@example.com")
    client = client_for(creator)
    payment = client.post(
        "/api/v1/supplier-payments/",
        {
            "supplier": supplier.pk,
            "payment_date": "2026-11-15",
            "currency": "NGN",
            "amount": "250",
            "method": "bank_transfer",
            "company_bank_account": bank.pk,
            "external_reference": "PAY-BANK-LINK-1",
        },
        format="json",
    )
    assert payment.status_code == 201, payment.content
    payment_id = payment.json()["id"]
    client.post(f"/api/v1/supplier-payments/{payment_id}/submit/")
    client_for(approver).post(f"/api/v1/supplier-payments/{payment_id}/approve/")
    recorded = client.post(f"/api/v1/supplier-payments/{payment_id}/record/", {}, format="json")
    assert recorded.status_code == 200, recorded.content

    transaction = BankTransaction.objects.get(
        source_type=BankTransaction.Source.SUPPLIER_PAYMENT, source_id=payment_id
    )
    assert transaction.bank_account_id == bank.pk
    assert transaction.amount == Decimal("-250.00")
    assert transaction.status == BankTransaction.Status.RECORDED
    assert transaction.matches.count() == 0
