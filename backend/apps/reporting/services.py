"""Reporting services.

Formal financial statements are calculated only from posted journal lines via
``apps.accounting.services``. Operational reports read the source documents and
say which statuses they include; they never describe a purchase order, draft
invoice or unposted event as actual accounting expenditure.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountingSettings,
    AccountRoleMapping,
    FinancialEvent,
    JournalEntry,
    JournalLine,
)
from apps.accounting.services import (
    Conflict,
    financial_statements,
    general_ledger,
    trial_balance,
)
from apps.banking.models import (
    BankAccount,
    BankStatement,
    CashAccount,
    Reconciliation,
)
from apps.core.models import TaxConfiguration
from apps.inventory.models import (
    InventoryPolicy,
    StockDamageLine,
    StockLayer,
    StockMovement,
)
from apps.inventory.services import PolicyNotConfigured, reorder_alerts, valuation_rows
from apps.invoicing.models import (
    CustomerInvoice,
    InvoiceNote,
    SupplierInvoice,
)
from apps.leasing.models import Equipment, EquipmentMaintenance, RentalAgreement
from apps.leasing.workflows import utilisation_rows
from apps.procurement.models import (
    DeliverySchedule,
    GoodsReceiptLine,
    PurchaseOrder,
    SupplierQuoteLine,
)
from apps.projects.costing import dashboard_rows, profitability
from apps.projects.models import Project, ProjectCost
from apps.services.models import WorkOrder

ZERO = Decimal("0")
CENT = Decimal("0.01")
QTY = Decimal("0.0001")


def money(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(CENT)


def quantity(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(QTY)


def _iso(value) -> str:
    return value.isoformat() if value else ""


def _bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "Current"
    if days_overdue <= 30:
        return "1–30 days"
    if days_overdue <= 60:
        return "31–60 days"
    if days_overdue <= 90:
        return "61–90 days"
    return "Over 90 days"


def accounting_configuration() -> dict:
    accounts = Account.objects.all()
    total = accounts.count()
    approved = accounts.filter(approved_at__isnull=False, is_active=True).count()
    mappings = AccountRoleMapping.objects.filter(is_active=True)
    reviewed = AccountingSettings.load().posting_reviewed_at is not None
    method = InventoryPolicy.load().valuation_method
    bank_links = BankAccount.objects.filter(gl_account__isnull=False, is_active=True).count()
    warnings = []
    if total == 0:
        warnings.append("No chart of accounts exists. Formal statements cannot be prepared.")
    elif approved < total:
        warnings.append(
            f"{total - approved} account(s) are unapproved or inactive; statements include only "
            "posted journals, but the chart is not fully approved."
        )
    if mappings.filter(approved_at__isnull=True).exists():
        warnings.append("Some account-role mappings are awaiting approval.")
    if not method:
        warnings.append(
            "No inventory valuation method is configured; inventory values are unavailable."
        )
    if bank_links == 0:
        warnings.append(
            "No bank account is linked to a GL account; the cash flow statement and GL cash "
            "balances are unavailable. Recorded bank book balances are shown separately."
        )
    return {
        "chart_accounts": total,
        "approved_accounts": approved,
        "approved_role_mappings": mappings.filter(approved_at__isnull=False).count(),
        "pending_role_mappings": mappings.filter(approved_at__isnull=True).count(),
        "posting_reviewed": reviewed,
        "inventory_valuation_method": method or "",
        "bank_accounts_linked_to_gl": bank_links,
        "warnings": warnings,
        "complete": total > 0 and approved == total and not warnings,
    }


def _document_warnings() -> list[str]:
    items = []
    count = FinancialEvent.objects.filter(status__in=["pending", "failed"]).count()
    if count:
        items.append(
            f"{count} financial event(s) are pending or failed and are not "
            "included in posted results."
        )
    return items


def financial_report(start: date, end: date) -> dict:
    statements = financial_statements(start=start, end=end)
    income = statements["income_statement"]
    balance_sheet = statements["balance_sheet"]
    trial = trial_balance(as_of=end)
    configuration = accounting_configuration()
    cash = cash_flow(start, end)
    return {
        "source": "posted_journal_lines",
        "status": "actual_posted",
        "start": _iso(start),
        "end": _iso(end),
        "currency": "NGN",
        "income_statement": {key: _stringify(value) for key, value in income.items()},
        "balance_sheet": {key: _stringify(value) for key, value in balance_sheet.items()},
        "trial_balance_balanced": trial["balanced"],
        "total_debit": str(trial["total_debit"]),
        "total_credit": str(trial["total_credit"]),
        "cash_flow": cash,
        "warnings": configuration["warnings"] + _document_warnings() + cash.get("warnings", []),
        "complete": configuration["complete"] and trial["balanced"] and cash.get("complete", False),
        "configuration": configuration,
    }


def cash_flow(start: date, end: date) -> dict:
    accounts = (
        BankAccount.objects.filter(is_active=True, gl_account__isnull=False)
        .values_list("gl_account_id", flat=True)
        .distinct()
    )
    cash_ids = set(accounts)
    if not cash_ids:
        return {
            "available": False,
            "complete": False,
            "reason": "No active bank account is linked to a GL account.",
            "rows": [],
            "by_activity": [],
            "net_change": "0.00",
            "opening_cash": "0.00",
            "closing_cash": "0.00",
            "warnings": [],
            "unclassified_accounts": [],
        }
    role_by_account: dict[int, set[str]] = defaultdict(set)
    mappings = AccountRoleMapping.objects.filter(
        is_active=True,
        approved_at__isnull=False,
        effective_from__lte=end,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=end))
    for mapping in mappings.select_related("role"):
        role_by_account[mapping.account_id].add(mapping.role.code)

    posted = JournalLine.objects.filter(
        journal__status=JournalEntry.Status.POSTED,
        journal__journal_date__gte=start,
        journal__journal_date__lte=end,
    )
    journal_ids = posted.filter(account_id__in=cash_ids).values_list("journal_id", flat=True)
    lines = list(
        posted.filter(journal_id__in=journal_ids)
        .exclude(account_id__in=cash_ids)
        .select_related("journal", "account")
        .order_by("journal__journal_date", "journal_id", "line_number")
    )
    buckets: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    detail = []
    unclassified = set()
    for line in lines:
        # Counterpart movement in the direction of cash: a credit to income or a
        # liability is a cash inflow; a debit to an asset or expense is an outflow.
        amount = line.credit - line.debit
        account_type = line.account.account_type
        roles = role_by_account.get(line.account_id, set())
        if roles & {
            "AR_CONTROL",
            "AP_CONTROL",
            "INVENTORY",
            "GRNI",
            "PROJECT_COST",
            "COST_OF_SALES",
            "REVENUE",
            "OUTPUT_TAX",
            "INPUT_TAX",
            "CUSTOMER_ADVANCES",
            "SUPPLIER_ADVANCES",
            "BANK_FEES",
            "FX_GAIN_LOSS",
            "STOCK_ADJUSTMENT",
            "SUSPENSE",
        }:
            activity = "Operating"
        elif account_type in {Account.Type.INCOME, Account.Type.EXPENSE}:
            activity = "Operating"
        elif account_type == Account.Type.ASSET:
            # An unmapped asset cannot be distinguished between working-capital
            # (operating) and property/equipment (investing). Do not guess.
            activity = "Unclassified"
            unclassified.add(line.account.code)
        elif account_type == Account.Type.LIABILITY:
            # An unmapped liability could be trade payables (operating) or
            # borrowings (financing). Do not guess.
            activity = "Unclassified"
            unclassified.add(line.account.code)
        else:
            activity = "Financing"
        buckets[(activity, account_type)] += amount
        detail.append(
            {
                "journal_number": line.journal.number,
                "journal_date": _iso(line.journal.journal_date),
                "description": line.description or line.journal.description,
                "counterpart_account": line.account.code,
                "counterpart_name": line.account.name,
                "activity": activity,
                "amount": str(money(amount)),
            }
        )
    by_activity = [
        {"activity": activity, "account_type": account_type, "amount": str(money(amount))}
        for (activity, account_type), amount in sorted(buckets.items())
    ]
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in by_activity:
        totals[row["activity"]] += Decimal(row["amount"])
    net = sum(totals.values(), ZERO)
    opening_lines = JournalLine.objects.filter(
        journal__status=JournalEntry.Status.POSTED,
        journal__journal_date__lt=start,
        account_id__in=cash_ids,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    opening = money((opening_lines["debit"] or ZERO) - (opening_lines["credit"] or ZERO))
    warnings = (
        [
            "Cash flow activity is unclassified for account(s) "
            + ", ".join(sorted(unclassified))
            + ". An approved account-role mapping is required before this statement is complete."
        ]
        if unclassified
        else []
    )
    return {
        "available": True,
        "complete": not unclassified,
        "reason": "",
        "rows": detail,
        "by_activity": [
            {"activity": key, "amount": str(money(value))} for key, value in sorted(totals.items())
        ],
        "net_change": str(money(net)),
        "opening_cash": str(opening),
        "closing_cash": str(money(opening + net)),
        "warnings": warnings,
        "unclassified_accounts": sorted(unclassified),
        "method": (
            "Direct classification of posted counterparty lines using approved account-role "
            "mappings. Cash accounts are derived only from active bank accounts linked to a GL "
            "account; unmapped balance-sheet counterparts are reported as Unclassified."
        ),
    }


def journal_register(start: date, end: date) -> dict:
    journals = (
        JournalEntry.objects.filter(journal_date__gte=start, journal_date__lte=end)
        .select_related("period", "created_by", "approved_by", "posted_by")
        .order_by("journal_date", "number")
    )
    rows = []
    posted_count = 0
    posted_total = ZERO
    for journal in journals:
        if journal.status == JournalEntry.Status.POSTED:
            posted_count += 1
            posted_total += journal.total_debit
        rows.append(
            {
                "id": journal.pk,
                "number": journal.number,
                "journal_date": _iso(journal.journal_date),
                "period": journal.period.name,
                "description": journal.description,
                "source": journal.source_type,
                "status": journal.status,
                "total_debit": str(journal.total_debit),
                "total_credit": str(journal.total_credit),
                "created_by": journal.created_by.full_name if journal.created_by_id else "",
                "approved_by": journal.approved_by.full_name if journal.approved_by_id else "",
                "posted_by": journal.posted_by.full_name if journal.posted_by_id else "",
            }
        )
    return {
        "status": "posted_and_unposted_register",
        "note": "Only posted journals affect the financial statements.",
        "rows": rows,
        "posted_count": posted_count,
        "posted_total": str(money(posted_total)),
        "unposted_count": journals.exclude(status=JournalEntry.Status.POSTED).count(),
    }


def receivable_report(as_of: date) -> dict:
    invoices = CustomerInvoice.objects.filter(
        status=CustomerInvoice.Status.APPROVED, invoice_date__lte=as_of
    ).select_related("customer", "project")
    rows = []
    buckets: dict[str, Decimal] = defaultdict(lambda: ZERO)
    currency_buckets: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    total = ZERO
    for invoice in invoices:
        balance = money(getattr(invoice, "payment_due", invoice.balance))
        if balance <= ZERO:
            continue
        days = (as_of - invoice.due_date).days
        bucket = _bucket(days)
        buckets[bucket] += balance
        currency_buckets[invoice.currency][bucket] += balance
        total += balance
        rows.append(
            {
                "id": invoice.pk,
                "number": invoice.number,
                "customer": invoice.customer.legal_name,
                "project": invoice.project.code if invoice.project_id else "",
                "invoice_date": _iso(invoice.invoice_date),
                "due_date": _iso(invoice.due_date),
                "currency": invoice.currency,
                "total": str(invoice.total),
                "balance": str(balance),
                "days_overdue": max(days, 0),
                "bucket": bucket,
            }
        )
    return _ageing_payload(
        rows, buckets, total, as_of, "approved_customer_invoices", currency_buckets
    )


def payable_report(as_of: date) -> dict:
    invoices = SupplierInvoice.objects.filter(
        status=SupplierInvoice.Status.APPROVED, invoice_date__lte=as_of
    ).select_related("supplier", "project")
    rows = []
    buckets: dict[str, Decimal] = defaultdict(lambda: ZERO)
    currency_buckets: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    total = ZERO
    for invoice in invoices:
        balance = money(invoice.payment_due)
        if balance <= ZERO:
            continue
        days = (as_of - invoice.due_date).days
        bucket = _bucket(days)
        buckets[bucket] += balance
        currency_buckets[invoice.currency][bucket] += balance
        total += balance
        rows.append(
            {
                "id": invoice.pk,
                "number": invoice.number,
                "supplier_invoice_number": invoice.supplier_invoice_number,
                "supplier": invoice.supplier.legal_name,
                "project": invoice.project.code if invoice.project_id else "",
                "invoice_date": _iso(invoice.invoice_date),
                "due_date": _iso(invoice.due_date),
                "currency": invoice.currency,
                "total": str(invoice.total),
                "balance": str(balance),
                "days_overdue": max(days, 0),
                "bucket": bucket,
            }
        )
    return _ageing_payload(
        rows, buckets, total, as_of, "approved_supplier_invoices", currency_buckets
    )


def _ageing_payload(rows, buckets, total, as_of, source, currency_buckets) -> dict:
    order = ["Current", "1–30 days", "31–60 days", "61–90 days", "Over 90 days"]
    by_currency = []
    for code, values in sorted(currency_buckets.items()):
        currency_total = sum(values.values(), ZERO)
        by_currency.append(
            {
                "currency": code,
                "total": str(money(currency_total)),
                "overdue": str(
                    money(sum((value for key, value in values.items() if key != "Current"), ZERO))
                ),
                "buckets": [
                    {"bucket": name, "amount": str(money(values.get(name, ZERO)))} for name in order
                ],
            }
        )
    mixed = len(currency_buckets) > 1
    return {
        "as_of": _iso(as_of),
        "source": source,
        "currency": "MIXED" if mixed else (next(iter(currency_buckets), "NGN")),
        "mixed_currency": mixed,
        "rows": rows,
        # Totals in different currencies are not added together.
        "buckets": []
        if mixed
        else [{"bucket": name, "amount": str(money(buckets.get(name, ZERO)))} for name in order],
        "by_currency": by_currency,
        "total": "" if mixed else str(money(total)),
        "overdue": ""
        if mixed
        else str(money(sum((value for key, value in buckets.items() if key != "Current"), ZERO))),
    }


def procurement_report(start: date, end: date) -> dict:
    orders = PurchaseOrder.objects.filter(
        created_at__date__gte=start, created_at__date__lte=end
    ).select_related("supplier")
    # Django cannot multiply two aggregates; calculate order values in Python.
    status_totals: dict[str, dict] = {}
    total_committed = ZERO
    for order in orders.prefetch_related("lines"):
        if order.status in {
            PurchaseOrder.Status.APPROVED,
            PurchaseOrder.Status.ISSUED,
            PurchaseOrder.Status.PARTIALLY_RECEIVED,
            PurchaseOrder.Status.RECEIVED,
        }:
            total_committed += money(order.total_value)
        entry = status_totals.setdefault(
            order.status, {"status": order.status, "count": 0, "value": ZERO}
        )
        entry["count"] += 1
        entry["value"] += money(order.total_value)
    supplier_rows = []
    for supplier in orders.values_list("supplier_id", flat=True).distinct():
        supplier_orders = orders.filter(supplier_id=supplier)
        supplier = supplier_orders.first().supplier
        invoices = SupplierInvoice.objects.filter(
            supplier_id=supplier.pk,
            status=SupplierInvoice.Status.APPROVED,
            invoice_date__gte=start,
            invoice_date__lte=end,
        ).aggregate(total=Sum("subtotal"))["total"]
        supplier_rows.append(
            {
                "supplier_id": supplier.pk,
                "supplier": supplier.legal_name,
                "orders": supplier_orders.count(),
                "order_value": str(money(sum((o.total_value for o in supplier_orders), ZERO))),
                "approved_invoice_value": str(money(invoices)),
            }
        )
    schedules = (
        DeliverySchedule.objects.filter(
            due_date__lte=end,
            order_line__order__status__in=[
                PurchaseOrder.Status.APPROVED,
                PurchaseOrder.Status.ISSUED,
                PurchaseOrder.Status.PARTIALLY_RECEIVED,
            ],
        )
        .select_related("order_line", "order_line__order", "order_line__item")
        .order_by("due_date")
    )
    outstanding = []
    for schedule in schedules:
        remaining = quantity(schedule.quantity) - quantity(schedule.quantity_delivered)
        if remaining <= ZERO:
            continue
        outstanding.append(
            {
                "order": schedule.order_line.order.number,
                "supplier": schedule.order_line.order.supplier.legal_name,
                "item": schedule.order_line.item.code,
                "due_date": _iso(schedule.due_date),
                "ordered": str(quantity(schedule.quantity)),
                "delivered": str(quantity(schedule.quantity_delivered)),
                "outstanding": str(remaining),
                "overdue": schedule.due_date < timezone.localdate(),
            }
        )
    rejected = GoodsReceiptLine.objects.filter(
        receipt__received_at__gte=start, receipt__received_at__lte=end
    ).aggregate(rejected=Sum("quantity_rejected"), damaged=Sum("quantity_damaged"))
    leads = SupplierQuoteLine.objects.filter(
        quote__received_at__gte=start, quote__received_at__lte=end
    ).aggregate(average=Sum("lead_time_days") / Count("id"))
    procurement_invoices = SupplierInvoice.objects.filter(
        status=SupplierInvoice.Status.APPROVED,
        invoice_date__gte=start,
        invoice_date__lte=end,
    ).aggregate(total=Sum("subtotal"), count=Count("id"))
    return {
        "start": _iso(start),
        "end": _iso(end),
        "currency": "NGN",
        "status": "committed_and_document_actual",
        "note": (
            "Purchase order values are commitments, not expenses. Approved supplier invoice "
            "subtotals are recorded document values and may still await ledger posting."
        ),
        "purchase_orders": {
            "count": orders.count(),
            "by_status": [
                {
                    "status": key,
                    "count": value["count"],
                    "value": str(money(value["value"])),
                }
                for key, value in sorted(status_totals.items())
            ],
            "committed_value": str(money(total_committed)),
        },
        "suppliers": supplier_rows,
        "outstanding_deliveries": outstanding,
        "rejected_quantity": str(quantity(rejected["rejected"])),
        "damaged_quantity": str(quantity(rejected["damaged"])),
        "average_lead_time_days": round(float(leads["average"]), 1) if leads["average"] else None,
        "approved_invoice_value": str(money(procurement_invoices["total"])),
        "approved_invoice_count": procurement_invoices["count"],
    }


def inventory_report(start: date, end: date) -> dict:
    try:
        valuation = valuation_rows()
        valuation_available = True
        valuation_error = ""
    except PolicyNotConfigured as exc:
        valuation = {"method": "", "rows": [], "total_quantity": ZERO, "total_value": ZERO}
        valuation_available = False
        valuation_error = str(exc)
    movements = StockMovement.objects.filter(
        movement_date__gte=start, movement_date__lte=end
    ).select_related("item", "warehouse", "project")
    movement_rows = [
        {
            "number": row.number,
            "date": _iso(row.movement_date),
            "type": row.movement_type,
            "item": row.item.code,
            "warehouse": row.warehouse.code,
            "quantity": str(quantity(row.quantity)),
            "value": str(money(row.value_delta)),
            "project": row.project.code if row.project_id else "",
        }
        for row in movements.order_by("-movement_date", "-id")
    ]
    project_issues = movements.filter(movement_type=StockMovement.Type.PROJECT_ISSUE)
    project_rows = [
        {
            "number": row.number,
            "date": _iso(row.movement_date),
            "project": row.project.code if row.project_id else "",
            "item": row.item.code,
            "quantity": str(abs(quantity(row.quantity))),
            "value": str(money(abs(row.value_delta))),
        }
        for row in project_issues
    ]
    ageing = []
    for layer in StockLayer.objects.filter(remaining_quantity__gt=0).select_related(
        "item", "warehouse"
    ):
        age = (end - layer.received_on).days
        bucket = (
            "0–30 days"
            if age <= 30
            else "31–60"
            if age <= 60
            else "61–90 days"
            if age <= 90
            else "Over 90 days"
        )
        ageing.append(
            {
                "item": layer.item.code,
                "warehouse": layer.warehouse.code,
                "received_on": _iso(layer.received_on),
                "remaining_quantity": str(quantity(layer.remaining_quantity)),
                "unit_cost": str(Decimal(layer.unit_cost)),
                "value": str(money(layer.remaining_quantity * layer.unit_cost)),
                "age_days": age,
                "bucket": bucket,
            }
        )
    damaged = StockDamageLine.objects.filter(
        damage__recorded_at__date__gte=start, damage__recorded_at__date__lte=end
    ).select_related("item", "warehouse", "damage")
    adjustments = movements.filter(
        movement_type__in=[StockMovement.Type.ADJUSTMENT_IN, StockMovement.Type.ADJUSTMENT_OUT]
    )
    by_warehouse = list(
        movements.values("warehouse__code").annotate(count=Count("id")).order_by("warehouse__code")
    )
    return {
        "start": _iso(start),
        "end": _iso(end),
        "valuation_available": valuation_available,
        "valuation_error": valuation_error,
        "valuation_method": valuation.get("method", ""),
        "total_quantity": str(quantity(valuation.get("total_quantity"))),
        "total_value": str(money(valuation.get("total_value"))),
        "balances": _stringify(valuation.get("rows", [])),
        "movements": movement_rows,
        "project_issues": project_rows,
        "ageing": ageing,
        "damaged": [
            {
                "number": row.damage.number,
                "item": row.item.code,
                "warehouse": row.warehouse.code,
                "quantity": str(quantity(row.quantity)),
                "value": str(money(row.value)),
            }
            for row in damaged
        ],
        "adjustments": [
            {
                "number": row.number,
                "date": _iso(row.movement_date),
                "item": row.item.code,
                "type": row.movement_type,
                "quantity": str(quantity(row.quantity)),
            }
            for row in adjustments
        ],
        "low_stock": _stringify(reorder_alerts()),
        "warehouse_activity": by_warehouse,
    }


def projects_report(start: date, end: date) -> dict:
    rows = dashboard_rows()
    profitability_rows = []
    for project in Project.objects.all():
        detail = profitability(project)
        if project.start_date and project.start_date > end:
            continue
        if project.end_date and project.end_date < start:
            continue
        profitability_rows.append(detail)
    milestones = []
    for project in Project.objects.prefetch_related("milestones"):
        for milestone in project.milestones.filter(is_active=True):
            milestones.append(
                {
                    "project": project.code,
                    "milestone": milestone.name,
                    "due_date": _iso(milestone.due_date),
                    "completed_on": _iso(milestone.completed_on),
                    "status": "completed" if milestone.completed_on else "open",
                    "overdue": bool(
                        not milestone.completed_on and milestone.due_date < timezone.localdate()
                    ),
                }
            )
    costs = (
        ProjectCost.objects.filter(
            cost_date__gte=start, cost_date__lte=end, status=ProjectCost.Status.APPROVED
        )
        .values("category")
        .annotate(amount=Sum("amount"), count=Count("id"))
    )
    return {
        "projects": rows,
        "profitability": profitability_rows,
        "milestones": milestones,
        "approved_cost_by_category": [
            {
                "category": row["category"],
                "amount": str(money(row["amount"])),
                "count": row["count"],
            }
            for row in costs
        ],
        "note": (
            "Revenue recognition is not calculated. Estimated margin uses contract value less "
            "actual cost and open commitments; it is an estimate, not a posted result."
        ),
    }


def operations_report(start: date, end: date) -> dict:
    work_orders = WorkOrder.objects.filter(
        Q(scheduled_start__gte=start, scheduled_start__lte=end)
        | Q(created_at__date__gte=start, created_at__date__lte=end)
    )
    wo_by_status = list(work_orders.values("status").annotate(count=Count("id")).order_by("status"))
    completion = work_orders.filter(
        status__in=[WorkOrder.Status.COMPLETED, WorkOrder.Status.ACCEPTED]
    ).count()
    total = work_orders.count()
    maintenance = EquipmentMaintenance.objects.filter(
        Q(scheduled_date__gte=start, scheduled_date__lte=end)
        | Q(completed_date__gte=start, completed_date__lte=end)
    ).aggregate(cost=Sum("cost"), count=Count("id"))
    agreements = RentalAgreement.objects.filter(
        Q(start_date__lte=end) & (Q(end_date__gte=start) | Q(end_date__isnull=True))
    ).select_related("customer")
    agreement_rows = []
    rental_value = ZERO
    for agreement in agreements.prefetch_related("lines"):
        agreement_total = sum((line.line_total for line in agreement.lines.all()), ZERO)
        rental_value += agreement_total
        agreement_rows.append(
            {
                "number": agreement.number,
                "customer": agreement.customer.legal_name,
                "status": agreement.status,
                "start_date": _iso(agreement.start_date),
                "end_date": _iso(agreement.end_date),
                "value": str(money(agreement_total)),
            }
        )
    utilisation = utilisation_rows(start, end)
    overdue_returns = []
    for agreement in agreements.prefetch_related("movements"):
        latest: dict[int, object] = {}
        for movement in agreement.movements.order_by("equipment_id", "movement_date", "id"):
            latest[movement.equipment_id] = movement
        for movement in latest.values():
            if (
                movement.kind == "dispatch"
                and agreement.end_date
                and agreement.end_date < timezone.localdate()
            ):
                overdue_returns.append(
                    {
                        "agreement": agreement.number,
                        "customer": agreement.customer.legal_name,
                        "equipment": movement.equipment.code,
                        "expected_return": _iso(
                            movement.expected_return_date or agreement.end_date
                        ),
                    }
                )
    return {
        "work_orders": {
            "total": total,
            "by_status": wo_by_status,
            "completion_rate": round(completion / total * 100, 1) if total else None,
        },
        "maintenance": {
            "count": maintenance["count"] or 0,
            "cost": str(money(maintenance["cost"])),
        },
        "equipment_utilisation": utilisation,
        "rental_agreements": agreement_rows,
        "rental_value": str(money(rental_value)),
        "overdue_returns": overdue_returns,
        "equipment_count": Equipment.objects.count(),
    }


def banking_report(start: date, end: date) -> dict:
    accounts = []
    for account in BankAccount.objects.select_related("gl_account").all():
        recorded = account.transactions.filter(
            transaction_date__gte=start, transaction_date__lte=end
        ).aggregate(total=Sum("amount"))["total"]
        accounts.append(
            {
                "id": account.pk,
                "code": account.code,
                "name": account.name,
                "bank": account.bank_name,
                "currency": account.currency,
                "gl_account": account.gl_account.code if account.gl_account_id else "",
                "opening_balance": str(money(account.opening_balance)),
                "recorded_movement": str(money(recorded)),
            }
        )
    reconciliations = [
        {
            "number": item.number,
            "bank_account": item.bank_account.code,
            "period_start": _iso(item.period_start),
            "period_end": _iso(item.period_end),
            "status": item.status,
            "posting_status": item.posting_status,
            "posting_blocker": item.posting_blocker,
            "statement_closing_balance": str(money(item.statement_closing_balance)),
        }
        for item in Reconciliation.objects.filter(
            period_end__gte=start, period_start__lte=end
        ).select_related("bank_account")
    ]
    statements = BankStatement.objects.filter(
        period_end__gte=start, period_start__lte=end
    ).select_related("bank_account")
    cash_accounts = [
        {
            "code": account.code,
            "name": account.name,
            "opening_balance": str(money(account.opening_balance)),
            "imprest_amount": str(money(account.imprest_amount)),
            "recorded_vouchers": account.vouchers.filter(status="recorded").count(),
        }
        for account in CashAccount.objects.all()
    ]
    return {
        "start": _iso(start),
        "end": _iso(end),
        "accounts": accounts,
        "reconciliations": reconciliations,
        "statements": {
            "count": statements.count(),
            "reconciled": statements.filter(status=BankStatement.Status.RECONCILED).count(),
        },
        "cash_accounts": cash_accounts,
        "note": (
            "Recorded movements are book entries, not confirmed bank balances. Confirmed balances "
            "come from the latest reconciled statement."
        ),
    }


def tax_report(start: date, end: date) -> dict:
    configs = [
        {
            "code": row.code,
            "name": row.name,
            "tax_type": row.tax_type,
            "rate": str(row.rate),
            "jurisdiction": row.jurisdiction,
            "review_status": row.review_status,
        }
        for row in TaxConfiguration.objects.all()
    ]
    def by_currency(queryset, amount_fields):
        grouped: dict[str, dict] = {}
        for document in queryset:
            row = grouped.setdefault(
                document.currency,
                {field: ZERO for field in amount_fields} | {"count": 0},
            )
            row["count"] += 1
            for field in amount_fields:
                row[field] += money(getattr(document, field))
        return grouped

    supplier = by_currency(
        SupplierInvoice.objects.filter(
            status=SupplierInvoice.Status.APPROVED,
            invoice_date__gte=start,
            invoice_date__lte=end,
        ),
        ("vat_total", "vat_recoverable_total", "wht_total"),
    )
    customer = by_currency(
        CustomerInvoice.objects.filter(
            status=CustomerInvoice.Status.APPROVED,
            invoice_date__gte=start,
            invoice_date__lte=end,
        ),
        ("vat_total", "wht_total"),
    )
    notes = by_currency(
        InvoiceNote.objects.filter(
            status=InvoiceNote.Status.APPROVED,
            note_date__gte=start,
            note_date__lte=end,
        ),
        ("vat_total",),
    )
    currencies = sorted(set(supplier) | set(customer) | set(notes))
    mixed = len(currencies) > 1

    def totals(grouped, fields, source):
        if not mixed:
            code = currencies[0] if currencies else "NGN"
            row = grouped.get(code, {field: ZERO for field in fields} | {"count": 0})
            payload = {
                "currency": code,
                "approved_invoices": row["count"],
                **{field: str(money(row[field])) for field in fields},
            }
        else:
            payload = {
                "currency": "MIXED",
                "approved_invoices": sum(row["count"] for row in grouped.values()),
                **{field: "" for field in fields},
            }
        payload["by_currency"] = [
            {
                "currency": code,
                "approved_invoices": grouped[code]["count"],
                **{field: str(money(grouped[code][field])) for field in fields},
            }
            for code in sorted(grouped)
        ]
        payload["source"] = source
        return payload

    input_vat = totals(supplier, ("vat_total", "vat_recoverable_total", "wht_total"), "supplier")
    output_vat = totals(customer, ("vat_total", "wht_total"), "customer")
    note_totals = totals(notes, ("vat_total",), "notes")
    return {
        "start": _iso(start),
        "end": _iso(end),
        "source": "approved_invoice_documents",
        "currency": "MIXED" if mixed else (currencies[0] if currencies else "NGN"),
        "mixed_currency": mixed,
        "note": (
            "Document tax totals are not a tax remittance report. Only approved invoices and notes "
            "are included; cancelled and draft documents are excluded."
        ),
        "configurations": configs,
        "input_vat": {
            **input_vat,
            "vat": input_vat["vat_total"],
            "recoverable": input_vat["vat_recoverable_total"],
            "wht": input_vat["wht_total"],
        },
        "output_vat": {
            **output_vat,
            "vat": output_vat["vat_total"],
            "wht": output_vat["wht_total"],
        },
        "notes": {
            **note_totals,
            "count": note_totals["approved_invoices"],
            "vat": note_totals["vat_total"],
        },
    }


def periods_report() -> dict:
    rows = []
    for period in AccountingPeriod.objects.select_related("fiscal_year").all():
        posted = JournalEntry.objects.filter(period=period, status=JournalEntry.Status.POSTED)
        aggregate = posted.aggregate(debit=Sum("total_debit"), credit=Sum("total_credit"))
        rows.append(
            {
                "id": period.pk,
                "fiscal_year": period.fiscal_year.code,
                "name": period.name,
                "start_date": _iso(period.start_date),
                "end_date": _iso(period.end_date),
                "status": period.status,
                "posted_journals": posted.count(),
                "unposted_journals": JournalEntry.objects.filter(period=period)
                .exclude(status=JournalEntry.Status.POSTED)
                .count(),
                "debit": str(money(aggregate["debit"])),
                "credit": str(money(aggregate["credit"])),
                "balanced": money(aggregate["debit"]) == money(aggregate["credit"]),
            }
        )
    return {"rows": rows}


def overview(start: date, end: date) -> dict:
    financial = financial_report(start, end)
    income = financial["income_statement"]
    cogs_accounts = AccountRoleMapping.objects.filter(
        role__code="COST_OF_SALES",
        is_active=True,
        approved_at__isnull=False,
        effective_from__lte=end,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=end))
    cogs_ids = list(cogs_accounts.values_list("account_id", flat=True).distinct())
    if cogs_ids:
        cost_of_sales = JournalLine.objects.filter(
            journal__status=JournalEntry.Status.POSTED,
            journal__journal_date__gte=start,
            journal__journal_date__lte=end,
            account_id__in=cogs_ids,
        ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
        cogs = money(cost_of_sales["debit"] or ZERO) - money(cost_of_sales["credit"] or ZERO)
        gross_profit = {
            "available": True,
            "value": str(money(Decimal(income["total_income"]) - cogs)),
            "reason": "",
        }
    else:
        gross_profit = {
            "available": False,
            "value": "",
            "reason": (
                "No approved COST_OF_SALES account mapping; gross profit cannot be "
                "distinguished from operating expenses."
            ),
        }
    payables = payable_report(end)
    receivables = receivable_report(end)
    try:
        valuation = valuation_rows()
        inventory = {
            "available": True,
            "value": str(money(valuation["total_value"])),
            "quantity": str(quantity(valuation["total_quantity"])),
            "method": valuation["method"],
        }
    except PolicyNotConfigured as exc:
        inventory = {"available": False, "value": "", "quantity": "", "reason": str(exc)}
    projects = dashboard_rows()
    operational = operations_report(start, end)
    procurement = procurement_report(start, end)
    configuration = financial["configuration"]
    cash = financial["cash_flow"]
    bank_book = BankAccount.objects.aggregate(total=Sum("opening_balance"))["total"] or ZERO
    return {
        "start": _iso(start),
        "end": _iso(end),
        "currency": "NGN",
        "status": "mixed_actual_and_operational",
        "actual": {
            "revenue": income["total_income"],
            "expenses": income["total_expenses"],
            "gross_profit": gross_profit,
            "net_result": income["net_result"],
            "source": "posted_journal_lines",
        },
        "cash": {
            "gl_closing_cash": cash["closing_cash"] if cash["available"] else "",
            "available": cash["available"],
            "recorded_bank_opening_balances": str(money(bank_book)),
            "reason": cash["reason"],
        },
        "receivables": {
            "total": receivables["total"],
            "overdue": receivables["overdue"],
            "mixed_currency": receivables["mixed_currency"],
            "currency": receivables["currency"],
        },
        "payables": {
            "total": payables["total"],
            "overdue": payables["overdue"],
            "mixed_currency": payables["mixed_currency"],
            "currency": payables["currency"],
        },
        "inventory": inventory,
        "projects": {
            "active": sum(1 for row in projects if row["status"] == "active"),
            "total_budget": str(
                money(sum((Decimal(row["budget_total"] or "0") for row in projects), ZERO))
            ),
            "actual_cost": str(
                money(sum((Decimal(row["actual_total"] or "0") for row in projects), ZERO))
            ),
            "open_commitments": str(
                money(sum((Decimal(row["open_commitment"] or "0") for row in projects), ZERO))
            ),
        },
        "procurement": {
            "committed_value": procurement["purchase_orders"]["committed_value"],
            "orders": procurement["purchase_orders"]["count"],
            "outstanding_deliveries": len(procurement["outstanding_deliveries"]),
        },
        "operations": {
            "open_work_orders": sum(
                1
                for row in operational["work_orders"]["by_status"]
                if row["status"] not in {"completed", "accepted", "cancelled"}
            ),
            "overdue_returns": len(operational["overdue_returns"]),
            "equipment_utilisation_rows": len(operational["equipment_utilisation"]),
        },
        "warnings": financial["warnings"],
        "configuration": configuration,
        "definitions": {
            "actual": "Revenue, expenses and net result are posted ledger figures for the period.",
            "receivables": "Approved customer invoice balances, not ledger receivables.",
            "payables": "Approved supplier invoice balances, not ledger payables.",
            "commitments": "Issued or approved purchase order values; not expenses.",
            "inventory": "Derived from the stock ledger using the configured valuation method.",
        },
    }


def _stringify(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _stringify(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stringify(item) for item in value]
    return value


def report_payload(name: str, start: date, end: date, *, account=None) -> dict:
    if name == "overview":
        return overview(start, end)
    if name == "financial-statements":
        return financial_report(start, end)
    if name == "cash-flow":
        return cash_flow(start, end)
    if name == "trial-balance":
        return _stringify(trial_balance(as_of=end))
    if name == "general-ledger":
        if account is None:
            raise Conflict("Choose an account for the general ledger.")
        return _stringify(general_ledger(account, start=start, end=end))
    if name == "journal-register":
        return journal_register(start, end)
    if name == "receivables-ageing":
        return receivable_report(end)
    if name == "payables-ageing":
        return payable_report(end)
    if name == "procurement":
        return procurement_report(start, end)
    if name == "inventory":
        return inventory_report(start, end)
    if name == "projects":
        return projects_report(start, end)
    if name == "operations":
        return operations_report(start, end)
    if name == "banking":
        return banking_report(start, end)
    if name == "tax":
        return tax_report(start, end)
    if name == "periods":
        return periods_report()
    raise Conflict("Unknown report.")
