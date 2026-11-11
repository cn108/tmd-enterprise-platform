from __future__ import annotations

import pytest

from apps.catalogue.models import CatalogueItem, ItemBatch, ItemPrice, SerialNumber

pytestmark = pytest.mark.django_db


def make_item(code: str = "ITEM-001", kind: str = "product") -> CatalogueItem:
    return CatalogueItem.objects.create(code=code, name="Pump", kind=kind)


def test_service_cannot_track_serials(auth_client):
    response = auth_client.post(
        "/api/v1/catalogue-items/",
        {"code": "SVC-1", "name": "Installation", "kind": "service", "tracks_serials": True},
        format="json",
    )

    assert response.status_code == 400


def test_sku_is_unique_across_products_and_services(auth_client):
    assert (
        auth_client.post(
            "/api/v1/catalogue-items/",
            {"code": "DUP-1", "name": "Pump", "kind": "product"},
            format="json",
        ).status_code
        == 201
    )

    response = auth_client.post(
        "/api/v1/catalogue-items/",
        {"code": "dup-1", "name": "Pump service", "kind": "service"},
        format="json",
    )

    assert response.status_code == 400


def test_product_reports_that_it_is_stock_tracked(auth_client):
    response = auth_client.post(
        "/api/v1/catalogue-items/",
        {"code": "ITEM-7", "name": "Valve", "kind": "product"},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["is_stock_tracked"] is True


def test_price_periods_cannot_overlap(auth_client):
    item = make_item()

    first = auth_client.post(
        "/api/v1/item-prices/",
        {"item": item.pk, "amount": "100.000000", "effective_from": "2026-01-01"},
        format="json",
    )
    overlapping = auth_client.post(
        "/api/v1/item-prices/",
        {"item": item.pk, "amount": "120.000000", "effective_from": "2026-06-01"},
        format="json",
    )

    assert first.status_code == 201, first.content
    assert overlapping.status_code == 400


def test_consecutive_price_periods_are_accepted(auth_client):
    item = make_item()

    first = auth_client.post(
        "/api/v1/item-prices/",
        {
            "item": item.pk,
            "amount": "100.000000",
            "effective_from": "2026-01-01",
            "effective_to": "2026-05-31",
        },
        format="json",
    )
    second = auth_client.post(
        "/api/v1/item-prices/",
        {"item": item.pk, "amount": "120.000000", "effective_from": "2026-06-01"},
        format="json",
    )

    assert first.status_code == 201, first.content
    assert second.status_code == 201, second.content


def test_price_history_is_append_only(auth_client):
    item = make_item()
    created = auth_client.post(
        "/api/v1/item-prices/",
        {"item": item.pk, "amount": "10.000000", "effective_from": "2026-01-01"},
        format="json",
    )
    price_id = created.json()["id"]

    patched = auth_client.patch(f"/api/v1/item-prices/{price_id}/", {}, format="json")
    assert patched.status_code == 405
    assert auth_client.delete(f"/api/v1/item-prices/{price_id}/").status_code == 405
    assert ItemPrice.objects.filter(pk=price_id).exists()


def test_specification_name_is_unique_per_item(auth_client):
    item = make_item()
    payload = {"item": item.pk, "name": "Flow rate", "value": "50", "unit": "m3/h"}

    created = auth_client.post("/api/v1/technical-specifications/", payload, format="json")
    assert created.status_code == 201
    assert (
        auth_client.post("/api/v1/technical-specifications/", payload, format="json").status_code
        == 400
    )


def test_batch_number_is_unique_per_item_only(auth_client):
    first_item = make_item("ITEM-A")
    second_item = make_item("ITEM-B")

    assert (
        auth_client.post(
            "/api/v1/item-batches/",
            {"item": first_item.pk, "batch_number": "LOT-1"},
            format="json",
        ).status_code
        == 201
    )
    assert (
        auth_client.post(
            "/api/v1/item-batches/",
            {"item": second_item.pk, "batch_number": "LOT-1"},
            format="json",
        ).status_code
        == 201
    )
    duplicate = auth_client.post(
        "/api/v1/item-batches/", {"item": first_item.pk, "batch_number": "LOT-1"}, format="json"
    )

    assert duplicate.status_code == 400


def test_serial_must_belong_to_the_same_item_as_its_batch(auth_client):
    item = make_item("ITEM-X")
    other = make_item("ITEM-Y")
    other_batch = ItemBatch.objects.create(item=other, batch_number="LOT-9")

    response = auth_client.post(
        "/api/v1/serial-numbers/",
        {"item": item.pk, "serial": "SN-1", "batch": other_batch.pk},
        format="json",
    )

    assert response.status_code == 400


def test_serial_number_is_unique_per_item(auth_client):
    item = make_item("ITEM-Z")
    SerialNumber.objects.create(item=item, serial="SN-1")

    response = auth_client.post(
        "/api/v1/serial-numbers/", {"item": item.pk, "serial": "SN-1"}, format="json"
    )

    assert response.status_code == 400


def test_certificate_requires_a_target(auth_client):
    response = auth_client.post(
        "/api/v1/certificates/", {"certificate_type": "Calibration"}, format="json"
    )

    assert response.status_code == 400


def test_certificate_can_reference_an_item(auth_client):
    item = make_item("ITEM-C")

    response = auth_client.post(
        "/api/v1/certificates/",
        {"item": item.pk, "certificate_type": "Calibration", "issuer": "Lab Ltd"},
        format="json",
    )

    assert response.status_code == 201, response.content
