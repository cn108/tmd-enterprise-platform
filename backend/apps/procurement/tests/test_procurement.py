"""Procurement lifecycle tests: requests, quotes, orders, deliveries."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.identity.models import User
from apps.parties.models import Party
from apps.procurement.models import (
    DeliverySchedule,
    Destination,
    PurchaseOrder,
    PurchaseRequest,
    SupplierSelection,
)

pytestmark = pytest.mark.django_db


def grant(user: User, codename: str) -> User:
    user.user_permissions.add(Permission.objects.get(codename=codename))
    return User.objects.get(pk=user.pk)


def make_supplier(code: str = "SUP-P1") -> Party:
    return Party.objects.create(code=code, legal_name="Supplier Ltd", is_supplier=True)


def make_warehouse():
    from apps.warehousing.models import Warehouse

    return Warehouse.objects.create(code="WH-P1", name="Stores")


def make_item(code: str = "ITEM-P1"):
    from apps.catalogue.models import CatalogueItem

    return CatalogueItem.objects.create(code=code, name="Pipe", kind="product")


def make_request(client, destination_id, item, quantity: str = "10") -> dict:
    response = client.post(
        "/api/v1/purchase-requests/",
        {
            "destination": destination_id,
            "justification": "Site requirement",
            "lines": [{"item": item.pk, "quantity": quantity}],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def make_approved_request(client, destination_id, item) -> dict:
    body = make_request(client, destination_id, item)
    client.post(f"/api/v1/purchase-requests/{body['id']}/submit/")
    approver = grant(
        User.objects.create_user(email="reqapprover@example.com", full_name="Approver"),
        "approve_purchaserequest",
    )
    approver_client = APIClient()
    approver_client.force_authenticate(user=approver)
    approved = approver_client.post(f"/api/v1/purchase-requests/{body['id']}/approve/")
    assert approved.status_code == 200, approved.content
    return approved.json()


class TestDestination:
    def test_warehouse_destination(self, auth_client):
        warehouse = make_warehouse()

        response = auth_client.post(
            "/api/v1/destinations/",
            {"kind": "warehouse", "warehouse": warehouse.pk},
            format="json",
        )

        assert response.status_code == 201, response.content

    def test_project_destination_requires_a_project(self, auth_client):
        response = auth_client.post("/api/v1/destinations/", {"kind": "project"}, format="json")

        assert response.status_code == 400

    def test_other_location_requires_a_name(self, auth_client):
        response = auth_client.post("/api/v1/destinations/", {"kind": "other"}, format="json")

        assert response.status_code == 400


class TestPurchaseRequest:
    def test_request_is_created_as_a_draft_with_a_number(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())

        body = make_request(auth_client, destination.pk, make_item())

        assert body["status"] == "draft"
        assert body["number"].startswith("PR-")

    def test_submitting_without_lines_is_refused(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        request = PurchaseRequest.objects.create(
            number="PR-TEST-1",
            requester=User.objects.get(email="staff@example.com"),
            destination=destination,
        )

        response = auth_client.post(f"/api/v1/purchase-requests/{request.pk}/submit/")

        assert response.status_code == 409

    def test_approval_requires_the_permission(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        body = make_request(auth_client, destination.pk, make_item())
        auth_client.post(f"/api/v1/purchase-requests/{body['id']}/submit/")

        response = auth_client.post(f"/api/v1/purchase-requests/{body['id']}/approve/")

        assert response.status_code == 403

    def test_requester_cannot_approve_their_own_request(self, auth_client, user):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        body = make_request(auth_client, destination.pk, make_item())
        auth_client.post(f"/api/v1/purchase-requests/{body['id']}/submit/")
        self_approver = grant(User.objects.get(pk=user.pk), "approve_purchaserequest")
        client = APIClient()
        client.force_authenticate(user=self_approver)

        response = client.post(f"/api/v1/purchase-requests/{body['id']}/approve/")

        assert response.status_code == 409

    def test_approval_records_who_and_when(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())

        assert approved["status"] == "approved"
        assert approved["approved_by"] == "reqapprover@example.com"
        assert approved["approved_at"] is not None


class TestQuotations:
    def test_rfq_requires_an_approved_request(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        body = make_request(auth_client, destination.pk, make_item())

        response = auth_client.post("/api/v1/rfqs/", {"request": body["id"]}, format="json")

        assert response.status_code == 400

    def test_rfq_cannot_be_issued_without_invited_suppliers(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())
        rfq = auth_client.post("/api/v1/rfqs/", {"request": approved["id"]}, format="json").json()

        response = auth_client.post(f"/api/v1/rfqs/{rfq['id']}/issue/")

        assert response.status_code == 409

    def test_quote_from_an_uninvited_supplier_is_refused(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())
        rfq = auth_client.post("/api/v1/rfqs/", {"request": approved["id"]}, format="json").json()
        auth_client.post(f"/api/v1/rfqs/{rfq['id']}/issue/")

        response = auth_client.post(
            "/api/v1/supplier-quotes/",
            {
                "rfq": rfq["id"],
                "supplier": make_supplier().pk,
                "lines": [
                    {
                        "request_line": approved["lines"][0]["id"],
                        "quantity": "10",
                        "unit_price": "500.000000",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 400

    def test_selection_requires_the_permission(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())
        supplier = make_supplier()
        rfq = auth_client.post("/api/v1/rfqs/", {"request": approved["id"]}, format="json").json()
        auth_client.post(
            "/api/v1/rfq-suppliers/",
            {"rfq": rfq["id"], "supplier": supplier.pk},
            format="json",
        )
        auth_client.post(f"/api/v1/rfqs/{rfq['id']}/issue/")
        quote = auth_client.post(
            "/api/v1/supplier-quotes/",
            {
                "rfq": rfq["id"],
                "supplier": supplier.pk,
                "lines": [
                    {
                        "request_line": approved["lines"][0]["id"],
                        "quantity": "10",
                        "unit_price": "500.000000",
                    }
                ],
            },
            format="json",
        ).json()

        response = auth_client.post(
            "/api/v1/supplier-selections/",
            {"rfq": rfq["id"], "quote": quote["id"], "reason": "Lowest price"},
            format="json",
        )

        assert response.status_code == 403

    def test_a_supplier_can_be_selected_once(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())
        supplier = make_supplier()
        selector = grant(
            User.objects.create_user(email="buyer@example.com", full_name="Buyer"),
            "select_supplier",
        )
        buyer = APIClient()
        buyer.force_authenticate(user=selector)
        rfq = auth_client.post("/api/v1/rfqs/", {"request": approved["id"]}, format="json").json()
        auth_client.post(
            "/api/v1/rfq-suppliers/",
            {"rfq": rfq["id"], "supplier": supplier.pk},
            format="json",
        )
        auth_client.post(f"/api/v1/rfqs/{rfq['id']}/issue/")
        quote = auth_client.post(
            "/api/v1/supplier-quotes/",
            {
                "rfq": rfq["id"],
                "supplier": supplier.pk,
                "lines": [
                    {
                        "request_line": approved["lines"][0]["id"],
                        "quantity": "10",
                        "unit_price": "500.000000",
                    }
                ],
            },
            format="json",
        ).json()
        payload = {"rfq": rfq["id"], "quote": quote["id"], "reason": "Best value"}

        assert buyer.post("/api/v1/supplier-selections/", payload, format="json").status_code == 201
        assert buyer.post("/api/v1/supplier-selections/", payload, format="json").status_code == 400


class TestPurchaseOrder:
    def _approved_request(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        return make_approved_request(auth_client, destination.pk, make_item()), destination

    def test_order_from_a_selection_copies_lines_and_price(self, auth_client):
        approved, destination = self._approved_request(auth_client)
        supplier = make_supplier()
        buyer = APIClient()
        buyer.force_authenticate(
            user=grant(
                User.objects.create_user(email="buyer2@example.com", full_name="Buyer"),
                "select_supplier",
            )
        )
        rfq = auth_client.post("/api/v1/rfqs/", {"request": approved["id"]}, format="json").json()
        auth_client.post(
            "/api/v1/rfq-suppliers/",
            {"rfq": rfq["id"], "supplier": supplier.pk},
            format="json",
        )
        auth_client.post(f"/api/v1/rfqs/{rfq['id']}/issue/")
        quote = auth_client.post(
            "/api/v1/supplier-quotes/",
            {
                "rfq": rfq["id"],
                "supplier": supplier.pk,
                "lines": [
                    {
                        "request_line": approved["lines"][0]["id"],
                        "quantity": "10",
                        "unit_price": "500.000000",
                    }
                ],
            },
            format="json",
        ).json()
        selection = buyer.post(
            "/api/v1/supplier-selections/",
            {"rfq": rfq["id"], "quote": quote["id"], "reason": "Best value"},
            format="json",
        ).json()

        response = auth_client.post(
            "/api/v1/purchase-orders/",
            {
                "selection": selection["id"],
                "supplier": supplier.pk,
                "request": approved["id"],
                "destination": destination.pk,
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        body = response.json()
        assert body["status"] == "draft"
        assert body["lines"][0]["unit_price"] == "500.000000"
        assert body["total_value"] == "5000.00"
        assert SupplierSelection.objects.count() == 1

    def test_order_needs_an_approved_request(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        body = make_request(auth_client, destination.pk, make_item())

        response = auth_client.post(
            "/api/v1/purchase-orders/",
            {
                "supplier": make_supplier().pk,
                "request": body["id"],
                "destination": destination.pk,
                "lines": [
                    {
                        "item": make_item("ITEM-P2").pk,
                        "quantity": "1",
                        "unit_price": "10.000000",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 400

    def test_issue_requires_approval(self, auth_client):
        approved, destination = self._approved_request(auth_client)
        order = auth_client.post(
            "/api/v1/purchase-orders/",
            {
                "supplier": make_supplier().pk,
                "request": approved["id"],
                "destination": destination.pk,
                "lines": [
                    {
                        "item": make_item("ITEM-P3").pk,
                        "quantity": "1",
                        "unit_price": "10.000000",
                    }
                ],
            },
            format="json",
        ).json()

        response = auth_client.post(f"/api/v1/purchase-orders/{order['id']}/issue/")

        assert response.status_code == 409


class TestReceiving:
    def _issued_order(self, auth_client, quantity: str = "10"):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())
        supplier = make_supplier()
        order = auth_client.post(
            "/api/v1/purchase-orders/",
            {
                "supplier": supplier.pk,
                "request": approved["id"],
                "destination": destination.pk,
                "lines": [
                    {
                        "item": make_item("ITEM-R1").pk,
                        "quantity": quantity,
                        "unit_price": "100.000000",
                    }
                ],
            },
            format="json",
        ).json()
        auth_client.post(f"/api/v1/purchase-orders/{order['id']}/submit/")
        approver = grant(
            User.objects.create_user(email="poapprover@example.com", full_name="Approver"),
            "approve_purchaseorder",
        )
        po_client = APIClient()
        po_client.force_authenticate(user=approver)
        approved_order = po_client.post(f"/api/v1/purchase-orders/{order['id']}/approve/")
        assert approved_order.status_code == 200, approved_order.content
        auth_client.post(f"/api/v1/purchase-orders/{order['id']}/issue/")
        order = PurchaseOrder.objects.get(pk=order["id"])
        line = order.lines.get()
        schedule = DeliverySchedule.objects.create(
            order_line=line,
            due_date="2026-12-01",
            quantity=Decimal(quantity),
            destination=destination,
        )
        return order, line, schedule

    def test_partial_delivery_updates_the_order(self, auth_client):
        order, line, schedule = self._issued_order(auth_client)
        approver = grant(
            grant(
                User.objects.create_user(email="receiver@example.com", full_name="Receiver"),
                "approve_purchaseorder",
            ),
            "add_goodsreceiptnote",
        )
        client = APIClient()
        client.force_authenticate(user=approver)

        response = client.post(
            f"/api/v1/purchase-orders/{order.pk}/receive/",
            {
                "received_at": "2026-12-01",
                "lines": [
                    {
                        "schedule": schedule.pk,
                        "order_line": line.pk,
                        "quantity_delivered": "4",
                        "quantity_accepted": "4",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        order.refresh_from_db()
        line.refresh_from_db()
        assert order.status == "partially_received"
        assert line.quantity_accepted == Decimal("4.0000")

    def test_rejected_goods_need_a_reason_and_are_not_accepted(self, auth_client):
        order, line, schedule = self._issued_order(auth_client)
        approver = grant(
            grant(
                User.objects.create_user(email="receiver2@example.com", full_name="Receiver"),
                "approve_purchaseorder",
            ),
            "add_goodsreceiptnote",
        )
        client = APIClient()
        client.force_authenticate(user=approver)
        payload = {
            "received_at": "2026-12-01",
            "lines": [
                {
                    "schedule": schedule.pk,
                    "order_line": line.pk,
                    "quantity_delivered": "3",
                    "quantity_accepted": "1",
                    "quantity_rejected": "2",
                }
            ],
        }

        missing_reason = client.post(
            f"/api/v1/purchase-orders/{order.pk}/receive/", payload, format="json"
        )
        assert missing_reason.status_code == 409

        payload["lines"][0]["rejection_reason"] = "Split casing"
        accepted = client.post(
            f"/api/v1/purchase-orders/{order.pk}/receive/", payload, format="json"
        )
        assert accepted.status_code == 201, accepted.content
        line.refresh_from_db()
        assert line.quantity_accepted == Decimal("1.0000")
        assert line.quantity_rejected == Decimal("2.0000")
        assert line.remaining_quantity == Decimal("9.0000")

    def test_over_receipt_is_refused(self, auth_client):
        order, line, schedule = self._issued_order(auth_client)
        approver = grant(
            grant(
                User.objects.create_user(email="receiver3@example.com", full_name="Receiver"),
                "approve_purchaseorder",
            ),
            "add_goodsreceiptnote",
        )
        client = APIClient()
        client.force_authenticate(user=approver)

        response = client.post(
            f"/api/v1/purchase-orders/{order.pk}/receive/",
            {
                "received_at": "2026-12-01",
                "lines": [
                    {
                        "schedule": schedule.pk,
                        "order_line": line.pk,
                        "quantity_delivered": "11",
                        "quantity_accepted": "11",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 409

    def test_split_schedules_cannot_exceed_the_order(self, auth_client):
        order, line, schedule = self._issued_order(auth_client)

        response = auth_client.post(
            "/api/v1/delivery-schedules/",
            {
                "order_line": line.pk,
                "due_date": "2026-12-15",
                "quantity": "5",
                "destination": schedule.destination_id,
            },
            format="json",
        )

        assert response.status_code == 400

    def test_split_delivery_across_two_locations(self, auth_client):
        order, line, schedule = self._issued_order(auth_client)
        schedule.quantity = Decimal("6")
        schedule.save(update_fields=["quantity"])
        second_destination = Destination.objects.create(
            kind="other", location_name="Lekki site store"
        )
        second = auth_client.post(
            "/api/v1/delivery-schedules/",
            {
                "order_line": line.pk,
                "due_date": "2026-12-15",
                "quantity": "4",
                "destination": second_destination.pk,
            },
            format="json",
        )

        assert second.status_code == 201, second.content
        assert DeliverySchedule.objects.count() == 2

    def test_full_receipt_marks_the_order_received_then_closure_blocks_receipts(self, auth_client):
        order, line, schedule = self._issued_order(auth_client, quantity="5")
        approver = grant(
            grant(
                User.objects.create_user(email="receiver4@example.com", full_name="Receiver"),
                "approve_purchaseorder",
            ),
            "add_goodsreceiptnote",
        )
        client = APIClient()
        client.force_authenticate(user=approver)
        payload = {
            "received_at": "2026-12-01",
            "lines": [
                {
                    "schedule": schedule.pk,
                    "order_line": line.pk,
                    "quantity_delivered": "5",
                    "quantity_accepted": "5",
                }
            ],
        }
        assert (
            client.post(
                f"/api/v1/purchase-orders/{order.pk}/receive/", payload, format="json"
            ).status_code
            == 201
        )
        order.refresh_from_db()
        assert order.status == "received"

        closed = auth_client.post(
            f"/api/v1/purchase-orders/{order.pk}/close/",
            {"reason": "Fully delivered"},
            format="json",
        )
        assert closed.status_code == 200, closed.content
        order.refresh_from_db()
        assert order.status == "closed"

        again = client.post(f"/api/v1/purchase-orders/{order.pk}/receive/", payload, format="json")
        assert again.status_code == 409


class TestOrderAmendment:
    def _draft_order(self, auth_client):
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())
        response = auth_client.post(
            "/api/v1/purchase-orders/",
            {
                "supplier": make_supplier().pk,
                "request": approved["id"],
                "destination": destination.pk,
                "lines": [
                    {"item": make_item("ITEM-AM1").pk, "quantity": "2", "unit_price": "10.000000"}
                ],
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        return response.json(), approved

    def test_draft_lines_are_replaced_and_revision_rises(self, auth_client):
        order, _ = self._draft_order(auth_client)

        response = auth_client.patch(
            f"/api/v1/purchase-orders/{order['id']}/",
            {
                "lines": [
                    {"item": make_item("ITEM-P2").pk, "quantity": "5", "unit_price": "12.500000"}
                ]
            },
            format="json",
        )

        assert response.status_code == 200, response.content
        assert response.json()["revision"] == 2
        assert response.json()["total_value"] == "62.50"
        assert len(response.json()["lines"]) == 1

    def test_submitted_order_cannot_be_amended(self, auth_client):
        order, _ = self._draft_order(auth_client)
        auth_client.post(f"/api/v1/purchase-orders/{order['id']}/submit/")

        response = auth_client.patch(
            f"/api/v1/purchase-orders/{order['id']}/",
            {
                "lines": [
                    {
                        "item": make_item("ITEM-P3").pk,
                        "quantity": "1",
                        "unit_price": "1.000000",
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 400
        assert PurchaseOrder.objects.get(pk=order["id"]).revision == 1


class TestProvisionalApprovalThreshold:
    def test_order_at_five_million_needs_two_distinct_approvers(self, auth_client):
        from django.core.management import call_command

        call_command("apply_provisional_governance")
        destination = Destination.objects.create(kind="warehouse", warehouse=make_warehouse())
        approved = make_approved_request(auth_client, destination.pk, make_item())
        order = auth_client.post(
            "/api/v1/purchase-orders/",
            {
                "supplier": make_supplier().pk,
                "request": approved["id"],
                "destination": destination.pk,
                "lines": [
                    {
                        "item": make_item("ITEM-HIGH").pk,
                        "quantity": "1",
                        "unit_price": "5000000.000000",
                    }
                ],
            },
            format="json",
        ).json()
        auth_client.post(f"/api/v1/purchase-orders/{order['id']}/submit/")
        first = grant(
            User.objects.create_user(email="first-approver@example.com", full_name="First"),
            "approve_purchaseorder",
        )
        second = grant(
            User.objects.create_user(email="second-approver@example.com", full_name="Second"),
            "approve_purchaseorder",
        )
        first_client = APIClient()
        first_client.force_authenticate(user=first)
        second_client = APIClient()
        second_client.force_authenticate(user=second)

        one = first_client.post(f"/api/v1/purchase-orders/{order['id']}/approve/")
        assert one.status_code == 200, one.content
        assert one.json()["status"] == "submitted"
        assert one.json()["approvals_required"] == 2
        assert one.json()["approvals_recorded"] == 1

        again = first_client.post(f"/api/v1/purchase-orders/{order['id']}/approve/")
        assert again.status_code == 409

        two = second_client.post(f"/api/v1/purchase-orders/{order['id']}/approve/")
        assert two.status_code == 200, two.content
        assert two.json()["status"] == "approved"
        assert two.json()["approvals_recorded"] == 2
