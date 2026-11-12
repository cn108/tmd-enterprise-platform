"""Reporting tests: ledger sources, status labels, dates, exports and permissions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountRole,
    AccountRoleMapping,
    FiscalYear,
    JournalEntry,
)
from apps.accounting.services import (
    approve_journal,
    create_journal,
    post_journal,
    submit_journal,
)
from apps.banking.models import BankAccount
from apps.core.models import AuditEvent
from apps.identity.models import User
from apps.invoicing.models import SupplierInvoice
from apps.parties.models import Party
from apps.reporting.models import ReportExport

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(
        email=f"reports-{uuid4().hex[:8]}@example.com", full_name="Reports Reader"
    )
    for codename in ("view_reporting", "view_financialreporting", "export_reporting"):
        user.user_permissions.add(Permission.objects.get(codename=codename))
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def operational_client(db):
    user = User.objects.create_user(
        email=f"reports-ops-{uuid4().hex[:8]}@example.com", full_name="Operational Reader"
    )
    user.user_permissions.add(Permission.objects.get(codename="view_reporting"))
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def actor(*codenames: str):
    user = User.objects.create_user(
        email=f"reporting-{uuid4().hex[:8]}@example.com", full_name="Reporting Actor"
    )
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    return user


def account(code: str, kind: str) -> Account:
    return Account.objects.create(
        code=code,
        name=code.title(),
        account_type=kind,
        normal_balance="debit" if kind in {"asset", "expense"} else "credit",
        approved_at=timezone.now(),
    )


def period() -> AccountingPeriod:
    year = FiscalYear.objects.create(
        code="FY26", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
    )
    return AccountingPeriod.objects.create(
        fiscal_year=year, name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
    )


def journal(period, lines, *, post=True):
    creator = actor("create_journal")
    created = create_journal(
        journal_date=date(2026, 1, 15),
        period=period,
        description="Reporting test",
        lines=lines,
        actor=creator,
    )
    submit_journal(created, creator)
    if post:
        approver = actor("approve_journal", "post_journal")
        approve_journal(created, approver)
        post_journal(created, approver)
    return created


class TestReportAccessAndValidation:
    def test_anonymous_access_is_refused(self, api_client):
        assert api_client.get("/api/v1/reporting/overview/").status_code == 401

    def test_bad_dates_are_rejected(self, auth_client):
        response = auth_client.get("/api/v1/reporting/overview/?start=2026-02-01&end=2026-01-01")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_filter"

    def test_unknown_report_is_404(self, auth_client):
        assert auth_client.get("/api/v1/reporting/nope/").status_code == 404

    def test_reporting_permission_is_required(self, user, api_client):
        api_client.force_authenticate(user=user)
        assert api_client.get("/api/v1/reporting/financial-statements/").status_code == 403

    def test_operational_reader_cannot_open_financial_reports(self, operational_client):
        assert (
            operational_client.get(
                "/api/v1/reporting/financial-statements/?start=2026-01-01&end=2026-01-31"
            ).status_code
            == 403
        )
        assert (
            operational_client.get(
                "/api/v1/reporting/procurement/?start=2026-01-01&end=2026-01-31"
            ).status_code
            == 200
        )

    def test_general_ledger_requires_an_account(self, auth_client):
        response = auth_client.get("/api/v1/reporting/general-ledger/")
        assert response.status_code == 400


class TestDashboard:
    def test_anonymous_dashboard_is_refused(self, api_client):
        assert api_client.get("/api/v1/dashboard/").status_code == 401

    def test_financial_summary_requires_financial_reporting_permission(
        self, auth_client, operational_client
    ):
        full = auth_client.get("/api/v1/dashboard/?start=2026-11-01&end=2026-11-12")
        assert full.status_code == 200
        body = full.json()
        assert body["financial_overview"] is not None
        assert body["focus"]["id"] in {"finance", "management"}
        assert "permission" not in str(body).lower()

        limited = operational_client.get("/api/v1/dashboard/?start=2026-11-01&end=2026-11-12")
        assert limited.status_code == 200
        assert limited.json()["financial_overview"] is None
        assert limited.json()["invoice_management"] is None
        assert limited.json()["notices"] == []

    def test_bad_dashboard_dates_are_rejected(self, auth_client):
        response = auth_client.get("/api/v1/dashboard/?start=2026-12-01&end=2026-11-01")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_filter"

    def test_dashboard_focus_uses_capabilities_not_role_names(self, db):
        project_user = actor("add_project", "change_project", "add_purchaseorder")
        client = APIClient()
        client.force_authenticate(user=project_user)
        body = client.get("/api/v1/dashboard/?start=2026-11-01&end=2026-11-12").json()
        assert body["focus"]["id"] == "projects"
        assert body["financial_overview"] is None
        assert body["operations"]["id"] == "projects"

        procurement_user = actor("add_purchaseorder", "view_purchaseorder")
        client.force_authenticate(user=procurement_user)
        body = client.get("/api/v1/dashboard/?start=2026-11-01&end=2026-11-12").json()
        assert body["focus"]["id"] == "procurement"
        assert body["operations"]["id"] == "procurement"

    def test_dashboard_marks_modules_the_account_cannot_open(self, db):
        user = actor("view_reporting")
        client = APIClient()
        client.force_authenticate(user=user)
        body = client.get("/api/v1/dashboard/?start=2026-11-01&end=2026-11-12").json()
        modules = {row["id"]: row for row in body["module_access"]}
        assert modules["master-data"]["readable"] is True
        assert modules["reports"]["readable"] is True
        assert modules["procurement"]["readable"] is False
        assert modules["administration"]["readable"] is False

    def test_activity_is_scoped_to_the_role_focus(self, db):
        user = actor(
            "view_purchaseorder",
            "view_supplierinvoice",
            "view_supplierpayment",
            "add_purchaseorder",
        )
        for action, entity_type, reference in (
            ("supplier_invoice.approved", "supplier_invoice", "SI-77"),
            ("supplier_payment.approved", "invoicing.supplierpayment", "PAY-77"),
            ("purchase_order.approved", "purchase_order", "PO-77"),
        ):
            AuditEvent.objects.create(
                actor=user,
                action=action,
                entity_type=entity_type,
                after={"number": reference},
                hash=uuid4().hex,
            )
        client = APIClient()
        client.force_authenticate(user=user)
        body = client.get("/api/v1/dashboard/?start=2026-11-01&end=2026-11-12").json()
        assert body["focus"]["id"] == "procurement"
        assert [row["reference"] for row in body["recent_activity"]] == ["PO-77"]

    def test_activity_deduplicates_dual_approval_events(self, db):
        user = actor("view_supplierpayment", "view_financialreporting")
        for action, entity_type in (
            ("approval.recorded", "payment"),
            ("supplier_payment.approved", "invoicing.supplierpayment"),
        ):
            AuditEvent.objects.create(
                actor=user,
                action=action,
                entity_type=entity_type,
                after={"number": "PAY-88"},
                hash=uuid4().hex,
            )
        client = APIClient()
        client.force_authenticate(user=user)
        body = client.get("/api/v1/dashboard/?start=2026-11-01&end=2026-11-12").json()
        payment_rows = [
            row for row in body["recent_activity"] if row["reference"] == "PAY-88"
        ]
        assert len(payment_rows) == 1

    def test_dashboard_does_not_invent_payment_receipts(self, auth_client):
        body = auth_client.get(
            "/api/v1/dashboard/?start=2026-11-01&end=2026-11-12"
        ).json()
        receipts = next(
            card for card in body["financial_overview"] if card["id"] == "payments_received"
        )
        assert receipts["available"] is False
        assert receipts["amount"] is None
        assert receipts["state"] == "no_data"


class TestFinancialReports:
    def test_statements_use_posted_ledger_only(self, auth_client):
        period_obj = period()
        cash = account("CASH", "asset")
        income = account("INCOME", "income")
        expense = account("EXPENSE", "expense")
        journal(
            period_obj,
            [
                {"account": cash, "debit": "1000", "credit": "0"},
                {"account": income, "debit": "0", "credit": "1000"},
            ],
        )
        journal(
            period_obj,
            [
                {"account": expense, "debit": "400", "credit": "0"},
                {"account": cash, "debit": "0", "credit": "400"},
            ],
        )
        journal(
            period_obj,
            [
                {"account": cash, "debit": "50", "credit": "0"},
                {"account": income, "debit": "0", "credit": "50"},
            ],
            post=False,
        )

        body = auth_client.get(
            "/api/v1/reporting/financial-statements/?start=2026-01-01&end=2026-01-31"
        ).json()

        assert body["source"] == "posted_journal_lines"
        assert body["income_statement"]["total_income"] == "1000.00"
        assert body["income_statement"]["total_expenses"] == "400.00"
        assert body["income_statement"]["net_result"] == "600.00"
        assert body["trial_balance_balanced"] is True
        assert JournalEntry.objects.filter(status="submitted").exists()

    def test_trial_balance_and_journal_register(self, auth_client):
        period_obj = period()
        cash = account("CASH", "asset")
        equity = account("EQUITY", "equity")
        journal(
            period_obj,
            [
                {"account": cash, "debit": "500", "credit": "0"},
                {"account": equity, "debit": "0", "credit": "500"},
            ],
        )
        trial = auth_client.get("/api/v1/reporting/trial-balance/?end=2026-01-31").json()
        register = auth_client.get(
            "/api/v1/reporting/journal-register/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert trial["balanced"] is True
        assert trial["total_debit"] == "500.00"
        assert register["posted_count"] == 1
        assert register["unposted_count"] == 0

    def test_cash_flow_refuses_to_guess_cash_accounts(self, auth_client):
        body = auth_client.get(
            "/api/v1/reporting/cash-flow/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert body["available"] is False
        assert "linked" in body["reason"]

    def test_cash_flow_uses_linked_bank_gl_accounts(self, auth_client):
        period_obj = period()
        cash = account("CASH", "asset")
        income = account("INCOME", "income")
        journal(
            period_obj,
            [
                {"account": cash, "debit": "750", "credit": "0"},
                {"account": income, "debit": "0", "credit": "750"},
            ],
        )
        BankAccount.objects.create(
            code="BANK-REP",
            name="Operating",
            bank_name="Test Bank",
            account_name="TMD",
            account_last4="0001",
            currency="NGN",
            classification="operating",
            opening_balance=Decimal("0"),
            opening_balance_date=date(2026, 1, 1),
            gl_account=cash,
        )
        body = auth_client.get(
            "/api/v1/reporting/cash-flow/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert body["available"] is True
        assert body["net_change"] == "750.00"
        assert body["closing_cash"] == "750.00"
        assert body["by_activity"] == [{"activity": "Operating", "amount": "750.00"}]

    def test_cash_flow_uses_account_roles_instead_of_guessing(self, auth_client):
        period_obj = period()
        cash = account("CASH", "asset")
        receivable = account("AR", "asset")
        role = AccountRole.objects.create(code="AR_CONTROL", name="Trade receivables")
        AccountRoleMapping.objects.create(
            role=role,
            account=receivable,
            effective_from=date(2026, 1, 1),
            approved_at=timezone.now(),
        )
        journal(
            period_obj,
            [
                {"account": cash, "debit": "300", "credit": "0"},
                {"account": receivable, "debit": "0", "credit": "300"},
            ],
        )
        BankAccount.objects.create(
            code="BANK-REP-ROLE",
            name="Operating",
            bank_name="Test Bank",
            account_name="TMD",
            account_last4="0002",
            currency="NGN",
            classification="operating",
            opening_balance=Decimal("0"),
            opening_balance_date=date(2026, 1, 1),
            gl_account=cash,
        )
        body = auth_client.get(
            "/api/v1/reporting/cash-flow/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert body["complete"] is True
        assert body["by_activity"] == [{"activity": "Operating", "amount": "300.00"}]

    def test_cash_flow_marks_unmapped_balance_sheet_accounts_as_incomplete(self, auth_client):
        period_obj = period()
        cash = account("CASH", "asset")
        equipment = account("PPE", "asset")
        journal(
            period_obj,
            [
                {"account": cash, "debit": "900", "credit": "0"},
                {"account": equipment, "debit": "0", "credit": "900"},
            ],
        )
        BankAccount.objects.create(
            code="BANK-REP-PPE",
            name="Operating",
            bank_name="Test Bank",
            account_name="TMD",
            account_last4="0003",
            currency="NGN",
            classification="operating",
            opening_balance=Decimal("0"),
            opening_balance_date=date(2026, 1, 1),
            gl_account=cash,
        )
        body = auth_client.get(
            "/api/v1/reporting/cash-flow/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert body["complete"] is False
        assert body["unclassified_accounts"] == ["PPE"]
        assert "account-role mapping" in body["warnings"][0]
        statements = auth_client.get(
            "/api/v1/reporting/financial-statements/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert statements["complete"] is False
        assert any("PPE" in warning for warning in statements["warnings"])


class TestOperationalReports:
    def test_payables_ageing_uses_approved_invoice_balances(self, auth_client):
        supplier = Party.objects.create(code="SUP-REP", legal_name="Supplier")
        SupplierInvoice.objects.create(
            number="SI-REP-1",
            supplier_invoice_number="INV-1",
            supplier_invoice_number_normalized="INV-1",
            supplier=supplier,
            invoice_date=date(2026, 1, 1),
            tax_point_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            currency="NGN",
            status=SupplierInvoice.Status.APPROVED,
            subtotal=Decimal("100.00"),
            total=Decimal("100.00"),
            payment_due=Decimal("100.00"),
        )
        SupplierInvoice.objects.create(
            number="SI-REP-2",
            supplier_invoice_number="INV-2",
            supplier_invoice_number_normalized="INV-2",
            supplier=supplier,
            invoice_date=date(2026, 1, 1),
            tax_point_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            currency="NGN",
            status=SupplierInvoice.Status.DRAFT,
            subtotal=Decimal("900.00"),
            total=Decimal("900.00"),
            payment_due=Decimal("900.00"),
        )
        body = auth_client.get("/api/v1/reporting/payables-ageing/?end=2026-01-31").json()
        assert body["total"] == "100.00"
        assert body["source"] == "approved_supplier_invoices"
        assert body["buckets"][1] == {"bucket": "1–30 days", "amount": "100.00"}

    def test_inventory_report_without_policy_is_explicit(self, auth_client):
        body = auth_client.get(
            "/api/v1/reporting/inventory/?start=2026-01-01&end=2026-01-31"
        ).json()
        assert body["valuation_available"] is False
        assert "valuation method" in body["valuation_error"]

    def test_overview_separates_actual_and_operational_values(self, auth_client):
        body = auth_client.get("/api/v1/reporting/overview/?start=2026-01-01&end=2026-01-31").json()
        assert body["actual"]["source"] == "posted_journal_lines"
        assert "definitions" in body
        assert body["inventory"]["available"] is False
        # Gross profit must never be substituted with the net result.
        assert body["actual"]["gross_profit"]["available"] is False
        assert body["actual"]["gross_profit"]["value"] == ""

    def test_gross_profit_requires_an_approved_cost_of_sales_mapping(self, auth_client):
        period_obj = period()
        income = account("REVENUE", "income")
        cost = account("COGS", "expense")
        cash = account("CASH", "asset")
        journal(
            period_obj,
            [
                {"account": cash, "debit": "1000", "credit": "0"},
                {"account": income, "debit": "0", "credit": "1000"},
            ],
        )
        journal(
            period_obj,
            [
                {"account": cost, "debit": "400", "credit": "0"},
                {"account": cash, "debit": "0", "credit": "400"},
            ],
        )
        role = AccountRole.objects.create(code="COST_OF_SALES", name="Cost of sales")
        AccountRoleMapping.objects.create(
            role=role,
            account=cost,
            effective_from=date(2026, 1, 1),
            approved_at=timezone.now(),
        )
        body = auth_client.get("/api/v1/reporting/overview/?start=2026-01-01&end=2026-01-31").json()
        assert body["actual"]["gross_profit"] == {
            "available": True,
            "value": "600.00",
            "reason": "",
        }


class TestExports:
    def test_csv_export_preserves_values(self, auth_client):
        response = auth_client.get(
            "/api/v1/reporting/overview/export/?start=2026-01-01&end=2026-01-31&output=csv"
        )
        assert response.status_code == 200, response.content
        assert response["Content-Type"].startswith("text/csv")
        assert "actual.revenue" in response.content.decode()
        assert ReportExport.objects.filter(report_name="overview", export_format="csv").exists()

    def test_pdf_export_is_a_pdf(self, auth_client):
        response = auth_client.get(
            "/api/v1/reporting/overview/export/?start=2026-01-01&end=2026-01-31&output=pdf"
        )
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")

    def test_csv_export_neutralises_spreadsheet_formulas(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "apps.reporting.views.report_payload",
            lambda *args, **kwargs: {
                "start": "2026-01-01",
                "end": "2026-01-31",
                "note": "=HYPERLINK(\"https://example.invalid\")",
                "negative": "-10.00",
            },
        )
        response = auth_client.get(
            "/api/v1/reporting/overview/export/?start=2026-01-01&end=2026-01-31&output=csv"
        )
        body = response.content.decode()
        assert "'=HYPERLINK" in body
        assert "-10.00" in body
        assert "'-10.00" not in body
