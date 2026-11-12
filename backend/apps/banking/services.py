"""Banking services: import, matching, reconciliation and cash workflows."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from openpyxl import load_workbook

from apps.banking.models import (
    BankAccount,
    BankingSettings,
    BankStatement,
    BankTransaction,
    BankTransfer,
    CashVoucher,
    PettyCashReplenishment,
    Reconciliation,
    ReconciliationMatch,
    StatementLine,
)
from apps.core.models import create_audit_event
from apps.procurement.numbering import next_number

ZERO = Decimal("0")

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d")


class BankingConflict(Exception):
    """A banking operation is not valid in the current state."""


def _decimal(value) -> Decimal:
    if value is None:
        return ZERO
    text = str(value).strip().replace(",", "").replace("₦", "").replace(" ", "")
    if text in {"", "-", "—"}:
        return ZERO
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise BankingConflict(f"'{value}' is not a valid amount.") from exc
    return -amount if negative else amount


def _date(value, date_format: str | None = None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    formats = (date_format,) if date_format else _DATE_FORMATS
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except (TypeError, ValueError):
            continue
    raise BankingConflict(f"'{value}' is not a recognised date.")


def _first(row: dict, names: list[str], headers: list[str] | None = None) -> str:
    available = headers if headers is not None else list(row.keys())
    for name in names:
        if name in available:
            return name
    return ""


def _read_rows(upload, mapping: dict) -> list[dict]:
    filename = (upload.name or "").lower()
    raw_rows: list[dict] = []
    if filename.endswith(".csv"):
        raw = upload.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        raw_rows = [dict(row) for row in reader]
    elif filename.endswith(".xlsx"):
        workbook = load_workbook(upload, read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return []
        headers = [str(value or "").strip() for value in values[0]]
        for row in values[1:]:
            if not any(value is not None and str(value).strip() for value in row):
                continue
            raw_rows.append(dict(zip(headers, row, strict=False)))
        workbook.close()
    else:
        raise BankingConflict("Only CSV and XLSX bank statements are supported.")

    if not raw_rows:
        raise BankingConflict("The statement contains no data rows.")

    headers = list(raw_rows[0].keys())
    date_key = mapping.get("date") or _first(
        raw_rows[0], ["Date", "Value Date", "Transaction Date", "date", "value_date"], headers
    )
    description_key = mapping.get("description") or _first(
        raw_rows[0], ["Description", "Narration", "Details", "description", "memo"], headers
    )
    reference_key = mapping.get("reference") or _first(
        raw_rows[0], ["Reference", "Ref", "Transaction Reference", "reference"], headers
    )
    debit_key = mapping.get("debit") or _first(
        raw_rows[0], ["Debit", "Withdrawal", "Money Out", "debit"], headers
    )
    credit_key = mapping.get("credit") or _first(
        raw_rows[0], ["Credit", "Deposit", "Money In", "credit"], headers
    )
    amount_key = mapping.get("amount") or _first(
        raw_rows[0], ["Amount", "Transaction Amount", "amount"], headers
    )
    balance_key = mapping.get("balance") or _first(
        raw_rows[0], ["Balance", "Running Balance", "balance"], headers
    )
    external_key = mapping.get("external_id") or _first(
        raw_rows[0], ["Transaction ID", "ID", "External ID", "external_id"], headers
    )

    if not date_key or (not description_key and not reference_key):
        raise BankingConflict("Map a date and a description or reference column.")
    if not (amount_key or debit_key or credit_key):
        raise BankingConflict("Map an amount column, or both debit and credit columns.")
    required = [
        key
        for key in (
            date_key,
            description_key,
            reference_key,
            amount_key,
            debit_key,
            credit_key,
            balance_key,
            external_key,
        )
        if key
    ]
    missing = [key for key in required if key not in headers]
    if missing:
        raise BankingConflict(f"Selected column(s) not found: {', '.join(missing)}.")
    return [
        {
            "date": row.get(date_key),
            "description": row.get(description_key) or row.get(reference_key) or "",
            "reference": row.get(reference_key) or "",
            "debit": row.get(debit_key) if debit_key else "",
            "credit": row.get(credit_key) if credit_key else "",
            "amount": row.get(amount_key) if amount_key else "",
            "balance": row.get(balance_key) if balance_key else "",
            "external_id": row.get(external_key) if external_key else "",
            "raw": {
                str(key): (value.isoformat() if isinstance(value, (date, datetime)) else value)
                for key, value in row.items()
            },
        }
        for row in raw_rows
    ]


def _find_duplicate_line(bank_account: BankAccount, statement: BankStatement, item: dict):
    """Find a likely repeat of the same bank line, including within this import.

    An external bank identifier is authoritative. Otherwise the same signed
    amount, reference and description within a short date window is treated as
    suspected and left for an authorised reviewer to investigate.
    """
    candidates = StatementLine.objects.filter(
        statement__bank_account=bank_account, amount=item["amount"]
    )
    external_id = item["external_id"].strip()
    if external_id:
        exact = candidates.filter(external_id__iexact=external_id).first()
        if exact is not None:
            return exact

    reference = item["reference"].strip()
    description = item["description"].strip()
    if not reference and not description:
        return None
    if reference:
        candidates = candidates.filter(reference__iexact=reference)
        if description:
            candidates = candidates.filter(description__iexact=description)
    else:
        candidates = candidates.filter(description__iexact=description)
    start = item["value_date"] - timedelta(days=7)
    end = item["value_date"] + timedelta(days=7)
    return candidates.filter(value_date__range=(start, end)).order_by("value_date", "id").first()


def _fingerprint(account_id: int, row: dict) -> str:
    payload = "|".join(
        [
            str(account_id),
            str(row["value_date"]),
            str(row["amount"]),
            str(row["reference"]).strip().lower(),
            str(row["description"]).strip().lower(),
            str(row["external_id"]).strip().lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@transaction.atomic
def import_statement(*, bank_account: BankAccount, upload, user, validated: dict) -> BankStatement:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    checksum = digest.hexdigest()
    if BankStatement.objects.filter(bank_account=bank_account, file_sha256=checksum).exists():
        raise BankingConflict(
            "This exact statement file has already been imported for this account."
        )

    mapping = validated.get("column_mapping") or {}
    if isinstance(mapping, str):
        try:
            mapping = json.loads(mapping)
        except json.JSONDecodeError as exc:
            raise BankingConflict("Column mapping must be valid JSON.") from exc
    rows = _read_rows(upload, mapping)
    parsed = []
    for index, row in enumerate(rows, start=1):
        debit = _decimal(row["debit"])
        credit = _decimal(row["credit"])
        signed = _decimal(row["amount"]) if row["amount"] != "" else credit - debit
        if signed == 0 and debit == 0 and credit == 0:
            continue
        if debit == 0 and credit == 0:
            debit, credit = (abs(signed), ZERO) if signed < 0 else (ZERO, signed)
        parsed.append(
            {
                "line_number": index,
                "value_date": _date(row["date"], mapping.get("date_format")),
                "description": str(row["description"] or "").strip()[:500],
                "reference": str(row["reference"] or "").strip()[:160],
                "debit": debit,
                "credit": credit,
                "amount": signed,
                "balance": _decimal(row["balance"]) if row["balance"] != "" else None,
                "external_id": str(row["external_id"] or "").strip()[:120],
                "raw_data": row["raw"],
            }
        )
    if not parsed:
        raise BankingConflict("The statement has no non-zero transaction rows.")

    statement = BankStatement.objects.create(
        number=next_number("BST"),
        bank_account=bank_account,
        reference=validated.get("reference", ""),
        period_start=validated["period_start"],
        period_end=validated["period_end"],
        currency=validated.get("currency") or bank_account.currency,
        opening_balance=validated.get("opening_balance"),
        closing_balance=validated.get("closing_balance"),
        source_file=upload,
        original_filename=upload.name,
        file_sha256=checksum,
        row_count=len(parsed),
        imported_by=user,
        imported_at=timezone.now(),
        notes=validated.get("notes", ""),
        created_by=user,
        updated_by=user,
    )
    for item in parsed:
        fingerprint = _fingerprint(bank_account.pk, item)
        duplicate = _find_duplicate_line(bank_account, statement, item)
        StatementLine.objects.create(
            statement=statement,
            duplicate_of=duplicate,
            duplicate_status=(
                StatementLine.DuplicateStatus.SUSPECTED
                if duplicate
                else StatementLine.DuplicateStatus.CLEAR
            ),
            fingerprint=fingerprint,
            **item,
        )
    reconciliation = Reconciliation.objects.create(
        number=next_number("REC"),
        bank_account=bank_account,
        statement=statement,
        period_start=statement.period_start,
        period_end=statement.period_end,
        statement_opening_balance=statement.opening_balance,
        statement_closing_balance=statement.closing_balance,
        prepared_by=user,
        posting_status=Reconciliation.PostingStatus.BLOCKED,
        posting_blocker="Stage 7B accounting activation and bank posting rules are not approved.",
        created_by=user,
        updated_by=user,
    )
    statement.status = BankStatement.Status.IN_RECONCILIATION
    statement.save(update_fields=["status", "updated_at"])
    create_audit_event(
        actor=user,
        action="bank_statement.imported",
        entity_type="banking.bankstatement",
        entity_id=statement.pk,
        after={"number": statement.number, "rows": statement.row_count},
    )
    create_audit_event(
        actor=user,
        action="bank_reconciliation.created",
        entity_type="banking.reconciliation",
        entity_id=reconciliation.pk,
        after={"number": reconciliation.number, "status": reconciliation.status},
    )
    return statement


def suggestions_for_line(line: StatementLine) -> list[dict]:
    settings = BankingSettings.load()
    tolerance = Decimal(settings.amount_tolerance or ZERO)
    target = abs(line.amount)
    candidates = BankTransaction.objects.filter(
        bank_account=line.statement.bank_account,
        currency=line.statement.currency,
        status__in=[BankTransaction.Status.EXPECTED, BankTransaction.Status.RECORDED],
    ).exclude(matches__status=ReconciliationMatch.Status.CONFIRMED)
    if settings.date_tolerance_days:
        from datetime import timedelta

        candidates = candidates.filter(
            transaction_date__gte=line.value_date - timedelta(days=settings.date_tolerance_days),
            transaction_date__lte=line.value_date + timedelta(days=settings.date_tolerance_days),
        )
    else:
        candidates = candidates.filter(transaction_date=line.value_date)
    results = []
    for candidate in candidates:
        difference = abs(abs(candidate.amount) - target)
        if difference > tolerance:
            continue
        if (candidate.amount > 0) != (line.amount > 0):
            continue
        confidence = Decimal("100.00")
        if difference > 0:
            confidence = max(Decimal("50.00"), Decimal("100.00") - difference)
        reference_match = bool(
            line.reference
            and candidate.reference
            and line.reference.strip().lower() == candidate.reference.strip().lower()
        )
        if not reference_match:
            confidence = min(confidence, Decimal("80.00"))
        results.append(
            {
                "transaction_id": candidate.pk,
                "transaction": candidate.number or str(candidate.pk),
                "transaction_date": candidate.transaction_date.isoformat(),
                "description": transaction.description,
                "reference": transaction.reference,
                "amount": str(transaction.amount),
                "difference": str(difference),
                "reference_match": reference_match,
                "confidence": str(confidence),
            }
        )
    return sorted(
        results, key=lambda item: (-Decimal(item["confidence"]), item["transaction_date"])
    )


def _refresh_line_status(line: StatementLine) -> None:
    confirmed = line.matches.filter(status=ReconciliationMatch.Status.CONFIRMED)
    matched = confirmed.aggregate(total=Sum("amount"))["total"] or ZERO
    if matched <= ZERO:
        line.status = StatementLine.Status.UNMATCHED
    elif matched >= abs(line.amount):
        line.status = StatementLine.Status.MATCHED
    else:
        line.status = StatementLine.Status.PARTIALLY_MATCHED
    line.save(update_fields=["status"])


@transaction.atomic
def match_statement_line(
    *,
    line: StatementLine,
    reconciliation: Reconciliation,
    transaction: BankTransaction,
    amount: Decimal,
    match_type: str,
    user,
    notes: str = "",
) -> ReconciliationMatch:
    line = StatementLine.objects.select_for_update().get(pk=line.pk)
    transaction = BankTransaction.objects.select_for_update().get(pk=transaction.pk)
    if reconciliation.status not in {Reconciliation.Status.DRAFT, Reconciliation.Status.REJECTED}:
        raise BankingConflict("Only a draft reconciliation can be changed.")
    if transaction.bank_account_id != line.statement.bank_account_id:
        raise BankingConflict("The transaction belongs to a different bank account.")
    if transaction.currency != line.statement.currency:
        raise BankingConflict("The statement line and transaction currencies differ.")
    if (transaction.amount > 0) != (line.amount > 0):
        raise BankingConflict("A receipt cannot be matched to an outgoing payment.")
    amount = Decimal(str(amount))
    if amount <= ZERO:
        raise BankingConflict("The match amount must be greater than zero.")
    if amount > line.remaining_amount:
        raise BankingConflict("The match amount exceeds the unmatched statement value.")
    if amount > transaction.remaining_amount:
        raise BankingConflict("The match amount exceeds the unmatched transaction value.")
    if ReconciliationMatch.objects.filter(
        reconciliation=reconciliation,
        statement_line=line,
        bank_transaction=transaction,
    ).exists():
        raise BankingConflict("This statement line is already matched to that transaction.")
    match = ReconciliationMatch.objects.create(
        reconciliation=reconciliation,
        statement_line=line,
        bank_transaction=transaction,
        amount=amount,
        match_type=match_type,
        status=ReconciliationMatch.Status.CONFIRMED,
        confidence=Decimal("100.00"),
        matched_by=user,
        matched_at=timezone.now(),
        notes=notes,
        created_by=user,
        updated_by=user,
    )
    _refresh_line_status(line)
    confirmed_total = (
        transaction.matches.filter(status=ReconciliationMatch.Status.CONFIRMED).aggregate(
            total=Sum("amount")
        )["total"]
        or ZERO
    )
    if confirmed_total >= abs(transaction.amount):
        transaction.status = BankTransaction.Status.RECONCILED
        transaction.save(update_fields=["status", "updated_at"])
    create_audit_event(
        actor=user,
        action="reconciliation_match.confirmed",
        entity_type="banking.reconciliationmatch",
        entity_id=match.pk,
        after={"line": line.pk, "transaction": transaction.pk, "amount": str(amount)},
    )
    return match


@transaction.atomic
def unmatch(match: ReconciliationMatch, user) -> None:
    if match.reconciliation.status not in {
        Reconciliation.Status.DRAFT,
        Reconciliation.Status.REJECTED,
    }:
        raise BankingConflict("Only a draft reconciliation can be changed.")
    line = match.statement_line
    transaction = match.bank_transaction
    match.delete()
    _refresh_line_status(line)
    if transaction is not None:
        transaction.status = BankTransaction.Status.RECORDED
        transaction.save(update_fields=["status", "updated_at"])
    create_audit_event(
        actor=user,
        action="reconciliation_match.removed",
        entity_type="banking.statementline",
        entity_id=line.pk,
        after={"match": match.pk},
    )


@transaction.atomic
def exclude_line(line: StatementLine, user, reason: str) -> StatementLine:
    if line.statement.reconciliation.status not in {
        Reconciliation.Status.DRAFT,
        Reconciliation.Status.REJECTED,
    }:
        raise BankingConflict("Only a draft reconciliation can be changed.")
    if line.matches.filter(status=ReconciliationMatch.Status.CONFIRMED).exists():
        raise BankingConflict("Remove the matches before excluding this line.")
    if not reason.strip():
        raise BankingConflict("An exclusion reason is required.")
    line.status = StatementLine.Status.EXCLUDED
    line.exclusion_reason = reason.strip()
    line.save(update_fields=["status", "exclusion_reason"])
    create_audit_event(
        actor=user,
        action="statement_line.excluded",
        entity_type="banking.statementline",
        entity_id=line.pk,
        after={"reason": reason.strip()},
    )
    return line


@transaction.atomic
def submit_reconciliation(reconciliation: Reconciliation, user) -> Reconciliation:
    reconciliation = Reconciliation.objects.select_for_update().get(pk=reconciliation.pk)
    if reconciliation.status not in {Reconciliation.Status.DRAFT, Reconciliation.Status.REJECTED}:
        raise BankingConflict("Only a draft or rejected reconciliation can be submitted.")
    unresolved = reconciliation.statement.lines.filter(
        status__in=[StatementLine.Status.UNMATCHED, StatementLine.Status.PARTIALLY_MATCHED]
    ).count()
    if unresolved:
        raise BankingConflict(
            f"{unresolved} statement line(s) are still unmatched or partially matched."
        )
    if not reconciliation.statement.lines.exists():
        raise BankingConflict("A reconciliation needs at least one statement line.")
    reconciliation.status = Reconciliation.Status.SUBMITTED
    reconciliation.submitted_at = timezone.now()
    reconciliation.updated_by = user
    reconciliation.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
    create_audit_event(
        actor=user,
        action="bank_reconciliation.submitted",
        entity_type="banking.reconciliation",
        entity_id=reconciliation.pk,
        after={"status": reconciliation.status},
    )
    return reconciliation


@transaction.atomic
def approve_reconciliation(reconciliation: Reconciliation, user) -> Reconciliation:
    reconciliation = Reconciliation.objects.select_for_update().get(pk=reconciliation.pk)
    if reconciliation.status != Reconciliation.Status.SUBMITTED:
        raise BankingConflict("Only a submitted reconciliation can be approved.")
    if reconciliation.prepared_by_id == user.pk:
        raise BankingConflict("A reconciliation cannot be approved by the person who prepared it.")
    unresolved = reconciliation.unmatched_count
    if unresolved:
        raise BankingConflict(
            "A reconciliation with unresolved statement lines cannot be approved."
        )
    reconciliation.status = Reconciliation.Status.APPROVED
    reconciliation.approved_by = user
    reconciliation.approved_at = timezone.now()
    reconciliation.posting_status = Reconciliation.PostingStatus.BLOCKED
    reconciliation.posting_blocker = (
        "Approved for control purposes only. Ledger posting remains blocked until Stage 7B "
        "authorisation and approved account mappings exist."
    )
    reconciliation.updated_by = user
    reconciliation.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "posting_status",
            "posting_blocker",
            "updated_by",
            "updated_at",
        ]
    )
    statement = reconciliation.statement
    statement.status = BankStatement.Status.RECONCILED
    statement.save(update_fields=["status", "updated_at"])
    create_audit_event(
        actor=user,
        action="bank_reconciliation.approved",
        entity_type="banking.reconciliation",
        entity_id=reconciliation.pk,
        after={"status": reconciliation.status, "posting_status": reconciliation.posting_status},
    )
    return reconciliation


@transaction.atomic
def reject_reconciliation(reconciliation: Reconciliation, user, reason: str) -> Reconciliation:
    if reconciliation.status != Reconciliation.Status.SUBMITTED:
        raise BankingConflict("Only a submitted reconciliation can be rejected.")
    if not reason.strip():
        raise BankingConflict("A rejection reason is required.")
    reconciliation.status = Reconciliation.Status.REJECTED
    reconciliation.rejection_reason = reason.strip()
    reconciliation.updated_by = user
    reconciliation.save(update_fields=["status", "rejection_reason", "updated_by", "updated_at"])
    create_audit_event(
        actor=user,
        action="bank_reconciliation.rejected",
        entity_type="banking.reconciliation",
        entity_id=reconciliation.pk,
        after={"reason": reason.strip()},
    )
    return reconciliation


@transaction.atomic
def record_transfer(transfer: BankTransfer, user) -> BankTransfer:
    transfer = BankTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.status != BankTransfer.Status.APPROVED:
        raise BankingConflict("Only an approved transfer can be recorded.")
    outgoing = BankTransaction.objects.create(
        number=next_number("BTX"),
        bank_account=transfer.from_account,
        transaction_date=transfer.transfer_date,
        description=f"Transfer to {transfer.to_account.code}",
        reference=transfer.reference,
        currency=transfer.from_account.currency,
        amount=-transfer.amount,
        source_type=BankTransaction.Source.TRANSFER,
        source_id=transfer.pk,
        status=BankTransaction.Status.RECORDED,
        created_by=user,
        updated_by=user,
    )
    incoming = BankTransaction.objects.create(
        number=next_number("BTX"),
        bank_account=transfer.to_account,
        transaction_date=transfer.transfer_date,
        description=f"Transfer from {transfer.from_account.code}",
        reference=transfer.reference,
        currency=transfer.to_account.currency,
        amount=transfer.amount,
        source_type=BankTransaction.Source.TRANSFER,
        source_id=transfer.pk,
        status=BankTransaction.Status.RECORDED,
        created_by=user,
        updated_by=user,
    )
    transfer.status = BankTransfer.Status.RECORDED
    transfer.recorded_by = user
    transfer.recorded_at = timezone.now()
    transfer.updated_by = user
    transfer.save(
        update_fields=["status", "recorded_by", "recorded_at", "updated_by", "updated_at"]
    )
    create_audit_event(
        actor=user,
        action="bank_transfer.recorded",
        entity_type="banking.banktransfer",
        entity_id=transfer.pk,
        after={"outgoing": outgoing.pk, "incoming": incoming.pk},
    )
    return transfer


@transaction.atomic
def record_cash_voucher(voucher: CashVoucher, user) -> CashVoucher:
    voucher = CashVoucher.objects.select_for_update().get(pk=voucher.pk)
    if voucher.status != CashVoucher.Status.APPROVED:
        raise BankingConflict("Only an approved voucher can be recorded.")
    voucher.status = CashVoucher.Status.RECORDED
    voucher.recorded_by = user
    voucher.recorded_at = timezone.now()
    voucher.updated_by = user
    voucher.save(update_fields=["status", "recorded_by", "recorded_at", "updated_by", "updated_at"])
    create_audit_event(
        actor=user,
        action="cash_voucher.recorded",
        entity_type="banking.cashvoucher",
        entity_id=voucher.pk,
        after={"status": voucher.status},
    )
    return voucher


@transaction.atomic
def record_replenishment(replenishment: PettyCashReplenishment, user) -> PettyCashReplenishment:
    replenishment = PettyCashReplenishment.objects.select_for_update().get(pk=replenishment.pk)
    if replenishment.status != PettyCashReplenishment.Status.APPROVED:
        raise BankingConflict("Only an approved replenishment can be recorded.")
    replenishment.status = PettyCashReplenishment.Status.RECORDED
    replenishment.recorded_by = user
    replenishment.recorded_at = timezone.now()
    replenishment.updated_by = user
    replenishment.save(
        update_fields=["status", "recorded_by", "recorded_at", "updated_by", "updated_at"]
    )
    create_audit_event(
        actor=user,
        action="petty_cash_replenishment.recorded",
        entity_type="banking.pettycashreplenishment",
        entity_id=replenishment.pk,
        after={"status": replenishment.status},
    )
    return replenishment


def sync_supplier_payment(payment) -> BankTransaction | None:
    """Create the company-side expectation for a recorded supplier payment."""
    if not payment.bank_account_id or not payment.company_bank_account_id:
        return None
    if payment.status != "recorded":
        return None
    transaction, created = BankTransaction.objects.get_or_create(
        source_type=BankTransaction.Source.SUPPLIER_PAYMENT,
        source_id=payment.pk,
        defaults={
            "number": next_number("BTX"),
            "bank_account": payment.company_bank_account,
            "transaction_date": payment.payment_date,
            "description": f"Supplier payment {payment.number}",
            "reference": payment.external_reference or payment.number,
            "currency": payment.currency,
            "amount": -payment.amount,
            "status": BankTransaction.Status.RECORDED,
        },
    )
    if not created:
        transaction.bank_account = payment.company_bank_account
        transaction.transaction_date = payment.payment_date
        transaction.currency = payment.currency
        transaction.amount = -payment.amount
        transaction.reference = payment.external_reference or payment.number
        transaction.save()
    return transaction


def account_summary(account: BankAccount) -> dict:
    latest = account.statements.order_by("-period_end", "-id").first()
    lines = StatementLine.objects.filter(statement__bank_account=account)
    unmatched = lines.filter(
        status__in=[StatementLine.Status.UNMATCHED, StatementLine.Status.PARTIALLY_MATCHED]
    ).count()
    pending = account.reconciliations.filter(
        status__in=[Reconciliation.Status.DRAFT, Reconciliation.Status.SUBMITTED]
    ).count()
    return {
        "id": account.pk,
        "code": account.code,
        "name": account.name,
        "bank_name": account.bank_name,
        "currency": account.currency,
        "classification": account.classification,
        "latest_statement": latest.number if latest else "",
        "latest_statement_end": latest.period_end.isoformat() if latest else "",
        "latest_statement_balance": str(latest.closing_balance)
        if latest and latest.closing_balance is not None
        else "",
        "opening_balance": str(account.opening_balance)
        if account.opening_balance is not None
        else "",
        "statement_line_count": lines.count(),
        "unmatched_count": unmatched,
        "pending_reconciliations": pending,
        "is_active": account.is_active,
    }


def report_rows(bank_account: BankAccount | None = None) -> list[dict]:
    query = Reconciliation.objects.select_related("bank_account", "statement").all()
    if bank_account:
        query = query.filter(bank_account=bank_account)
    rows = []
    for reconciliation in query:
        rows.append(
            {
                "id": reconciliation.pk,
                "number": reconciliation.number,
                "bank_account": reconciliation.bank_account.code,
                "statement": reconciliation.statement.number,
                "period_start": reconciliation.period_start.isoformat(),
                "period_end": reconciliation.period_end.isoformat(),
                "status": reconciliation.status,
                "statement_closing_balance": str(reconciliation.statement_closing_balance or ""),
                "matched_lines": reconciliation.matches.filter(
                    status=ReconciliationMatch.Status.CONFIRMED
                )
                .values("statement_line")
                .distinct()
                .count(),
                "unmatched_lines": reconciliation.unmatched_count,
                "excluded_lines": reconciliation.excluded_count,
                "difference": str(reconciliation.difference)
                if reconciliation.difference is not None
                else "",
                "posting_status": reconciliation.posting_status,
            }
        )
    return rows
