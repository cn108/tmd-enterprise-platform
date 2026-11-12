"""Shared fixtures for master-data API tests."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from django.db.models import Q
from rest_framework.test import APIClient

from apps.identity.models import User


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="staff@example.com",
        full_name="Staff User",
        password="Tmd-Staff-Pass-2026!",
    )


@pytest.fixture
def auth_client(user) -> APIClient:
    # A separate client so ``api_client`` stays anonymous; force_authenticate()
    # mutates the client it is called on.
    client = APIClient()
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label__in=["organisation", "parties", "catalogue", "warehousing"],
        ).filter(
            Q(codename__startswith="view_")
            | Q(codename__startswith="add_")
            | Q(codename__startswith="change_")
            | Q(codename__startswith="delete_")
        )
    )
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="accounting", codename__startswith="view_"
        )
    )
    client.force_authenticate(user=user)
    return client
