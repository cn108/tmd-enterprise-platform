"""Controlled Stage 7B posting for approved supplier and customer invoices.

Posting is intentionally strict:

- activation must be recorded before any live invoice can be posted;
- the invoice must be approved and must not be a test document;
- every account role must have an approved, effective mapping;
- the posting date must fall inside an open accounting period;
- foreign-currency and WHT invoices are refused until those policies are
  configured. They are not silently approximated.

No account, tax rate or policy value is created here. The Finance Controller
supplies those through the existing accounting configuration.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounting.models import AccountingPeriod, AccountRole, JournalEntry
from apps.accounting.services import Conflict as AccountingConflict
from apps.accounting.services import post_system_journal, resolve_role_account
from apps.core.models import create_audit_event
from apps.invoicing.exceptions import InvoiceConflict
from apps.invoicing.models import ZERO, CustomerInvoice, InvoiceSettings, SupplierInvoice


def _period_for(invoice) -> AccountingPeriod:
    period = (
        AccountingPeriod.objects.filter(
            start_date__lte=invoice.invoice_date,
            end_date__gte=invoice.invoice_date,
        )
        .order_by("start_date")
        .first()
    )
    if period is None:
        raise InvoiceConflict(
            f"No accounting period covers {invoice.invoice_date.isoformat()}. "
            "Create and open the period before posting."
        )
    if period.status != AccountingPeriod.Status.OPEN:
        raise InvoiceConflict("The accounting period covering this invoice is closed.")
    return period


def _account_resolver(invoice_date):
    cache: dict[str, object] = {}

    def resolve(role_code: str):
        if role_code in cache:
            return cache[role_code]
        role = AccountRole.objects.filter(code=role_code).first()
        if role is None:
            raise InvoiceConflict(f"Account role {role_code} is not configured.")
        account = resolve_role_account(role, invoice_date)
        if account is None:
            raise InvoiceConflict(
                f"Account role {role_code} has no approved, effective mapping."
            )
        cache[role_code] = account
        return account

    return resolve


def _supplier_lines(invoice: SupplierInvoice, resolve):
    lines = []
    party = invoice.supplier
    for line in invoice.lines.select_related("item").order_by("id"):
        cost_role = "COST_OF_SALES"
        if invoice.project_id:
            cost_role = "PROJECT_COST"
        elif line.item is not None and line.item.kind == "product":
            cost_role = "INVENTORY"

        non_recoverable_vat = line.vat_amount - line.vat_recoverable_amount
        cost_amount = line.subtotal + non_recoverable_vat
        if cost_amount:
            lines.append(
                {
                    "account": resolve(cost_role),
                    "debit": cost_amount,
                    "credit": ZERO,
                    "description": (line.description or f"Supplier invoice {invoice.number}")[:255],
                    "project": invoice.project,
                    "party": party,
                    "item": line.item,
                }
            )
        if line.vat_recoverable_amount:
            lines.append(
                {
                    "account": resolve("INPUT_TAX"),
                    "debit": line.vat_recoverable_amount,
                    "credit": ZERO,
                    "description": f"Input VAT on {invoice.number}"[:255],
                    "project": invoice.project,
                    "party": party,
                }
            )

    payable = invoice.total
    if payable:
        lines.append(
            {
                "account": resolve("AP_CONTROL"),
                "debit": ZERO,
                "credit": payable,
                "description": f"Supplier invoice {invoice.number}"[:255],
                "project": invoice.project,
                "party": party,
            }
        )
    return lines


def _customer_lines(invoice: CustomerInvoice, resolve):
    lines = []
    party = invoice.customer
    for line in invoice.lines.select_related("item").order_by("id"):
        if line.subtotal:
            lines.append(
                {
                    "account": resolve("REVENUE"),
                    "debit": ZERO,
                    "credit": line.subtotal,
                    "description": (line.description or f"Customer invoice {invoice.number}")[:255],
                    "project": invoice.project,
                    "party": party,
                    "item": line.item,
                }
            )
        if line.vat_amount:
            lines.append(
                {
                    "account": resolve("OUTPUT_TAX"),
                    "debit": ZERO,
                    "credit": line.vat_amount,
                    "description": f"Output VAT on {invoice.number}"[:255],
                    "project": invoice.project,
                    "party": party,
                }
            )

    receivable = invoice.total
    if receivable:
        lines.append(
            {
                "account": resolve("AR_CONTROL"),
                "debit": receivable,
                "credit": ZERO,
                "description": f"Customer invoice {invoice.number}"[:255],
                "project": invoice.project,
                "party": party,
            }
        )
    return lines


def _assert_postable(invoice) -> None:
    settings = InvoiceSettings.load()
    if not settings.can_issue:
        raise InvoiceConflict(
            "Stage 7B has not been authorised: production invoice issuance and "
            "posting are disabled."
        )
    if invoice.is_test:
        raise InvoiceConflict("A test invoice cannot be posted to the ledger.")
    expected = (
        SupplierInvoice.Status.APPROVED
        if isinstance(invoice, SupplierInvoice)
        else CustomerInvoice.Status.APPROVED
    )
    if invoice.status != expected:
        raise InvoiceConflict("Only an approved invoice can be posted.")
    if invoice.journal_entry_id is not None:
        raise InvoiceConflict("This invoice has already been posted.")
    if invoice.currency != settings.default_currency:
        raise InvoiceConflict(
            "Foreign-currency invoice posting is not configured. "
            "Use an approved FX policy before posting this invoice."
        )
    if invoice.wht_total != ZERO:
        raise InvoiceConflict(
            "WHT invoice posting is not configured. Approve the WHT payable/receivable "
            "treatment before posting this invoice."
        )


@transaction.atomic
def post_invoice(invoice, actor):
    _assert_postable(invoice)
    period = _period_for(invoice)
    resolve = _account_resolver(invoice.invoice_date)

    if isinstance(invoice, SupplierInvoice):
        lines = _supplier_lines(invoice, resolve)
        kind = "Supplier"
        action = "supplier_invoice.posted"
        entity_type = "invoicing.supplierinvoice"
        party = invoice.supplier
    else:
        lines = _customer_lines(invoice, resolve)
        kind = "Customer"
        action = "customer_invoice.posted"
        entity_type = "invoicing.customerinvoice"
        party = invoice.customer

    if not lines:
        raise InvoiceConflict("This invoice has no amount that can be posted.")

    try:
        journal = post_system_journal(
            source_type=JournalEntry.Source.EVENT,
            actor=actor,
            journal_date=invoice.invoice_date,
            period=period,
            description=f"{kind} invoice {invoice.number} - {party.legal_name}"[:255],
            lines=lines,
            event_reference=f"{invoice._meta.label_lower}:{invoice.pk}",
        )
    except AccountingConflict as exc:
        raise InvoiceConflict(str(exc)) from exc

    invoice.journal_entry = journal
    invoice.updated_by = actor
    invoice.save(update_fields=["journal_entry", "updated_by", "updated_at"])

    create_audit_event(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=invoice.pk,
        after={
            "number": invoice.number,
            "journal": journal.number,
            "total": str(invoice.total),
        },
    )
    return journal
