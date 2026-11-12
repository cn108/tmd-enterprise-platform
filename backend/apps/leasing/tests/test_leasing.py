from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.identity.models import User
from apps.leasing.models import Equipment, EquipmentMaintenance, EquipmentMovement
from apps.parties.models import Party

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
    return Party.objects.get_or_create(
        code="CUS-LEASE",
        defaults={"legal_name": "Equipment Customer", "is_customer": True},
    )[0]


def make_equipment(client: APIClient) -> dict:
    response = client.post(
        "/api/v1/equipment/",
        {
            "code": "EQ-001",
            "name": "80-tonne mobile crane",
            "category": None,
            "ownership": "owned",
            "serial_number": "CRANE-2026-001",
            "location": "Lagos yard",
            "status": "available",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def make_agreement(client: APIClient, equipment_id: int) -> dict:
    customer = make_customer()
    response = client.post(
        "/api/v1/rental-agreements/",
        {
            "customer": customer.pk,
            "start_date": "2026-05-01",
            "end_date": "2026-05-10",
            "lines": [
                {
                    "equipment": equipment_id,
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-10",
                    "quantity": "1",
                    "rate_amount": "250000.00",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def test_equipment_register_records_configurable_classification(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "manage_equipment", "view_equipment")
    created = make_equipment(auth_client)
    assert created["status"] == "available"
    assert created["asset_classification"] == ""

    updated = auth_client.patch(
        f"/api/v1/equipment/{created['id']}/",
        {"asset_classification": "Finance review pending"},
        format="json",
    )
    assert updated.status_code == 200, updated.content
    assert updated.json()["asset_classification"] == "Finance review pending"


def test_rental_agreement_approval_is_independent_and_computes_value(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner, "manage_equipment", "view_equipment", "add_rentalagreement", "view_rentalagreement"
    )
    equipment = make_equipment(auth_client)
    agreement = make_agreement(auth_client, equipment["id"])
    assert agreement["total_value"] == "2500000.00"
    assert (
        auth_client.post(f"/api/v1/rental-agreements/{agreement['id']}/approve/").status_code == 403
    )

    approver = client_for(
        "lease-approver@example.com",
        "view_rentalagreement",
        "approve_rentalagreement",
        "view_equipment",
    )
    approved = approver.post(f"/api/v1/rental-agreements/{agreement['id']}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"
    equipment_record = Equipment.objects.get(pk=equipment["id"])
    assert equipment_record.status == Equipment.Status.RESERVED


def test_overlapping_agreement_cannot_be_approved(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner, "manage_equipment", "view_equipment", "add_rentalagreement", "view_rentalagreement"
    )
    equipment = make_equipment(auth_client)
    first = make_agreement(auth_client, equipment["id"])
    second = make_agreement(auth_client, equipment["id"])
    approver = client_for(
        "lease-overlap-approver@example.com",
        "view_rentalagreement",
        "approve_rentalagreement",
    )
    assert approver.post(f"/api/v1/rental-agreements/{first['id']}/approve/").status_code == 200
    overlapping = approver.post(f"/api/v1/rental-agreements/{second['id']}/approve/")
    assert overlapping.status_code == 409
    assert "overlapping" in overlapping.json()["error"]["message"]


def test_reservation_overlap_is_rejected_on_confirmation(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner,
        "manage_equipment",
        "view_equipment",
        "add_rentalagreement",
        "view_rentalagreement",
        "add_equipmentreservation",
        "change_equipmentreservation",
        "view_equipmentreservation",
    )
    equipment = make_equipment(auth_client)
    first = make_agreement(auth_client, equipment["id"])
    approver = client_for(
        "reservation-approver@example.com",
        "view_rentalagreement",
        "approve_rentalagreement",
    )
    assert approver.post(f"/api/v1/rental-agreements/{first['id']}/approve/").status_code == 200
    customer = Party.objects.get(code="CUS-LEASE")
    reservation = auth_client.post(
        "/api/v1/equipment-reservations/",
        {
            "equipment": equipment["id"],
            "customer": customer.pk,
            "start_date": "2026-05-03",
            "end_date": "2026-05-05",
            "quantity": "1",
        },
        format="json",
    )
    assert reservation.status_code == 201, reservation.content
    confirmed = auth_client.post(
        f"/api/v1/equipment-reservations/{reservation.json()['id']}/confirm/"
    )
    assert confirmed.status_code == 409
    assert "overlapping" in confirmed.json()["error"]["message"]


def test_dispatch_return_inspection_and_maintenance(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner,
        "manage_equipment",
        "view_equipment",
        "add_rentalagreement",
        "view_rentalagreement",
        "approve_rentalagreement",
        "dispatch_rental",
        "return_equipment",
        "close_rentalagreement",
        "record_inspection",
        "manage_maintenance",
        "view_equipmentinspection",
        "view_equipmentmaintenance",
        "view_equipmentmovement",
        "view_equipment",
    )
    equipment = make_equipment(auth_client)
    agreement = make_agreement(auth_client, equipment["id"])
    approver = client_for(
        "dispatch-approver@example.com",
        "view_rentalagreement",
        "approve_rentalagreement",
    )
    approved = approver.post(f"/api/v1/rental-agreements/{agreement['id']}/approve/")
    assert approved.status_code == 200, approved.content

    dispatched = auth_client.post(
        f"/api/v1/rental-agreements/{agreement['id']}/dispatch/",
        {
            "equipment": equipment["id"],
            "movement_date": "2026-05-01",
            "expected_return_date": "2026-05-10",
        },
        format="json",
    )
    assert dispatched.status_code == 201, dispatched.content
    assert Equipment.objects.get(pk=equipment["id"]).status == Equipment.Status.RENTED
    assert (
        EquipmentMovement.objects.filter(equipment_id=equipment["id"], kind="dispatch").count() == 1
    )

    returned = auth_client.post(
        f"/api/v1/rental-agreements/{agreement['id']}/return_equipment/",
        {"equipment": equipment["id"], "movement_date": "2026-05-09", "condition": "damaged"},
        format="json",
    )
    assert returned.status_code == 201, returned.content
    assert Equipment.objects.get(pk=equipment["id"]).status == Equipment.Status.MAINTENANCE

    closed = auth_client.post(f"/api/v1/rental-agreements/{agreement['id']}/close/")
    assert closed.status_code == 200, closed.content
    assert closed.json()["status"] == "closed"

    inspection = auth_client.post(
        "/api/v1/equipment-inspections/",
        {
            "equipment": equipment["id"],
            "kind": "damage",
            "inspection_date": "2026-05-10",
            "condition": "damaged",
            "damage_found": True,
            "damage_description": "Boom hydraulic hose damaged.",
            "charge_amount": "15000.00",
        },
        format="json",
    )
    assert inspection.status_code == 201, inspection.content

    maintenance = auth_client.post(
        "/api/v1/equipment-maintenance/",
        {
            "equipment": equipment["id"],
            "kind": "corrective",
            "scheduled_date": "2026-05-11",
            "description": "Replace hydraulic hose.",
        },
        format="json",
    )
    assert maintenance.status_code == 201, maintenance.content
    started = auth_client.post(f"/api/v1/equipment-maintenance/{maintenance.json()['id']}/start/")
    assert started.status_code == 200, started.content
    completed = auth_client.post(
        f"/api/v1/equipment-maintenance/{maintenance.json()['id']}/complete/"
    )
    assert completed.status_code == 200, completed.content
    assert completed.json()["status"] == "completed"
    assert Equipment.objects.get(pk=equipment["id"]).status == Equipment.Status.AVAILABLE


def test_utilisation_and_warning_reports(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner,
        "manage_equipment",
        "view_equipment",
        "add_rentalagreement",
        "view_rentalagreement",
        "approve_rentalagreement",
        "view_equipmentmaintenance",
    )
    equipment = make_equipment(auth_client)
    agreement = make_agreement(auth_client, equipment["id"])
    approver = client_for(
        "utilisation-approver@example.com",
        "view_rentalagreement",
        "approve_rentalagreement",
    )
    assert approver.post(f"/api/v1/rental-agreements/{agreement['id']}/approve/").status_code == 200
    EquipmentMaintenance.objects.create(
        equipment_id=equipment["id"],
        kind="preventive",
        scheduled_date="2026-05-20",
        description="Planned service",
    )

    utilisation = auth_client.get("/api/v1/equipment-utilisation/?start=2026-05-01&end=2026-05-10")
    assert utilisation.status_code == 200, utilisation.content
    row = utilisation.json()["results"][0]
    assert row["rented_days"] == 10
    assert row["utilisation_percent"] == "100.00"

    warnings = auth_client.get("/api/v1/equipment-warnings/")
    assert warnings.status_code == 200, warnings.content
    assert any(item["kind"] == "maintenance" for item in warnings.json()["results"])

    availability = auth_client.get(
        "/api/v1/equipment-availability/?start=2026-05-02&end=2026-05-04"
    )
    assert availability.status_code == 200, availability.content
    assert availability.json()["results"][0]["available"] is False


def test_leasing_views_require_permissions(auth_client):
    assert auth_client.get("/api/v1/equipment/").status_code == 403
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "view_equipment")
    auth_client.force_authenticate(user=owner)
    assert auth_client.get("/api/v1/equipment/").status_code == 200
