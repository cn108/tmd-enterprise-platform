"""Project cost, commitment and profitability calculations.

Procurement and inventory remain the source documents for their own costs. This
module combines them for reporting; it does not copy a purchase order, receipt
or warehouse transfer into an actual cost. A purchase order is an open
commitment until an approved supplier invoice is recorded against it.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.projects.models import Project, ProjectBudget, ProjectCost

ZERO = Decimal("0")


def _approved_budget(project: Project) -> ProjectBudget | None:
    return project.budgets.filter(status=ProjectBudget.Status.APPROVED).order_by("-version").first()


def _money(value) -> Decimal:
    return Decimal(str(value or ZERO))


def commitment_data(project: Project) -> dict:
    from apps.invoicing.models import SupplierInvoice
    from apps.procurement.models import PurchaseOrder

    orders = (
        PurchaseOrder.objects.filter(
            destination__kind="project",
            destination__project=project,
            status__in=[
                PurchaseOrder.Status.APPROVED,
                PurchaseOrder.Status.ISSUED,
                PurchaseOrder.Status.PARTIALLY_RECEIVED,
                PurchaseOrder.Status.RECEIVED,
            ],
        )
        .prefetch_related("lines")
        .select_related("supplier")
    )
    invoices = SupplierInvoice.objects.filter(
        project=project,
        status=SupplierInvoice.Status.APPROVED,
        purchase_order__isnull=False,
    )
    invoiced_by_order: dict[int, Decimal] = {}
    for invoice in invoices:
        invoiced_by_order[invoice.purchase_order_id] = invoiced_by_order.get(
            invoice.purchase_order_id, ZERO
        ) + _money(invoice.subtotal)
    total = ZERO
    open_total = ZERO
    rows = []
    for order in orders:
        value = _money(order.total_value)
        invoiced = invoiced_by_order.get(order.pk, ZERO)
        open_value = max(value - invoiced, ZERO)
        total += value
        open_total += open_value
        rows.append(
            {
                "id": order.pk,
                "number": order.number,
                "supplier": order.supplier.legal_name,
                "status": order.status,
                "order_value": str(value),
                "invoiced_value": str(invoiced),
                "open_commitment": str(open_value),
            }
        )
    return {"total": total, "open": open_total, "rows": rows}


def material_issue_data(project: Project) -> dict:
    from apps.inventory.models import StockMovement

    movements = StockMovement.objects.filter(
        project=project, movement_type=StockMovement.Type.PROJECT_ISSUE
    ).select_related("item", "warehouse", "issue_line")
    total = ZERO
    rows = []
    for movement in movements:
        value = (
            abs(_money(movement.value_delta))
            if movement.value_delta is not None
            else abs(_money(movement.unit_cost) * _money(movement.quantity))
        )
        total += value
        rows.append(
            {
                "id": movement.pk,
                "number": movement.number,
                "movement_date": movement.movement_date.isoformat(),
                "item": movement.item.code,
                "item_name": movement.item.name,
                "warehouse": movement.warehouse.code,
                "quantity": str(movement.quantity),
                "value": str(value),
                "reason": movement.reason,
            }
        )
    return {"total": total, "rows": rows}


def direct_cost_data(project: Project) -> dict:
    costs = ProjectCost.objects.filter(project=project, status=ProjectCost.Status.APPROVED)
    total = ZERO
    by_category: dict[str, Decimal] = {}
    rows = []
    for cost in costs.select_related("supplier"):
        amount = _money(cost.amount)
        total += amount
        by_category[cost.category] = by_category.get(cost.category, ZERO) + amount
        rows.append(
            {
                "id": cost.pk,
                "cost_date": cost.cost_date.isoformat(),
                "category": cost.category,
                "description": cost.description,
                "supplier": cost.supplier.legal_name if cost.supplier_id else "",
                "amount": str(amount),
                "reference": cost.reference,
                "source_type": cost.source_type,
            }
        )
    return {"total": total, "by_category": by_category, "rows": rows}


def supplier_invoice_data(project: Project) -> dict:
    from apps.invoicing.models import SupplierInvoice

    invoices = SupplierInvoice.objects.filter(
        project=project, status=SupplierInvoice.Status.APPROVED
    ).select_related("supplier", "purchase_order")
    total = _money(invoices.aggregate(total=Sum("subtotal"))["total"])
    rows = [
        {
            "id": invoice.pk,
            "number": invoice.number,
            "supplier_invoice_number": invoice.supplier_invoice_number,
            "supplier": invoice.supplier.legal_name,
            "invoice_date": invoice.invoice_date.isoformat(),
            "subtotal": str(invoice.subtotal),
            "purchase_order": invoice.purchase_order.number if invoice.purchase_order_id else "",
        }
        for invoice in invoices
    ]
    return {"total": total, "rows": rows}


def cost_summary(project: Project) -> dict:
    budget = _approved_budget(project)
    budget_total = _money(budget.total_value) if budget else ZERO
    invoices = supplier_invoice_data(project)
    issues = material_issue_data(project)
    direct = direct_cost_data(project)
    commitments = commitment_data(project)
    actual = invoices["total"] + issues["total"] + direct["total"]
    available = budget_total - actual - commitments["open"] if budget else None
    by_category = {
        "supplier_invoices": invoices["total"],
        "project_material_issues": issues["total"],
        **direct["by_category"],
    }
    return {
        "project": {
            "id": project.pk,
            "code": project.code,
            "name": project.name,
            "status": project.status,
            "currency": budget.currency if budget else "NGN",
        },
        "budget": {
            "id": budget.pk if budget else None,
            "version": budget.version if budget else None,
            "total": str(budget_total),
            "approved_at": budget.approved_at.isoformat() if budget and budget.approved_at else "",
        },
        "actual_total": str(actual),
        "committed_total": str(commitments["total"]),
        "open_commitment": str(commitments["open"]),
        "available_budget": str(available) if available is not None else "",
        "supplier_invoices": str(invoices["total"]),
        "project_material_issues": str(issues["total"]),
        "direct_costs": str(direct["total"]),
        "by_category": {key: str(value) for key, value in by_category.items()},
        "commitments": commitments["rows"],
        "material_issues": issues["rows"],
        "direct_cost_rows": direct["rows"],
        "supplier_invoice_rows": invoices["rows"],
        "note": (
            "Purchase orders are commitments. Goods receipts and project-site transfers are not "
            "consumed cost. Actual cost is approved supplier invoices, project stock issues and "
            "approved direct project costs."
        ),
    }


def profitability(project: Project) -> dict:
    contracts = project.contracts.filter(is_active=True)
    contract_value = _money(contracts.aggregate(total=Sum("value"))["total"])
    costs = cost_summary(project)
    actual = _money(costs["actual_total"])
    open_commitment = _money(costs["open_commitment"])
    estimated_cost = actual + open_commitment
    margin = contract_value - estimated_cost
    margin_percent = (margin / contract_value * 100) if contract_value else None
    return {
        "project": costs["project"],
        "contract_value": str(contract_value),
        "actual_cost": str(actual),
        "open_commitments": str(open_commitment),
        "estimated_cost_to_complete": str(estimated_cost),
        "estimated_margin": str(margin),
        "estimated_margin_percent": f"{margin_percent:.2f}" if margin_percent is not None else "",
        "revenue_recognised": "0.00",
        "revenue_recognition_note": (
            "Revenue recognition is not calculated. It remains governed by the approved accounting "
            "policy and is disabled until that policy is authorised."
        ),
        "currency": costs["project"]["currency"],
        "budget_variance": (
            str(_money(costs["budget"]["total"]) - actual) if costs["budget"]["id"] else ""
        ),
    }


def dashboard_rows() -> list[dict]:
    rows = []
    for project in Project.objects.all():
        summary = cost_summary(project)
        rows.append(
            {
                "id": project.pk,
                "code": project.code,
                "name": project.name,
                "status": project.status,
                "start_date": project.start_date.isoformat() if project.start_date else "",
                "end_date": project.end_date.isoformat() if project.end_date else "",
                "budget_version": summary["budget"]["version"] or "",
                "budget_total": summary["budget"]["total"],
                "actual_total": summary["actual_total"],
                "committed_total": summary["committed_total"],
                "open_commitment": summary["open_commitment"],
                "available_budget": summary["available_budget"],
            }
        )
    return rows
