"""Provisional governance: roles, approval bands, mappings, audit and report."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountRole,
    AccountRoleMapping,
    FinancialEvent,
    FiscalYear,
    JournalEntry,
    PostingRule,
    PostingRuleLine,
)
from apps.accounting.services import (
    approve_posting_rule,
    create_monthly_periods,
    post_event,
    post_financial_event,
)
from apps.core.approvals import ApprovalError, register_approval
from apps.core.models import (
    ApprovalPolicy,
    ApprovalRecord,
    AuditEvent,
    NumberingScheme,
    PolicyDecision,
    create_audit_event,
)
from apps.core.numbering import allocate_document_number
from apps.core.role_matrix import ROLE_NAMES
from apps.identity.models import User

pytestmark = pytest.mark.django_db


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, full_name=email.split("@")[0])


def make_period() -> AccountingPeriod:
    year = FiscalYear.objects.create(
        code="FY26", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
    )
    return AccountingPeriod.objects.create(
        fiscal_year=year,
        name="January",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )


def test_command_applies_roles_bands_and_account_roles_without_accounts():
    call_command("apply_provisional_governance")

    assert Group.objects.count() == 10
    assert set(Group.objects.values_list("name", flat=True)) == set(ROLE_NAMES)
    assert ApprovalPolicy.objects.filter(document_type="purchase_order").count() == 2
    assert ApprovalPolicy.objects.get(code="PO-HIGH-1").required_approvals == 2
    assert ApprovalPolicy.objects.filter(document_type="supplier_invoice").count() == 2
    assert ApprovalPolicy.objects.filter(document_type="payment").count() == 2
    assert Group.objects.get(name="Finance Controller").user_set.count() == 0
    assert AccountRole.objects.count() == 19
    assert PostingRule.objects.count() == 4
    assert Account.objects.count() == 0
    assert PolicyDecision.objects.filter(code="D-04", status="provisional").exists()


def test_high_value_band_needs_two_distinct_approvers():
    call_command("apply_provisional_governance")
    first = make_user("first@example.com")
    second = make_user("second@example.com")
    amount = Decimal("5000000.00")

    one = register_approval(
        document_type="purchase_order", document_id=1, approver=first, amount=amount
    )
    assert one.required == 2
    assert one.recorded == 1
    assert one.final is False

    with pytest.raises(ApprovalError):
        register_approval(
            document_type="purchase_order", document_id=1, approver=first, amount=amount
        )

    two = register_approval(
        document_type="purchase_order", document_id=1, approver=second, amount=amount
    )
    assert two.recorded == 2
    assert two.final is True
    assert ApprovalRecord.objects.filter(document_id=1).count() == 2


def test_creator_cannot_approve_under_the_policy():
    call_command("apply_provisional_governance")
    creator = make_user("creator@example.com")

    with pytest.raises(ApprovalError):
        register_approval(
            document_type="project_budget",
            document_id=2,
            approver=creator,
            amount=Decimal("10.00"),
            creators={creator.pk},
        )


def test_administrator_may_decide_on_a_record_they_created():
    call_command("apply_provisional_governance")
    administrator = User.objects.create_superuser(
        email="admin@example.com", full_name="Administrator", password="Tmd-Pass-2026!"
    )

    outcome = register_approval(
        document_type="purchase_order",
        document_id=88,
        approver=administrator,
        amount=Decimal("10.00"),
        creators={administrator.pk},
    )

    assert outcome.final is True
    assert outcome.recorded == 1
    assert ApprovalRecord.objects.filter(document_id=88, approver=administrator).exists()


def test_role_based_rule_resolves_an_approved_mapping():
    period = make_period()
    inventory = Account.objects.create(
        code="INV",
        name="Inventory",
        account_type="asset",
        normal_balance="debit",
        approved_at=timezone.now(),
    )
    grni = Account.objects.create(
        code="GRNI",
        name="Goods received not invoiced",
        account_type="liability",
        normal_balance="credit",
        approved_at=timezone.now(),
    )
    inventory_role = AccountRole.objects.create(code="INVENTORY", name="Inventory")
    grni_role = AccountRole.objects.create(code="GRNI", name="GRNI")
    for role, account in ((inventory_role, inventory), (grni_role, grni)):
        AccountRoleMapping.objects.create(
            role=role,
            account=account,
            effective_from=date(2026, 1, 1),
            approved_at=timezone.now(),
        )
    rule = PostingRule.objects.create(code="e02", name="E-02", event_type="E-02")
    PostingRuleLine.objects.create(
        rule=rule, line_number=1, account_role=inventory_role, direction="debit", amount_key="value"
    )
    PostingRuleLine.objects.create(
        rule=rule, line_number=2, account_role=grni_role, direction="credit", amount_key="value"
    )
    approver = make_user("rule-approver@example.com")
    approve_posting_rule(rule, approver)

    journal = post_event(
        rule,
        approver,
        journal_date=date(2026, 1, 15),
        period=period,
        description="Receipt before invoice",
        amounts={"value": Decimal("100.00")},
        reference="GRN-1",
    )

    assert journal.status == JournalEntry.Status.POSTED
    assert journal.total_debit == Decimal("100.00")


def test_audit_events_are_immutable_at_the_database():
    event = create_audit_event(actor=None, action="test.created", entity_type="test", entity_id="1")

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_auditevent SET action = %s WHERE id = %s",
                    ["tampered", event.pk],
                )

    assert AuditEvent.objects.get(pk=event.pk).action == "test.created"


def test_configuration_report_reports_blocked_posting(auth_client):
    call_command("apply_provisional_governance")
    response = auth_client.get("/api/v1/governance/configuration-report/")

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["policy_version"] == "1.0-provisional"
    assert body["configuration"]["production_posting_enabled"] is False
    assert any("Finance Controller" in item for item in body["outstanding_controls"])
    assert len(body["implemented"]) >= 8


def test_numbering_is_sequential_and_resets_by_year():
    NumberingScheme.objects.create(
        document_type="test_invoice", prefix="INV", padding=4, reset_yearly=True
    )

    assert allocate_document_number("test_invoice", date(2026, 1, 2)) == "INV-2026-0001"
    assert allocate_document_number("test_invoice", date(2026, 12, 31)) == "INV-2026-0002"
    assert allocate_document_number("test_invoice", date(2027, 1, 1)) == "INV-2027-0001"


def test_monthly_periods_are_clipped_to_the_fiscal_year():
    year = FiscalYear.objects.create(
        code="FY27", name="2027", start_date=date(2026, 7, 1), end_date=date(2027, 6, 30)
    )

    periods = create_monthly_periods(year, make_user("period.creator@example.com"))

    assert len(periods) == 12
    assert periods[0].start_date == date(2026, 7, 1)
    assert periods[0].end_date == date(2026, 7, 31)
    assert periods[-1].start_date == date(2027, 6, 1)
    assert periods[-1].end_date == date(2027, 6, 30)


def test_automatic_event_posting_waits_for_finance_review():
    event = FinancialEvent.objects.create(
        code="E-02",
        source_type="test.receipt",
        source_id=99,
        event_date=date(2026, 1, 15),
        amount=Decimal("100.00"),
    )

    processed = post_financial_event(event, make_user("poster@example.com"))

    assert processed.status == FinancialEvent.Status.PENDING
    assert "Finance Controller" in processed.error


def test_tax_configuration_needs_a_different_reviewer_and_records_audit():
    creator = User.objects.create_user(
        email="tax.creator@example.com", full_name="Tax Creator", password="Tmd-Pass-2026!"
    )
    creator.user_permissions.add(
        Permission.objects.get(content_type__app_label="core", codename="add_taxconfiguration"),
        Permission.objects.get(content_type__app_label="core", codename="change_taxconfiguration"),
    )
    reviewer = User.objects.create_superuser(
        email="tax.reviewer@example.com", full_name="Tax Reviewer", password="Tmd-Pass-2026!"
    )
    creator_client = APIClient()
    creator_client.force_authenticate(user=creator)
    reviewer_client = APIClient()
    reviewer_client.force_authenticate(user=reviewer)

    response = creator_client.post(
        "/api/v1/governance/tax-configuration/",
        {
            "code": "VAT-TEST",
            "name": "Test VAT",
            "tax_type": "vat",
            "rate": "7.5000",
            "effective_from": "2026-01-01",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    tax_id = response.json()["id"]

    own_review = creator_client.post(
        f"/api/v1/governance/tax-configuration/{tax_id}/review/",
        {"notes": "Self review must fail."},
        format="json",
    )
    assert own_review.status_code == 409

    missing_notes = reviewer_client.post(
        f"/api/v1/governance/tax-configuration/{tax_id}/review/", {}, format="json"
    )
    assert missing_notes.status_code == 400

    reviewed = reviewer_client.post(
        f"/api/v1/governance/tax-configuration/{tax_id}/review/",
        {"notes": "Checked against the approved tax advice."},
        format="json",
    )
    assert reviewed.status_code == 200, reviewed.content
    assert reviewed.json()["review_status"] == "reviewed"
    assert AuditEvent.objects.filter(action="tax.reviewed", entity_id=str(tax_id)).exists()

    edited = reviewer_client.patch(
        f"/api/v1/governance/tax-configuration/{tax_id}/",
        {"rate": "8.0000"},
        format="json",
    )
    assert edited.status_code == 409
