"""Access administration: roles are empty until management defines them."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, Permission
from rest_framework.test import APIClient

from apps.identity.models import User

pytestmark = pytest.mark.django_db


def actor(*codenames: str) -> APIClient:
    user = User.objects.create_user(
        email="access-admin@example.com", full_name="Access Admin", password="Tmd-Access-Pass-2026!"
    )
    for codename in codenames:
        if "." in codename:
            app_label, name = codename.split(".", 1)
            permission = Permission.objects.get(
                content_type__app_label=app_label, codename=name
            )
        else:
            permission = Permission.objects.get(codename=codename)
        user.user_permissions.add(permission)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_no_roles_are_seeded(auth_client):
    assert Group.objects.count() == 0


def test_role_requires_the_admin_permission(auth_client):
    response = auth_client.post("/api/v1/access/roles/", {"name": "Buyer"}, format="json")

    assert response.status_code == 403
    assert Group.objects.count() == 0


def test_role_assigns_permissions_and_me_reports_them():
    admin = actor("add_group", "change_group", "view_group", "identity.change_user")
    created = admin.post(
        "/api/v1/access/roles/",
        {
            "name": "Buyer",
            "permissions": [
                "procurement.approve_purchaserequest",
                "procurement.approve_purchaseorder",
            ],
        },
        format="json",
    )

    assert created.status_code == 201, created.content
    assert created.json()["permission_codenames"] == [
        "procurement.approve_purchaseorder",
        "procurement.approve_purchaserequest",
    ]

    buyer = User.objects.create_user(email="buyer@example.com", full_name="Buyer")
    buyer.groups.add(Group.objects.get(name="Buyer"))
    client = APIClient()
    client.force_authenticate(user=buyer)

    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.json()["roles"] == ["Buyer"]
    assert "procurement.approve_purchaserequest" in me.json()["permissions"]


def test_unknown_permission_is_refused():
    admin = actor("add_group")

    response = admin.post(
        "/api/v1/access/roles/",
        {"name": "Buyer", "permissions": ["procurement.invent_a_permission"]},
        format="json",
    )

    assert response.status_code == 400
    assert Group.objects.count() == 0


def test_user_administration_creates_an_account_with_a_role():
    admin = actor("identity.add_user", "identity.view_user", "add_group")
    role = admin.post("/api/v1/access/roles/", {"name": "Storekeeper"}, format="json").json()

    response = admin.post(
        "/api/v1/access/users/",
        {
            "email": "store@example.com",
            "full_name": "Store Keeper",
            "password": "Tmd-Store-Pass-2026!",
            "roles": [role["name"]],
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    created = User.objects.get(email="store@example.com")
    assert created.check_password("Tmd-Store-Pass-2026!")
    assert list(created.groups.values_list("name", flat=True)) == ["Storekeeper"]


def test_administrator_cannot_deactivate_themselves():
    admin = actor("identity.change_user")
    me = User.objects.get(email="access-admin@example.com")

    response = admin.patch(
        f"/api/v1/access/users/{me.pk}/", {"is_active": False}, format="json"
    )

    assert response.status_code == 409
    me.refresh_from_db()
    assert me.is_active is True


def test_permission_catalogue_lists_backend_codes():
    admin = actor("view_permission")

    response = admin.get("/api/v1/access/permissions/")

    assert response.status_code == 200
    codenames = {row["codename"] for row in response.json()}
    assert "inventory.issue_stock" in codenames
    assert "projects.approve_projectbudget" in codenames