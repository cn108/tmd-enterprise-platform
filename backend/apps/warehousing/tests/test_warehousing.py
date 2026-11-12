from __future__ import annotations

import pytest

from apps.warehousing.models import StorageLocation, Warehouse

pytestmark = pytest.mark.django_db


def test_warehouse_code_is_normalised(auth_client):
    response = auth_client.post(
        "/api/v1/warehouses/", {"code": " wh-1 ", "name": "Main store"}, format="json"
    )

    assert response.status_code == 201, response.content
    assert response.json()["code"] == "WH-1"


def test_location_code_is_unique_within_a_warehouse(auth_client):
    first = Warehouse.objects.create(code="WH-1", name="Main")
    second = Warehouse.objects.create(code="WH-2", name="Site")

    assert (
        auth_client.post(
            "/api/v1/storage-locations/",
            {"warehouse": first.pk, "code": "A1"},
            format="json",
        ).status_code
        == 201
    )
    assert (
        auth_client.post(
            "/api/v1/storage-locations/",
            {"warehouse": second.pk, "code": "A1"},
            format="json",
        ).status_code
        == 201
    )
    duplicate = auth_client.post(
        "/api/v1/storage-locations/", {"warehouse": first.pk, "code": "A1"}, format="json"
    )

    assert duplicate.status_code == 400


def test_is_active_filter_excludes_deactivated_records(auth_client):
    Warehouse.objects.create(code="WH-1", name="Main")
    Warehouse.objects.create(code="WH-2", name="Closed", is_active=False)

    codes = [
        row["code"]
        for row in auth_client.get("/api/v1/warehouses/?is_active=false").json()["results"]
    ]

    assert codes == ["WH-2"]


def test_warehouse_is_not_deleted(auth_client):
    warehouse = Warehouse.objects.create(code="WH-1", name="Main")

    response = auth_client.delete(f"/api/v1/warehouses/{warehouse.pk}/")

    assert response.status_code == 409
    assert Warehouse.objects.filter(pk=warehouse.pk).exists()
    assert StorageLocation.objects.count() == 0
