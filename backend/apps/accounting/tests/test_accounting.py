"""Accounting tests: chart approval, balanced journals, closing and reporting."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth.models import Permission
from django.db import DatabaseError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountingSettings,
    FiscalYear,
    JournalEntry,
    JournalLine,
)
from apps.identity.models import User
from apps.projects.models import Project

pytestmark = pytest.mark.django_db


def granted(*codenames: str) -> APIClient:
    user = User.objects.create_user(
        email=f"accounting-{uuid4().hex[:8]}@example.com", full_name="Accounting Actor"
    )
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    client = APIClient()
    client.force_authenticate(user=User.objects.get(pk=user.pk))
    return client


def make_account(
    code: str,
    account_type: str = "asset",
    normal_balance: str | None = None,
    approved: bool = True,
) -> Account:
    return Account.objects.create(
        code=code,
        name=code.title(),
        account_type=account_type,
        normal_balance=normal_balance
        or ("debit" if account_type in {"asset", "expense"} else "credit"),
        approved_at=timezone.now() if approved else None,
    )


def make_period(name: str = "January") -> tuple[FiscalYear, AccountingPeriod]:
    year = FiscalYear.objects.create(
        code="FY26",
        name="2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    period = AccountingPeriod.objects.create(
        fiscal_year=year,
        name=name,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    return year, period


def make_journal(
    period: AccountingPeriod,
    lines: list[dict],
    *,
    journal_date: str = "2026-01-15",
    source_type: str = "manual",
    reason: str = "",
    post: bool = True,
) -> dict:
    creator = granted("create_journal")
    response = creator.post(
        "/api/v1/journals/",
        {
            "journal_date": journal_date,
            "period": period.pk,
            "description": "Test journal",
            "source_type": source_type,
            "reason": reason,
            "lines": lines,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    journal = response.json()
    assert creator.post(f"/api/v1/journals/{journal['id']}/submit/").status_code == 200
    if not post:
        return journal
    approver = granted("approve_journal")
    approved = approver.post(f"/api/v1/journals/{journal['id']}/approve/")
    assert approved.status_code == 200, approved.content
    poster = granted("post_journal")
    posted = poster.post(f"/api/v1/journals/{journal['id']}/post/")
    assert posted.status_code == 200, posted.content
    return posted.json()


def line(account: Account, debit: str = "0", credit: str = "0") -> dict:
    return {"account": account.pk, "debit": debit, "credit": credit}


def make_rule(
    code: str,
    accounts: list[tuple[Account, str, str]],
    *,
    approve: bool = True,
) -> dict:
    manager = granted("manage_postingrules")
    response = manager.post(
        "/api/v1/posting-rules/",
        {
            "code": code,
            "name": code.title(),
            "lines": [
                {"account": account.pk, "direction": direction, "amount_key": key}
                for account, direction, key in accounts
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    rule = response.json()
    if approve:
        approver = granted("approve_postingrule")
        approved = approver.post(f"/api/v1/posting-rules/{rule['id']}/approve/")
        assert approved.status_code == 200, approved.content
        rule = approved.json()
    return rule


def post_event(rule: dict, amounts: dict, *, reference: str = "EV-1") -> object:
    client = granted("post_journal")
    return client.post(
        f"/api/v1/posting-rules/{rule['id']}/post-event/",
        {
            "journal_date": "2026-01-15",
            "period": AccountingPeriod.objects.get().pk,
            "description": "Inventory received",
            "reference": reference,
            "amounts": amounts,
        },
        format="json",
    )


class TestChartOfAccounts:
    def test_no_chart_of_accounts_is_seeded(self, auth_client):
        assert Account.objects.count() == 0
        assert auth_client.get("/api/v1/accounts/").json()["results"] == []

    def test_account_codes_are_normalised_and_approval_requires_a_second_user(self):
        creator = granted("manage_accounts", "approve_account")
        created = creator.post(
            "/api/v1/accounts/",
            {
                "code": " cash ",
                "name": "Cash",
                "account_type": "asset",
                "normal_balance": "debit",
            },
            format="json",
        )
        assert created.status_code == 201, created.content
        body = created.json()
        assert body["code"] == "CASH"
        assert body["is_approved"] is False

        assert creator.post(f"/api/v1/accounts/{body['id']}/approve/").status_code == 409
        approved = granted("approve_account").post(f"/api/v1/accounts/{body['id']}/approve/")
        assert approved.status_code == 200, approved.content
        assert approved.json()["is_approved"] is True
        assert approved.json()["approved_by"].startswith("accounting-")

    def test_account_approval_requires_permission(self, auth_client):
        account = make_account("CASH", approved=False)

        assert auth_client.post(f"/api/v1/accounts/{account.pk}/approve/").status_code == 403


class TestJournalLifecycle:
    def test_unbalanced_journal_is_refused(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")

        response = granted("create_journal").post(
            "/api/v1/journals/",
            {
                "journal_date": "2026-01-15",
                "period": period.pk,
                "description": "Unbalanced",
                "lines": [line(cash, debit="100"), line(equity, credit="90")],
            },
            format="json",
        )

        assert response.status_code == 409
        assert JournalEntry.objects.count() == 0

    def test_a_line_with_two_sides_is_refused(self):
        _, period = make_period()
        cash = make_account("CASH")

        response = granted("create_journal").post(
            "/api/v1/journals/",
            {
                "journal_date": "2026-01-15",
                "period": period.pk,
                "description": "Two sides",
                "lines": [
                    {"account": cash.pk, "debit": "100", "credit": "100"},
                    {"account": cash.pk, "debit": "0", "credit": "0"},
                ],
            },
            format="json",
        )

        assert response.status_code == 409

    def test_balanced_journal_flows_through_approval_to_posting(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        creator = granted("create_journal")
        created = creator.post(
            "/api/v1/journals/",
            {
                "journal_date": "2026-01-15",
                "period": period.pk,
                "description": "Owner contribution",
                "lines": [line(cash, debit="100"), line(equity, credit="100")],
            },
            format="json",
        )
        assert created.status_code == 201, created.content
        journal = created.json()
        assert journal["status"] == "draft"
        assert journal["total_debit"] == "100.00"

        submitted = creator.post(f"/api/v1/journals/{journal['id']}/submit/")
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"

        approver = granted("approve_journal")
        approved = approver.post(f"/api/v1/journals/{journal['id']}/approve/")
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        poster = granted("post_journal")
        posted = poster.post(f"/api/v1/journals/{journal['id']}/post/")
        assert posted.status_code == 200, posted.content
        assert posted.json()["status"] == "posted"
        assert posted.json()["posted_by"].startswith("accounting-")

    def test_creator_cannot_approve_their_own_journal(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        creator = granted("create_journal", "approve_journal")
        journal = creator.post(
            "/api/v1/journals/",
            {
                "journal_date": "2026-01-15",
                "period": period.pk,
                "description": "Self approval",
                "lines": [line(cash, debit="100"), line(equity, credit="100")],
            },
            format="json",
        ).json()
        creator.post(f"/api/v1/journals/{journal['id']}/submit/")

        response = creator.post(f"/api/v1/journals/{journal['id']}/approve/")

        assert response.status_code == 409

    def test_unapproved_account_blocks_posting(self):
        _, period = make_period()
        cash = make_account("CASH", approved=False)
        equity = make_account("EQUITY", "equity")
        creator = granted("create_journal")
        journal = creator.post(
            "/api/v1/journals/",
            {
                "journal_date": "2026-01-15",
                "period": period.pk,
                "description": "Unapproved account",
                "lines": [line(cash, debit="100"), line(equity, credit="100")],
            },
            format="json",
        ).json()
        creator.post(f"/api/v1/journals/{journal['id']}/submit/")
        granted("approve_journal").post(f"/api/v1/journals/{journal['id']}/approve/")

        response = granted("post_journal").post(f"/api/v1/journals/{journal['id']}/post/")

        assert response.status_code == 409
        assert JournalEntry.objects.get(pk=journal["id"]).status == "approved"

    def test_posted_journal_is_immutable(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        journal = make_journal(period, [line(cash, debit="100"), line(equity, credit="100")])

        read = granted("post_journal")
        assert (
            read.patch(f"/api/v1/journals/{journal['id']}/", {}, format="json").status_code == 405
        )
        assert read.delete(f"/api/v1/journals/{journal['id']}/").status_code == 405
        assert JournalEntry.objects.get(pk=journal["id"]).status == "posted"

    def test_database_refuses_raw_changes_to_a_posted_journal(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        journal = make_journal(period, [line(cash, debit="100"), line(equity, credit="100")])

        with pytest.raises(DatabaseError), transaction.atomic():
            JournalEntry.objects.filter(pk=journal["id"]).update(description="Tampered")
        with pytest.raises(DatabaseError), transaction.atomic():
            JournalLine.objects.filter(journal_id=journal["id"]).delete()
        with pytest.raises(DatabaseError), transaction.atomic():
            JournalLine.objects.create(
                journal_id=journal["id"],
                line_number=99,
                account=cash,
                debit=Decimal("1.00"),
            )

        assert JournalEntry.objects.get(pk=journal["id"]).description == "Test journal"

    def test_adjustment_journal_needs_a_reason(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        payload = {
            "journal_date": "2026-01-15",
            "period": period.pk,
            "description": "Correction",
            "source_type": "adjustment",
            "lines": [line(cash, debit="100"), line(equity, credit="100")],
        }
        creator = granted("create_journal")

        missing = creator.post("/api/v1/journals/", payload, format="json")
        assert missing.status_code == 400

        payload["reason"] = "Reclassify contribution"
        assert creator.post("/api/v1/journals/", payload, format="json").status_code == 201

    def test_journal_date_must_fall_inside_the_period(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")

        response = granted("create_journal").post(
            "/api/v1/journals/",
            {
                "journal_date": "2026-02-15",
                "period": period.pk,
                "description": "Wrong period",
                "lines": [line(cash, debit="100"), line(equity, credit="100")],
            },
            format="json",
        )

        assert response.status_code == 409


class TestTrialBalanceAndLedger:
    def _posted_activity(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        expense = make_account("EXPENSE", "expense")
        make_journal(period, [line(cash, debit="1000"), line(equity, credit="1000")])
        make_journal(period, [line(expense, debit="400"), line(cash, credit="400")])
        return period, cash, equity, expense

    def test_trial_balance_is_balanced_and_filters_by_period(self, auth_client):
        period, cash, equity, expense = self._posted_activity()

        response = auth_client.get(f"/api/v1/trial-balance/?period={period.pk}")

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["balanced"] is True
        assert body["total_debit"] == "1400.00"
        assert body["total_credit"] == "1400.00"
        by_code = {row["code"]: row for row in body["rows"]}
        assert by_code["CASH"]["balance"] == "600.00"
        assert by_code["EQUITY"]["balance"] == "-1000.00"

    def test_general_ledger_runs_a_balance(self, auth_client):
        period, cash, _equity, _expense = self._posted_activity()

        response = auth_client.get(
            f"/api/v1/general-ledger/?account={cash.pk}&start=2026-01-01&end=2026-01-31"
        )

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["opening_balance"] == "0.00"
        assert body["closing_balance"] == "600.00"
        assert len(body["entries"]) == 2

    def test_trial_balance_needs_a_period_or_date(self, auth_client):
        assert auth_client.get("/api/v1/trial-balance/").status_code == 400


class TestReversal:
    def test_reversal_posts_the_opposite_and_can_only_happen_once(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        original = make_journal(period, [line(cash, debit="100"), line(equity, credit="100")])
        reverser = granted("reverse_journal")

        response = reverser.post(
            f"/api/v1/journals/{original['id']}/reverse/",
            {"reason": "Posted in error"},
            format="json",
        )

        assert response.status_code == 201, response.content
        reversal = response.json()
        assert reversal["status"] == "posted"
        assert reversal["reversal_of"] == original["id"]
        assert reversal["total_debit"] == "100.00"
        lines = {line["account"]: line for line in reversal["lines"]}
        assert Decimal(lines[cash.pk]["credit"]) == Decimal("100.00")
        assert JournalEntry.objects.get(pk=original["id"]).status == "posted"

        assert (
            reverser.post(
                f"/api/v1/journals/{original['id']}/reverse/",
                {"reason": "Again"},
                format="json",
            ).status_code
            == 409
        )

    def test_closed_period_needs_an_open_target_for_the_reversal(self):
        _, january = make_period("January")
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        original = make_journal(january, [line(cash, debit="100"), line(equity, credit="100")])
        january.status = AccountingPeriod.Status.CLOSED
        january.save(update_fields=["status"])
        february = AccountingPeriod.objects.create(
            fiscal_year=january.fiscal_year,
            name="February",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
        )
        reverser = granted("reverse_journal")

        missing_target = reverser.post(
            f"/api/v1/journals/{original['id']}/reverse/",
            {"reason": "Correction"},
            format="json",
        )
        assert missing_target.status_code == 409

        response = reverser.post(
            f"/api/v1/journals/{original['id']}/reverse/",
            {
                "reason": "Correction",
                "period": february.pk,
                "journal_date": "2026-02-15",
            },
            format="json",
        )
        assert response.status_code == 201, response.content


class TestOpeningBalances:
    def test_opening_balance_posts_once_and_enters_the_ledger(self, auth_client):
        year, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        manager = granted("manage_openingbalance")
        created = manager.post(
            "/api/v1/opening-balances/",
            {
                "fiscal_year": year.pk,
                "period": period.pk,
                "as_of_date": "2026-01-01",
                "lines": [line(cash, debit="500"), line(equity, credit="500")],
            },
            format="json",
        )
        assert created.status_code == 201, created.content
        opening = created.json()
        assert opening["status"] == "draft"

        poster = granted("post_journal")
        posted = poster.post(f"/api/v1/opening-balances/{opening['id']}/post/")
        assert posted.status_code == 200, posted.content
        assert posted.json()["status"] == "posted"
        assert posted.json()["posted_journal_number"].startswith("JV-")

        trial = auth_client.get("/api/v1/trial-balance/?as_of=2026-01-31").json()
        assert trial["balanced"] is True
        assert trial["total_debit"] == "500.00"
        assert poster.post(f"/api/v1/opening-balances/{opening['id']}/post/").status_code == 409
        duplicate = manager.post(
            "/api/v1/opening-balances/",
            {
                "fiscal_year": year.pk,
                "period": period.pk,
                "as_of_date": "2026-01-01",
                "lines": [line(cash, debit="1"), line(equity, credit="1")],
            },
            format="json",
        )
        assert duplicate.status_code == 400

    def test_unbalanced_opening_balance_cannot_post(self):
        year, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        opening = (
            granted("manage_openingbalance")
            .post(
                "/api/v1/opening-balances/",
                {
                    "fiscal_year": year.pk,
                    "period": period.pk,
                    "as_of_date": "2026-01-01",
                    "lines": [line(cash, debit="500"), line(equity, credit="400")],
                },
                format="json",
            )
            .json()
        )

        response = granted("post_journal").post(f"/api/v1/opening-balances/{opening['id']}/post/")

        assert response.status_code == 409


class TestPeriodClose:
    def test_close_transfers_the_result_and_blocks_new_journals(self, auth_client):
        _, period = make_period()
        cash = make_account("CASH")
        income = make_account("INCOME", "income")
        expense = make_account("EXPENSE", "expense")
        retained = make_account("RETAINED", "equity")
        configure = granted("configure_accounting")
        assert (
            configure.patch(
                "/api/v1/accounting-settings/",
                {"retained_earnings_account": retained.pk},
                format="json",
            ).status_code
            == 200
        )
        make_journal(period, [line(cash, debit="1000"), line(income, credit="1000")])
        make_journal(period, [line(expense, debit="400"), line(cash, credit="400")])
        closer = granted("close_period")

        closed = closer.post(f"/api/v1/accounting-periods/{period.pk}/close/")

        assert closed.status_code == 200, closed.content
        assert closed.json()["status"] == "closed"
        assert JournalEntry.objects.filter(source_type="period_close").exists()
        trial = auth_client.get(f"/api/v1/trial-balance/?period={period.pk}").json()
        assert trial["balanced"] is True
        by_code = {row["code"]: row for row in trial["rows"]}
        assert by_code["INCOME"]["balance"] == "0.00"
        assert by_code["EXPENSE"]["balance"] == "0.00"
        assert by_code["RETAINED"]["balance"] == "-600.00"

        statements = auth_client.get(
            "/api/v1/financial-statements/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert statements["income_statement"]["net_result"] == "600.00"
        assert statements["balance_sheet"]["balanced"] is True

        new_journal = granted("create_journal").post(
            "/api/v1/journals/",
            {
                "journal_date": "2026-01-20",
                "period": period.pk,
                "description": "Too late",
                "lines": [line(cash, debit="1"), line(retained, credit="1")],
            },
            format="json",
        )
        assert new_journal.status_code == 409

    def test_close_requires_retained_earnings_when_there_is_a_result(self):
        _, period = make_period()
        cash = make_account("CASH")
        income = make_account("INCOME", "income")
        make_journal(period, [line(cash, debit="100"), line(income, credit="100")])

        response = granted("close_period").post(f"/api/v1/accounting-periods/{period.pk}/close/")

        assert response.status_code == 409

    def test_close_is_blocked_by_an_unposted_journal(self):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        make_journal(
            period,
            [line(cash, debit="100"), line(equity, credit="100")],
            post=False,
        )

        response = granted("close_period").post(f"/api/v1/accounting-periods/{period.pk}/close/")

        assert response.status_code == 409

    def test_periods_cannot_overlap(self):
        year, _period = make_period()
        manager = granted("manage_periods")

        response = manager.post(
            "/api/v1/accounting-periods/",
            {
                "fiscal_year": year.pk,
                "name": "Overlapping",
                "start_date": "2026-01-15",
                "end_date": "2026-02-15",
            },
            format="json",
        )

        assert response.status_code == 400


class TestFinancialStatements:
    def test_income_statement_and_balance_sheet(self, auth_client):
        _, period = make_period()
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        income = make_account("INCOME", "income")
        expense = make_account("EXPENSE", "expense")
        make_journal(period, [line(cash, debit="1000"), line(equity, credit="1000")])
        make_journal(period, [line(cash, debit="1000"), line(income, credit="1000")])
        make_journal(period, [line(expense, debit="400"), line(cash, credit="400")])

        response = auth_client.get("/api/v1/financial-statements/?start=2026-01-01&end=2026-01-31")

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["income_statement"]["total_income"] == "1000.00"
        assert body["income_statement"]["total_expenses"] == "400.00"
        assert body["income_statement"]["net_result"] == "600.00"
        assert body["balance_sheet"]["total_assets"] == "1600.00"
        assert body["balance_sheet"]["unclosed_result"] == "600.00"
        assert body["balance_sheet"]["balanced"] is True


class TestPostingRules:
    def _rule(self, *, approve: bool = True) -> tuple[dict, Account, Account]:
        _, _period = make_period()
        inventory = make_account("INVENTORY")
        payable = make_account("PAYABLE", "liability")
        rule = make_rule(
            "goods_receipt",
            [(inventory, "debit", "inventory"), (payable, "credit", "payable")],
            approve=approve,
        )
        return rule, inventory, payable

    def test_event_posts_a_balanced_journal_with_dimensions(self, auth_client):
        rule, inventory, payable = self._rule()
        project = Project.objects.create(code="PRJ-ACC", name="Project")
        poster = granted("post_journal")

        response = poster.post(
            f"/api/v1/posting-rules/{rule['id']}/post-event/",
            {
                "journal_date": "2026-01-15",
                "period": AccountingPeriod.objects.get().pk,
                "description": "Goods received",
                "reference": "GRN-1",
                "amounts": {"inventory": "500", "payable": "500"},
                "project": project.pk,
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        journal = response.json()
        assert journal["status"] == "posted"
        assert journal["total_debit"] == journal["total_credit"] == "500.00"
        assert {line["account"] for line in journal["lines"]} == {
            inventory.pk,
            payable.pk,
        }
        assert all(line["project"] == project.pk for line in journal["lines"])

    def test_unapproved_rule_cannot_post(self):
        rule, _inventory, _payable = self._rule(approve=False)

        response = post_event(rule, {"inventory": "100", "payable": "100"})

        assert response.status_code == 409

    def test_event_amounts_must_match_the_rule_and_balance(self):
        rule, _inventory, _payable = self._rule()

        unknown = post_event(rule, {"inventory": "100", "other": "100"})
        unbalanced = post_event(rule, {"inventory": "100", "payable": "90"})

        assert unknown.status_code == 409
        assert unbalanced.status_code == 409

    def test_event_reference_is_idempotent(self):
        rule, _inventory, _payable = self._rule()
        first = post_event(rule, {"inventory": "100", "payable": "100"})
        second = post_event(rule, {"inventory": "100", "payable": "100"})

        assert first.status_code == 201, first.content
        assert second.status_code == 409
        assert JournalEntry.objects.filter(posting_rule__isnull=False).count() == 1

    def test_posting_rule_approval_requires_permission_and_a_second_user(self):
        _, _period = make_period()
        inventory = make_account("INVENTORY")
        payable = make_account("PAYABLE", "liability")
        manager = granted("manage_postingrules", "approve_postingrule")
        rule = manager.post(
            "/api/v1/posting-rules/",
            {
                "code": "inventory_receipt",
                "name": "Inventory receipt",
                "lines": [
                    {"account": inventory.pk, "direction": "debit", "amount_key": "inventory"},
                    {"account": payable.pk, "direction": "credit", "amount_key": "payable"},
                ],
            },
            format="json",
        ).json()

        assert manager.post(f"/api/v1/posting-rules/{rule['id']}/approve/").status_code == 409
        assert (
            granted("approve_postingrule")
            .post(f"/api/v1/posting-rules/{rule['id']}/approve/")
            .status_code
            == 200
        )


class TestSettings:
    def test_retained_earnings_must_be_an_approved_equity_account(self):
        cash = make_account("CASH")
        equity = make_account("EQUITY", "equity")
        configure = granted("configure_accounting")

        bad = configure.patch(
            "/api/v1/accounting-settings/",
            {"retained_earnings_account": cash.pk},
            format="json",
        )
        good = configure.patch(
            "/api/v1/accounting-settings/",
            {"retained_earnings_account": equity.pk},
            format="json",
        )

        assert bad.status_code == 409
        assert good.status_code == 200, good.content
        assert good.json()["retained_earnings_account"] == equity.pk
        assert AccountingSettings.load().retained_earnings_account_id == equity.pk


def test_financial_views_require_accounting_permission():
    employee = User.objects.create_user(
        email="unprivileged@example.com", full_name="Unprivileged Employee"
    )
    client = APIClient()
    client.force_authenticate(user=employee)

    assert client.get("/api/v1/accounts/").status_code == 403
    assert client.get("/api/v1/trial-balance/?as_of=2026-01-31").status_code == 403
    assert (
        client.get("/api/v1/financial-statements/?start=2026-01-01&end=2026-01-31").status_code
        == 403
    )

    employee.user_permissions.add(Permission.objects.get(codename="view_account"))
    employee = User.objects.get(pk=employee.pk)
    client.force_authenticate(user=employee)
    assert client.get("/api/v1/accounts/").status_code == 200
    assert client.get("/api/v1/trial-balance/?as_of=2026-01-31").status_code == 200
    assert (
        client.get("/api/v1/financial-statements/?start=2026-01-01&end=2026-01-31").status_code
        == 200
    )
