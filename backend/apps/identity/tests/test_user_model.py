"""Custom user model behaviour (ADM-01, ADM-02)."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.identity.models import User
from apps.organisation.models import Department

PASSWORD = "Tmd-Str0ng-Pass-2026!"


@pytest.mark.django_db
def test_email_is_normalised_to_lower_case():
    user = User.objects.create_user(
        email="  Ama.Okafor@Example.COM ", full_name="Ama", password=PASSWORD
    )

    assert user.email == "ama.okafor@example.com"
    assert User.objects.filter(email="ama.okafor@example.com").exists()


@pytest.mark.django_db
def test_duplicate_email_is_rejected_case_insensitively():
    User.objects.create_user(email="ama@example.com", full_name="Ama", password=PASSWORD)

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(email="AMA@example.com", full_name="Other", password=PASSWORD)


@pytest.mark.django_db
def test_password_is_hashed_with_argon2():
    user = User.objects.create_user(email="ama@example.com", full_name="Ama", password=PASSWORD)

    assert user.password.startswith("argon2$")
    assert PASSWORD not in user.password
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_department_with_users_cannot_be_deleted():
    department = Department.objects.create(code="fin", name="Finance")
    User.objects.create_user(
        email="ama@example.com", full_name="Ama", password=PASSWORD, department=department
    )

    assert department.code == "FIN"
    with pytest.raises(ProtectedError):
        department.delete()


@pytest.mark.django_db
def test_department_cannot_be_its_own_parent():
    department = Department.objects.create(code="OPS", name="Operations")
    department.parent = department

    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        department.full_clean()
