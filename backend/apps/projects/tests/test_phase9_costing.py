from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.catalogue.models import CatalogueItem
from apps.identity.models import User
from apps.inventory.models import StockMovement
from apps.invoicing.models import SupplierInvoice
from apps.parties.models import Party
from apps.procurement.models import Destination, PurchaseOrder, PurchaseOrderLine, PurchaseRequest
from apps.projects.models import Project, ProjectBudget, ProjectCost
from apps.warehousing.models import Warehouse

pytestmark = pytest.mark.django_db


def grant(user: User, *codenames: str) -> None:
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))


def client_for(email: str, *codenames: str) -> APIClient:
    user = User.objects.create_user(email=email, full_name=email.split("@")[0])
    grant(user, *codenames)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_project(code="PRJ-P9"):
    return Project.objects.create(code=code, name="Phase nine project")


def test_project_document_attachment_is_private_and_linked():
    from apps.documents.models import Document, DocumentLink

    project = make_project()
    owner = client_for("project-docs@example.com", "view_project", "change_project")
    response = owner.post(
        f"/api/v1/projects/{project.pk}/attach/",
        {
            "title": "Signed contract",
            "file": SimpleUploadedFile("contract.pdf", b"%PDF-1.4 test", "application/pdf"),
        },
        format="multipart",
    )

    assert response.status_code == 201, response.content
    document = Document.objects.get(pk=response.json()["document"])
    assert document.is_private is True
    assert document.original_filename == "contract.pdf"
    assert DocumentLink.objects.filter(
        document=document, entity_type=DocumentLink.EntityType.PROJECT, entity_id=project.pk
    ).exists()


def test_project_supports_manager_department_and_cost_centre(auth_client):
    from apps.organisation.models import CostCentre, Department

    department = Department.objects.create(code="ENG", name="Engineering")
    cost_centre = CostCentre.objects.create(code="CC-ENG", name="Engineering")
    manager = User.objects.create_user(email="pm@example.com", full_name="Project Manager")

    response = auth_client.post(
        "/api/v1/projects/",
        {
            "code": "PRJ-MGR",
            "name": "Managed project",
            "project_manager": manager.pk,
            "department": department.pk,
            "cost_centre": cost_centre.pk,
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["project_manager_email"] == "pm@example.com"
    assert response.json()["department_code"] == "ENG"


def test_budget_categories_and_revision_reason_are_preserved(auth_client):
    project = make_project()
    first = auth_client.post(
        "/api/v1/project-budgets/",
        {
            "project": project.pk,
            "revision_reason": "Original cost plan",
            "lines": [
                {"category": "materials", "description": "Steel", "amount": "1000.00"},
                {"category": "labour", "description": "Site labour", "amount": "500.00"},
            ],
        },
        format="json",
    )
    assert first.status_code == 201, first.content
    assert first.json()["lines"][0]["category"] == "materials"
    assert first.json()["revision_reason"] == "Original cost plan"
    second = auth_client.post(
        "/api/v1/project-budgets/",
        {
            "project": project.pk,
            "revision_reason": "Additional labour",
            "lines": [{"category": "labour", "description": "Extra labour", "amount": "2000.00"}],
        },
        format="json",
    )
    assert second.status_code == 201, second.content
    assert second.json()["version"] == 2
    assert ProjectBudget.objects.filter(project=project).count() == 2


def test_direct_project_cost_requires_independent_approval(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "add_projectcost", "view_projectcost")
    project = make_project()
    created = auth_client.post(
        "/api/v1/project-costs/",
        {
            "project": project.pk,
            "cost_date": "2026-03-01",
            "category": "labour",
            "description": "Site labour",
            "amount": "4500.00",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    cost_id = created.json()["id"]
    assert auth_client.post(f"/api/v1/project-costs/{cost_id}/approve/").status_code == 403

    approver = client_for("cost-approver@example.com", "view_projectcost", "approve_projectcost")
    approved = approver.post(f"/api/v1/project-costs/{cost_id}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"
    cost = ProjectCost.objects.get(pk=cost_id)
    assert cost.approved_by.email == "cost-approver@example.com"


def test_cost_summary_does_not_double_count_commitments_receipts_or_project_stock_transfers(
    auth_client,
):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner,
        "view_project",
        "view_projectcost",
        "view_projectbudget",
        "add_projectcost",
        "view_supplierinvoice",
        "view_stockmovement",
    )
    project = make_project()
    budget = ProjectBudget.objects.create(
        project=project, version=1, status=ProjectBudget.Status.APPROVED
    )
    from apps.projects.models import BudgetLine

    BudgetLine.objects.create(
        budget=budget, category="materials", description="Plan", amount=Decimal("100000.00")
    )
    supplier = Party.objects.create(code="SUP-P9", legal_name="Supplier", is_supplier=True)
    item = CatalogueItem.objects.create(code="ITEM-P9", name="Steel", kind="product")
    destination = Destination.objects.create(kind="project", project=project)
    request = PurchaseRequest.objects.create(
        number="PR-P9-1", requester=owner, destination=destination, status="approved"
    )
    order = PurchaseOrder.objects.create(
        number="PO-P9-1",
        supplier=supplier,
        request=request,
        destination=destination,
        status=PurchaseOrder.Status.ISSUED,
    )
    PurchaseOrderLine.objects.create(
        order=order, item=item, quantity=Decimal("10"), unit_price=Decimal("1000")
    )
    SupplierInvoice.objects.create(
        number="SI-P9-1",
        supplier_invoice_number="INV-P9-1",
        supplier=supplier,
        project=project,
        purchase_order=order,
        invoice_date=date(2026, 3, 2),
        status=SupplierInvoice.Status.APPROVED,
        subtotal=Decimal("2000"),
        total=Decimal("2000"),
    )
    warehouse = Warehouse.objects.create(code="WH-P9", name="Project store")
    StockMovement.objects.create(
        number="SM-P9-1",
        movement_type=StockMovement.Type.PROJECT_ISSUE,
        item=item,
        warehouse=warehouse,
        quantity=Decimal("-2"),
        unit_cost=Decimal("1000"),
        value_delta=Decimal("-2000"),
        project=project,
        movement_date=date(2026, 3, 3),
    )
    # A project-site transfer is not a consumed cost and must be ignored.
    StockMovement.objects.create(
        number="SM-P9-2",
        movement_type=StockMovement.Type.TRANSFER_OUT,
        item=item,
        warehouse=warehouse,
        quantity=Decimal("-5"),
        unit_cost=Decimal("1000"),
        value_delta=Decimal("-5000"),
        project=project,
        movement_date=date(2026, 3, 4),
    )
    ProjectCost.objects.create(
        project=project,
        cost_date=date(2026, 3, 5),
        category="labour",
        description="Site labour",
        amount=Decimal("3000"),
        status=ProjectCost.Status.APPROVED,
    )

    response = auth_client.get(f"/api/v1/projects/{project.pk}/cost_summary/")

    assert response.status_code == 200, response.content
    body = response.json()
    assert Decimal(body["actual_total"]) == Decimal("7000")
    assert Decimal(body["committed_total"]) == Decimal("10000")
    assert Decimal(body["open_commitment"]) == Decimal("8000")
    assert Decimal(body["available_budget"]) == Decimal("85000")
    assert Decimal(body["project_material_issues"]) == Decimal("2000")
    assert Decimal(body["direct_costs"]) == Decimal("3000")


def test_project_profitability_labels_unconfigured_revenue(auth_client):
    project = make_project()
    response = auth_client.get(f"/api/v1/projects/{project.pk}/profitability/")
    assert response.status_code == 200, response.content
    assert response.json()["revenue_recognised"] == "0.00"
    assert "approved accounting policy" in response.json()["revenue_recognition_note"]


def test_project_dashboard_lists_budget_actual_and_commitments(auth_client):
    project = make_project()
    user = User.objects.get(email="staff@example.com")
    grant(user, "view_project")
    auth_client.force_authenticate(user=user)
    response = auth_client.get("/api/v1/project-dashboard/")
    assert response.status_code == 200, response.content
    assert response.json()["count"] == 1
    row = response.json()["results"][0]
    assert row["code"] == project.code
    assert "actual_total" in row
