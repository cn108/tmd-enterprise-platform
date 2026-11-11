"""Double-entry rules, journal lifecycle, closing and financial statements.

All money movements pass through :func:`_create_journal`, which refuses an
unbalanced entry before it exists. Every posting path — manual, adjustment,
opening balance, reversal, period close and configured financial event — uses
that same validation and the same immutable journal lines.

No account code, posting rule, fiscal year or retained-earnings account is
created here. D-05 remains unresolved, so the engine can only post against
records an authorised user has explicitly approved.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import (
    ZERO,
    Account,
    AccountingPeriod,
    AccountingSettings,
    JournalEntry,
    JournalLine,
    OpeningBalance,
    PostingRule,
)
from apps.procurement.numbering import next_number

MONEY = Decimal("0.01")


class Conflict(Exception):
    """The request is valid but the accounting records do not allow it."""


def _money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise Conflict(f"{value!r} is not a valid amount.") from exc
    return amount.quantize(MONEY)


def _assert_period_open(period: AccountingPeriod, journal_date: date) -> None:
    if period.status != AccountingPeriod.Status.OPEN:
        raise Conflict("The accounting period is closed.")
    if not (period.start_date <= journal_date <= period.end_date):
        raise Conflict("The journal date falls outside the accounting period.")


def approve_account(account: Account, actor) -> Account:
    if account.approved_at is not None:
        raise Conflict("This account is already approved.")
    if account.created_by_id is not None and account.created_by_id == actor.pk:
        raise Conflict("The person who created the account cannot approve it.")
    account.approved_by = actor
    account.approved_at = timezone.now()
    account.save(update_fields=["approved_by", "approved_at", "updated_at"])
    return account


def approve_posting_rule(rule: PostingRule, actor) -> PostingRule:
    if rule.approved_at is not None:
        raise Conflict("This posting rule is already approved.")
    if rule.created_by_id is not None and rule.created_by_id == actor.pk:
        raise Conflict("The person who created the rule cannot approve it.")
    if not rule.lines.exists():
        raise Conflict("A posting rule needs at least one line before approval.")
    unapproved = rule.lines.select_related("account").filter(account__approved_at__isnull=True)
    if unapproved.exists():
        raise Conflict("Every account on the rule must be approved first.")
    rule.approved_by = actor
    rule.approved_at = timezone.now()
    rule.save(update_fields=["approved_by", "approved_at", "updated_at"])
    return rule


def configure_retained_earnings(account: Account | None, actor) -> AccountingSettings:
    if account is None:
        raise Conflict("Choose the retained-earnings account.")
    if account.account_type != Account.Type.EQUITY:
        raise Conflict("Retained earnings must be an equity account.")
    if not account.is_active:
        raise Conflict("The retained-earnings account is inactive.")
    if not account.is_approved:
        raise Conflict("The retained-earnings account must be approved first.")
    settings = AccountingSettings.load()
    settings.retained_earnings_account = account
    settings.updated_by = actor
    settings.save()
    return settings


def _prepare_lines(lines: Iterable[dict]) -> tuple[list[dict], Decimal, Decimal]:
    prepared = []
    total_debit = ZERO
    total_credit = ZERO
    for index, entry in enumerate(lines, start=1):
        account = entry.get("account")
        if account is None:
            raise Conflict("Every journal line needs an account.")
        if not account.is_active:
            raise Conflict(f"Account {account.code} is inactive.")
        debit = _money(entry.get("debit", ZERO))
        credit = _money(entry.get("credit", ZERO))
        if debit < 0 or credit < 0:
            raise Conflict("Debit and credit amounts cannot be negative.")
        if (debit > 0) == (credit > 0):
            raise Conflict("Each journal line must have a debit or a credit, not both.")
        prepared.append(
            {
                "line_number": index,
                "account": account,
                "debit": debit,
                "credit": credit,
                "description": entry.get("description", ""),
                "project": entry.get("project"),
                "cost_centre": entry.get("cost_centre"),
                "party": entry.get("party"),
                "item": entry.get("item"),
            }
        )
        total_debit += debit
        total_credit += credit
    if not prepared:
        raise Conflict("A journal needs at least one line.")
    if total_debit != total_credit:
        raise Conflict(
            f"The journal does not balance: debits {total_debit} and credits {total_credit}."
        )
    if total_debit == 0:
        raise Conflict("A journal must carry a non-zero amount.")
    return prepared, total_debit, total_credit


@transaction.atomic
def create_journal(
    *,
    journal_date: date,
    period: AccountingPeriod,
    description: str,
    lines,
    actor,
    source_type: str = JournalEntry.Source.MANUAL,
    reason: str = "",
    reversal_of: JournalEntry | None = None,
    posting_rule: PostingRule | None = None,
    event_reference: str = "",
) -> JournalEntry:
    _assert_period_open(period, journal_date)
    if source_type == JournalEntry.Source.ADJUSTMENT and not reason.strip():
        raise Conflict("An adjustment journal needs a reason.")
    prepared, total_debit, total_credit = _prepare_lines(lines)
    journal = JournalEntry.objects.create(
        number=next_number("JV"),
        journal_date=journal_date,
        period=period,
        description=description.strip(),
        source_type=source_type,
        reason=reason.strip(),
        total_debit=total_debit,
        total_credit=total_credit,
        reversal_of=reversal_of,
        posting_rule=posting_rule,
        event_reference=event_reference.strip(),
        created_by=actor,
        updated_by=actor,
    )
    JournalLine.objects.bulk_create([JournalLine(journal=journal, **line) for line in prepared])
    return journal


def submit_journal(journal: JournalEntry, actor) -> JournalEntry:
    if journal.status != JournalEntry.Status.DRAFT:
        raise Conflict("Only a draft journal can be submitted.")
    if journal.lines.count() < 2:
        raise Conflict("A journal needs at least two lines.")
    journal.status = JournalEntry.Status.SUBMITTED
    journal.submitted_at = timezone.now()
    journal.submitted_by = actor
    journal.updated_by = actor
    journal.save(
        update_fields=["status", "submitted_at", "submitted_by", "updated_by", "updated_at"]
    )
    return journal


def approve_journal(journal: JournalEntry, actor) -> JournalEntry:
    if journal.status != JournalEntry.Status.SUBMITTED:
        raise Conflict("Only a submitted journal can be approved.")
    if journal.created_by_id is not None and journal.created_by_id == actor.pk:
        raise Conflict("The person who created the journal cannot approve it.")
    journal.status = JournalEntry.Status.APPROVED
    journal.approved_at = timezone.now()
    journal.approved_by = actor
    journal.updated_by = actor
    journal.save(update_fields=["status", "approved_at", "approved_by", "updated_by", "updated_at"])
    return journal


def _assert_postable(journal: JournalEntry) -> None:
    _assert_period_open(journal.period, journal.journal_date)
    lines = list(journal.lines.select_related("account"))
    if len(lines) < 2:
        raise Conflict("A journal needs at least two lines before it can post.")
    total_debit = ZERO
    total_credit = ZERO
    for line in lines:
        if not line.account.is_active:
            raise Conflict(f"Account {line.account.code} is inactive.")
        if not line.account.is_approved:
            raise Conflict(f"Account {line.account.code} has not been approved.")
        total_debit += line.debit
        total_credit += line.credit
    if total_debit != total_credit or total_debit == 0:
        raise Conflict("The journal lines do not balance.")
    journal.total_debit = _money(total_debit)
    journal.total_credit = _money(total_credit)


def post_journal(journal: JournalEntry, actor) -> JournalEntry:
    if journal.status != JournalEntry.Status.APPROVED:
        raise Conflict("Only an approved journal can be posted.")
    _assert_postable(journal)
    journal.status = JournalEntry.Status.POSTED
    journal.posted_at = timezone.now()
    journal.posted_by = actor
    journal.updated_by = actor
    journal.save(
        update_fields=[
            "status",
            "posted_at",
            "posted_by",
            "total_debit",
            "total_credit",
            "updated_by",
            "updated_at",
        ]
    )
    return journal


@transaction.atomic
def _post_system_journal(
    *,
    source_type: str,
    actor,
    journal_date: date,
    period: AccountingPeriod,
    description: str,
    lines,
    reason: str = "",
    reversal_of: JournalEntry | None = None,
    posting_rule: PostingRule | None = None,
    event_reference: str = "",
) -> JournalEntry:
    journal = create_journal(
        journal_date=journal_date,
        period=period,
        description=description,
        lines=lines,
        actor=actor,
        source_type=source_type,
        reason=reason,
        reversal_of=reversal_of,
        posting_rule=posting_rule,
        event_reference=event_reference,
    )
    _assert_postable(journal)
    journal.status = JournalEntry.Status.POSTED
    journal.posted_at = timezone.now()
    journal.posted_by = actor
    journal.updated_at = timezone.now()
    journal.save(
        update_fields=[
            "status",
            "posted_at",
            "posted_by",
            "total_debit",
            "total_credit",
            "updated_at",
        ]
    )
    return journal


def reverse_journal(
    journal: JournalEntry,
    actor,
    reason: str,
    *,
    period: AccountingPeriod | None = None,
    journal_date: date | None = None,
) -> JournalEntry:
    if journal.status != JournalEntry.Status.POSTED:
        raise Conflict("Only a posted journal can be reversed.")
    if journal.reversal_of_id is not None:
        raise Conflict("A reversal cannot itself be reversed; post an adjustment instead.")
    if JournalEntry.objects.filter(reversal_of=journal).exists():
        raise Conflict("This journal has already been reversed.")
    if not reason.strip():
        raise Conflict("A reversal needs a reason.")
    target_period = period or journal.period
    target_date = journal_date or journal.journal_date
    _assert_period_open(target_period, target_date)
    lines = [
        {
            "account": line.account,
            "debit": line.credit,
            "credit": line.debit,
            "description": f"Reversal of {journal.number}: {line.description}".strip(),
            "project": line.project,
            "cost_centre": line.cost_centre,
            "party": line.party,
            "item": line.item,
        }
        for line in journal.lines.select_related("account").order_by("line_number")
    ]
    return _post_system_journal(
        source_type=JournalEntry.Source.REVERSAL,
        actor=actor,
        journal_date=target_date,
        period=target_period,
        description=f"Reversal of {journal.number}: {journal.description}"[:255],
        lines=lines,
        reason=reason.strip(),
        reversal_of=journal,
    )


def post_opening_balance(opening: OpeningBalance, actor) -> OpeningBalance:
    if opening.status != OpeningBalance.Status.DRAFT:
        raise Conflict("Only a draft opening balance can be posted.")
    if not (opening.fiscal_year.start_date <= opening.as_of_date <= opening.fiscal_year.end_date):
        raise Conflict("The opening balance date falls outside its fiscal year.")
    _assert_period_open(opening.period, opening.as_of_date)
    lines = list(opening.lines.select_related("account").order_by("line_number"))
    if not lines:
        raise Conflict("An opening balance needs at least one line.")
    prepared = [
        {
            "account": line.account,
            "debit": line.debit,
            "credit": line.credit,
            "description": line.description,
            "project": line.project,
            "cost_centre": line.cost_centre,
        }
        for line in lines
    ]
    journal = _post_system_journal(
        source_type=JournalEntry.Source.OPENING_BALANCE,
        actor=actor,
        journal_date=opening.as_of_date,
        period=opening.period,
        description=f"Opening balances {opening.fiscal_year.code}",
        lines=prepared,
        reason=opening.notes,
    )
    opening.status = OpeningBalance.Status.POSTED
    opening.posted_journal = journal
    opening.posted_at = timezone.now()
    opening.posted_by = actor
    opening.updated_by = actor
    opening.save(
        update_fields=[
            "status",
            "posted_journal",
            "posted_at",
            "posted_by",
            "updated_by",
            "updated_at",
        ]
    )
    return opening


def post_event(
    rule: PostingRule,
    actor,
    *,
    journal_date: date,
    period: AccountingPeriod,
    description: str,
    amounts: dict,
    reference: str = "",
    project=None,
    cost_centre=None,
    party=None,
) -> JournalEntry:
    if not rule.is_active:
        raise Conflict("The posting rule is inactive.")
    if not rule.is_approved:
        raise Conflict("The posting rule has not been approved.")
    if not description.strip():
        raise Conflict("A financial event needs a description.")
    reference = reference.strip()
    if (
        reference
        and JournalEntry.objects.filter(posting_rule=rule, event_reference=reference).exists()
    ):
        raise Conflict("This event reference has already been posted for the rule.")
    rule_lines = list(rule.lines.select_related("account").order_by("line_number"))
    if not rule_lines:
        raise Conflict("The posting rule has no lines.")
    known_keys = {line.amount_key for line in rule_lines}
    provided = {key: _money(value) for key, value in amounts.items()}
    if set(provided) - known_keys:
        raise Conflict("An amount key is not used by this posting rule.")
    missing = known_keys - set(provided)
    if missing:
        raise Conflict(f"Missing amounts: {', '.join(sorted(missing))}.")
    lines = []
    for rule_line in rule_lines:
        amount = provided[rule_line.amount_key]
        if amount < 0:
            raise Conflict("Event amounts cannot be negative.")
        if amount == 0:
            continue
        lines.append(
            {
                "account": rule_line.account,
                "debit": amount if rule_line.direction == "debit" else ZERO,
                "credit": amount if rule_line.direction == "credit" else ZERO,
                "description": description,
                "project": project,
                "cost_centre": cost_centre,
                "party": party,
            }
        )
    return _post_system_journal(
        source_type=JournalEntry.Source.EVENT,
        actor=actor,
        journal_date=journal_date,
        period=period,
        description=description,
        lines=lines,
        posting_rule=rule,
        event_reference=reference,
    )


def close_period(period: AccountingPeriod, actor) -> AccountingPeriod:
    if period.status != AccountingPeriod.Status.OPEN:
        raise Conflict("This period is already closed.")
    if (
        JournalEntry.objects.filter(period=period)
        .exclude(status=JournalEntry.Status.POSTED)
        .exists()
    ):
        raise Conflict("Post or remove every unposted journal before closing the period.")
    if OpeningBalance.objects.filter(period=period, status=OpeningBalance.Status.DRAFT).exists():
        raise Conflict("Post the draft opening balance before closing the period.")
    rows = (
        JournalLine.objects.filter(
            journal__period=period,
            journal__status=JournalEntry.Status.POSTED,
            account__account_type__in=[Account.Type.INCOME, Account.Type.EXPENSE],
        )
        .values("account_id", "account__code")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("account__code")
    )
    zeroing = []
    for row in rows:
        balance = (row["debit"] or ZERO) - (row["credit"] or ZERO)
        if balance == 0:
            continue
        account = Account.objects.get(pk=row["account_id"])
        zeroing.append(
            {
                "account": account,
                "debit": -balance if balance < 0 else ZERO,
                "credit": balance if balance > 0 else ZERO,
                "description": "Period close",
            }
        )
    if zeroing:
        settings = AccountingSettings.load()
        retained = settings.retained_earnings_account
        if retained is None:
            raise Conflict("Configure a retained-earnings account before closing the period.")
        if not retained.is_approved or not retained.is_active:
            raise Conflict("The retained-earnings account must be approved and active.")
        if retained.account_type != Account.Type.EQUITY:
            raise Conflict("Retained earnings must be an equity account.")
        debit_total = sum((line["debit"] for line in zeroing), ZERO)
        credit_total = sum((line["credit"] for line in zeroing), ZERO)
        difference = debit_total - credit_total
        if difference > 0:
            zeroing.append(
                {
                    "account": retained,
                    "debit": ZERO,
                    "credit": difference,
                    "description": "Period result to retained earnings",
                }
            )
        elif difference < 0:
            zeroing.append(
                {
                    "account": retained,
                    "debit": -difference,
                    "credit": ZERO,
                    "description": "Period result to retained earnings",
                }
            )
        _post_system_journal(
            source_type=JournalEntry.Source.PERIOD_CLOSE,
            actor=actor,
            journal_date=period.end_date,
            period=period,
            description=f"Close period {period.name}"[:255],
            lines=zeroing,
            reason="Period close",
        )
    period.status = AccountingPeriod.Status.CLOSED
    period.closed_at = timezone.now()
    period.closed_by = actor
    period.updated_by = actor
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_by", "updated_at"])
    return period


def _posted_lines(*, start=None, end=None, period=None, exclude_closing=False):
    lines = JournalLine.objects.filter(journal__status=JournalEntry.Status.POSTED)
    if period is not None:
        lines = lines.filter(journal__period=period)
    if start is not None:
        lines = lines.filter(journal__journal_date__gte=start)
    if end is not None:
        lines = lines.filter(journal__journal_date__lte=end)
    if exclude_closing:
        lines = lines.exclude(journal__source_type=JournalEntry.Source.PERIOD_CLOSE)
    return lines


def trial_balance(*, period: AccountingPeriod | None = None, as_of: date | None = None) -> dict:
    if period is None and as_of is None:
        raise Conflict("Supply an accounting period or an as-of date.")
    lines = _posted_lines(period=period, end=as_of)
    rows = (
        lines.values("account_id", "account__code", "account__name", "account__account_type")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("account__code")
    )
    output = []
    total_debit = ZERO
    total_credit = ZERO
    for row in rows:
        debit = _money(row["debit"] or ZERO)
        credit = _money(row["credit"] or ZERO)
        output.append(
            {
                "account_id": row["account_id"],
                "code": row["account__code"],
                "name": row["account__name"],
                "account_type": row["account__account_type"],
                "debit": debit,
                "credit": credit,
                "balance": _money(debit - credit),
            }
        )
        total_debit += debit
        total_credit += credit
    return {
        "rows": output,
        "total_debit": _money(total_debit),
        "total_credit": _money(total_credit),
        "balanced": total_debit == total_credit,
    }


def general_ledger(account: Account, *, start: date | None = None, end: date | None = None) -> dict:
    lines = _posted_lines(start=start, end=end).filter(account=account)
    if start is not None:
        before = _posted_lines(end=start - timedelta(days=1)).filter(account=account)
        opening = _money(sum((line.debit - line.credit for line in before), ZERO))
    else:
        opening = ZERO
    entries = []
    running = opening
    for line in lines.select_related("journal", "project", "cost_centre").order_by(
        "journal__journal_date", "journal_id", "line_number"
    ):
        running += line.debit - line.credit
        entries.append(
            {
                "journal_id": line.journal_id,
                "journal_number": line.journal.number,
                "journal_date": line.journal.journal_date,
                "description": line.description or line.journal.description,
                "debit": _money(line.debit),
                "credit": _money(line.credit),
                "balance": _money(running),
                "project": line.project_id,
                "cost_centre": line.cost_centre_id,
            }
        )
    return {
        "account_id": account.pk,
        "code": account.code,
        "name": account.name,
        "opening_balance": opening,
        "entries": entries,
        "closing_balance": _money(running),
    }


def financial_statements(*, start: date, end: date) -> dict:
    if end < start:
        raise Conflict("The statement end date cannot precede its start date.")
    period_lines = _posted_lines(start=start, end=end, exclude_closing=True)
    income_rows = []
    expense_rows = []
    income_total = ZERO
    expense_total = ZERO
    grouped = (
        period_lines.filter(account__account_type__in=[Account.Type.INCOME, Account.Type.EXPENSE])
        .values("account_id", "account__code", "account__name", "account__account_type")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("account__code")
    )
    for row in grouped:
        debit = row["debit"] or ZERO
        credit = row["credit"] or ZERO
        if row["account__account_type"] == Account.Type.INCOME:
            amount = _money(credit - debit)
            income_rows.append(
                {"code": row["account__code"], "name": row["account__name"], "amount": amount}
            )
            income_total += amount
        else:
            amount = _money(debit - credit)
            expense_rows.append(
                {"code": row["account__code"], "name": row["account__name"], "amount": amount}
            )
            expense_total += amount

    as_of = _posted_lines(end=end)
    balances = (
        as_of.values("account_id", "account__code", "account__name", "account__account_type")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("account__code")
    )
    asset_rows = []
    liability_rows = []
    equity_rows = []
    asset_total = ZERO
    liability_total = ZERO
    equity_total = ZERO
    unclosed = ZERO
    for row in balances:
        debit = row["debit"] or ZERO
        credit = row["credit"] or ZERO
        if row["account__account_type"] == Account.Type.ASSET:
            amount = _money(debit - credit)
            asset_rows.append(
                {"code": row["account__code"], "name": row["account__name"], "amount": amount}
            )
            asset_total += amount
        elif row["account__account_type"] == Account.Type.LIABILITY:
            amount = _money(credit - debit)
            liability_rows.append(
                {"code": row["account__code"], "name": row["account__name"], "amount": amount}
            )
            liability_total += amount
        elif row["account__account_type"] == Account.Type.EQUITY:
            amount = _money(credit - debit)
            equity_rows.append(
                {"code": row["account__code"], "name": row["account__name"], "amount": amount}
            )
            equity_total += amount
        elif row["account__account_type"] == Account.Type.INCOME:
            unclosed += credit - debit
        else:
            unclosed -= debit - credit
    unclosed = _money(unclosed)
    net_result = _money(income_total - expense_total)
    return {
        "start": start,
        "end": end,
        "income_statement": {
            "income": income_rows,
            "expenses": expense_rows,
            "total_income": _money(income_total),
            "total_expenses": _money(expense_total),
            "net_result": net_result,
        },
        "balance_sheet": {
            "as_of": end,
            "assets": asset_rows,
            "liabilities": liability_rows,
            "equity": equity_rows,
            "total_assets": _money(asset_total),
            "total_liabilities": _money(liability_total),
            "total_equity": _money(equity_total),
            "unclosed_result": unclosed,
            "total_equity_and_liabilities": _money(liability_total + equity_total + unclosed),
            "balanced": _money(asset_total) == _money(liability_total + equity_total + unclosed),
        },
    }
