"""Authentication endpoints (ADM-02, ADM-04, S-04, S-06)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from apps.identity.models import User

PASSWORD = "Tmd-Str0ng-Pass-2026!"
NEW_PASSWORD = "Tmd-New-Pass-2027!"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="Ama@Example.com",
        full_name="Ama Okafor",
        password=PASSWORD,
    )


def sign_in(client, email: str = "ama@example.com", password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )


def test_login_returns_identity_and_starts_session(user, client):
    response = sign_in(client)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ama@example.com"
    assert body["full_name"] == "Ama Okafor"
    assert client.session["_auth_user_id"] == str(user.pk)


def test_wrong_password_is_rejected(user, client):
    response = sign_in(client, password="Wrong-Pass-2026!")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_unknown_email_is_indistinguishable_from_wrong_password(user, client):
    unknown = sign_in(client, email="nobody@example.com", password=PASSWORD)
    wrong = sign_in(client, password="Wrong-Pass-2026!")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]
    assert unknown.json()["error"]["code"] == wrong.json()["error"]["code"]


@pytest.mark.django_db
def test_disabled_account_cannot_sign_in(user, client):
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = sign_in(client)

    assert response.status_code == 401


@pytest.mark.django_db
def test_lockout_blocks_even_the_correct_password(user, client):
    for _ in range(settings.AXES_FAILURE_LIMIT):
        sign_in(client, password="Wrong-Pass-2026!")

    response = sign_in(client)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_locked"
    assert "lock" in response.json()["error"]["message"].lower()


@pytest.mark.django_db
def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_current_user(user, client):
    sign_in(client)

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.json()["email"] == "ama@example.com"
    # Roles arrive in W4; the response must not invent them.
    assert response.json()["roles"] == []


def test_logout_ends_the_session(user, client):
    sign_in(client)

    assert client.post("/api/v1/auth/logout/").status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 401


@pytest.mark.django_db
def test_authenticated_mutation_without_csrf_token_is_refused(user):
    client = Client(enforce_csrf_checks=True)
    sign_in(client)

    response = client.post("/api/v1/auth/logout/")

    assert response.status_code == 403


def test_password_change_requires_the_current_password(user, client):
    sign_in(client)

    response = client.post(
        "/api/v1/auth/password/change/",
        {"current_password": "Not-My-Password-1!", "new_password": NEW_PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "current_password" in response.json()["error"]["details"]


def test_password_change_rejects_a_weak_password(user, client):
    sign_in(client)

    response = client.post(
        "/api/v1/auth/password/change/",
        {"current_password": PASSWORD, "new_password": "abc"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "new_password" in response.json()["error"]["details"]
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


def test_password_change_keeps_the_current_session(user, client):
    sign_in(client)

    response = client.post(
        "/api/v1/auth/password/change/",
        {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 200
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


def test_absolute_session_timeout_ends_the_session(user, client):
    client.force_login(user)
    session = client.session
    session["session_started_at"] = (
        timezone.now() - timedelta(seconds=settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS + 1)
    ).isoformat()
    session.save()

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def _csrf_token(client) -> str:
    client.get("/api/v1/auth/csrf/")
    return client.cookies["csrftoken"].value


@pytest.mark.django_db
def test_dev_proxy_origin_is_trusted_for_csrf(user):
    """The SPA on :4200 proxies to :8000; its Origin must be trusted locally."""
    client = Client(enforce_csrf_checks=True)
    sign_in(client)
    token = _csrf_token(client)

    response = client.post(
        "/api/v1/auth/logout/",
        headers={"Origin": "http://127.0.0.1:4200", "X-CSRFToken": token},
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_untrusted_origin_is_refused_even_with_a_valid_token(user):
    client = Client(enforce_csrf_checks=True)
    sign_in(client)
    token = _csrf_token(client)

    response = client.post(
        "/api/v1/auth/logout/",
        headers={"Origin": "http://evil.example", "X-CSRFToken": token},
    )

    assert response.status_code == 403
