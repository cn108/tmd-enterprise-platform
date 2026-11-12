"""Project budgets and milestones (PRJ-03, PRJ-05)."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.identity.models import User
from apps.projects.models import Project, ProjectBudget

pytestmark = pytest.mark.django_db


def make_project(code: str = "PRJ-B1") -> Project:
    return Project.objects.create(code=code, name="Budgeted works")


def approver() -> APIClient:
    user = User.objects.create_user(email="budget-approver@example.com", full_name="Approver")
    user.user_permissions.add(Permission.objects.get(codename="approve_projectbudget"))
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_budget_versions_start_at_one_and_total_the_lines(auth_client):
    project = make_project()
    payload = {
        "project": project.pk,
        "notes": "Client-approved cost plan",
        "lines": [
            {"description": "Materials", "amount": "1000.00"},
            {"description": "Labour", "amount": "500.50"},
        ],
    }

    first = auth_client.post("/api/v1/project-budgets/", payload, format="json")
    second = auth_client.post("/api/v1/project-budgets/", payload, format="json")

    assert first.status_code == 201, first.content
    assert first.json()["version"] == 1
    assert first.json()["total_value"] == "1500.50"
    assert first.json()["status"] == "draft"
    assert second.status_code == 201, second.content
    assert second.json()["version"] == 2


def test_budget_requires_at_least_one_line(auth_client):
    response = auth_client.post(
        "/api/v1/project-budgets/",
        {"project": make_project().pk, "lines": []},
        format="json",
    )

    assert response.status_code == 400


def test_approval_needs_the_permission_and_a_second_person(auth_client):
    project = make_project()
    budget = auth_client.post(
        "/api/v1/project-budgets/",
        {
            "project": project.pk,
            "lines": [{"description": "Materials", "amount": "100.00"}],
        },
        format="json",
    ).json()

    assert auth_client.post(f"/api/v1/project-budgets/{budget['id']}/approve/").status_code == 403

    approved = approver().post(f"/api/v1/project-budgets/{budget['id']}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "budget-approver@example.com"


def test_creator_cannot_approve_their_own_budget(auth_client):
    user = User.objects.get(email="staff@example.com")
    user.user_permissions.add(Permission.objects.get(codename="approve_projectbudget"))
    budget = auth_client.post(
        "/api/v1/project-budgets/",
        {
            "project": make_project().pk,
            "lines": [{"description": "Materials", "amount": "100.00"}],
        },
        format="json",
    ).json()

    response = auth_client.post(f"/api/v1/project-budgets/{budget['id']}/approve/")

    assert response.status_code == 409
    assert ProjectBudget.objects.get(pk=budget["id"]).status == "draft"


def test_approved_budget_cannot_be_edited(auth_client):
    budget = auth_client.post(
        "/api/v1/project-budgets/",
        {
            "project": make_project().pk,
            "lines": [{"description": "Materials", "amount": "100.00"}],
        },
        format="json",
    ).json()
    approver().post(f"/api/v1/project-budgets/{budget['id']}/approve/")

    response = auth_client.patch(
        f"/api/v1/project-budgets/{budget['id']}/",
        {"notes": "Changed after approval"},
        format="json",
    )

    assert response.status_code == 400


def test_milestones_are_maintained_and_not_deleted(auth_client):
    project = make_project()
    created = auth_client.post(
        "/api/v1/project-milestones/",
        {"project": project.pk, "name": "Foundation complete", "due_date": "2026-03-01"},
        format="json",
    )

    assert created.status_code == 201, created.content
    milestone = created.json()
    completed = auth_client.patch(
        f"/api/v1/project-milestones/{milestone['id']}/",
        {"completed_on": "2026-02-27"},
        format="json",
    )
    assert completed.status_code == 200
    assert completed.json()["completed_on"] == "2026-02-27"
    assert auth_client.delete(f"/api/v1/project-milestones/{milestone['id']}/").status_code == 409
