from __future__ import annotations

import pytest

from apps.parties.models import Party

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


def test_bank_account_number_is_write_only(auth_client):
    supplier = make_supplier()

    response = auth_client.post(
        "/api/v1/bank-accounts/",
        {
            "supplier": supplier.pk,
            "bank_name": "Example Bank",
            "account_name": "Acme Supplies",
            "account_number": "0123456789",
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    body = response.json()
    assert "account_number" not in body
    assert body["masked_account"] == "••••6789"
    assert "0123456789" not in str(auth_client.get("/api/v1/bank-accounts/").json())


def test_bank_account_requires_a_supplier(auth_client):
    customer = Party.objects.create(code="CUS-9", legal_name="Buyer", is_customer=True)

    response = auth_client.post(
        "/api/v1/bank-accounts/",
        {
            "supplier": customer.pk,
            "bank_name": "Example Bank",
            "account_name": "Buyer",
            "account_number": "1",
        },
        format="json",
    )

    assert response.status_code == 400


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
