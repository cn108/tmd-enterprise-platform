from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.identity.models import User
from apps.parties.models import Party
from apps.projects.models import Project
from apps.services.models import WorkOrderReport

pytestmark = pytest.mark.django_db


def grant(user: User, *codenames: str) -> None:
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))


def client_for(email: str, *codenames: str) -> APIClient:
    user = User.objects.create_user(email=email, full_name=email.split("@")[0])
    grant(user, *codenames)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_customer():
    return Party.objects.create(code="CUS-SVC", legal_name="Service Customer", is_customer=True)


def make_work_order(client: APIClient) -> dict:
    customer = make_customer()
    project = Project.objects.create(code="PRJ-SVC", name="Service project")
    response = client.post(
        "/api/v1/work-orders/",
        {
            "customer": customer.pk,
            "project": project.pk,
            "request_type": "corrective_maintenance",
            "priority": "high",
            "title": "Pump seal replacement",
            "description": "Replace the failed mechanical seal.",
            "site": "Riverside plant",
            "hse_requirements": "Permit to work and isolation certificate.",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def test_work_order_full_workflow(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner,
        "add_workorder",
        "change_workorder",
        "view_workorder",
        "assign_workorder",
        "complete_workorder",
        "accept_workorder",
        "view_workorderreport",
        "view_servicechecklistitem",
        "view_hserecord",
    )
    work_order = make_work_order(auth_client)
    work_order_id = work_order["id"]
    assert work_order["status"] == "draft"

    scheduled = auth_client.post(
        f"/api/v1/work-orders/{work_order_id}/schedule/",
        {"scheduled_start": "2026-04-01", "scheduled_end": "2026-04-03"},
        format="json",
    )
    assert scheduled.status_code == 200, scheduled.content
    assert scheduled.json()["status"] == "scheduled"

    started = auth_client.post(
        f"/api/v1/work-orders/{work_order_id}/start/", {"actual_start": "2026-04-01"}, format="json"
    )
    assert started.status_code == 200, started.content
    assert started.json()["status"] == "in_progress"

    technician = User.objects.create_user(email="tech@example.com", full_name="Technician")
    assigned = auth_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign/",
        {"user": technician.pk, "role": "Mechanical technician", "planned_hours": "16.00"},
        format="json",
    )
    assert assigned.status_code == 201, assigned.content
    assert assigned.json()["user_email"] == "tech@example.com"

    checklist = auth_client.post(
        "/api/v1/service-checklists/",
        {
            "work_order": work_order_id,
            "sequence": 1,
            "description": "Isolation certificate verified",
            "is_required": True,
        },
        format="json",
    )
    assert checklist.status_code == 201, checklist.content
    checklist_id = checklist.json()["id"]

    progress = auth_client.post(
        f"/api/v1/work-orders/{work_order_id}/progress/",
        {
            "percent_complete": 60,
            "notes": "Seal removed, replacement prepared.",
            "labour_hours": "8.00",
            "materials_used": "Mechanical seal kit",
        },
        format="json",
    )
    assert progress.status_code == 200, progress.content
    assert progress.json()["progress_percent"] == 60

    report = auth_client.post(
        "/api/v1/work-order-reports/",
        {
            "work_order": work_order_id,
            "summary": "Seal replaced and pump tested.",
            "findings": "Wear consistent with dry running.",
            "recommendations": "Add a low-flow alarm.",
            "completed_on": "2026-04-03",
        },
        format="json",
    )
    assert report.status_code == 201, report.content
    report_id = report.json()["id"]
    submitted = auth_client.post(f"/api/v1/work-order-reports/{report_id}/submit/")
    assert submitted.status_code == 200, submitted.content

    blocked = auth_client.post(f"/api/v1/work-orders/{work_order_id}/complete/")
    assert blocked.status_code == 409
    assert "checklist" in blocked.json()["error"]["message"]

    completed_item = auth_client.post(f"/api/v1/service-checklists/{checklist_id}/complete/")
    assert completed_item.status_code == 200, completed_item.content

    completed = auth_client.post(f"/api/v1/work-orders/{work_order_id}/complete/")
    assert completed.status_code == 200, completed.content
    assert completed.json()["status"] == "completed"

    accepted = auth_client.post(
        f"/api/v1/work-orders/{work_order_id}/accept/",
        {"customer_representative": "Plant Engineer"},
        format="json",
    )
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["status"] == "accepted"
    assert WorkOrderReport.objects.get(pk=report_id).status == "accepted"


def test_work_order_report_is_one_per_work_order(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "add_workorder", "change_workorder", "view_workorderreport")
    work_order = make_work_order(auth_client)
    payload = {"work_order": work_order["id"], "summary": "Initial report"}
    first = auth_client.post("/api/v1/work-order-reports/", payload, format="json")
    assert first.status_code == 201, first.content
    second = auth_client.post("/api/v1/work-order-reports/", payload, format="json")
    assert second.status_code == 400


def test_hse_record_can_be_recorded(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "add_workorder", "change_workorder", "view_workorder", "view_hserecord")
    work_order = make_work_order(auth_client)
    response = auth_client.post(
        "/api/v1/hse-records/",
        {
            "work_order": work_order["id"],
            "kind": "permit_to_work",
            "record_date": "2026-04-01",
            "description": "Isolation and gas test completed.",
            "outcome": "satisfactory",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["recorded_by_email"] == "staff@example.com"


def test_service_contract_activation_requires_an_independent_approver(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "add_servicecontract", "view_servicecontract")
    customer = make_customer()
    created = auth_client.post(
        "/api/v1/service-contracts/",
        {
            "customer": customer.pk,
            "kind": "maintenance",
            "title": "Annual pump maintenance",
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "value": "240000.00",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    contract_id = created.json()["id"]
    assert auth_client.post(f"/api/v1/service-contracts/{contract_id}/activate/").status_code == 403

    approver = client_for(
        "service-approver@example.com",
        "view_servicecontract",
        "approve_servicecontract",
    )
    approved = approver.post(f"/api/v1/service-contracts/{contract_id}/activate/")
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "active"


def test_service_views_require_permissions(auth_client):
    response = auth_client.get("/api/v1/work-orders/")
    assert response.status_code == 403
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "view_workorder")
    auth_client.force_authenticate(user=owner)
    assert auth_client.get("/api/v1/work-orders/").status_code == 200
