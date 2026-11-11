"""Password reset tokens (ADM-03)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.identity.models import PasswordResetToken, User

PASSWORD = "Tmd-Str0ng-Pass-2026!"
NEW_PASSWORD = "Tmd-Reset-Pass-2028!"


@pytest.fixture
def user(db):
    return User.objects.create_user(email="ama@example.com", full_name="Ama", password=PASSWORD)


def reset(client, token: str, password: str = NEW_PASSWORD):
    return client.post(
        "/api/v1/auth/password/reset/",
        {"token": token, "new_password": password},
        content_type="application/json",
    )


def test_only_the_hash_is_stored(user):
    token, raw = PasswordResetToken.issue(user)

    assert token.token_hash != raw
    assert token.token_hash == PasswordResetToken.hash_token(raw)
    assert raw not in token.token_hash


def test_reset_changes_the_password(user, client):
    _, raw = PasswordResetToken.issue(user)

    assert reset(client, raw).status_code == 204
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


def test_token_is_single_use(user, client):
    _, raw = PasswordResetToken.issue(user)

    assert reset(client, raw).status_code == 204
    assert reset(client, raw).status_code == 400


def test_expired_token_is_rejected(user, client):
    token, raw = PasswordResetToken.issue(user)
    token.expires_at = timezone.now() - timedelta(minutes=1)
    token.save(update_fields=["expires_at"])

    response = reset(client, raw)

    assert response.status_code == 400
    assert "token" in response.json()["error"]["details"]


def test_unknown_token_is_rejected(user, client):
    assert reset(client, "not-a-real-token").status_code == 400


def test_disabled_account_cannot_reset(user, client):
    user.is_active = False
    user.save(update_fields=["is_active"])
    _, raw = PasswordResetToken.issue(user)

    response = reset(client, raw)

    assert response.status_code == 400
    assert user.check_password(PASSWORD)


def test_password_change_invalidates_outstanding_tokens(user, client):
    client.post(
        "/api/v1/auth/login/",
        {"email": "ama@example.com", "password": PASSWORD},
        content_type="application/json",
    )
    PasswordResetToken.issue(user)
    PasswordResetToken.issue(user)

    client.post(
        "/api/v1/auth/password/change/",
        {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        content_type="application/json",
    )

    assert PasswordResetToken.objects.filter(user=user).count() == 0
