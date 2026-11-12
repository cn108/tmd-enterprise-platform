"""Inventory tests: ledger, reservations, transfers, valuation and counts."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth.models import Permission
from django.db import DatabaseError, connection, transaction
from rest_framework.test import APIClient

from apps.catalogue.models import CatalogueItem, SerialNumber
from apps.identity.models import User
from apps.inventory.models import InventoryPolicy, ReorderLevel, StockMovement
from apps.parties.models import Party
from apps.procurement.models import DeliverySchedule, Destination, PurchaseOrder, PurchaseRequest
from apps.projects.models import Project
from apps.warehousing.models import Warehouse

pytestmark = pytest.mark.django_db


def make_warehouse(code: str = "WH-I1") -> Warehouse:
    return Warehouse.objects.create(code=code, name="Stores")


def make_item(code: str = "ITEM-I1") -> CatalogueItem:
    return CatalogueItem.objects.create(code=code, name="Cable", kind="product")


def grant(codename: str, email: str | None = None) -> APIClient:
    user = User.objects.create_user(
        email=email or f"{codename}-{uuid4().hex[:8]}@example.com",
        full_name="Inventory Actor",
    )
    user.user_permissions.add(Permission.objects.get(codename=codename))
    client = APIClient()
    client.force_authenticate(user=User.objects.get(pk=user.pk))
    return client


def configure(method: str = "fifo") -> InventoryPolicy:
    policy, _ = InventoryPolicy.objects.update_or_create(
        pk=1, defaults={"valuation_method": method}
    )
    return policy


def receive(
    client,
    warehouse: Warehouse,
    item: CatalogueItem,
    quantity: str = "10",
    unit_cost: str = "100",
    received_at: str = "2026-12-01",
) -> dict:
    response = client.post(
        "/api/v1/stock-receipts/",
        {
            "warehouse": warehouse.pk,
            "received_at": received_at,
            "lines": [{"item": item.pk, "quantity": quantity, "unit_cost": unit_cost}],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def rows(client, warehouse: Warehouse | None = None) -> list[dict]:
    url = "/api/v1/stock-balances/"
    if warehouse is not None:
        url += f"?warehouse={warehouse.pk}"
    response = client.get(url)
    assert response.status_code == 200, response.content
    return response.json()["rows"]


def row_for(client, warehouse: Warehouse, item: CatalogueItem) -> dict | None:
    return next(
        (row for row in rows(client, warehouse) if row["item_code"] == item.code),
        None,
    )


class TestPolicy:
    def test_valuation_refuses_until_a_method_is_recorded(self, auth_client):
        warehouse = make_warehouse()
        receive(grant("receive_stock"), warehouse, make_item())

        response = auth_client.get("/api/v1/inventory-valuation/")

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_state"

    def test_setting_the_method_requires_the_permission(self, auth_client):
        response = auth_client.patch("/api/v1/inventory-policy/", {"method": "fifo"}, format="json")

        assert response.status_code == 403

    def test_method_is_recorded_with_the_approver(self):
        client = grant("set_valuation_method")

        response = client.patch(
            "/api/v1/inventory-policy/",
            {"method": "weighted_average", "note": "Finance decision pending D-06"},
            format="json",
        )

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["valuation_method"] == "weighted_average"
        assert body["configured"] is True
        assert body["approved_by"].startswith("set_valuation_method-")

    def test_method_cannot_change_once_movements_exist(self):
        configure("fifo")
        receive(grant("receive_stock"), make_warehouse(), make_item())

        response = grant("set_valuation_method").patch(
            "/api/v1/inventory-policy/", {"method": "weighted_average"}, format="json"
        )

        assert response.status_code == 409


class TestReceiptsAndBalances:
    def test_receipt_posts_a_signed_movement_and_a_derived_balance(self, auth_client):
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")

        balance = row_for(auth_client, warehouse, item)

        assert balance["on_hand"] == "10.0000"
        assert balance["reserved"] == "0.0000"
        assert balance["available"] == "10.0000"
        assert balance["value"] == "1000.00"
        movements = auth_client.get("/api/v1/stock-movements/").json()["results"]
        assert movements[0]["movement_type"] == "receipt"
        assert movements[0]["quantity"] == "10.0000"
        assert movements[0]["value_delta"] == "1000.00"

    def test_movements_are_read_only(self, auth_client):
        receive(grant("receive_stock"), make_warehouse(), make_item())
        movement = StockMovement.objects.get()

        assert (
            auth_client.patch(
                f"/api/v1/stock-movements/{movement.pk}/", {}, format="json"
            ).status_code
            == 405
        )
        assert auth_client.delete(f"/api/v1/stock-movements/{movement.pk}/").status_code == 405
        assert StockMovement.objects.filter(pk=movement.pk).exists()

    def test_balances_have_no_write_route(self, auth_client):
        assert auth_client.post("/api/v1/stock-balances/", {}, format="json").status_code == 405

    def test_warehouses_keep_separate_balances(self, auth_client):
        first = make_warehouse("WH-A")
        second = make_warehouse("WH-B")
        item = make_item()
        receive(grant("receive_stock"), first, item, "10", "100")
        receive(grant("receive_stock"), second, item, "4", "150")

        first_row = row_for(auth_client, first, item)
        second_row = row_for(auth_client, second, item)

        assert first_row["on_hand"] == "10.0000"
        assert first_row["value"] == "1000.00"
        assert second_row["on_hand"] == "4.0000"
        assert second_row["value"] == "600.00"
        assert len(rows(auth_client)) == 2


class TestReservations:
    def test_reservation_reduces_availability_without_moving_stock(self, auth_client):
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        reserve = grant("reserve_stock")

        created = reserve.post(
            "/api/v1/stock-reservations/",
            {"item": item.pk, "warehouse": warehouse.pk, "quantity": "4"},
            format="json",
        )

        assert created.status_code == 201, created.content
        balance = row_for(auth_client, warehouse, item)
        assert balance["on_hand"] == "10.0000"
        assert balance["reserved"] == "4.0000"
        assert balance["available"] == "6.0000"

    def test_release_restores_availability(self, auth_client):
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        reserve = grant("reserve_stock")
        reservation = reserve.post(
            "/api/v1/stock-reservations/",
            {"item": item.pk, "warehouse": warehouse.pk, "quantity": "4"},
            format="json",
        ).json()

        released = reserve.post(f"/api/v1/stock-reservations/{reservation['id']}/release/")

        assert released.status_code == 200, released.content
        assert row_for(auth_client, warehouse, item)["available"] == "10.0000"

    def test_over_reserving_is_refused(self):
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        reserve = grant("reserve_stock")

        response = reserve.post(
            "/api/v1/stock-reservations/",
            {"item": item.pk, "warehouse": warehouse.pk, "quantity": "11"},
            format="json",
        )

        assert response.status_code == 409


class TestIssues:
    def test_issue_records_the_project_and_moves_stock_out(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        project = Project.objects.create(code="PRJ-I1", name="Riverside")
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        issue = grant("issue_stock")

        response = issue.post(
            "/api/v1/stock-issues/",
            {
                "project": project.pk,
                "lines": [{"item": item.pk, "warehouse": warehouse.pk, "quantity": "4"}],
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        body = response.json()
        assert body["lines"][0]["value"] == "400.00"
        assert row_for(auth_client, warehouse, item)["on_hand"] == "6.0000"
        assert StockMovement.objects.get(movement_type="project_issue").project_id == project.pk

    def test_traceable_item_uses_specific_identification_over_weighted_average(self):
        configure("weighted_average")
        warehouse = make_warehouse()
        item = make_item("SERIAL-ITEM")
        item.tracks_serials = True
        item.save(update_fields=["tracks_serials"])
        first = SerialNumber.objects.create(item=item, serial="SN-1")
        second = SerialNumber.objects.create(item=item, serial="SN-2")
        receiver = grant("receive_stock")
        for serial, cost in ((first, "100"), (second, "200")):
            response = receiver.post(
                "/api/v1/stock-receipts/",
                {
                    "warehouse": warehouse.pk,
                    "received_at": "2026-12-01",
                    "lines": [
                        {
                            "item": item.pk,
                            "quantity": "1",
                            "unit_cost": cost,
                            "serial": serial.pk,
                        }
                    ],
                },
                format="json",
            )
            assert response.status_code == 201, response.content

        response = grant("issue_stock").post(
            "/api/v1/stock-issues/",
            {
                "lines": [
                    {
                        "item": item.pk,
                        "warehouse": warehouse.pk,
                        "quantity": "1",
                        "serial": first.pk,
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        assert response.json()["lines"][0]["value"] == "100.00"

    def test_stock_movements_are_immutable_at_the_database(self):
        configure("fifo")
        warehouse = make_warehouse()
        receive(grant("receive_stock"), warehouse, make_item(), "1", "10")
        movement = StockMovement.objects.get()

        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE inventory_stockmovement SET quantity = 99 WHERE id = %s",
                        [movement.pk],
                    )

    def test_issue_consumes_a_reservation(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        reserve = grant("reserve_stock")
        reservation = reserve.post(
            "/api/v1/stock-reservations/",
            {"item": item.pk, "warehouse": warehouse.pk, "quantity": "4"},
            format="json",
        ).json()

        response = grant("issue_stock").post(
            "/api/v1/stock-issues/",
            {
                "lines": [
                    {
                        "item": item.pk,
                        "warehouse": warehouse.pk,
                        "quantity": "4",
                        "reservation": reservation["id"],
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        assert row_for(auth_client, warehouse, item)["on_hand"] == "6.0000"
        assert row_for(auth_client, warehouse, item)["reserved"] == "0.0000"

    def test_issue_needs_the_permission(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")

        response = auth_client.post(
            "/api/v1/stock-issues/",
            {"lines": [{"item": item.pk, "warehouse": warehouse.pk, "quantity": "1"}]},
            format="json",
        )

        assert response.status_code == 403

    def test_issue_beyond_available_stock_is_refused(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "1", "100")
        issue = grant("issue_stock")

        response = issue.post(
            "/api/v1/stock-issues/",
            {"lines": [{"item": item.pk, "warehouse": warehouse.pk, "quantity": "2"}]},
            format="json",
        )

        assert response.status_code == 409
        assert row_for(auth_client, warehouse, item)["on_hand"] == "1.0000"


class TestTransfers:
    def test_transfer_moves_stock_between_warehouses_at_cost(self, auth_client):
        configure("fifo")
        source = make_warehouse("WH-S")
        destination = make_warehouse("WH-D")
        item = make_item()
        receive(grant("receive_stock"), source, item, "10", "100")
        transfer_client = grant("transfer_stock")

        created = transfer_client.post(
            "/api/v1/stock-transfers/",
            {
                "from_warehouse": source.pk,
                "to_warehouse": destination.pk,
                "lines": [{"item": item.pk, "quantity": "4"}],
            },
            format="json",
        )
        assert created.status_code == 201, created.content
        transfer = created.json()

        dispatched = transfer_client.post(f"/api/v1/stock-transfers/{transfer['id']}/dispatch/")
        assert dispatched.status_code == 200, dispatched.content
        assert row_for(auth_client, source, item)["on_hand"] == "6.0000"
        assert row_for(auth_client, destination, item) is None

        received = transfer_client.post(f"/api/v1/stock-transfers/{transfer['id']}/receive/")
        assert received.status_code == 200, received.content
        destination_row = row_for(auth_client, destination, item)
        assert destination_row["on_hand"] == "4.0000"
        assert destination_row["value"] == "400.00"
        assert received.json()["lines"][0]["unit_cost"] == "100.000000"

    def test_transfer_cannot_dispatch_more_than_is_available(self, auth_client):
        configure("fifo")
        source = make_warehouse("WH-S")
        destination = make_warehouse("WH-D")
        item = make_item()
        receive(grant("receive_stock"), source, item, "2", "100")
        transfer_client = grant("transfer_stock")
        transfer = transfer_client.post(
            "/api/v1/stock-transfers/",
            {
                "from_warehouse": source.pk,
                "to_warehouse": destination.pk,
                "lines": [{"item": item.pk, "quantity": "3"}],
            },
            format="json",
        ).json()

        response = transfer_client.post(f"/api/v1/stock-transfers/{transfer['id']}/dispatch/")

        assert response.status_code == 409
        assert row_for(auth_client, source, item)["on_hand"] == "2.0000"

    def test_a_transfer_cannot_be_received_twice(self):
        configure("fifo")
        source = make_warehouse("WH-S")
        destination = make_warehouse("WH-D")
        item = make_item()
        receive(grant("receive_stock"), source, item, "5", "100")
        transfer_client = grant("transfer_stock")
        transfer = transfer_client.post(
            "/api/v1/stock-transfers/",
            {
                "from_warehouse": source.pk,
                "to_warehouse": destination.pk,
                "lines": [{"item": item.pk, "quantity": "5"}],
            },
            format="json",
        ).json()
        transfer_client.post(f"/api/v1/stock-transfers/{transfer['id']}/dispatch/")
        assert (
            transfer_client.post(f"/api/v1/stock-transfers/{transfer['id']}/receive/").status_code
            == 200
        )

        assert (
            transfer_client.post(f"/api/v1/stock-transfers/{transfer['id']}/receive/").status_code
            == 409
        )


class TestReturnsAdjustmentsDamage:
    def test_return_brings_stock_back_at_its_cost(self, auth_client):
        warehouse = make_warehouse()
        item = make_item()

        response = grant("return_stock").post(
            "/api/v1/stock-returns/",
            {
                "lines": [
                    {
                        "item": item.pk,
                        "warehouse": warehouse.pk,
                        "quantity": "5",
                        "unit_cost": "120",
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        assert row_for(auth_client, warehouse, item)["on_hand"] == "5.0000"
        assert row_for(auth_client, warehouse, item)["value"] == "600.00"

    def test_adjustment_increase_needs_a_cost(self, auth_client):
        warehouse = make_warehouse()
        item = make_item()
        adjustment = grant("adjust_stock")

        response = adjustment.post(
            "/api/v1/stock-adjustments/",
            {
                "reason": "Opening correction",
                "lines": [
                    {
                        "item": item.pk,
                        "warehouse": warehouse.pk,
                        "quantity": "2",
                        "direction": "increase",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 409
        assert row_for(auth_client, warehouse, item) is None

    def test_adjustment_decrease_cannot_exceed_stock(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "5", "100")
        adjustment = grant("adjust_stock")

        response = adjustment.post(
            "/api/v1/stock-adjustments/",
            {
                "reason": "Recount",
                "lines": [
                    {
                        "item": item.pk,
                        "warehouse": warehouse.pk,
                        "quantity": "10",
                        "direction": "decrease",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 409
        assert row_for(auth_client, warehouse, item)["on_hand"] == "5.0000"

    def test_adjustment_decrease_posts_the_loss(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "5", "100")

        response = grant("adjust_stock").post(
            "/api/v1/stock-adjustments/",
            {
                "reason": "Recount",
                "lines": [
                    {
                        "item": item.pk,
                        "warehouse": warehouse.pk,
                        "quantity": "2",
                        "direction": "decrease",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        assert row_for(auth_client, warehouse, item)["on_hand"] == "3.0000"
        assert StockMovement.objects.get(movement_type="adjustment_out").value_delta == (
            Decimal("-200.00")
        )

    def test_damage_needs_a_reason_and_writes_stock_off(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "5", "100")
        damage = grant("write_off_stock")

        missing_reason = damage.post(
            "/api/v1/stock-damages/",
            {"lines": [{"item": item.pk, "warehouse": warehouse.pk, "quantity": "2"}]},
            format="json",
        )
        assert missing_reason.status_code == 400

        recorded = damage.post(
            "/api/v1/stock-damages/",
            {
                "reason": "Crushed in transit",
                "lines": [{"item": item.pk, "warehouse": warehouse.pk, "quantity": "2"}],
            },
            format="json",
        )

        assert recorded.status_code == 201, recorded.content
        assert row_for(auth_client, warehouse, item)["on_hand"] == "3.0000"
        assert StockMovement.objects.get(movement_type="damage").value_delta == Decimal("-200.00")


class TestCounts:
    def test_count_posts_the_variance_and_cannot_be_posted_twice(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        counter = grant("count_stock")
        count = counter.post(
            "/api/v1/stock-counts/",
            {
                "warehouse": warehouse.pk,
                "lines": [{"item": item.pk, "counted_quantity": "7"}],
            },
            format="json",
        ).json()

        posted = counter.post(f"/api/v1/stock-counts/{count['id']}/post/")

        assert posted.status_code == 200, posted.content
        assert posted.json()["status"] == "posted"
        assert posted.json()["lines"][0]["variance"] == "-3.0000"
        assert row_for(auth_client, warehouse, item)["on_hand"] == "7.0000"
        assert counter.post(f"/api/v1/stock-counts/{count['id']}/post/").status_code == 409
        assert (
            counter.patch(f"/api/v1/stock-counts/{count['id']}/", {}, format="json").status_code
            == 405
        )

    def test_count_gain_without_existing_stock_needs_a_cost(self):
        warehouse = make_warehouse()
        item = make_item()
        counter = grant("count_stock")
        count = counter.post(
            "/api/v1/stock-counts/",
            {
                "warehouse": warehouse.pk,
                "lines": [{"item": item.pk, "counted_quantity": "5"}],
            },
            format="json",
        ).json()

        assert counter.post(f"/api/v1/stock-counts/{count['id']}/post/").status_code == 409

        valued = counter.post(
            "/api/v1/stock-counts/",
            {
                "warehouse": warehouse.pk,
                "lines": [{"item": item.pk, "counted_quantity": "5", "unit_cost": "20"}],
            },
            format="json",
        ).json()

        assert counter.post(f"/api/v1/stock-counts/{valued['id']}/post/").status_code == 200


class TestReorderAlerts:
    def test_alert_fires_at_or_below_the_level(self, auth_client):
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "5", "100")
        level = ReorderLevel.objects.create(
            item=item, warehouse=warehouse, minimum_quantity=Decimal("5")
        )

        alerts = auth_client.get("/api/v1/reorder-alerts/").json()

        assert alerts["count"] == 1
        assert alerts["rows"][0]["shortfall"] == "0.0000"

        ReorderLevel.objects.filter(pk=level.pk).update(minimum_quantity=Decimal("4"))

        assert auth_client.get("/api/v1/reorder-alerts/").json()["rows"] == []

    def test_reorder_level_is_not_deleted(self, auth_client):
        level = ReorderLevel.objects.create(
            item=make_item(), warehouse=make_warehouse(), minimum_quantity="1"
        )

        response = auth_client.delete(f"/api/v1/reorder-levels/{level.pk}/")

        assert response.status_code == 409


class TestValuation:
    def test_fifo_consumes_the_oldest_layers(self, auth_client):
        configure("fifo")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        receive(grant("receive_stock"), warehouse, item, "10", "200")

        issue = grant("issue_stock").post(
            "/api/v1/stock-issues/",
            {"lines": [{"item": item.pk, "warehouse": warehouse.pk, "quantity": "15"}]},
            format="json",
        )

        assert issue.status_code == 201, issue.content
        assert issue.json()["lines"][0]["value"] == "2000.00"
        valuation = auth_client.get("/api/v1/inventory-valuation/").json()
        assert valuation["method"] == "fifo"
        assert valuation["total_quantity"] == "5.0000"
        assert valuation["total_value"] == "1000.00"
        assert valuation["rows"][0]["unit_cost"] == "200.000000"

    def test_weighted_average_uses_the_running_average(self, auth_client):
        configure("weighted_average")
        warehouse = make_warehouse()
        item = make_item()
        receive(grant("receive_stock"), warehouse, item, "10", "100")
        receive(grant("receive_stock"), warehouse, item, "10", "200")

        issue = grant("issue_stock").post(
            "/api/v1/stock-issues/",
            {"lines": [{"item": item.pk, "warehouse": warehouse.pk, "quantity": "5"}]},
            format="json",
        )

        assert issue.status_code == 201, issue.content
        assert issue.json()["lines"][0]["value"] == "750.00"
        valuation = auth_client.get("/api/v1/inventory-valuation/").json()
        assert valuation["method"] == "weighted_average"
        assert valuation["total_quantity"] == "15.0000"
        assert valuation["total_value"] == "2250.00"
        assert valuation["rows"][0]["unit_cost"] == "150.000000"


class TestGoodsReceiptIntegration:
    def _receipt(self, auth_client, destination: Destination, accepted: str, rejected: str):
        warehouse_item = make_item("ITEM-G1")
        supplier = Party.objects.create(code="SUP-G1", legal_name="Supplier Ltd", is_supplier=True)
        request = auth_client.post(
            "/api/v1/purchase-requests/",
            {
                "destination": destination.pk,
                "lines": [{"item": warehouse_item.pk, "quantity": "10"}],
            },
            format="json",
        ).json()
        auth_client.post(f"/api/v1/purchase-requests/{request['id']}/submit/")
        request_approver = grant("approve_purchaserequest", "grn-req@example.com")
        approved = request_approver.post(f"/api/v1/purchase-requests/{request['id']}/approve/")
        assert approved.status_code == 200, approved.content
        order = auth_client.post(
            "/api/v1/purchase-orders/",
            {
                "supplier": supplier.pk,
                "request": request["id"],
                "destination": destination.pk,
                "lines": [
                    {
                        "item": warehouse_item.pk,
                        "quantity": "10",
                        "unit_price": "100",
                    }
                ],
            },
            format="json",
        ).json()
        auth_client.post(f"/api/v1/purchase-orders/{order['id']}/submit/")
        order_approver = grant("approve_purchaseorder", "grn-po@example.com")
        assert (
            order_approver.post(f"/api/v1/purchase-orders/{order['id']}/approve/").status_code
            == 200
        )
        auth_client.post(f"/api/v1/purchase-orders/{order['id']}/issue/")
        stored = PurchaseOrder.objects.get(pk=order["id"])
        line = stored.lines.get()
        schedule = DeliverySchedule.objects.create(
            order_line=line,
            due_date="2026-12-01",
            quantity=Decimal("10"),
            destination=destination,
        )
        receipt = auth_client.post(
            f"/api/v1/purchase-orders/{order['id']}/receive/",
            {
                "received_at": "2026-12-01",
                "lines": [
                    {
                        "schedule": schedule.pk,
                        "order_line": line.pk,
                        "quantity_delivered": "10",
                        "quantity_accepted": accepted,
                        "quantity_rejected": rejected,
                        "rejection_reason": "Damaged on arrival" if rejected != "0" else "",
                    }
                ],
            },
            format="json",
        )
        assert receipt.status_code == 201, receipt.content
        return warehouse_item, receipt.json()

    def test_accepted_warehouse_quantities_enter_the_ledger(self, auth_client):
        warehouse = make_warehouse()
        destination = Destination.objects.create(kind="warehouse", warehouse=warehouse)

        item, receipt = self._receipt(auth_client, destination, "6", "4")

        balance = row_for(auth_client, warehouse, item)
        assert balance["on_hand"] == "6.0000"
        assert balance["value"] == "600.00"
        movement = StockMovement.objects.get(goods_receipt_line__receipt__number=receipt["number"])
        assert movement.quantity == Decimal("6.0000")
        assert movement.movement_type == "receipt"

    def test_direct_project_delivery_does_not_enter_warehouse_stock(self, auth_client):
        project = Project.objects.create(code="PRJ-G1", name="Site")
        destination = Destination.objects.create(kind="project", project=project)

        item, receipt = self._receipt(auth_client, destination, "5", "0")

        assert StockMovement.objects.count() == 0
        assert PurchaseRequest.objects.filter(orders__receipts__number=receipt["number"]).exists()
        assert item.code == "ITEM-G1"
