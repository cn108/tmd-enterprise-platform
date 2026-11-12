from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.banking.models import (
    BankAccount,
    BankStatement,
    BankTransaction,
    BankTransfer,
    CashAccount,
    CashVoucher,
    Reconciliation,
    StatementLine,
)
from apps.identity.models import User

pytestmark = pytest.mark.django_db


def grant(user: User, *codenames: str) -> None:
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))


def client_for(email: str, *codenames: str) -> APIClient:
    user = User.objects.create_user(email=email, full_name=email.split("@")[0])
    grant(user, *codenames)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_account(code: str = "BANK-001") -> BankAccount:
    return BankAccount.objects.create(
        code=code,
        name="Operating account",
        bank_name="Example Bank",
        account_last4="1234",
        currency="NGN",
        classification=BankAccount.Classification.OPERATING,
    )


def statement_file(name: str = "statement.csv", rows: str | None = None) -> SimpleUploadedFile:
    content = rows or (
        "Date,Description,Reference,Debit,Credit,Balance,Transaction ID\n"
        "2026-01-05,Supplier payment,PAY-001,1250.00,,10000.00,TX-1\n"
        "2026-01-06,Customer receipt,RCP-001,,5000.00,15000.00,TX-2\n"
    )
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


def import_csv(client: APIClient, account: BankAccount, upload=None):
    return client.post(
        "/api/v1/bank-statements/",
        {
            "bank_account": account.pk,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "opening_balance": "8000.00",
            "closing_balance": "11750.00",
            "source_file": upload or statement_file(),
        },
        format="multipart",
    )


def test_bank_account_create_and_opening_balance_date_validation(auth_client):
    grant(User.objects.get(email="staff@example.com"), "manage_bankaccounts", "view_bankaccount")

    created = auth_client.post(
        "/api/v1/company-bank-accounts/",
        {
            "code": "bank-001",
            "name": "Operating account",
            "bank_name": "Example Bank",
            "currency": "NGN",
            "classification": "operating",
        },
        format="json",
    )

    assert created.status_code == 201, created.content
    assert created.json()["code"] == "BANK-001"

    invalid = auth_client.post(
        "/api/v1/company-bank-accounts/",
        {
            "code": "BANK-002",
            "name": "Opening only",
            "bank_name": "Example Bank",
            "opening_balance": "100.00",
        },
        format="json",
    )
    assert invalid.status_code == 400
    assert "opening_balance_date" in invalid.json()["error"]["details"]


def test_csv_statement_import_creates_lines_and_draft_reconciliation(auth_client):
    grant(
        User.objects.get(email="staff@example.com"),
        "import_bankstatement",
        "view_bankstatement",
        "view_statementline",
    )
    account = make_account()

    response = import_csv(auth_client, account)

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["row_count"] == 2
    statement = BankStatement.objects.get(pk=body["id"])
    assert statement.lines.count() == 2
    assert statement.lines.first().amount == Decimal("-1250.00")
    assert statement.lines.last().amount == Decimal("5000.00")
    reconciliation = Reconciliation.objects.get(statement=statement)
    assert reconciliation.status == Reconciliation.Status.DRAFT
    assert reconciliation.posting_status == Reconciliation.PostingStatus.BLOCKED


def test_exact_duplicate_file_is_refused(auth_client):
    grant(User.objects.get(email="staff@example.com"), "import_bankstatement", "view_bankstatement")
    account = make_account()
    first = import_csv(auth_client, account)
    assert first.status_code == 201

    second = import_csv(auth_client, account)

    assert second.status_code == 409
    assert "already been imported" in second.json()["error"]["message"]


def test_duplicate_statement_line_is_flagged_without_being_deleted(auth_client):
    grant(User.objects.get(email="staff@example.com"), "import_bankstatement", "view_statementline")
    account = make_account()
    assert import_csv(auth_client, account).status_code == 201
    second_file = statement_file(
        "statement-2.csv",
        "Date,Description,Reference,Debit,Credit,Balance,Transaction ID\n"
        "2026-01-05,Supplier payment,PAY-001,1250.00,,10000.00,TX-1\n"
        "2026-01-07,Another payment,PAY-003,300.00,,9700.00,TX-3\n",
    )
    response = import_csv(auth_client, account, second_file)

    assert response.status_code == 201, response.content
    duplicate = StatementLine.objects.filter(
        statement_id=response.json()["id"], duplicate_status="suspected"
    ).first()
    assert duplicate is not None
    assert duplicate.duplicate_of_id is not None


def test_duplicate_within_the_same_statement_is_flagged(auth_client):
    grant(User.objects.get(email="staff@example.com"), "import_bankstatement", "view_statementline")
    account = make_account()
    upload = statement_file(
        "statement-duplicate.csv",
        "Date,Description,Reference,Debit,Credit,Balance,Transaction ID\n"
        "2026-01-05,Customer receipt,RCP-001,,5000.00,13000.00,TX-2\n"
        "2026-01-06,Customer receipt,RCP-001,,5000.00,18000.00,TX-2\n",
    )

    response = import_csv(auth_client, account, upload)

    assert response.status_code == 201, response.content
    lines = StatementLine.objects.filter(statement_id=response.json()["id"]).order_by("id")
    assert [line.duplicate_status for line in lines] == ["clear", "suspected"]
    assert lines[1].duplicate_of_id == lines[0].pk


def test_match_rejects_wrong_account_and_supports_partial_split(auth_client):
    grant(
        User.objects.get(email="staff@example.com"),
        "import_bankstatement",
        "match_banktransaction",
        "view_statementline",
        "view_reconciliation",
    )
    account = make_account()
    import_csv(auth_client, account)
    line = StatementLine.objects.filter(statement__bank_account=account, amount__lt=0).first()
    other = make_account("BANK-002")
    wrong = BankTransaction.objects.create(
        bank_account=other,
        transaction_date=date(2026, 1, 5),
        description="Wrong account",
        amount=Decimal("-1250.00"),
        source_type=BankTransaction.Source.MANUAL,
    )
    bad = auth_client.post(
        f"/api/v1/statement-lines/{line.pk}/match/",
        {"bank_transaction": wrong.pk, "amount": "1250.00"},
        format="json",
    )
    assert bad.status_code == 409

    first = BankTransaction.objects.create(
        bank_account=account,
        transaction_date=date(2026, 1, 5),
        description="Payment part 1",
        reference="PAY-001",
        amount=Decimal("-600.00"),
        source_type=BankTransaction.Source.MANUAL,
    )
    second = BankTransaction.objects.create(
        bank_account=account,
        transaction_date=date(2026, 1, 5),
        description="Payment part 2",
        reference="PAY-001",
        amount=Decimal("-650.00"),
        source_type=BankTransaction.Source.MANUAL,
    )

    part = auth_client.post(
        f"/api/v1/statement-lines/{line.pk}/match/",
        {"bank_transaction": first.pk, "amount": "600.00", "match_type": "one_to_many"},
        format="json",
    )
    assert part.status_code == 200, part.content
    line.refresh_from_db()
    assert line.status == StatementLine.Status.PARTIALLY_MATCHED

    rest = auth_client.post(
        f"/api/v1/statement-lines/{line.pk}/match/",
        {"bank_transaction": second.pk, "amount": "650.00", "match_type": "one_to_many"},
        format="json",
    )
    assert rest.status_code == 200, rest.content
    line.refresh_from_db()
    assert line.status == StatementLine.Status.MATCHED


def test_many_to_one_supports_combined_deposits(auth_client):
    grant(
        User.objects.get(email="staff@example.com"),
        "import_bankstatement",
        "match_banktransaction",
        "view_statementline",
        "view_reconciliation",
    )
    account = make_account()
    assert import_csv(auth_client, account).status_code == 201
    reconciliation = Reconciliation.objects.get(bank_account=account)
    transaction = BankTransaction.objects.create(
        bank_account=account,
        transaction_date=date(2026, 1, 6),
        description="Combined deposit",
        amount=Decimal("5000.00"),
        source_type=BankTransaction.Source.MANUAL,
    )
    line = StatementLine.objects.get(statement__bank_account=account, amount__gt=0)
    response = auth_client.post(
        f"/api/v1/statement-lines/{line.pk}/match/",
        {"bank_transaction": transaction.pk, "amount": "5000.00", "match_type": "many_to_one"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert reconciliation.matches.count() == 1


def test_reconciliation_requires_all_lines_resolved_and_independent_approval(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner,
        "import_bankstatement",
        "view_reconciliation",
        "submit_reconciliation",
        "match_banktransaction",
    )
    account = make_account()
    assert import_csv(auth_client, account).status_code == 201
    reconciliation = Reconciliation.objects.get(bank_account=account)

    blocked = auth_client.post(f"/api/v1/reconciliations/{reconciliation.pk}/submit/")
    assert blocked.status_code == 409
    assert "unmatched" in blocked.json()["error"]["message"]

    for line in reconciliation.statement.lines.all():
        response = auth_client.post(
            f"/api/v1/statement-lines/{line.pk}/exclude/",
            {"reason": "Test exclusion - investigated with bank"},
            format="json",
        )
        assert response.status_code == 200, response.content

    submitted = auth_client.post(f"/api/v1/reconciliations/{reconciliation.pk}/submit/")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == "submitted"

    approver = client_for(
        "bank-approver@example.com",
        "view_reconciliation",
        "approve_reconciliation",
    )
    approved = approver.post(f"/api/v1/reconciliations/{reconciliation.pk}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"
    assert approved.json()["posting_status"] == "blocked"


def test_reconciliation_cannot_be_approved_by_its_preparer(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(
        owner,
        "import_bankstatement",
        "view_reconciliation",
        "submit_reconciliation",
        "approve_reconciliation",
        "match_banktransaction",
    )
    account = make_account()
    import_csv(auth_client, account)
    reconciliation = Reconciliation.objects.get(bank_account=account)
    for line in reconciliation.statement.lines.all():
        auth_client.post(
            f"/api/v1/statement-lines/{line.pk}/exclude/",
            {"reason": "Resolved by owner"},
            format="json",
        )
    assert (
        auth_client.post(f"/api/v1/reconciliations/{reconciliation.pk}/submit/").status_code == 200
    )
    response = auth_client.post(f"/api/v1/reconciliations/{reconciliation.pk}/approve/")
    assert response.status_code == 409
    assert "cannot be approved" in response.json()["error"]["message"]


def test_xlsx_statement_import(auth_client):
    grant(User.objects.get(email="staff@example.com"), "import_bankstatement", "view_statementline")
    account = make_account()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Description", "Reference", "Amount", "Balance", "Transaction ID"])
    sheet.append(["2026-02-01", "Bank charge", "CHG-1", "-25.00", "9975.00", "TX-X1"])
    sheet.append(["2026-02-02", "Customer receipt", "RCP-2", "750.00", "10725.00", "TX-X2"])
    stream = __import__("io").BytesIO()
    workbook.save(stream)
    upload = SimpleUploadedFile(
        "statement.xlsx",
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    response = auth_client.post(
        "/api/v1/bank-statements/",
        {
            "bank_account": account.pk,
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
            "source_file": upload,
        },
        format="multipart",
    )

    assert response.status_code == 201, response.content
    assert response.json()["row_count"] == 2
    assert StatementLine.objects.filter(statement_id=response.json()["id"]).count() == 2


def test_transfer_records_two_internal_transactions_and_requires_second_approver(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "manage_banktransfer", "view_banktransfer", "view_bankaccount")
    source = make_account()
    target = make_account("BANK-002")
    created = auth_client.post(
        "/api/v1/bank-transfers/",
        {
            "from_account": source.pk,
            "to_account": target.pk,
            "transfer_date": "2026-01-10",
            "amount": "1000.00",
            "reference": "MOVE-1",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    transfer = BankTransfer.objects.get(pk=created.json()["id"])
    assert auth_client.post(f"/api/v1/bank-transfers/{transfer.pk}/submit/").status_code == 200

    approver = client_for(
        "transfer-approver@example.com",
        "view_banktransfer",
        "approve_banktransfer",
    )
    approved = approver.post(f"/api/v1/bank-transfers/{transfer.pk}/approve/")
    assert approved.status_code == 200, approved.content
    recorded = approver.post(f"/api/v1/bank-transfers/{transfer.pk}/record/")
    assert recorded.status_code == 200, recorded.content
    assert (
        BankTransaction.objects.filter(source_type="transfer", source_id=transfer.pk).count() == 2
    )


def test_petty_cash_voucher_lifecycle(auth_client):
    owner = User.objects.get(email="staff@example.com")
    grant(owner, "manage_pettycash", "view_cashvoucher", "view_cashaccount")
    cash = CashAccount.objects.create(
        code="PETTY-1", name="Petty cash", currency="NGN", opening_balance=Decimal("5000.00")
    )
    created = auth_client.post(
        "/api/v1/cash-vouchers/",
        {
            "cash_account": cash.pk,
            "kind": "expense",
            "voucher_date": "2026-01-11",
            "payee": "Site petty purchase",
            "description": "Bolts and PPE",
            "amount": "250.00",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    voucher = CashVoucher.objects.get(pk=created.json()["id"])
    assert auth_client.post(f"/api/v1/cash-vouchers/{voucher.pk}/submit/").status_code == 200

    approver = client_for(
        "cash-approver@example.com",
        "view_cashvoucher",
        "approve_cashvoucher",
    )
    approved = approver.post(f"/api/v1/cash-vouchers/{voucher.pk}/approve/")
    assert approved.status_code == 200, approved.content
    recorded = approver.post(f"/api/v1/cash-vouchers/{voucher.pk}/record/")
    assert recorded.status_code == 200, recorded.content
    voucher.refresh_from_db()
    assert voucher.status == CashVoucher.Status.RECORDED


def test_banking_read_requires_permission(auth_client):
    make_account()
    response = auth_client.get("/api/v1/company-bank-accounts/")
    assert response.status_code == 403

    user = User.objects.get(email="staff@example.com")
    grant(user, "view_bankaccount")
    auth_client.force_authenticate(user=user)
    response = auth_client.get("/api/v1/company-bank-accounts/")
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_summary_and_unmatched_reports(auth_client):
    grant(
        User.objects.get(email="staff@example.com"),
        "import_bankstatement",
        "view_bankaccount",
        "view_statementline",
    )
    account = make_account()
    import_csv(auth_client, account)

    summary = auth_client.get("/api/v1/banking-summary/")
    assert summary.status_code == 200
    assert summary.json()["count"] == 1
    assert summary.json()["results"][0]["unmatched_count"] == 2

    unmatched = auth_client.get("/api/v1/banking-unmatched-transactions/")
    assert unmatched.status_code == 200
    assert unmatched.json()["count"] == 2
