"""Role bundles must not drift behind newly delivered modules."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group

from apps.core.role_matrix import apply_matrix

pytestmark = pytest.mark.django_db


def permissions(role: str) -> set[str]:
    return {
        f"{permission.content_type.app_label}.{permission.codename}"
        for permission in Group.objects.get(name=role).permissions.select_related("content_type")
    }


def test_later_modules_and_reporting_are_in_the_role_bundles():
    apply_matrix()

    management = permissions("Management")
    assert "banking.view_bankaccount" in management
    assert "services.view_workorder" in management
    assert "leasing.view_equipment" in management
    assert "reporting.view_financialreporting" in management
    assert "reporting.export_reporting" in management


def test_operational_roles_get_operational_but_not_financial_reporting():
    apply_matrix()

    procurement = permissions("Procurement Officer")
    assert "reporting.view_reporting" in procurement
    assert "reporting.view_financialreporting" not in procurement

    operations = permissions("Operations / HSE")
    assert "services.view_workorder" in operations
    assert "leasing.view_equipment" in operations
    assert "reporting.view_reporting" in operations


def test_crud_actions_and_operational_lifecycle_permissions_are_applied():
    apply_matrix()

    procurement = permissions("Procurement Officer")
    assert "procurement.view_purchaseorder" in procurement
    assert "procurement.add_purchaseorder" in procurement
    assert "procurement.change_purchaseorder" in procurement
    assert "procurement.add_goodsreceiptnote" in procurement

    finance = permissions("Finance Officer")
    assert "banking.import_bankstatement" in finance
    assert "banking.match_banktransaction" in finance
    assert "banking.submit_reconciliation" in finance

    controller = permissions("Finance Controller")
    assert "banking.approve_reconciliation" in controller
    assert "banking.approve_banktransfer" in controller

    operations = permissions("Operations / HSE")
    assert "services.add_workorder" in operations
    assert "services.complete_workorder" in operations
    assert "leasing.dispatch_rental" in operations
    assert "leasing.record_inspection" in operations
