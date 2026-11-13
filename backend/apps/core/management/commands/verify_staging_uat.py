"""Reconcile the synthetic staging ledger, documents, stock and bank."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.accounting.models import Account, AccountingPeriod, JournalEntry, JournalLine
from apps.accounting.services import financial_statements, general_ledger, trial_balance
from apps.banking.models import BankStatement, Reconciliation
from apps.inventory.services import valuation_rows
from apps.invoicing.models import CustomerInvoice, SupplierInvoice, SupplierPayment
from apps.procurement.models import PurchaseOrder

ZERO = Decimal("0.00")
STAGING_DB = "tmd_staging"


def money(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(Decimal("0.01"))


class Command(BaseCommand):
    help = "Reconcile staging journals, control accounts, stock and bank evidence."

    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != STAGING_DB:
            raise CommandError(f"This command only runs against {STAGING_DB}.")

        period = AccountingPeriod.objects.get(name="November 2026 (UAT)")
        trial = trial_balance(period=period)
        statements = financial_statements(start=date(2026, 11, 1), end=date(2026, 11, 30))
        valuation = valuation_rows()
        ap_account = Account.objects.get(code="2000-STG")
        ar_account = Account.objects.get(code="1100-STG")
        inventory_account = Account.objects.get(code="1200-STG")
        bank_account = Account.objects.get(code="1000-STG")
        ap_ledger = -general_ledger(ap_account)["closing_balance"]
        ar_ledger = general_ledger(ar_account)["closing_balance"]
        inventory_ledger = general_ledger(inventory_account)["closing_balance"]
        bank_ledger = general_ledger(bank_account)["closing_balance"]
        supplier_invoice = SupplierInvoice.objects.get()
        customer_invoice = CustomerInvoice.objects.get()
        statement = BankStatement.objects.get()
        reconciliation = Reconciliation.objects.get()
        payment = SupplierPayment.objects.get()
        po = PurchaseOrder.objects.get()

        checks = {
            "trial_balance_balanced": trial["balanced"]
            and money(trial["total_debit"]) == money(trial["total_credit"]),
            "balance_sheet_balanced": statements["balance_sheet"]["balanced"],
            "ap_ledger_matches_invoice": abs(ap_ledger - money(supplier_invoice.balance))
            < Decimal("0.01"),
            "ar_ledger_matches_invoice": abs(ar_ledger - money(customer_invoice.balance))
            < Decimal("0.01"),
            "inventory_ledger_matches_valuation": abs(
                inventory_ledger - money(valuation["total_value"])
            )
            < Decimal("0.01"),
            "bank_ledger_matches_statement": abs(bank_ledger - money(statement.closing_balance))
            < Decimal("0.01"),
            "bank_reconciliation_approved": reconciliation.status == Reconciliation.Status.APPROVED,
            "po_partially_received": po.status == PurchaseOrder.Status.PARTIALLY_RECEIVED,
            "payment_recorded_not_executed": payment.status == SupplierPayment.Status.RECORDED
            and payment.execution_status == SupplierPayment.ExecutionStatus.RECORDED,
            "posted_journals_immutable_source": set(
                JournalEntry.objects.values_list("status", flat=True)
            )
            == {JournalEntry.Status.POSTED},
            "october_period_closed": AccountingPeriod.objects.get(name="October 2026 (UAT)").status
            == AccountingPeriod.Status.CLOSED,
        }
        payload = {
            "database": connection.settings_dict["NAME"],
            "generated_for": "TICO MCDON UAT staging (synthetic)",
            "checks": checks,
            "all_passed": all(checks.values()),
            "trial_balance": {
                "total_debit": str(trial["total_debit"]),
                "total_credit": str(trial["total_credit"]),
                "rows": len(trial["rows"]),
            },
            "income_statement": statements["income_statement"],
            "balance_sheet": statements["balance_sheet"],
            "control_reconciliation": {
                "ap_ledger": str(ap_ledger),
                "supplier_invoice_balance": str(supplier_invoice.balance),
                "ar_ledger": str(ar_ledger),
                "customer_invoice_balance": str(customer_invoice.balance),
                "inventory_ledger": str(inventory_ledger),
                "inventory_valuation": str(valuation["total_value"]),
                "bank_ledger": str(bank_ledger),
                "bank_statement_closing": str(statement.closing_balance),
            },
            "documents": {
                "purchase_order": po.number,
                "purchase_order_status": po.status,
                "supplier_invoice": supplier_invoice.number,
                "customer_invoice": customer_invoice.number,
                "payment": payment.number,
                "reconciliation": reconciliation.number,
                "journal_count": JournalEntry.objects.count(),
                "journal_line_count": JournalLine.objects.count(),
            },
            "stock": {
                "method": valuation["method"],
                "total_quantity": str(valuation["total_quantity"]),
                "total_value": str(valuation["total_value"]),
            },
            "bank_statement": {
                "number": statement.number,
                "opening": str(statement.opening_balance),
                "closing": str(statement.closing_balance),
                "lines": statement.lines.count(),
            },
        }

        evidence = Path(settings.BASE_DIR).parent / "docs" / "reports" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "staging-reconciliation.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Synthetic staging reconciliation",
            "",
            f"Database: `{payload['database']}`",
            f"All checks passed: **{payload['all_passed']}**",
            "",
            "| Check | Result |",
            "| --- | --- |",
        ]
        for name, result in checks.items():
            lines.append(f"| {name} | {'PASS' if result else 'FAIL'} |")
        lines += [
            "",
            "| Control | Ledger | Document / stock / bank |",
            "| --- | ---: | ---: |",
            (f"| Accounts payable | {ap_ledger} | {money(supplier_invoice.balance)} |"),
            f"| Accounts receivable | {ar_ledger} | {money(customer_invoice.balance)} |",
            f"| Inventory | {inventory_ledger} | {money(valuation['total_value'])} |",
            f"| Bank | {bank_ledger} | {money(statement.closing_balance)} |",
            "",
            f"Trial balance: debit {trial['total_debit']} = credit {trial['total_credit']}",
            "",
            f"November net result: {statements['income_statement']['net_result']}",
            "",
            f"PO status: `{po.status}`; supplier invoice balance: "
            f"`{supplier_invoice.balance}`; bank reconciliation: "
            f"`{reconciliation.status}`.",
        ]
        (evidence / "staging-reconciliation.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        self.stdout.write(json.dumps(payload["checks"], indent=2))
        self.stdout.write(self.style.SUCCESS(f"All checks passed: {payload['all_passed']}"))
        if not payload["all_passed"]:
            raise CommandError("Reconciliation failed; see docs/reports/evidence.")
