"""Verify the eight seeded end-to-end workflows and their control outcomes."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.accounting.models import AccountingPeriod, JournalEntry
from apps.accounting.services import financial_statements, trial_balance
from apps.banking.models import Reconciliation
from apps.inventory.models import StockIssue, StockReceipt
from apps.invoicing.models import CustomerInvoice, SupplierInvoice, SupplierPayment
from apps.leasing.models import (
    EquipmentInspection,
    EquipmentMaintenance,
    EquipmentMovement,
    RentalAgreement,
)
from apps.procurement.models import GoodsReceiptNote, PurchaseOrder, PurchaseRequest
from apps.projects.models import Project, ProjectBudget, ProjectCost
from apps.reporting.services import report_payload
from apps.services.models import ServiceContract, WorkOrder

STAGING_DB = "tmd_staging"


class Command(BaseCommand):
    help = "Verify procurement, inventory, finance, projects, services and leasing workflows."

    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != STAGING_DB:
            raise CommandError(f"This command only runs against {STAGING_DB}.")
        pr = PurchaseRequest.objects.get()
        po = PurchaseOrder.objects.get()
        grn = GoodsReceiptNote.objects.get()
        receipt = StockReceipt.objects.get()
        issue = StockIssue.objects.get()
        supplier_invoice = SupplierInvoice.objects.get()
        customer_invoice = CustomerInvoice.objects.get()
        payment = SupplierPayment.objects.get()
        reconciliation = Reconciliation.objects.get()
        project = Project.objects.get()
        budget = ProjectBudget.objects.get()
        costs = list(ProjectCost.objects.all())
        contract = ServiceContract.objects.get()
        work_order = WorkOrder.objects.get()
        rental = RentalAgreement.objects.get()
        movements = EquipmentMovement.objects.filter(agreement=rental)
        inspection = EquipmentInspection.objects.get()
        maintenance = EquipmentMaintenance.objects.get()
        trial = trial_balance(period=AccountingPeriod.objects.get(name="November 2026 (UAT)"))
        statements = financial_statements(start=date(2026, 11, 1), end=date(2026, 11, 30))
        damaged = sum((line.quantity_damaged for line in grn.lines.all()), start=0)
        rejected = sum((line.quantity_rejected for line in grn.lines.all()), start=0)

        workflows = {
            "A_procurement_to_inventory": {
                "passed": pr.status == PurchaseRequest.Status.APPROVED
                and po.status == PurchaseOrder.Status.PARTIALLY_RECEIVED
                and receipt.lines.count() > 0,
                "evidence": {
                    "request": pr.number,
                    "order": po.number,
                    "goods_receipt": grn.number,
                    "receipt": receipt.number,
                },
            },
            "B_procurement_to_supplier_invoice": {
                "passed": supplier_invoice.status == SupplierInvoice.Status.APPROVED
                and supplier_invoice.match_status == SupplierInvoice.MatchStatus.MATCHED,
                "evidence": {
                    "invoice": supplier_invoice.number,
                    "match_status": supplier_invoice.match_status,
                    "total": str(supplier_invoice.total),
                },
            },
            "C_customer_delivery_to_receivables": {
                "passed": customer_invoice.status == CustomerInvoice.Status.APPROVED
                and customer_invoice.balance > 0,
                "evidence": {
                    "invoice": customer_invoice.number,
                    "balance": str(customer_invoice.balance),
                },
            },
            "D_payment_to_bank_reconciliation": {
                "passed": payment.status == SupplierPayment.Status.RECORDED
                and payment.execution_status == SupplierPayment.ExecutionStatus.RECORDED
                and reconciliation.status == Reconciliation.Status.APPROVED,
                "evidence": {
                    "payment": payment.number,
                    "payment_status": payment.status,
                    "execution": payment.execution_status,
                    "reconciliation": reconciliation.number,
                },
            },
            "E_inventory_allocation_to_project_cost": {
                "passed": issue.project_id == project.pk
                and any(line.value == 240000 for line in issue.lines.all()),
                "evidence": {
                    "issue": issue.number,
                    "project": project.code,
                    "issue_value": str(sum((line.value for line in issue.lines.all()), start=0)),
                },
            },
            "F_project_budget_to_expenditure": {
                "passed": budget.status == ProjectBudget.Status.APPROVED
                and report_payload("projects", date(2026, 1, 1), date(2026, 12, 31))["projects"][0][
                    "actual_total"
                ]
                == "540000.00",
                "evidence": {
                    "budget": budget.version,
                    "budget_status": budget.status,
                    "actual_cost": str(sum((cost.amount for cost in costs), start=0)),
                },
            },
            "G_equipment_rental_lifecycle": {
                "passed": movements.count() >= 2
                and inspection.pk is not None
                and rental.status in {RentalAgreement.Status.CLOSED, RentalAgreement.Status.ACTIVE}
                and maintenance.status
                in {EquipmentMaintenance.Status.PLANNED, EquipmentMaintenance.Status.COMPLETED},
                "evidence": {
                    "agreement": rental.number,
                    "agreement_status": rental.status,
                    "movements": movements.count(),
                    "inspection_damage": inspection.damage_found,
                    "maintenance": maintenance.status,
                },
            },
            "H_accounting_to_management_reporting": {
                "passed": trial["balanced"]
                and statements["income_statement"]["net_result"] == 2485000
                and JournalEntry.objects.count() == 11,
                "evidence": {
                    "journals": JournalEntry.objects.count(),
                    "net_result": str(statements["income_statement"]["net_result"]),
                    "trial_balanced": trial["balanced"],
                },
            },
            "partial_and_damaged_delivery_handled": {
                "passed": damaged == 1
                and rejected == 0
                and bool(grn.lines.first().rejection_reason),
                "evidence": {
                    "damaged": str(damaged),
                    "rejected": str(rejected),
                    "reason": grn.lines.first().rejection_reason,
                },
            },
            "service_contract_to_customer_acceptance": {
                "passed": contract.status == ServiceContract.Status.ACTIVE
                and work_order.status == WorkOrder.Status.ACCEPTED,
                "evidence": {
                    "contract": contract.number,
                    "work_order": work_order.number,
                    "status": work_order.status,
                },
            },
        }
        failures = [name for name, result in workflows.items() if not result["passed"]]
        payload = {
            "database": connection.settings_dict["NAME"],
            "workflows": workflows,
            "failures": failures,
            "all_passed": not failures,
        }
        evidence = Path(settings.BASE_DIR).parent / "docs" / "reports" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "workflow-checks.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# End-to-end workflow evidence",
            "",
            f"All workflows passed: **{payload['all_passed']}**",
            "",
            "| Workflow | Result | Evidence |",
            "| --- | --- | --- |",
        ]
        for name, result in workflows.items():
            detail = "; ".join(f"{key}={value}" for key, value in result["evidence"].items())
            lines.append(f"| {name} | {'PASS' if result['passed'] else 'FAIL'} | {detail} |")
        (evidence / "workflow-checks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(json.dumps(workflows, indent=2, default=str))
        if failures:
            raise CommandError(f"Workflow verification failed: {', '.join(failures)}")
        self.stdout.write(self.style.SUCCESS("All eight workflows passed."))
