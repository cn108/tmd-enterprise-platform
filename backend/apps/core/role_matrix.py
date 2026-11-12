"""The provisional nine-role permission matrix plus the Finance Controller.

This is the policy supplied on 12 November 2026, recorded as provisional. It is
deliberately data, not role-name checks in views: the same mechanism can accept
the reviewed matrix later without code changes.

Nine roles are used. The earlier eleven-role draft's HSE capabilities are folded
into Operations / HSE, and Requester is not a role because every authenticated
employee may raise a purchase request. This reduction is recorded in the
configuration report and is reversible by an access administrator.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.db.models import Q

from apps.core.models import PolicyDecision

ROLE_NAMES = (
    "System Administrator",
    "Management",
    "Accountant",
    "Finance Controller",
    "Finance Officer",
    "Procurement Officer",
    "Project Manager",
    "Storekeeper",
    "Operations / HSE",
    "Auditor",
)


def _permissions(codenames):
    return Permission.objects.filter(codename__in=codenames)


def _crud(app_labels, actions=("view", "add", "change")):
    """Every non-delete permission for the given apps.

    Delete is never granted: master records are deactivated and transaction
    history is immutable.
    """

    prefixes = tuple(f"{action}_" for action in actions)
    query = Q()
    for prefix in prefixes:
        query |= Q(codename__startswith=prefix)
    return Permission.objects.filter(query, content_type__app_label__in=app_labels)


def _view(app_labels):
    return Permission.objects.filter(
        content_type__app_label__in=app_labels, codename__startswith="view_"
    )


MATRIX = {
    "System Administrator": (
        _crud(["organisation", "parties", "catalogue", "warehousing", "documents"])
        | _view(
            [
                "procurement",
                "inventory",
                "projects",
                "accounting",
                "core",
                "banking",
                "services",
                "leasing",
            ]
        )
        | _view(["invoicing"])
        | _permissions(
            [
                "view_group",
                "add_group",
                "change_group",
                "view_permission",
                "view_user",
                "add_user",
                "change_user",
                "manage_accounts",
                "manage_fiscalyears",
                "manage_periods",
                "manage_openingbalance",
                "manage_postingrules",
                "configure_accounting",
                "view_audit",
                "view_taxconfiguration",
                "add_taxconfiguration",
                "change_taxconfiguration",
                "view_taxprofile",
                "add_taxprofile",
                "change_taxprofile",
                "view_numberingscheme",
                "add_numberingscheme",
                "change_numberingscheme",
                "manage_invoicesettings",
                "email_supplierinvoice",
                "email_customerinvoice",
                "view_reporting",
                "view_financialreporting",
                "export_reporting",
            ]
        )
    ),
    "Management": (
        _view(
            [
                "organisation",
                "parties",
                "catalogue",
                "warehousing",
                "documents",
                "projects",
                "procurement",
                "inventory",
                "accounting",
                "invoicing",
                "banking",
                "services",
                "leasing",
            ]
        )
        | _permissions(
            [
                "approve_purchaserequest",
                "approve_purchaseorder",
                "approve_projectbudget",
                "approve_journal",
                "close_period",
                "reopen_period",
                "view_group",
                "view_permission",
                "view_user",
                "view_audit",
                "approve_supplierinvoice",
                "approve_customerinvoice",
                "approve_invoicenote",
                "approve_payment",
                "email_supplierinvoice",
                "email_customerinvoice",
                "add_purchaserequest",
                "approve_reconciliation",
                "approve_servicecontract",
                "accept_workorder",
                "approve_rentalagreement",
                "view_reporting",
                "view_financialreporting",
                "export_reporting",
            ]
        )
    ),
    "Accountant": (
        _view(
            [
                "organisation",
                "parties",
                "catalogue",
                "warehousing",
                "documents",
                "projects",
                "procurement",
                "inventory",
                "banking",
                "services",
                "leasing",
            ]
        )
        | _crud(["accounting"])
        | _crud(["invoicing"])
        | _permissions(
            [
                "approve_account",
                "approve_postingrule",
                "approve_journal",
                "post_journal",
                "reverse_journal",
                "close_period",
                "reopen_period",
                "configure_accounting",
                "add_purchaserequest",
                "approve_reconciliation",
                "manage_bankaccounts",
                "set_valuation_method",
                "view_audit",
                "view_taxconfiguration",
                "add_taxconfiguration",
                "change_taxconfiguration",
                "view_taxprofile",
                "add_taxprofile",
                "change_taxprofile",
                "view_numberingscheme",
                "view_reporting",
                "view_financialreporting",
                "export_reporting",
                "email_supplierinvoice",
                "email_customerinvoice",
            ]
        )
    ),
    "Finance Controller": (
        _view(
            [
                "organisation",
                "parties",
                "catalogue",
                "warehousing",
                "documents",
                "projects",
                "procurement",
                "inventory",
                "accounting",
                "invoicing",
                "banking",
                "services",
                "leasing",
                "core",
            ]
        )
        | _permissions(
            [
                "approve_supplierinvoice",
                "approve_customerinvoice",
                "approve_invoicenote",
                "approve_payment",
                "email_supplierinvoice",
                "email_customerinvoice",
                "add_purchaserequest",
                "approve_reconciliation",
                "approve_banktransfer",
                "approve_account",
                "approve_postingrule",
                "approve_journal",
                "configure_accounting",
                "view_audit",
                "view_reporting",
                "view_financialreporting",
                "export_reporting",
            ]
        )
    ),
    "Finance Officer": (
        _view(
            [
                "organisation",
                "parties",
                "catalogue",
                "warehousing",
                "documents",
                "projects",
                "procurement",
                "inventory",
                "accounting",
                "invoicing",
                "banking",
                "services",
                "leasing",
            ]
        )
        | _crud(["invoicing"], actions=("view", "add", "change"))
        | _permissions(
            [
                "record_payment",
                "allocate_payment",
                "email_supplierinvoice",
                "email_customerinvoice",
                "add_purchaserequest",
                "import_bankstatement",
                "match_banktransaction",
                "submit_reconciliation",
                "manage_banktransfer",
                "view_reporting",
                "view_financialreporting",
                "export_reporting",
            ]
        )
    ),
    "Procurement Officer": (
        _crud(["procurement", "parties", "documents"])
        | _view(
            [
                "organisation",
                "catalogue",
                "warehousing",
                "projects",
                "inventory",
                "accounting",
                "invoicing",
                "services",
                "leasing",
            ]
        )
        | _permissions(
            [
                "select_supplier",
                "add_purchaserequest",
                "add_goodsreceiptnote",
                "view_reporting",
            ]
        )
    ),
    "Project Manager": (
        _crud(["projects", "documents"])
        | _view(
            [
                "organisation",
                "parties",
                "catalogue",
                "warehousing",
                "procurement",
                "inventory",
                "accounting",
                "invoicing",
                "services",
                "leasing",
            ]
        )
        | _crud(["procurement"], actions=("view", "add", "change"))
        | _permissions(
            [
                "add_purchaserequest",
                "add_servicecontract",
                "change_servicecontract",
                "add_workorder",
                "change_workorder",
                "assign_workorder",
                "complete_workorder",
                "accept_workorder",
                "add_rentalagreement",
                "change_rentalagreement",
                "add_equipmentreservation",
                "change_equipmentreservation",
                "dispatch_rental",
                "return_equipment",
                "record_inspection",
                "close_rentalagreement",
                "view_reporting",
            ]
        )
    ),
    "Storekeeper": (
        _view(
            [
                "organisation",
                "parties",
                "catalogue",
                "warehousing",
                "documents",
                "projects",
                "procurement",
                "accounting",
                "invoicing",
                "services",
                "leasing",
            ]
        )
        | _view(["inventory"])
        | _permissions(
            [
                "receive_stock",
                "transfer_stock",
                "issue_stock",
                "return_stock",
                "adjust_stock",
                "write_off_stock",
                "count_stock",
                "reserve_stock",
                "add_purchaserequest",
                "add_goodsreceiptnote",
                "view_audit",
                "view_reporting",
            ]
        )
    ),
    "Operations / HSE": (
        _crud(["documents", "parties"])
        | _view(
            [
                "organisation",
                "catalogue",
                "warehousing",
                "projects",
                "procurement",
                "inventory",
                "accounting",
                "services",
                "leasing",
            ]
        )
        | _permissions(
            [
                "add_purchaserequest",
                "add_workorder",
                "change_workorder",
                "assign_workorder",
                "complete_workorder",
                "add_servicechecklistitem",
                "change_servicechecklistitem",
                "add_hserecord",
                "change_hserecord",
                "add_workorderreport",
                "change_workorderreport",
                "manage_equipment",
                "add_equipmentreservation",
                "change_equipmentreservation",
                "dispatch_rental",
                "return_equipment",
                "record_inspection",
                "close_rentalagreement",
                "add_equipmentmaintenance",
                "change_equipmentmaintenance",
                "view_reporting",
            ]
        )
    ),
    "Auditor": (
        _view(
            [
                "organisation",
                "parties",
                "catalogue",
                "warehousing",
                "documents",
                "projects",
                "procurement",
                "inventory",
                "accounting",
                "invoicing",
                "banking",
                "services",
                "leasing",
                "core",
            ]
        )
        | _permissions(
            [
                "view_group",
                "view_permission",
                "view_user",
                "view_audit",
                "view_reporting",
                "view_financialreporting",
                "export_reporting",
            ]
        )
    ),
}


def apply_matrix() -> dict:
    """Create or update the nine operational groups and the unassigned controller."""

    created = 0
    updated = 0
    for name in ROLE_NAMES:
        group, was_created = Group.objects.get_or_create(name=name)
        permissions = list(MATRIX[name].distinct())
        group.permissions.set(permissions)
        if was_created:
            created += 1
        else:
            updated += 1
    PolicyDecision.objects.update_or_create(
        code="D-03",
        version="1.0-provisional",
        defaults={
            "title": "Nine operational roles plus unassigned Finance Controller",
            "status": PolicyDecision.Status.PROVISIONAL,
            "effective_from": "2026-11-12",
            "owner": "Management",
            "summary": (
                "Nine provisional operational roles applied as permission bundles, plus a "
                "separate Finance Controller role created for Stage 7B and left unassigned. "
                "HSE duties are "
                "folded into Operations / HSE; Requester is not a role because every "
                "authenticated employee may raise a request."
            ),
            "configuration": {"roles": list(ROLE_NAMES)},
            "notes": "Requires management confirmation before production use.",
        },
    )
    return {"roles_created": created, "roles_updated": updated}
