"""Role-aware operational dashboard.

Every value is read from a real source document or posted record. The endpoint
never fills a missing figure with zero: a card that has no source records says
``available: false`` and the browser shows an empty state. Sections are omitted
entirely when the signed-in user lacks permission to read their source module.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone

from apps.banking.models import BankTransaction, Reconciliation, StatementLine
from apps.core.models import AuditEvent
from apps.inventory.models import StockMovement
from apps.inventory.services import PolicyNotConfigured, reorder_alerts, valuation_rows
from apps.invoicing.models import (
    CustomerInvoice,
    InvoiceNote,
    InvoiceSettings,
    SupplierInvoice,
    SupplierPayment,
)
from apps.procurement.models import (
    DeliverySchedule,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseRequest,
    RequestForQuotation,
    SupplierQuote,
)
from apps.projects.costing import cost_summary
from apps.projects.models import CustomerContract, Project, ProjectBudget, ProjectMilestone

ZERO = Decimal("0")
CENT = Decimal("0.01")
TODAY = timezone.localdate

SUPPLIER_BALANCE = ExpressionWrapper(
    F("payment_due") - F("amount_paid"),
    output_field=DecimalField(max_digits=18, decimal_places=2),
)


def _money(value) -> str:
    return str(Decimal(str(value or ZERO)).quantize(CENT))


def _card(
    identifier: str,
    label: str,
    *,
    amount: Decimal | None = None,
    count: int = 0,
    available: bool = True,
    basis: str = "",
    state: str = "actual",
    link: str = "",
    note: str = "",
    tone: str = "neutral",
) -> dict:
    return {
        "id": identifier,
        "label": label,
        "amount": _money(amount) if amount is not None else None,
        "count": count,
        "available": available,
        "basis": basis,
        "state": state if available else "no_data",
        "link": link,
        "note": note,
        "tone": tone,
    }


def _action(
    identifier: str,
    label: str,
    count: int,
    link: str,
    description: str,
    *,
    tone: str = "attention",
) -> dict:
    return {
        "id": identifier,
        "label": label,
        "count": count,
        "link": link,
        "description": description,
        "tone": tone if count else "clear",
    }


def _invoice_state(*querysets) -> str:
    if any(queryset.filter(is_test=False).exists() for queryset in querysets):
        return "actual"
    return "test"


def _can(user, permission: str) -> bool:
    return user.has_perm(permission)


def _financial_overview(user, start: date, end: date) -> list[dict] | None:
    if not _can(user, "reporting.view_financialreporting"):
        return None

    approved_customers = CustomerInvoice.objects.filter(
        status=CustomerInvoice.Status.APPROVED
    )
    approved_suppliers = SupplierInvoice.objects.filter(
        status=SupplierInvoice.Status.APPROVED
    )
    customers = approved_customers.filter(currency="NGN")
    suppliers = approved_suppliers.filter(currency="NGN")
    customer_outstanding = customers.filter(balance__gt=ZERO)
    customer_overdue = customer_outstanding.filter(due_date__lt=TODAY())
    supplier_outstanding = suppliers.filter(payment_due__gt=F("amount_paid"))
    supplier_due = supplier_outstanding.filter(due_date__lte=TODAY())

    supplier_outstanding_total = supplier_outstanding.aggregate(
        total=Sum(SUPPLIER_BALANCE)
    )["total"]
    supplier_due_total = supplier_due.aggregate(total=Sum(SUPPLIER_BALANCE))["total"]

    receipts = BankTransaction.objects.filter(
        source_type=BankTransaction.Source.CUSTOMER_RECEIPT,
        status__in=[BankTransaction.Status.RECORDED, BankTransaction.Status.RECONCILED],
        transaction_date__gte=start,
        transaction_date__lte=end,
        currency="NGN",
        amount__gt=ZERO,
    )
    payments = SupplierPayment.objects.filter(
        status=SupplierPayment.Status.RECORDED,
        payment_date__gte=start,
        payment_date__lte=end,
        currency="NGN",
    )

    other_customer_currency = (
        approved_customers.exclude(currency="NGN").filter(balance__gt=ZERO).count()
    )
    other_supplier_currency = (
        approved_suppliers.exclude(currency="NGN")
        .filter(payment_due__gt=F("amount_paid"))
        .count()
    )
    notes = []
    if other_customer_currency or other_supplier_currency:
        notes.append(
            "Amounts exclude invoices in other currencies; those records are counted separately."
        )

    return [
        _card(
            "customer_outstanding",
            "Outstanding customer invoices",
            amount=customer_outstanding.aggregate(total=Sum("balance"))["total"],
            count=customer_outstanding.count(),
            available=approved_customers.exists() or other_customer_currency > 0,
            basis="Approved customer invoice balances, NGN",
            state=_invoice_state(customers),
            link="/invoicing?tab=customer-invoices&status=approved",
            note="Document balances, not a posted ledger total.",
            tone="positive",
        ),
        _card(
            "customer_overdue",
            "Overdue customer invoices",
            amount=customer_overdue.aggregate(total=Sum("balance"))["total"],
            count=customer_overdue.count(),
            available=approved_customers.exists() or other_customer_currency > 0,
            basis="Approved invoices past their due date, NGN",
            state=_invoice_state(customers),
            link="/invoicing?tab=customer-invoices&status=approved",
            note="Still outstanding; excludes paid and cancelled invoices.",
            tone="warning",
        ),
        _card(
            "supplier_outstanding",
            "Outstanding supplier invoices",
            amount=supplier_outstanding_total,
            count=supplier_outstanding.count(),
            available=approved_suppliers.exists() or other_supplier_currency > 0,
            basis="Approved supplier invoice payment due less amounts paid, NGN",
            state=_invoice_state(suppliers),
            link="/invoicing?tab=supplier-invoices&status=approved",
            note="Document balances; a payment may still be awaiting allocation.",
            tone="warning",
        ),
        _card(
            "supplier_due",
            "Supplier invoices due for payment",
            amount=supplier_due_total,
            count=supplier_due.count(),
            available=approved_suppliers.exists() or other_supplier_currency > 0,
            basis="Approved supplier invoices due on or before today, NGN",
            state=_invoice_state(suppliers),
            link="/invoicing?tab=supplier-invoices&status=approved",
            note="Due date reached; includes overdue balances.",
            tone="warning",
        ),
        _card(
            "payments_received",
            "Payments received",
            amount=receipts.aggregate(total=Sum("amount"))["total"],
            count=receipts.count(),
            available=BankTransaction.objects.filter(
                source_type=BankTransaction.Source.CUSTOMER_RECEIPT
            ).exists(),
            basis="Customer receipts recorded in the selected period, NGN",
            state="recorded",
            link="/banking?tab=bank-transactions",
            note="Recorded receipts; not all are necessarily bank-reconciled.",
            tone="positive",
        ),
        _card(
            "payments_made",
            "Payments made",
            amount=payments.aggregate(total=Sum("amount"))["total"],
            count=payments.count(),
            available=SupplierPayment.objects.exists(),
            basis="Supplier payments recorded in the selected period, NGN",
            state="recorded",
            link="/invoicing?tab=payments&status=recorded",
            note="Externally recorded payments; execution status is shown in the payment record.",
            tone="positive",
        ),
    ]


def _invoice_management(user, *, issued: bool) -> list[dict] | None:
    rows: list[dict] = []

    if _can(user, "invoicing.view_supplierinvoice"):
        suppliers = SupplierInvoice.objects.all()
        rows.extend(
            [
                _card(
                    "supplier_awaiting_approval",
                    "Supplier invoices awaiting approval",
                    count=suppliers.filter(status=SupplierInvoice.Status.SUBMITTED).count(),
                    available=True,
                    basis="Submitted supplier invoices",
                    state=_invoice_state(suppliers),
                    link="/invoicing?tab=supplier-invoices&status=submitted",
                    tone="attention",
                ),
                _card(
                    "supplier_drafts",
                    "Draft supplier invoices",
                    count=suppliers.filter(status=SupplierInvoice.Status.DRAFT).count(),
                    available=True,
                    basis="Supplier invoice drafts",
                    state=_invoice_state(suppliers),
                    link="/invoicing?tab=supplier-invoices&status=draft",
                ),
                _card(
                    "supplier_exceptions",
                    "Supplier matching discrepancies",
                    count=suppliers.filter(match_status=SupplierInvoice.MatchStatus.EXCEPTION).count(),
                    available=True,
                    basis="Supplier invoices with matching exceptions",
                    state=_invoice_state(suppliers),
                    link="/invoicing?tab=supplier-invoices&match_status=exception",
                    tone="warning",
                ),
                _card(
                    "supplier_overdue",
                    "Overdue supplier invoices",
                    count=suppliers.filter(
                        status=SupplierInvoice.Status.APPROVED,
                        due_date__lt=TODAY(),
                        payment_due__gt=F("amount_paid"),
                    ).count(),
                    available=suppliers.exists(),
                    basis="Approved supplier invoices past due with a balance",
                    state=_invoice_state(suppliers),
                    link="/invoicing?tab=supplier-invoices&status=approved",
                    tone="warning",
                ),
            ]
        )

    if _can(user, "invoicing.view_customerinvoice"):
        customers = CustomerInvoice.objects.all()
        rows.extend(
            [
                _card(
                    "customer_awaiting_approval",
                    "Customer invoices awaiting approval",
                    count=customers.filter(status=CustomerInvoice.Status.SUBMITTED).count(),
                    available=True,
                    basis="Submitted customer invoices",
                    state=_invoice_state(customers),
                    link="/invoicing?tab=customer-invoices&status=submitted",
                    tone="attention",
                ),
                _card(
                    "customer_drafts",
                    "Draft customer invoices",
                    count=customers.filter(status=CustomerInvoice.Status.DRAFT).count(),
                    available=True,
                    basis="Customer invoice drafts",
                    state=_invoice_state(customers),
                    link="/invoicing?tab=customer-invoices&status=draft",
                ),
                _card(
                    "customer_overdue",
                    "Overdue customer invoices",
                    count=customers.filter(
                        status=CustomerInvoice.Status.APPROVED,
                        due_date__lt=TODAY(),
                        balance__gt=ZERO,
                    ).count(),
                    available=customers.exists(),
                    basis="Approved customer invoices past due with a balance",
                    state=_invoice_state(customers),
                    link="/invoicing?tab=customer-invoices&status=approved",
                    tone="warning",
                ),
            ]
        )
        if issued:
            rows.append(
                _card(
                    "recent_customer_approved",
                    "Recently approved customer invoices",
                    count=customers.filter(
                        status=CustomerInvoice.Status.APPROVED,
                        approved_at__isnull=False,
                    ).count(),
                    available=customers.exists(),
                    basis="Approved customer invoices; production issuance is authorised",
                    state=_invoice_state(customers),
                    link="/invoicing?tab=customer-invoices&status=approved",
                    tone="positive",
                )
            )

    if _can(user, "invoicing.view_invoicenote"):
        notes = InvoiceNote.objects.all()
        rows.append(
            _card(
                "notes_review",
                "Credit and debit notes requiring review",
                count=notes.filter(status=InvoiceNote.Status.SUBMITTED).count(),
                available=notes.exists(),
                basis="Submitted credit and debit notes",
                state=_invoice_state(notes),
                link="/invoicing?tab=notes&status=submitted",
                tone="attention",
            )
        )

    return rows or None


def _pending_actions(user) -> list[dict]:
    actions: list[dict] = []

    if _can(user, "invoicing.approve_supplierinvoice"):
        count = SupplierInvoice.objects.filter(status=SupplierInvoice.Status.SUBMITTED).count()
        actions.append(
            _action(
                "supplier_invoices",
                "Supplier invoices awaiting your approval",
                count,
                "/invoicing?tab=supplier-invoices&status=submitted",
                "Review the invoice, matching result and supporting documents.",
            )
        )
    if _can(user, "invoicing.approve_customerinvoice"):
        count = CustomerInvoice.objects.filter(status=CustomerInvoice.Status.SUBMITTED).count()
        actions.append(
            _action(
                "customer_invoices",
                "Customer invoices awaiting your approval",
                count,
                "/invoicing?tab=customer-invoices&status=submitted",
                "Check customer details, values and tax before approving.",
            )
        )
    if _can(user, "invoicing.approve_payment"):
        count = SupplierPayment.objects.filter(status=SupplierPayment.Status.SUBMITTED).count()
        actions.append(
            _action(
                "payments",
                "Payments awaiting your approval",
                count,
                "/invoicing?tab=payments&status=submitted",
                "Approval records the decision; it does not execute a bank payment.",
            )
        )
    if _can(user, "procurement.approve_purchaserequest"):
        count = PurchaseRequest.objects.filter(status=PurchaseRequest.Status.SUBMITTED).count()
        actions.append(
            _action(
                "purchase_requests",
                "Purchase requests awaiting your approval",
                count,
                "/procurement?tab=requests&status=submitted",
                "Approved requests can be used to raise purchase orders.",
            )
        )
    if _can(user, "procurement.approve_purchaseorder"):
        count = PurchaseOrder.objects.filter(status=PurchaseOrder.Status.SUBMITTED).count()
        actions.append(
            _action(
                "purchase_orders",
                "Purchase orders awaiting your approval",
                count,
                "/procurement?tab=orders&status=submitted",
                "Orders remain unissued until approved.",
            )
        )
    if _can(user, "accounting.approve_journal"):
        from apps.accounting.models import JournalEntry

        count = JournalEntry.objects.filter(status=JournalEntry.Status.SUBMITTED).count()
        actions.append(
            _action(
                "journals",
                "Journals awaiting your approval",
                count,
                "/accounting?tab=journals&status=submitted",
                "Only posted journals affect the financial statements.",
            )
        )
    if _can(user, "banking.match_banktransaction"):
        count = StatementLine.objects.filter(status=StatementLine.Status.UNMATCHED).count()
        actions.append(
            _action(
                "bank_lines",
                "Bank transactions awaiting reconciliation",
                count,
                "/banking?tab=lines&status=unmatched",
                "Match statement lines to recorded company transactions.",
            )
        )
    if _can(user, "banking.approve_reconciliation"):
        count = Reconciliation.objects.filter(status=Reconciliation.Status.SUBMITTED).count()
        actions.append(
            _action(
                "reconciliations",
                "Bank reconciliations awaiting your approval",
                count,
                "/banking?tab=reconciliations&status=submitted",
                "Review the statement, matches and unexplained differences.",
            )
        )
    if _can(user, "projects.approve_projectbudget"):
        count = ProjectBudget.objects.filter(status=ProjectBudget.Status.DRAFT).count()
        actions.append(
            _action(
                "project_budgets",
                "Project budgets awaiting your approval",
                count,
                "/projects?tab=budgets&status=draft",
                "Approved budgets become the baseline for cost control.",
            )
        )
    if _can(user, "invoicing.view_supplierinvoice"):
        count = SupplierInvoice.objects.filter(
            match_status=SupplierInvoice.MatchStatus.EXCEPTION
        ).count()
        actions.append(
            _action(
                "supplier_matching",
                "Supplier invoice matching discrepancies",
                count,
                "/invoicing?tab=supplier-invoices&match_status=exception",
                "Resolve quantity, price or receipt differences before approval.",
            )
        )
    return actions


def _allowed_project_queryset(user):
    assigned = Project.objects.filter(Q(managers=user) | Q(project_manager=user)).distinct()
    if assigned.exists():
        return assigned
    return Project.objects.all()


def _operations(user, focus_id: str) -> dict | None:
    if focus_id == "management":
        projects = Project.objects.all()
        contracts = CustomerContract.objects.filter(is_active=True, currency="NGN")
        open_orders = PurchaseOrder.objects.filter(
            status__in=[
                PurchaseOrder.Status.APPROVED,
                PurchaseOrder.Status.ISSUED,
                PurchaseOrder.Status.PARTIALLY_RECEIVED,
            ]
        ).prefetch_related("lines")
        committed = sum((order.total_value for order in open_orders), ZERO)
        return {
            "id": "portfolio",
            "title": "Portfolio and commitments",
            "description": "Company-wide delivery position; commitments are not expenses.",
            "cards": [
                {
                    "id": "active_projects",
                    "label": "Active projects",
                    "value": projects.filter(status=Project.Status.ACTIVE).count(),
                    "format": "number",
                    "detail": "Projects in the register",
                    "link": "/projects?tab=projects&status=active",
                },
                {
                    "id": "contract_value",
                    "label": "Active contract value",
                    "value": _money(contracts.aggregate(total=Sum("value"))["total"]),
                    "format": "currency",
                    "detail": "Active customer contracts, NGN",
                    "link": "/projects?tab=contracts",
                },
                {
                    "id": "procurement_commitments",
                    "label": "Procurement commitments",
                    "value": _money(committed),
                    "format": "currency",
                    "detail": "Open purchase orders with remaining delivery",
                    "link": "/procurement?tab=orders",
                },
                {
                    "id": "open_milestones",
                    "label": "Open milestones",
                    "value": ProjectMilestone.objects.filter(
                        is_active=True, completed_on__isnull=True
                    ).count(),
                    "format": "number",
                    "detail": "Across all active and draft projects",
                    "link": "/projects?tab=milestones",
                },
            ],
        }

    if focus_id == "finance":
        return {
            "id": "treasury",
            "title": "Treasury workspace",
            "description": "Payment recording and bank reconciliation work in progress.",
            "cards": [
                {
                    "id": "unmatched_lines",
                    "label": "Bank lines to reconcile",
                    "value": StatementLine.objects.filter(
                        status=StatementLine.Status.UNMATCHED
                    ).count(),
                    "format": "number",
                    "detail": "Statement lines without a confirmed match",
                    "link": "/banking?tab=lines&status=unmatched",
                },
                {
                    "id": "payments_recorded",
                    "label": "Payments recorded",
                    "value": SupplierPayment.objects.filter(
                        status=SupplierPayment.Status.RECORDED
                    ).count(),
                    "format": "number",
                    "detail": "All recorded supplier payments",
                    "link": "/invoicing?tab=payments&status=recorded",
                },
                {
                    "id": "allocations",
                    "label": "Unallocated payments",
                    "value": SupplierPayment.objects.filter(
                        status=SupplierPayment.Status.RECORDED, allocated_amount=ZERO
                    ).count(),
                    "format": "number",
                    "detail": "Recorded payments with no invoice allocation",
                    "link": "/invoicing?tab=payments",
                },
            ],
        }

    if focus_id == "warehouse":
        try:
            valuation = valuation_rows()
            stock_value = _money(valuation["total_value"])
            low_stock = len(reorder_alerts())
        except (PolicyNotConfigured, KeyError):
            stock_value = ""
            low_stock = None
        return {
            "id": "warehouse",
            "title": "Warehouse workspace",
            "description": "Stock position, movement and replenishment signals.",
            "cards": [
                {
                    "id": "stock_value",
                    "label": "Stock value",
                    "value": stock_value,
                    "format": "currency" if stock_value else "empty",
                    "detail": "Current valuation; unavailable until a method is approved"
                    if not stock_value
                    else "Current approved valuation method, NGN",
                    "link": "/inventory?tab=balances",
                },
                {
                    "id": "low_stock",
                    "label": "Low-stock alerts",
                    "value": low_stock if low_stock is not None else "",
                    "format": "number" if low_stock is not None else "empty",
                    "detail": "Items at or below their reorder level",
                    "link": "/inventory?tab=reorder-levels",
                },
                {
                    "id": "transfers",
                    "label": "Transfer dispatches",
                    "value": StockMovement.objects.filter(
                        movement_type=StockMovement.Type.TRANSFER_OUT
                    ).count(),
                    "format": "number",
                    "detail": "Outbound transfer movements recorded",
                    "link": "/inventory?tab=transfers",
                },
                {
                    "id": "receipts",
                    "label": "Goods receipts recorded",
                    "value": GoodsReceiptNote.objects.count(),
                    "format": "number",
                    "detail": "Receipts posted against purchase orders",
                    "link": "/procurement?tab=receipts",
                },
            ],
        }

    if focus_id == "projects":
        projects = _allowed_project_queryset(user)
        approved_budgets = ProjectBudget.objects.filter(
            project__in=projects, status=ProjectBudget.Status.APPROVED
        )
        budget_total = sum((budget.total_value for budget in approved_budgets), ZERO)
        actual_total = sum(
            (Decimal(cost_summary(project)["actual_total"]) for project in projects), ZERO
        )
        return {
            "id": "projects",
            "title": "Project workspace",
            "description": "Your assigned projects and their current cost position.",
            "cards": [
                {
                    "id": "assigned_projects",
                    "label": "Your projects",
                    "value": projects.count(),
                    "format": "number",
                    "detail": "Projects you manage or lead",
                    "link": "/projects?tab=projects",
                },
                {
                    "id": "budget",
                    "label": "Approved budget",
                    "value": _money(budget_total),
                    "format": "currency",
                    "detail": "Latest approved budget versions, NGN",
                    "link": "/projects?tab=budgets&status=approved",
                },
                {
                    "id": "actual_cost",
                    "label": "Actual cost",
                    "value": _money(actual_total),
                    "format": "currency",
                    "detail": "Approved invoices, project issues and direct costs",
                    "link": "/projects?tab=costs",
                },
                {
                    "id": "milestones",
                    "label": "Open milestones",
                    "value": ProjectMilestone.objects.filter(
                        project__in=projects, is_active=True, completed_on__isnull=True
                    ).count(),
                    "format": "number",
                    "detail": "Not yet completed",
                    "link": "/projects?tab=milestones",
                },
            ],
        }

    if focus_id == "procurement":
        outstanding = 0
        for schedule in DeliverySchedule.objects.filter(
            order_line__order__status__in=[
                PurchaseOrder.Status.APPROVED,
                PurchaseOrder.Status.ISSUED,
                PurchaseOrder.Status.PARTIALLY_RECEIVED,
            ]
        ):
            if schedule.quantity > schedule.quantity_delivered:
                outstanding += 1
        return {
            "id": "procurement",
            "title": "Procurement workspace",
            "description": "Requests, commitments and deliveries that need attention.",
            "cards": [
                {
                    "id": "open_orders",
                    "label": "Open purchase orders",
                    "value": PurchaseOrder.objects.filter(
                        status__in=[
                            PurchaseOrder.Status.APPROVED,
                            PurchaseOrder.Status.ISSUED,
                            PurchaseOrder.Status.PARTIALLY_RECEIVED,
                        ]
                    ).count(),
                    "format": "number",
                    "detail": "Approved, issued or partly received",
                    "link": "/procurement?tab=orders",
                },
                {
                    "id": "outstanding_deliveries",
                    "label": "Deliveries outstanding",
                    "value": outstanding,
                    "format": "number",
                    "detail": "Schedules with quantity still to arrive",
                    "link": "/procurement?tab=schedules",
                },
                {
                    "id": "active_rfqs",
                    "label": "RFQs open",
                    "value": RequestForQuotation.objects.filter(
                        status=RequestForQuotation.Status.ISSUED
                    ).count(),
                    "format": "number",
                    "detail": "Issued requests awaiting supplier quotations",
                    "link": "/procurement?tab=rfqs&status=issued",
                },
                {
                    "id": "quotes",
                    "label": "Supplier quotations",
                    "value": SupplierQuote.objects.count(),
                    "format": "number",
                    "detail": "Quotations recorded for issued RFQs",
                    "link": "/procurement?tab=quotes",
                },
            ],
        }

    return None


ACTIVITY_TYPES = {
    "invoicing.supplierinvoice": (
        "Supplier invoice",
        "invoicing.view_supplierinvoice",
        "/invoicing?tab=supplier-invoices",
    ),
    "supplier_invoice": (
        "Supplier invoice",
        "invoicing.view_supplierinvoice",
        "/invoicing?tab=supplier-invoices",
    ),
    "invoicing.customerinvoice": (
        "Customer invoice",
        "invoicing.view_customerinvoice",
        "/invoicing?tab=customer-invoices",
    ),
    "customer_invoice": (
        "Customer invoice",
        "invoicing.view_customerinvoice",
        "/invoicing?tab=customer-invoices",
    ),
    "invoicing.supplierpayment": (
        "Supplier payment",
        "invoicing.view_supplierpayment",
        "/invoicing?tab=payments",
    ),
    "payment": ("Supplier payment", "invoicing.view_supplierpayment", "/invoicing?tab=payments"),
    "purchase_order": (
        "Purchase order",
        "procurement.view_purchaseorder",
        "/procurement?tab=orders",
    ),
    "purchase_request": (
        "Purchase request",
        "procurement.view_purchaserequest",
        "/procurement?tab=requests",
    ),
    "procurement.goodsreceiptnote": (
        "Goods receipt",
        "procurement.view_goodsreceiptnote",
        "/procurement?tab=goods-receipts",
    ),
    "inventory.stockmovement": (
        "Stock movement",
        "inventory.view_stockmovement",
        "/inventory?tab=movements",
    ),
    "projects.projectbudget": (
        "Project budget",
        "projects.view_projectbudget",
        "/projects?tab=budgets",
    ),
}

ACTIVITY_LABELS = {
    "supplier_invoice.submitted": "Supplier invoice submitted",
    "supplier_invoice.approved": "Supplier invoice approved",
    "supplier_invoice.rejected": "Supplier invoice rejected",
    "supplier_invoice.emailed": "Supplier invoice emailed",
    "customer_invoice.submitted": "Customer invoice submitted",
    "customer_invoice.approved": "Customer invoice approved",
    "customer_invoice.rejected": "Customer invoice rejected",
    "customer_invoice.emailed": "Customer invoice emailed",
    "supplier_payment.recorded": "Payment recorded",
    "supplier_payment.approved": "Payment approved",
    "supplier_payment.allocated": "Payment allocated",
    "approval.recorded": "Approval recorded",
    "stock.movement": "Stock movement recorded",
}


def _reference(entity_type: str, entity_id: str, after: dict) -> str:
    for key in ("number", "reference", "title"):
        value = after.get(key)
        if value:
            return str(value)
    model = {
        "invoicing.supplierinvoice": SupplierInvoice,
        "supplier_invoice": SupplierInvoice,
        "invoicing.customerinvoice": CustomerInvoice,
        "customer_invoice": CustomerInvoice,
        "invoicing.supplierpayment": SupplierPayment,
        "payment": SupplierPayment,
        "purchase_order": PurchaseOrder,
        "purchase_request": PurchaseRequest,
        "inventory.stockmovement": StockMovement,
        "projects.projectbudget": ProjectBudget,
    }.get(entity_type)
    if model is None or not entity_id:
        return ""
    try:
        record = model.objects.filter(pk=int(entity_id)).first()
    except (TypeError, ValueError):
        return ""
    if record is None:
        return ""
    for field in ("number", "reference", "code"):
        value = getattr(record, field, "")
        if value:
            return str(value)
    return ""


def _activity_label(event: AuditEvent) -> str:
    if event.action == "approval.recorded":
        label = ACTIVITY_TYPES.get(event.entity_type, ("Document", "", ""))[0]
        return f"{label} approved"
    if event.action == "stock.movement":
        if event.after.get("movement_type") == StockMovement.Type.PROJECT_ISSUE:
            return "Stock issued to a project"
        return "Stock movement recorded"
    return ACTIVITY_LABELS.get(
        event.action, event.action.replace(".", " ").replace("_", " ").capitalize()
    )


ACTIVITY_FOCUS = {
    "finance": {
        "invoicing.supplierinvoice",
        "supplier_invoice",
        "invoicing.customerinvoice",
        "customer_invoice",
        "invoicing.supplierpayment",
        "payment",
    },
    "procurement": {
        "purchase_request",
        "purchase_order",
        "procurement.goodsreceiptnote",
    },
    "warehouse": {"inventory.stockmovement", "procurement.goodsreceiptnote"},
    "projects": {"projects.projectbudget"},
}


def _recent_activity(user, focus_id: str, limit: int = 8) -> list[dict]:
    allowed = {
        entity: value
        for entity, value in ACTIVITY_TYPES.items()
        if _can(user, value[1])
    }
    if focus_id in ACTIVITY_FOCUS:
        allowed = {
            entity: value
            for entity, value in allowed.items()
            if entity in ACTIVITY_FOCUS[focus_id]
        }
    if not allowed:
        return []
    events = (
        AuditEvent.objects.filter(entity_type__in=allowed)
        .select_related("actor")
        .order_by("-id")[: limit * 3]
    )
    rows = []
    seen = set()
    for event in events:
        reference = _reference(event.entity_type, event.entity_id, event.after)
        if event.action == "approval.recorded" or event.action.endswith(".approved"):
            seen_key = (reference or event.entity_type, "approved")
        else:
            seen_key = (reference or event.entity_type, event.action)
        if seen_key in seen:
            continue
        seen.add(seen_key)
        label, _, link = allowed[event.entity_type]
        record_link = f"{link}&record={event.entity_id}" if event.entity_id else link
        rows.append(
            {
                "id": event.pk,
                "action": _activity_label(event),
                "entity": label,
                "reference": reference,
                "user": event.actor.full_name if event.actor else "System",
                "occurred_at": event.occurred_at.isoformat(),
                "link": record_link,
            }
        )
        if len(rows) >= limit:
            break
    return rows


MODULE_ACCESS = (
    (
        "master-data",
        "Master data",
        "/master-data",
        "Suppliers, customers, catalogue, warehouses and projects.",
        (),
    ),
    (
        "procurement",
        "Procurement",
        "/procurement",
        "Purchase requests, orders, quotations and goods receipts.",
        ("procurement.view_purchaserequest", "procurement.view_purchaseorder"),
    ),
    (
        "inventory",
        "Inventory",
        "/inventory",
        "Balances, movements, reorder alerts and the stock ledger.",
        ("inventory.view_stockmovement", "inventory.view_reorderlevel"),
    ),
    (
        "accounting",
        "Accounting",
        "/accounting",
        "Chart of accounts, journals and approved posting rules.",
        ("accounting.view_account", "accounting.view_journalentry"),
    ),
    (
        "invoicing",
        "Invoices and payments",
        "/invoicing",
        "Supplier and customer invoices, notes, payments and NRS state.",
        (
            "invoicing.view_supplierinvoice",
            "invoicing.view_customerinvoice",
            "invoicing.view_invoicenote",
            "invoicing.view_supplierpayment",
        ),
    ),
    (
        "banking",
        "Banking",
        "/banking",
        "Statement import, matching, reconciliations and petty cash.",
        ("banking.view_bankaccount", "banking.view_banktransaction"),
    ),
    (
        "projects",
        "Projects",
        "/projects",
        "Budgets, commitments, project costs and profitability.",
        ("projects.view_project",),
    ),
    (
        "services",
        "Services",
        "/services",
        "Engineering and maintenance work orders, HSE and reports.",
        ("services.view_workorder",),
    ),
    (
        "leasing",
        "Leasing",
        "/leasing",
        "Equipment register, rental agreements and utilisation.",
        ("leasing.view_equipment",),
    ),
    (
        "reports",
        "Reports",
        "/reports",
        "Operational and financial reports with controlled exports.",
        ("reporting.view_reporting",),
    ),
    (
        "administration",
        "Administration",
        "/administration",
        "Users, roles, access settings and audit access.",
        ("identity.view_user",),
    ),
)


def _module_access(user) -> list[dict]:
    """Show every module, and label the ones this account cannot open."""

    return [
        {
            "id": identifier,
            "label": label,
            "path": path,
            "description": description,
            "readable": not permissions or any(_can(user, item) for item in permissions),
        }
        for identifier, label, path, description, permissions in MODULE_ACCESS
    ]


def _quick_actions(user) -> list[dict]:
    definitions = [
        (
            "create_supplier_invoice",
            "Create supplier invoice",
            "Capture a supplier document for matching and approval.",
            "invoicing.add_supplierinvoice",
            "/invoicing?tab=supplier-invoices&new=1",
        ),
        (
            "draft_customer_invoice",
            "Draft customer invoice",
            "Prepare a customer invoice for review.",
            "invoicing.add_customerinvoice",
            "/invoicing?tab=customer-invoices&new=1",
        ),
        (
            "record_payment",
            "Record payment",
            "Record a supplier payment made outside the system.",
            "invoicing.add_supplierpayment",
            "/invoicing?tab=payments&new=1",
        ),
        (
            "create_purchase_request",
            "Create purchase request",
            "Raise a request for goods or services.",
            "procurement.add_purchaserequest",
            "/procurement?tab=requests&new=1",
        ),
        (
            "upload_statement",
            "Upload bank statement",
            "Import a CSV or XLSX statement for reconciliation.",
            "banking.import_bankstatement",
            "/banking?tab=statements&new=1",
        ),
        (
            "register_project",
            "Register project",
            "Add a project to the delivery portfolio.",
            "projects.add_project",
            "/projects?tab=projects&new=1",
        ),
    ]
    return [
        {"id": identifier, "label": label, "description": description, "link": link}
        for identifier, label, description, permission, link in definitions
        if _can(user, permission)
    ]


def _focus(user, financial: bool) -> dict:
    if financial and (
        _can(user, "procurement.approve_purchaseorder")
        or _can(user, "projects.approve_projectbudget")
    ):
        return {
            "id": "management",
            "title": "Management overview",
            "description": "Company financial position, approvals and delivery commitments.",
        }
    if financial:
        return {
            "id": "finance",
            "title": "Finance workspace",
            "description": "Receivables, payables, payments and reconciliation.",
        }
    if _can(user, "projects.change_project") or _can(user, "projects.add_project"):
        return {
            "id": "projects",
            "title": "Project workspace",
            "description": "Your projects, budgets, costs and milestones.",
        }
    if _can(user, "procurement.add_purchaseorder") or _can(
        user, "procurement.approve_purchaseorder"
    ):
        return {
            "id": "procurement",
            "title": "Procurement workspace",
            "description": "Requests, orders, quotations and deliveries.",
        }
    if _can(user, "inventory.receive_stock") or _can(user, "inventory.issue_stock"):
        return {
            "id": "warehouse",
            "title": "Warehouse workspace",
            "description": "Stock position, receipts, transfers and replenishment.",
        }
    return {
        "id": "general",
        "title": "Your workspace",
        "description": "The tasks and information available to your account.",
    }


def dashboard_payload(user, start: date, end: date) -> dict:
    settings = InvoiceSettings.load()
    financial = _financial_overview(user, start, end)
    focus = _focus(user, financial is not None)
    show_invoices = financial is not None or any(
        _can(user, permission)
        for permission in (
            "invoicing.add_supplierinvoice",
            "invoicing.add_customerinvoice",
            "invoicing.change_supplierinvoice",
            "invoicing.change_customerinvoice",
            "invoicing.approve_supplierinvoice",
            "invoicing.approve_customerinvoice",
        )
    )
    invoice_rows = (
        _invoice_management(user, issued=settings.can_issue) if show_invoices else None
    )
    actions = [action for action in _pending_actions(user) if action["count"] > 0]
    notices = []
    if financial is not None or show_invoices:
        if not settings.can_issue:
            notices.append(
                "Invoice issuance is in test mode. Invoice and payment figures are provisional "
                "document records until Finance Controller and management activation."
            )
        test_documents = (
            SupplierInvoice.objects.filter(is_test=True).count()
            + CustomerInvoice.objects.filter(is_test=True).count()
            + SupplierPayment.objects.filter(is_test=True).count()
            + InvoiceNote.objects.filter(is_test=True).count()
        )
        if test_documents:
            notices.append(
                f"{test_documents} invoice, note or payment record(s) are marked as test data."
            )

    return {
        "generated_at": timezone.now().isoformat(),
        "currency": "NGN",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "focus": focus,
        "issuance_authorised": settings.can_issue,
        "test_mode": not settings.can_issue,
        "notices": notices,
        "financial_overview": financial,
        "invoice_management": invoice_rows,
        "pending_actions": actions,
        "module_access": _module_access(user),
        "quick_actions": _quick_actions(user),
        "operations": _operations(user, focus["id"]),
        "recent_activity": _recent_activity(user, focus["id"]),
    }
