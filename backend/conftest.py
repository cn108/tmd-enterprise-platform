"""Shared fixtures for master-data API tests."""

from __future__ import annotations

import pytest
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
    client.force_authenticate(user=user)
    return client
