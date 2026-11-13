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
from django.utils import timezone

from apps.accounting.models import AccountingPeriod, AccountRole, JournalEntry
from apps.accounting.services import Conflict as AccountingConflict
from apps.accounting.services import post_system_journal, resolve_role_account
from apps.core.models import create_audit_event
from apps.invoicing.exceptions import InvoiceConflict
from apps.invoicing.models import (
    ZERO,
    CustomerInvoice,
    CustomerReceipt,
    IdempotencyRecord,
    InvoiceNote,
    InvoiceSettings,
    SupplierInvoice,
    SupplierPayment,
)


def _period_for_date(value, label: str = "document") -> AccountingPeriod:
    period = (
        AccountingPeriod.objects.filter(start_date__lte=value, end_date__gte=value)
        .order_by("start_date")
        .first()
    )
    if period is None:
        raise InvoiceConflict(
            f"No accounting period covers {value.isoformat()}. "
            "Create and open the period before posting."
        )
    if period.status != AccountingPeriod.Status.OPEN:
        raise InvoiceConflict(f"The accounting period covering this {label} is closed.")
    return period


def _period_for(invoice) -> AccountingPeriod:
    return _period_for_date(invoice.invoice_date, "invoice")

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
    if invoice.invoice_notes.filter(status=InvoiceNote.Status.APPROVED).exists():
        raise InvoiceConflict(
            "This invoice has approved credit or debit notes. Note posting is not "
            "configured yet, so posting the gross invoice would make the ledger and "
            "the document balance disagree."
        )
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


def _replay_journal(scope: str, key: str) -> JournalEntry | None:
    if not key:
        return None
    record = (
        IdempotencyRecord.objects.select_for_update().filter(scope=scope, key=key).first()
    )
    if record is None:
        return None
    journal_id = record.response.get("journal_entry")
    journal = JournalEntry.objects.filter(pk=journal_id).first()
    if journal is None:
        raise InvoiceConflict(
            "A previous posting receipt exists but its journal could not be found. "
            "Inspect the document before retrying."
        )
    return journal


def _remember_post(scope: str, key: str, journal: JournalEntry) -> None:
    if not key:
        return
    IdempotencyRecord.objects.create(
        scope=scope,
        key=key,
        response={"journal_entry": journal.pk, "journal_number": journal.number},
    )


@transaction.atomic
def post_invoice(invoice, actor, idempotency_key: str = ""):
    """Post an approved invoice, returning ``(journal, replayed)``."""

    model = SupplierInvoice if isinstance(invoice, SupplierInvoice) else CustomerInvoice
    locked = model.objects.select_for_update().get(pk=invoice.pk)
    kind_slug = "supplier" if isinstance(locked, SupplierInvoice) else "customer"
    scope = f"invoice.post:{kind_slug}:{locked.pk}"
    replay = _replay_journal(scope, idempotency_key)
    if replay is not None:
        return replay, True

    _assert_postable(locked)
    period = _period_for(locked)
    resolve = _account_resolver(locked.invoice_date)

    if isinstance(locked, SupplierInvoice):
        lines = _supplier_lines(locked, resolve)
        kind = "Supplier"
        action = "supplier_invoice.posted"
        entity_type = "invoicing.supplierinvoice"
        party = locked.supplier
    else:
        lines = _customer_lines(locked, resolve)
        kind = "Customer"
        action = "customer_invoice.posted"
        entity_type = "invoicing.customerinvoice"
        party = locked.customer

    if not lines:
        raise InvoiceConflict("This invoice has no amount that can be posted.")

    try:
        journal = post_system_journal(
            source_type=JournalEntry.Source.EVENT,
            actor=actor,
            journal_date=locked.invoice_date,
            period=period,
            description=f"{kind} invoice {locked.number} - {party.legal_name}"[:255],
            lines=lines,
            event_reference=f"{locked._meta.label_lower}:{locked.pk}",
        )
    except AccountingConflict as exc:
        raise InvoiceConflict(str(exc)) from exc

    locked.journal_entry = journal
    locked.updated_by = actor
    locked.save(update_fields=["journal_entry", "updated_by", "updated_at"])

    create_audit_event(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=locked.pk,
        after={
            "number": locked.number,
            "journal": journal.number,
            "total": str(locked.total),
        },
    )
    _remember_post(scope, idempotency_key, journal)
    return journal, False


@transaction.atomic
def post_supplier_payment(payment: SupplierPayment, actor, idempotency_key: str = ""):
    """Post a recorded supplier payment, returning ``(journal, replayed)``."""

    locked = SupplierPayment.objects.select_for_update().get(pk=payment.pk)
    scope = f"payment.post:{locked.pk}"
    replay = _replay_journal(scope, idempotency_key)
    if replay is not None:
        return replay, True

    settings = InvoiceSettings.load()
    if not settings.can_issue:
        raise InvoiceConflict(
            "Stage 7B has not been authorised: production payment posting is disabled."
        )
    if locked.is_test:
        raise InvoiceConflict("A test payment cannot be posted to the ledger.")
    if locked.status != SupplierPayment.Status.RECORDED:
        raise InvoiceConflict("Only a recorded payment can be posted.")
    if locked.journal_entry_id is not None:
        raise InvoiceConflict("This payment has already been posted.")
    if locked.currency != settings.default_currency:
        raise InvoiceConflict(
            "Foreign-currency payment posting is not configured. "
            "Use an approved FX policy before posting this payment."
        )

    period = _period_for_date(locked.payment_date, "payment")
    resolve = _account_resolver(locked.payment_date)
    allocations = list(
        locked.allocations.select_related("supplier_invoice").order_by("id")
    )
    allocated = sum((allocation.amount for allocation in allocations), ZERO)
    if allocated > locked.amount:
        raise InvoiceConflict("Payment allocations exceed the recorded payment amount.")

    for allocation in allocations:
        invoice = allocation.supplier_invoice
        if invoice.status != SupplierInvoice.Status.APPROVED:
            raise InvoiceConflict(
                f"Allocated invoice {invoice.number} is no longer approved."
            )
        if invoice.journal_entry_id is None:
            raise InvoiceConflict(
                f"Invoice {invoice.number} must be posted before its payment."
            )
        if invoice.wht_total != ZERO:
            raise InvoiceConflict(
                "Payment posting against a WHT invoice is not configured. "
                "Approve the WHT payable treatment before posting this payment."
            )
        if invoice.invoice_notes.filter(status=InvoiceNote.Status.APPROVED).exists():
            raise InvoiceConflict(
                f"Invoice {invoice.number} has approved notes. Note posting is not "
                "configured, so its payment cannot be posted yet."
            )
        if invoice.currency != locked.currency:
            raise InvoiceConflict(
                f"Invoice {invoice.number} and the payment use different currencies."
            )

    lines = []
    if allocated:
        lines.append(
            {
                "account": resolve("AP_CONTROL"),
                "debit": allocated,
                "credit": ZERO,
                "description": f"Payment {locked.number} allocated to supplier invoices"[:255],
                "party": locked.supplier,
            }
        )
    unallocated = locked.amount - allocated
    if unallocated:
        lines.append(
            {
                "account": resolve("SUPPLIER_ADVANCES"),
                "debit": unallocated,
                "credit": ZERO,
                "description": f"Unallocated supplier payment {locked.number}"[:255],
                "party": locked.supplier,
            }
        )

    if locked.method == SupplierPayment.Method.CASH:
        credit_account = resolve("CASH")
    elif locked.company_bank_account_id and locked.company_bank_account.gl_account_id:
        credit_account = locked.company_bank_account.gl_account
        if not credit_account.is_approved or not credit_account.is_active:
            raise InvoiceConflict(
                "The payment bank account has no approved, active ledger account."
            )
    else:
        credit_account = resolve("BANK")

    lines.append(
        {
            "account": credit_account,
            "debit": ZERO,
            "credit": locked.amount,
            "description": f"Supplier payment {locked.number} - {locked.supplier.legal_name}"[:255],
            "party": locked.supplier,
        }
    )

    try:
        journal = post_system_journal(
            source_type=JournalEntry.Source.EVENT,
            actor=actor,
            journal_date=locked.payment_date,
            period=period,
            description=f"Supplier payment {locked.number} - {locked.supplier.legal_name}"[:255],
            lines=lines,
            event_reference=f"{locked._meta.label_lower}:{locked.pk}",
        )
    except AccountingConflict as exc:
        raise InvoiceConflict(str(exc)) from exc

    locked.journal_entry = journal
    locked.updated_by = actor
    locked.save(update_fields=["journal_entry", "updated_by", "updated_at"])
    create_audit_event(
        actor=actor,
        action="supplier_payment.posted",
        entity_type="invoicing.supplierpayment",
        entity_id=locked.pk,
        after={
            "number": locked.number,
            "journal": journal.number,
            "amount": str(locked.amount),
            "allocated": str(allocated),
        },
    )
    _remember_post(scope, idempotency_key, journal)
    return journal, False


@transaction.atomic
def post_customer_receipt(receipt: CustomerReceipt, actor, idempotency_key: str = ""):
    """Post an approved customer receipt, returning ``(journal, replayed)``."""

    locked = CustomerReceipt.objects.select_for_update().get(pk=receipt.pk)
    scope = f"customer_receipt.post:{locked.pk}"
    replay = _replay_journal(scope, idempotency_key)
    if replay is not None:
        return replay, True

    settings = InvoiceSettings.load()
    if not settings.can_issue:
        raise InvoiceConflict(
            "Stage 7B has not been authorised: production receipt posting is disabled."
        )
    if locked.is_test:
        raise InvoiceConflict("A test receipt cannot be posted to the ledger.")
    if locked.status != CustomerReceipt.Status.APPROVED:
        raise InvoiceConflict("Only an approved customer receipt can be posted.")
    if locked.journal_entry_id is not None:
        raise InvoiceConflict("This receipt has already been posted.")
    if locked.currency != settings.default_currency:
        raise InvoiceConflict(
            "Foreign-currency receipt posting is not configured. "
            "Use an approved FX policy before posting this receipt."
        )

    period = _period_for_date(locked.receipt_date, "receipt")
    resolve = _account_resolver(locked.receipt_date)
    allocations = list(
        locked.allocations.select_related("invoice")
        .filter(is_reversed=False)
        .order_by("id")
    )
    allocated = sum((allocation.amount for allocation in allocations), ZERO)
    if allocated > locked.amount:
        raise InvoiceConflict("Receipt allocations exceed the recorded receipt amount.")
    for allocation in allocations:
        invoice = allocation.invoice
        if invoice.status != CustomerInvoice.Status.APPROVED:
            raise InvoiceConflict(
                f"Allocated invoice {invoice.number} is no longer approved."
            )
        if invoice.journal_entry_id is None:
            raise InvoiceConflict(
                f"Invoice {invoice.number} must be posted before its receipt."
            )
        if invoice.invoice_notes.filter(status=InvoiceNote.Status.APPROVED).exists():
            raise InvoiceConflict(
                f"Invoice {invoice.number} has approved notes. Note posting is not "
                "configured, so its receipt cannot be posted yet."
            )
        if invoice.currency != locked.currency:
            raise InvoiceConflict(
                f"Invoice {invoice.number} and the receipt use different currencies."
            )

    lines = []
    if locked.method == CustomerReceipt.Method.CASH:
        debit_account = resolve("CASH")
    elif locked.company_bank_account_id and locked.company_bank_account.gl_account_id:
        debit_account = locked.company_bank_account.gl_account
        if not debit_account.is_approved or not debit_account.is_active:
            raise InvoiceConflict(
                "The receipt bank account has no approved, active ledger account."
            )
    else:
        debit_account = resolve("BANK")

    lines.append(
        {
            "account": debit_account,
            "debit": locked.amount,
            "credit": ZERO,
            "description": f"Customer receipt {locked.number} - {locked.customer.legal_name}"[:255],
            "party": locked.customer,
        }
    )
    if allocated:
        lines.append(
            {
                "account": resolve("AR_CONTROL"),
                "debit": ZERO,
                "credit": allocated,
                "description": f"Receipt {locked.number} allocated to customer invoices"[:255],
                "party": locked.customer,
            }
        )
    unallocated = locked.amount - allocated
    if unallocated:
        lines.append(
            {
                "account": resolve("CUSTOMER_ADVANCES"),
                "debit": ZERO,
                "credit": unallocated,
                "description": f"Unapplied customer receipt {locked.number}"[:255],
                "party": locked.customer,
            }
        )

    try:
        journal = post_system_journal(
            source_type=JournalEntry.Source.EVENT,
            actor=actor,
            journal_date=locked.receipt_date,
            period=period,
            description=f"Customer receipt {locked.number} - {locked.customer.legal_name}"[:255],
            lines=lines,
            event_reference=f"{locked._meta.label_lower}:{locked.pk}",
        )
    except AccountingConflict as exc:
        raise InvoiceConflict(str(exc)) from exc

    locked.journal_entry = journal
    locked.status = CustomerReceipt.Status.POSTED
    locked.posted_at = timezone.now()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "journal_entry",
            "status",
            "posted_at",
            "updated_by",
            "updated_at",
        ]
    )
    create_audit_event(
        actor=actor,
        action="customer_receipt.posted",
        entity_type="invoicing.customerreceipt",
        entity_id=locked.pk,
        after={
            "number": locked.number,
            "journal": journal.number,
            "amount": str(locked.amount),
            "allocated": str(allocated),
        },
    )
    _remember_post(scope, idempotency_key, journal)
    return journal, False
