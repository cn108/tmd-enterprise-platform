"""Management commands that bootstrap and recover accounts."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.identity.models import PasswordResetToken, User

PASSWORD = "Tmd-Str0ng-Pass-2026!"


@pytest.mark.django_db
def test_create_initial_admin_creates_a_superuser():
    call_command(
        "create_initial_admin",
        email="Admin@Example.com",
        full_name="System Administrator",
        password=PASSWORD,
    )

    user = User.objects.get()
    assert user.email == "admin@example.com"
    assert user.is_superuser and user.is_staff
    assert user.must_change_password is True


@pytest.mark.django_db
def test_create_initial_admin_refuses_a_second_account():
    User.objects.create_user(email="ama@example.com", full_name="Ama", password=PASSWORD)

    with pytest.raises(CommandError):
        call_command(
            "create_initial_admin",
            email="other@example.com",
            full_name="Other",
            password=PASSWORD,
        )


@pytest.mark.django_db
def test_issue_password_reset_creates_one_usable_token():
    user = User.objects.create_user(email="ama@example.com", full_name="Ama", password=PASSWORD)

    call_command("issue_password_reset", "ama@example.com")

    tokens = PasswordResetToken.objects.filter(user=user, used_at__isnull=True)
    assert tokens.count() == 1
    user.refresh_from_db()
    assert user.must_change_password is True


@pytest.mark.django_db
def test_issue_password_reset_refuses_unknown_user():
    with pytest.raises(CommandError):
        call_command("issue_password_reset", "nobody@example.com")
