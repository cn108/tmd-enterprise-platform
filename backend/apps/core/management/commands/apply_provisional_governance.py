from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounting.models import AccountRole, PostingRule, PostingRuleLine
from apps.core.models import (
    ApprovalPolicy,
    NumberingScheme,
    PolicyDecision,
    create_audit_event,
)
from apps.core.role_matrix import ROLE_NAMES, apply_matrix
from apps.inventory.models import InventoryPolicy
from apps.invoicing.models import InvoiceSettings

EFFECTIVE = date(2026, 11, 12)
FIVE_MILLION = Decimal("5000000.00")

ACCOUNT_ROLES = {
    "AR_CONTROL": "Trade receivables control",
    "AP_CONTROL": "Trade payables control",
    "INVENTORY": "Inventory",
    "GRNI": "Goods received not invoiced",
    "PROJECT_COST": "Project cost / work in progress",
    "COST_OF_SALES": "Cost of sales",
    "REVENUE": "Revenue",
    "OUTPUT_TAX": "Output VAT",
    "INPUT_TAX": "Input VAT",
    "BANK": "Bank",
    "CASH": "Cash",
    "CUSTOMER_ADVANCES": "Customer advances",
    "SUPPLIER_ADVANCES": "Supplier advances",
    "BANK_FEES": "Bank fees",
    "FX_GAIN_LOSS": "Foreign-exchange gain or loss",
    "STOCK_ADJUSTMENT": "Stock adjustment / write-off",
    "SUSPENSE": "Suspense (temporary only)",
    "RETAINED_EARNINGS": "Retained earnings",
    "OPENING_BALANCE_EQUITY": "Opening balance equity",
}

POSTING_RULES = (
    (
        "e02_grn_accrual",
        "E-02",
        "Goods received before supplier invoice",
        (("INVENTORY", "debit"), ("GRNI", "credit")),
    ),
    (
        "e04_project_issue",
        "E-04",
        "Stock issued to a project",
        (("PROJECT_COST", "debit"), ("INVENTORY", "credit")),
    ),
    (
        "e16_stock_loss",
        "E16_LOSS",
        "Stock loss, damage or negative count variance",
        (("STOCK_ADJUSTMENT", "debit"), ("INVENTORY", "credit")),
    ),
    (
        "e16_stock_gain",
        "E16_GAIN",
        "Stock gain or positive count variance",
        (("INVENTORY", "debit"), ("STOCK_ADJUSTMENT", "credit")),
    ),
)

DECISIONS = (
    ("D-03", "Nine-role permission matrix", "role matrix", {"roles": list(ROLE_NAMES)}),
    (
        "D-04",
        "₦5,000,000 provisional approval threshold",
        "approval bands",
        {
            "threshold": "5000000.00",
            "below": "one independent approval",
            "at_or_above": "two independent approvals",
        },
    ),
    (
        "D-05",
        "Provisional chart-of-accounts roles",
        "account-role mappings",
        {"account_roles": list(ACCOUNT_ROLES), "accounts_seeded": False},
    ),
    (
        "D-06",
        "Weighted average for ordinary stock; specific identification for traceable items",
        "valuation policy",
        {"ordinary": "weighted_average", "traceable": "specific_identification"},
    ),
    (
        "P-04",
        "Monthly accounting periods with controlled closure",
        "period policy",
        {"period": "monthly", "closure": "controlled", "reopen": "permission and reason"},
    ),
    (
        "P-06",
        "GRNI accrual accounting",
        "GRNI",
        {"policy": "accrual", "roles": ["INVENTORY", "GRNI"]},
    ),
    (
        "E-02",
        "Goods received before invoice",
        "financial event",
        {"debit": "INVENTORY", "credit": "GRNI", "status": "awaiting mappings"},
    ),
    (
        "E-04",
        "Stock issued to a project",
        "financial event",
        {"debit": "PROJECT_COST", "credit": "INVENTORY", "status": "awaiting mappings"},
    ),
    (
        "E-16",
        "Stock adjustment, count or damage",
        "financial event",
        {
            "loss": {"debit": "STOCK_ADJUSTMENT", "credit": "INVENTORY"},
            "gain": {"debit": "INVENTORY", "credit": "STOCK_ADJUSTMENT"},
            "status": "awaiting mappings",
        },
    ),
    (
        "E-21",
        "Opening balances",
        "financial event",
        {"path": "opening balance document", "accounts_seeded": False},
    ),
    (
        "E-22",
        "Period reopen adjustment",
        "financial event",
        {"path": "controlled reopen plus reasoned adjustment journal"},
    ),
    (
        "TAX-01",
        "Nigerian VAT, WHT, Tax ID and NRS configuration",
        "tax",
        {"rate_seeded": False, "nrs_seeded": False, "review_required": True},
    ),
    (
        "AUD-01",
        "Immutable journals, stock movements and audit trail",
        "controls",
        {"journal_trigger": True, "stock_movement_trigger": True, "audit_trigger": True},
    ),
)


class Command(BaseCommand):
    help = "Apply the provisional governance decisions. Idempotent; seeds no accounts or rates."

    @transaction.atomic
    def handle(self, *args, **options):
        matrix = apply_matrix()

        for code, title, summary, configuration in DECISIONS:
            PolicyDecision.objects.update_or_create(
                code=code,
                version="1.0-provisional",
                defaults={
                    "title": title,
                    "status": PolicyDecision.Status.PROVISIONAL,
                    "effective_from": EFFECTIVE,
                    "review_date": date(2027, 2, 28),
                    "owner": "Management / Accountant",
                    "summary": summary,
                    "configuration": configuration,
                    "notes": (
                        "Provisional policy. Not a verified historical record; production "
                        "posting requires Finance Controller review."
                    ),
                },
            )

        for code, name in ACCOUNT_ROLES.items():
            AccountRole.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": "Approved account role; map to a real account.",
                },
            )

        bands = (
            ("PO-STD-1", "purchase_order", "0", FIVE_MILLION, 1),
            ("PO-HIGH-1", "purchase_order", FIVE_MILLION, None, 2),
            ("BUDGET-STD-1", "project_budget", "0", FIVE_MILLION, 1),
            ("BUDGET-HIGH-1", "project_budget", FIVE_MILLION, None, 2),
            ("PR-STD-1", "purchase_request", "0", None, 1),
            ("SI-STD-1", "supplier_invoice", "0", FIVE_MILLION, 1),
            ("SI-HIGH-1", "supplier_invoice", FIVE_MILLION, None, 2),
            ("PAY-STD-1", "payment", "0", FIVE_MILLION, 1),
            ("PAY-HIGH-1", "payment", FIVE_MILLION, None, 2),
            ("CI-STD-1", "customer_invoice", "0", FIVE_MILLION, 1),
            ("CI-HIGH-1", "customer_invoice", FIVE_MILLION, None, 2),
            ("NOTE-STD-1", "invoice_note", "0", FIVE_MILLION, 1),
            ("NOTE-HIGH-1", "invoice_note", FIVE_MILLION, None, 2),
        )
        for code, document_type, minimum, maximum, required in bands:
            ApprovalPolicy.objects.update_or_create(
                code=code,
                defaults={
                    "document_type": document_type,
                    "version": "1",
                    "min_amount": Decimal(minimum),
                    "max_amount": maximum,
                    "required_approvals": required,
                    "effective_from": EFFECTIVE,
                    "is_active": True,
                    "notes": "Provisional ₦5,000,000 threshold; requires review.",
                },
            )

        roles = {role.code: role for role in AccountRole.objects.all()}
        for code, event_type, name, lines in POSTING_RULES:
            rule, _ = PostingRule.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": "Provisional role-based rule; requires mapped accounts.",
                    "event_type": event_type,
                    "is_active": True,
                },
            )
            rule.lines.all().delete()
            for index, (role_code, direction) in enumerate(lines, start=1):
                PostingRuleLine.objects.create(
                    rule=rule,
                    line_number=index,
                    account_role=roles[role_code],
                    direction=direction,
                    amount_key="event_amount",
                )

        inventory = InventoryPolicy.load()
        if not inventory.valuation_method:
            inventory.valuation_method = InventoryPolicy.Method.WEIGHTED_AVERAGE
            inventory.note = (
                "Provisional: weighted average for ordinary stock; items tracked by batch "
                "or serial use specific identification. Not reviewed by an accountant."
            )
            inventory.save(update_fields=["valuation_method", "note", "updated_at"])

        NumberingScheme.objects.get_or_create(
            document_type="customer_invoice",
            defaults={
                "prefix": "INV",
                "padding": 6,
                "reset_yearly": True,
                "review_status": "provisional",
                "notes": "Provisional format; invoice issuance is not implemented in Phase 6.",
            },
        )

        InvoiceSettings.load()

        create_audit_event(
            actor=None,
            action="governance.provisional_applied",
            entity_type="core.governance",
            entity_id="1.0-provisional",
            after={"effective_from": EFFECTIVE.isoformat(), "roles": list(ROLE_NAMES)},
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Applied provisional governance: "
                f"{matrix['roles_created']} roles created, {matrix['roles_updated']} updated; "
                f"{len(ACCOUNT_ROLES)} account roles; {len(POSTING_RULES)} posting rules; "
                f"{len(bands)} approval bands. No accounts, tax rates or balances were seeded."
            )
        )
