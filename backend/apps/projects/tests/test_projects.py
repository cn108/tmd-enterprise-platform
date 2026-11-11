from __future__ import annotations

import pytest

from apps.parties.models import Party
from apps.projects.models import ContractRevision, CustomerContract, Project

pytestmark = pytest.mark.django_db


def make_customer(code: str = "CUS-001") -> Party:
    return Party.objects.create(code=code, legal_name="Client Ltd", is_customer=True)


def make_project(code: str = "PRJ-001") -> Project:
    return Project.objects.create(code=code, name="Riverside works")


def test_new_project_starts_as_draft(auth_client):
    customer = make_customer()

    response = auth_client.post(
        "/api/v1/projects/",
        {"code": "prj-1", "name": "Riverside", "customer": customer.pk},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["code"] == "PRJ-1"
    assert response.json()["status"] == "draft"


def test_project_cannot_be_created_as_active(auth_client):
    response = auth_client.post(
        "/api/v1/projects/", {"code": "PRJ-2", "name": "Direct", "status": "active"}, format="json"
    )

    assert response.status_code == 400


def test_illegal_status_transition_is_refused(auth_client):
    project = make_project()

    response = auth_client.patch(
        f"/api/v1/projects/{project.pk}/", {"status": "closed"}, format="json"
    )

    assert response.status_code == 400
    project.refresh_from_db()
    assert project.status == "draft"


def test_draft_to_active_is_allowed(auth_client):
    project = make_project()

    response = auth_client.patch(
        f"/api/v1/projects/{project.pk}/", {"status": "active"}, format="json"
    )

    assert response.status_code == 200, response.content
    project.refresh_from_db()
    assert project.status == "active"


def test_project_customer_must_be_a_customer(auth_client):
    supplier = Party.objects.create(code="SUP-1", legal_name="Vendor", is_supplier=True)

    response = auth_client.post(
        "/api/v1/projects/",
        {"code": "PRJ-3", "name": "Wrong party", "customer": supplier.pk},
        format="json",
    )

    assert response.status_code == 400


def test_contract_end_cannot_precede_start(auth_client):
    project = make_project()
    customer = make_customer()

    response = auth_client.post(
        "/api/v1/customer-contracts/",
        {
            "project": project.pk,
            "customer": customer.pk,
            "reference": "CON-1",
            "value": "1000.00",
            "start_date": "2026-06-01",
            "end_date": "2026-01-01",
        },
        format="json",
    )

    assert response.status_code == 400


def test_contract_revisions_are_numbered_and_append_only(auth_client):
    project = make_project()
    customer = make_customer()
    contract = CustomerContract.objects.create(
        project=project,
        customer=customer,
        reference="CON-1",
        value="1000.00",
        start_date="2026-01-01",
    )
    payload = {
        "contract": contract.pk,
        "value": "1200.00",
        "start_date": "2026-01-01",
        "reason": "Scope increase",
    }

    first = auth_client.post("/api/v1/contract-revisions/", payload, format="json")
    second = auth_client.post("/api/v1/contract-revisions/", payload, format="json")

    assert first.status_code == 201, first.content
    assert first.json()["revision_number"] == 1
    assert second.status_code == 201, second.content
    assert second.json()["revision_number"] == 2

    revision_id = first.json()["id"]
    assert (
        auth_client.patch(
            f"/api/v1/contract-revisions/{revision_id}/", {}, format="json"
        ).status_code
        == 405
    )
    assert auth_client.delete(f"/api/v1/contract-revisions/{revision_id}/").status_code == 405
    assert ContractRevision.objects.count() == 2


def test_project_is_not_deleted(auth_client):
    project = make_project()

    response = auth_client.delete(f"/api/v1/projects/{project.pk}/")

    assert response.status_code == 409
    assert Project.objects.filter(pk=project.pk).exists()
