"""MFA enrolment, verification, replay and recovery controls."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.identity.mfa import current_code, decrypt_secret
from apps.identity.models import MfaDevice, User

PASSWORD = "Tmd-Str0ng-Pass-2026!"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="mfa@example.com",
        full_name="MFA Tester",
        password=PASSWORD,
        mfa_required=True,
    )


def sign_in(client):
    return client.post(
        "/api/v1/auth/login/",
        {"email": "mfa@example.com", "password": PASSWORD},
        content_type="application/json",
    )


def challenge_token(response) -> str:
    return response.json()["error"]["details"]["challenge_token"]


def enrol(client):
    first = sign_in(client)
    assert first.status_code == 401
    assert first.json()["error"]["code"] == "mfa_enrollment_required"
    token = challenge_token(first)
    setup = client.post(
        "/api/v1/auth/mfa/setup/",
        {"challenge_token": token},
        content_type="application/json",
    )
    assert setup.status_code == 200
    body = setup.json()
    code = current_code(body["secret"])
    confirm = client.post(
        "/api/v1/auth/mfa/confirm/",
        {"challenge_token": token, "code": code},
        content_type="application/json",
    )
    assert confirm.status_code == 200
    return body, token


@pytest.mark.django_db
def test_enrolment_confirms_device_and_starts_session(user, client):
    body, _ = enrol(client)

    device = MfaDevice.objects.get(user=user)
    assert device.confirmed_at is not None
    assert decrypt_secret(device.secret_encrypted) == body["secret"]
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert len(body["recovery_codes"]) == 10
    assert client.get("/api/v1/auth/me/").status_code == 200


@pytest.mark.django_db
def test_login_requires_totp_after_enrolment_and_rejects_replay(user, client):
    body, _ = enrol(client)
    client.post("/api/v1/auth/logout/")

    first = sign_in(client)
    assert first.status_code == 401
    assert first.json()["error"]["code"] == "mfa_required"
    token = challenge_token(first)
    code = current_code(body["secret"], at_time=timezone.now() + timedelta(seconds=30))
    verified = client.post(
        "/api/v1/auth/mfa/verify/",
        {"challenge_token": token, "code": code},
        content_type="application/json",
    )
    assert verified.status_code == 200

    replay = client.post(
        "/api/v1/auth/mfa/verify/",
        {"challenge_token": token, "code": code},
        content_type="application/json",
    )
    assert replay.status_code == 400
    assert replay.json()["error"]["code"] == "invalid_mfa_challenge"


@pytest.mark.django_db
def test_recovery_code_is_single_use(user, client):
    body, _ = enrol(client)
    device = MfaDevice.objects.get(user=user)
    assert body["recovery_codes"][0] not in device.recovery_codes
    assert all(len(code) == 17 for code in body["recovery_codes"])
    assert len(set(body["recovery_codes"])) == 10
    client.post("/api/v1/auth/logout/")

    first = sign_in(client)
    token = challenge_token(first)
    recovery = body["recovery_codes"][0]
    verified = client.post(
        "/api/v1/auth/mfa/verify/",
        {"challenge_token": token, "code": recovery},
        content_type="application/json",
    )
    assert verified.status_code == 200
    assert len(MfaDevice.objects.get(user=user).recovery_codes) == 9

    client.post("/api/v1/auth/logout/")
    second = sign_in(client)
    reused = client.post(
        "/api/v1/auth/mfa/verify/",
        {"challenge_token": challenge_token(second), "code": recovery},
        content_type="application/json",
    )
    assert reused.status_code == 400


@pytest.mark.django_db
def test_global_mfa_forces_enrolment_for_unflagged_user(settings, db, client):
    User.objects.create_user(email="forced@example.com", full_name="Forced", password=PASSWORD)
    settings.MFA_REQUIRED_FOR_ALL_USERS = True

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "forced@example.com", "password": PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "mfa_enrollment_required"


@pytest.mark.django_db
def test_invalid_mfa_code_does_not_create_session(user, client):
    _, _ = enrol(client)
    client.post("/api/v1/auth/logout/")

    first = sign_in(client)
    response = client.post(
        "/api/v1/auth/mfa/verify/",
        {"challenge_token": challenge_token(first), "code": "000000"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert client.get("/api/v1/auth/me/").status_code == 401
