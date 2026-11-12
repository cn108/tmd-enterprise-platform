from __future__ import annotations

import pytest

from apps.organisation.models import CostCentre, Department

pytestmark = pytest.mark.django_db


def test_cost_centres_can_be_hierarchical(auth_client):
    parent = CostCentre.objects.create(code="CC-100", name="Operations")
    department = Department.objects.create(code="OPS", name="Operations")

    response = auth_client.post(
        "/api/v1/cost-centres/",
        {"code": "cc-110", "name": "Field work", "parent": parent.pk, "department": department.pk},
        format="json",
    )

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["code"] == "CC-110"
    assert body["parent"] == parent.pk


def test_cost_centre_cannot_be_its_own_parent(auth_client):
    centre = CostCentre.objects.create(code="CC-1", name="Ops")

    response = auth_client.patch(
        f"/api/v1/cost-centres/{centre.pk}/", {"parent": centre.pk}, format="json"
    )

    assert response.status_code == 400


def test_cost_centre_hierarchy_cannot_cycle(auth_client):
    top = CostCentre.objects.create(code="CC-1", name="Top")
    child = CostCentre.objects.create(code="CC-2", name="Child", parent=top)

    response = auth_client.patch(
        f"/api/v1/cost-centres/{top.pk}/", {"parent": child.pk}, format="json"
    )

    assert response.status_code == 400


def test_departments_are_listed_and_not_deleted(auth_client):
    department = Department.objects.create(code="FIN", name="Finance")

    listed = auth_client.get("/api/v1/departments/")

    assert listed.status_code == 200
    assert [row["code"] for row in listed.json()["results"]] == ["FIN"]

    deletion = auth_client.delete(f"/api/v1/departments/{department.pk}/")

    assert deletion.status_code == 409
    assert Department.objects.filter(pk=department.pk).exists()


def test_cost_centre_api_requires_authentication(api_client):
    assert api_client.get("/api/v1/cost-centres/").status_code == 401
