from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.identity.models import User
from apps.parties.models import BankAccount, BankAccountChangeRequest, Party

pytestmark = pytest.mark.django_db


def make_supplier(code: str = "SUP-001", **extra) -> Party:
    return Party.objects.create(code=code, legal_name="Acme Supplies", is_supplier=True, **extra)


def test_anonymous_access_is_refused(api_client):
    assert api_client.get("/api/v1/suppliers/").status_code == 401


def test_supplier_code_is_normalised_and_role_is_implicit(auth_client):
    response = auth_client.post(
        "/api/v1/suppliers/",
        {"code": " sup-01 ", "legal_name": "Acme Supplies"},
        format="json",
    )

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["code"] == "SUP-01"
    assert body["is_customer"] is False
    party = Party.objects.get(pk=body["id"])
    assert party.is_supplier is True
    assert party.is_customer is False


def test_supplier_and_customer_cannot_share_a_code(auth_client):
    auth_client.post("/api/v1/suppliers/", {"code": "p-1", "legal_name": "Acme"}, format="json")

    response = auth_client.post(
        "/api/v1/customers/", {"code": "P-1", "legal_name": "Acme buyer"}, format="json"
    )

    assert response.status_code == 400


def test_supplier_list_excludes_customers(auth_client):
    Party.objects.create(code="CUS-1", legal_name="Buyer Ltd", is_customer=True)
    Party.objects.create(code="SUP-1", legal_name="Vendor Ltd", is_supplier=True)

    codes = [row["code"] for row in auth_client.get("/api/v1/suppliers/").json()]

    assert codes == ["SUP-1"]


def test_customer_credit_fields_are_stored(auth_client):
    response = auth_client.post(
        "/api/v1/customers/",
        {
            "code": "CUS-2",
            "legal_name": "Client Ltd",
            "credit_limit": "250000.00",
            "credit_hold": True,
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["credit_limit"] == "250000.00"
    assert response.json()["credit_hold"] is True


def grant_bank_approver(user: User) -> User:
    permission = Permission.objects.get(codename="approve_bankaccountchange")
    user.user_permissions.add(permission)
    return User.objects.get(pk=user.pk)


def make_account(supplier: Party, number: str = "0123456789") -> BankAccount:
    account = BankAccount(supplier=supplier, bank_name="Example Bank", account_name="Acme Supplies")
    account.set_account_number(number)
    account.save()
    return account


def propose_bank_change(client, supplier: Party, **overrides):
    payload = {
        "supplier": supplier.pk,
        "proposed_bank_name": "Example Bank",
        "proposed_account_name": "Acme Supplies",
        "proposed_account_number": "0123456789",
        "reason": "Initial bank account",
    }
    payload.update(overrides)
    return client.post("/api/v1/bank-account-change-requests/", payload, format="json")


def test_bank_accounts_are_read_only(auth_client):
    supplier = make_supplier()
    account = make_account(supplier)

    created = auth_client.post(
        "/api/v1/bank-accounts/",
        {
            "supplier": supplier.pk,
            "bank_name": "Example Bank",
            "account_name": "Acme Supplies",
            "account_number": "0123456789",
        },
        format="json",
    )

    assert created.status_code == 405
    assert (
        auth_client.patch(
            f"/api/v1/bank-accounts/{account.pk}/", {"bank_name": "Other"}, format="json"
        ).status_code
        == 405
    )
    assert auth_client.delete(f"/api/v1/bank-accounts/{account.pk}/").status_code == 405


def test_change_request_stores_ciphertext_not_plaintext(auth_client):
    supplier = make_supplier()

    response = propose_bank_change(auth_client, supplier)

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["status"] == "pending"
    assert body["proposed_masked_account"] == "••••6789"
    assert "proposed_account_number" not in body
    change = BankAccountChangeRequest.objects.get()
    assert change.proposed_account_number_encrypted.startswith("v1:")
    assert "0123456789" not in change.proposed_account_number_encrypted
    assert change.proposed_account_last4 == "6789"


def test_change_request_requires_a_supplier(auth_client):
    customer = Party.objects.create(code="CUS-9", legal_name="Buyer", is_customer=True)

    response = propose_bank_change(auth_client, customer)

    assert response.status_code == 400


def test_approval_creates_the_bank_account(auth_client, user):
    supplier = make_supplier()
    change_id = propose_bank_change(auth_client, supplier).json()["id"]

    approver = grant_bank_approver(
        User.objects.create_user(email="approver@example.com", full_name="Approver")
    )
    approver_client = APIClient()
    approver_client.force_authenticate(user=approver)
    response = approver_client.post(
        f"/api/v1/bank-account-change-requests/{change_id}/approve/",
        {"review_note": "Checked against the bank letter."},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "approved"
    assert response.json()["reviewed_by"] == "approver@example.com"
    account = BankAccount.objects.get(supplier=supplier)
    assert account.account_last4 == "6789"
    assert account.account_number_encrypted.startswith("v1:")
    assert "0123456789" not in account.account_number_encrypted
    assert account.get_account_number() == "0123456789"

    listed = approver_client.get("/api/v1/bank-accounts/").json()
    assert listed[0]["masked_account"] == "••••6789"
    assert "0123456789" not in str(listed)


def test_self_approval_is_refused(auth_client, user):
    supplier = make_supplier()
    change_id = propose_bank_change(auth_client, supplier).json()["id"]
    self_approver = grant_bank_approver(User.objects.get(pk=user.pk))
    client = APIClient()
    client.force_authenticate(user=self_approver)

    response = client.post(
        f"/api/v1/bank-account-change-requests/{change_id}/approve/", {}, format="json"
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "self_approval"
    assert BankAccountChangeRequest.objects.get(pk=change_id).status == "pending"
    assert BankAccount.objects.count() == 0


def test_approval_requires_the_permission(auth_client):
    supplier = make_supplier()
    change_id = propose_bank_change(auth_client, supplier).json()["id"]
    other = User.objects.create_user(email="other@example.com", full_name="Other User")
    client = APIClient()
    client.force_authenticate(user=other)

    response = client.post(
        f"/api/v1/bank-account-change-requests/{change_id}/approve/", {}, format="json"
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_rejection_leaves_no_account(auth_client):
    supplier = make_supplier()
    change_id = propose_bank_change(auth_client, supplier).json()["id"]
    approver = grant_bank_approver(
        User.objects.create_user(email="reviewer@example.com", full_name="Reviewer")
    )
    client = APIClient()
    client.force_authenticate(user=approver)

    response = client.post(
        f"/api/v1/bank-account-change-requests/{change_id}/reject/",
        {"review_note": "Account name does not match."},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "rejected"
    assert BankAccount.objects.count() == 0


def test_approved_change_updates_an_existing_account(auth_client):
    supplier = make_supplier()
    account = make_account(supplier, "0123456789")
    change_id = propose_bank_change(
        auth_client,
        supplier,
        bank_account=account.pk,
        proposed_account_number="9876543210",
    ).json()["id"]
    approver = grant_bank_approver(
        User.objects.create_user(email="approver2@example.com", full_name="Approver")
    )
    client = APIClient()
    client.force_authenticate(user=approver)

    response = client.post(
        f"/api/v1/bank-account-change-requests/{change_id}/approve/", {}, format="json"
    )

    assert response.status_code == 200, response.content
    account.refresh_from_db()
    assert account.account_last4 == "3210"
    assert account.get_account_number() == "9876543210"
    assert BankAccount.objects.count() == 1


def test_decisions_are_written_to_the_audit_log(auth_client, caplog):
    supplier = make_supplier()
    change_id = propose_bank_change(auth_client, supplier).json()["id"]
    approver = grant_bank_approver(
        User.objects.create_user(email="auditor@example.com", full_name="Auditor")
    )
    client = APIClient()
    client.force_authenticate(user=approver)

    caplog.set_level("INFO", logger="apps.parties.audit")
    client.post(f"/api/v1/bank-account-change-requests/{change_id}/approve/", {}, format="json")

    assert "bank_account_change.approved" in caplog.text
    assert "0123456789" not in caplog.text


def test_requests_are_visible_only_to_the_requester(auth_client):
    supplier = make_supplier()
    propose_bank_change(auth_client, supplier)
    stranger = User.objects.create_user(email="stranger@example.com", full_name="Stranger")
    client = APIClient()
    client.force_authenticate(user=stranger)

    assert client.get("/api/v1/bank-account-change-requests/").json() == []

    approver = grant_bank_approver(
        User.objects.create_user(email="seer@example.com", full_name="Seer")
    )
    seer = APIClient()
    seer.force_authenticate(user=approver)
    assert len(seer.get("/api/v1/bank-account-change-requests/").json()) == 1


def test_tax_registration_duplicate_is_refused(auth_client):
    supplier = make_supplier()
    payload = {"party": supplier.pk, "scheme": "TIN", "number": "12345678"}

    assert auth_client.post("/api/v1/tax-registrations/", payload, format="json").status_code == 201
    duplicate = auth_client.post("/api/v1/tax-registrations/", payload, format="json")

    assert duplicate.status_code == 400


def test_contact_and_address_attach_to_the_party(auth_client):
    supplier = make_supplier()

    contact = auth_client.post(
        "/api/v1/contacts/",
        {"party": supplier.pk, "name": "Ada Obi", "email": "ada@example.com", "is_primary": True},
        format="json",
    )
    address = auth_client.post(
        "/api/v1/addresses/",
        {"party": supplier.pk, "line1": "12 Marina", "city": "Lagos"},
        format="json",
    )

    assert contact.status_code == 201, contact.content
    assert address.status_code == 201, address.content


def test_compliance_document_expiry_cannot_precede_issue(auth_client):
    supplier = make_supplier()

    response = auth_client.post(
        "/api/v1/compliance-documents/",
        {
            "supplier": supplier.pk,
            "document_type": "Tax clearance",
            "issued_on": "2026-06-01",
            "expires_on": "2026-01-01",
        },
        format="json",
    )

    assert response.status_code == 400


def test_supplier_is_deactivated_not_deleted(auth_client):
    supplier = make_supplier()

    deletion = auth_client.delete(f"/api/v1/suppliers/{supplier.pk}/")

    assert deletion.status_code == 409
    assert deletion.json()["error"]["code"] == "delete_not_permitted"
    assert Party.objects.filter(pk=supplier.pk).exists()

    patched = auth_client.patch(
        f"/api/v1/suppliers/{supplier.pk}/", {"is_active": False}, format="json"
    )

    assert patched.status_code == 200
    supplier.refresh_from_db()
    assert supplier.is_active is False
