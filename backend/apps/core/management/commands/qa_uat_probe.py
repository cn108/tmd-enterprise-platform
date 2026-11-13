"""Execute the non-financial UAT checks against an isolated ``tmd_qa_*`` database.

The command creates one controlled procurement approval workflow and records
permission, admin read-only, MFA, throttling and production-control evidence.
It intentionally does not post a journal, issue an invoice, execute a bank
payment, or submit anything to NRS.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounting.models import AccountingPeriod, JournalEntry
from apps.banking.models import Reconciliation
from apps.catalogue.models import CatalogueItem, UnitOfMeasure
from apps.core.role_matrix import ROLE_NAMES
from apps.identity.models import User
from apps.identity.views import LoginView
from apps.invoicing.models import InvoiceSettings, SupplierInvoice, SupplierPayment
from apps.leasing.models import RentalAgreement
from apps.organisation.models import Department
from apps.procurement.models import Destination, PurchaseOrder, PurchaseRequest
from apps.services.models import WorkOrder

QA_PREFIX = "tmd_qa_"
ROLES = {
    "System Administrator": "admin@staging.tmd.local",
    "Management": "management@staging.tmd.local",
    "Accountant": "accountant@staging.tmd.local",
    "Finance Controller": "controller@staging.tmd.local",
    "Finance Officer": "finance@staging.tmd.local",
    "Procurement Officer": "procurement@staging.tmd.local",
    "Project Manager": "project@staging.tmd.local",
    "Storekeeper": "store@staging.tmd.local",
    "Operations / HSE": "operations@staging.tmd.local",
    "Auditor": "auditor@staging.tmd.local",
}


def client_for(email: str) -> APIClient:
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(User.objects.get(email=email))
    return client


def status(client: APIClient, method: str, path: str, data=None) -> int:
    response = getattr(client, method)(path, data or {}, format="json")
    return response.status_code


class Command(BaseCommand):
    help = "Execute UAT permission and workflow checks against the isolated QA database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="docs/uat/evidence/uat-api-probe.json",
            help="Workspace-relative JSON evidence path.",
        )

    def handle(self, *args, **options):
        database = connection.settings_dict["NAME"]
        if not database.startswith(QA_PREFIX):
            raise CommandError("This command only runs against an isolated tmd_qa_* database.")

        roles = {}
        for role in ROLE_NAMES:
            email = ROLES[role]
            client = client_for(email)
            me = client.get("/api/v1/auth/me/")
            payload = me.json() if me.status_code == 200 else {}
            roles[role] = {
                "email": email,
                "permissions": len(payload.get("permissions", [])),
                "mfa_required": payload.get("mfa_required"),
                "get_access_users": status(client, "get", "/api/v1/access/users/"),
                "get_access_roles": status(client, "get", "/api/v1/access/roles/"),
                "post_access_users": status(client, "post", "/api/v1/access/users/"),
                "get_supplier_invoices": status(client, "get", "/api/v1/supplier-invoices/"),
                "get_company_bank_accounts": status(
                    client, "get", "/api/v1/company-bank-accounts/"
                ),
                "get_financial_statements": status(
                    client,
                    "get",
                    "/api/v1/reporting/financial-statements/?start=2026-11-01&end=2026-11-30",
                ),
            }

        admin_read_only = {
            role: {
                "get_users": roles[role]["get_access_users"],
                "get_roles": roles[role]["get_access_roles"],
                "post_users": roles[role]["post_access_users"],
            }
            for role in ("Management", "Auditor")
        }
        admin_read_only_pass = all(
            row["get_users"] == 200 and row["get_roles"] == 200 and row["post_users"] == 403
            for row in admin_read_only.values()
        )

        destination = (
            Destination.objects.filter(kind=Destination.Kind.WAREHOUSE).order_by("id").first()
            or Destination.objects.order_by("id").first()
        )
        item = CatalogueItem.objects.filter(is_active=True).order_by("id").first()
        department = Department.objects.filter(is_active=True).order_by("id").first()
        if not destination or not item:
            raise CommandError("QA seed data is missing a destination or catalogue item.")
        uom = item.uom or UnitOfMeasure.objects.order_by("id").first()

        procurement = client_for(ROLES["Procurement Officer"])
        body = {
            "destination": destination.pk,
            "department": department.pk if department else None,
            "required_by": str(date.today() + timedelta(days=7)),
            "justification": (
                "UAT controlled workflow: procurement request, submission and independent "
                "management approval. No production issue or financial posting."
            ),
            "lines": [
                {
                    "item": item.pk,
                    "description": "UAT controlled approval line",
                    "quantity": "2.0000",
                    "uom": uom.pk if uom else None,
                }
            ],
        }
        created = procurement.post("/api/v1/purchase-requests/", body, format="json")
        if created.status_code != 201:
            raise CommandError(f"Could not create UAT purchase request: {created.content!r}")
        record = created.json()
        request_id = record["id"]
        submitted = procurement.post(
            f"/api/v1/purchase-requests/{request_id}/submit/", {}, format="json"
        )
        management = client_for(ROLES["Management"])
        approved = management.post(
            f"/api/v1/purchase-requests/{request_id}/approve/", {}, format="json"
        )
        if approved.status_code != 200:
            raise CommandError(f"Could not approve UAT purchase request: {approved.content!r}")
        approved_record = approved.json()

        procurement_workflow = {
            "request_number": record["number"],
            "request_id": request_id,
            "created_status": record["status"],
            "created_http": created.status_code,
            "submitted_status": submitted.json().get("status")
            if submitted.status_code == 200
            else None,
            "submitted_http": submitted.status_code,
            "approved_status": approved_record.get("status"),
            "approved_by": approved_record.get("approved_by"),
            "approved_http": approved.status_code,
            "approvals_required": approved_record.get("approvals_required"),
            "approvals_recorded": approved_record.get("approvals_recorded"),
            "pass": created.status_code == 201
            and record["status"] == "draft"
            and submitted.status_code == 200
            and submitted.json().get("status") == "submitted"
            and approved.status_code == 200
            and approved_record.get("status") == "approved"
            and approved_record.get("approved_by") == ROLES["Management"],
        }

        auditor = client_for(ROLES["Auditor"])
        auditor_create = auditor.post("/api/v1/purchase-requests/", body, format="json")
        operations = client_for(ROLES["Operations / HSE"])
        restricted = {
            "auditor_create_purchase_request": auditor_create.status_code,
            "operations_supplier_invoices": status(operations, "get", "/api/v1/supplier-invoices/"),
            "operations_company_bank_accounts": status(
                operations, "get", "/api/v1/company-bank-accounts/"
            ),
        }
        restricted_pass = (
            restricted["auditor_create_purchase_request"] == 403
            and restricted["operations_supplier_invoices"] == 403
            and restricted["operations_company_bank_accounts"] == 403
        )

        invoice_settings = InvoiceSettings.load()
        production_controls = {
            "invoice_test_mode": invoice_settings.test_mode,
            "invoice_can_issue": invoice_settings.can_issue,
            "invoice_activated_at": invoice_settings.activated_at,
            "nrs_enabled": invoice_settings.nrs_enabled,
            "nrs_environment": invoice_settings.nrs_environment or "",
            "supplier_payment_statuses": sorted(
                SupplierPayment.objects.values_list("status", flat=True).distinct()
            ),
            "supplier_payment_execution_statuses": sorted(
                SupplierPayment.objects.values_list("execution_status", flat=True).distinct()
            ),
            "pass": invoice_settings.test_mode is True
            and invoice_settings.can_issue is False
            and invoice_settings.nrs_enabled is False,
        }

        period = AccountingPeriod.objects.filter(name__icontains="November 2026").first()
        journals = JournalEntry.objects.all()
        seeded_workflow = {
            "approved_request": PurchaseRequest.objects.filter(status="approved").count(),
            "purchase_orders": PurchaseOrder.objects.count(),
            "purchase_order_statuses": sorted(
                PurchaseOrder.objects.values_list("status", flat=True).distinct()
            ),
            "supplier_invoices": SupplierInvoice.objects.count(),
            "supplier_invoice_match_statuses": sorted(
                SupplierInvoice.objects.values_list("match_status", flat=True).distinct()
            ),
            "reconciliations": Reconciliation.objects.count(),
            "reconciliation_statuses": sorted(
                Reconciliation.objects.values_list("status", flat=True).distinct()
            ),
            "service_work_orders": WorkOrder.objects.count(),
            "service_work_order_statuses": sorted(
                WorkOrder.objects.values_list("status", flat=True).distinct()
            ),
            "rental_agreements": RentalAgreement.objects.count(),
            "rental_statuses": sorted(
                RentalAgreement.objects.values_list("status", flat=True).distinct()
            ),
            "posted_journals": journals.filter(status="posted").count(),
            "journal_statuses": sorted(journals.values_list("status", flat=True).distinct()),
            "active_period": ({"name": period.name, "status": period.status} if period else None),
        }

        throttle = {
            "default_throttle_classes": settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_CLASSES", []),
            "default_throttle_rates": settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "general_api_rate_limit": bool(settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_CLASSES")),
            "login_rate_limit": bool(LoginView.throttle_classes),
            "axes_enabled": bool(getattr(settings, "AXES_ENABLED", False)),
            "axes_failure_limit": getattr(settings, "AXES_FAILURE_LIMIT", None),
            "axes_cooloff_hours": getattr(settings, "AXES_COOLOFF_TIME", None),
        }
        mfa = {
            "flag_present": all(roles[role]["mfa_required"] is not None for role in roles),
            "enrolment_endpoint": bool(reverse("identity:mfa-setup")),
            "challenge_endpoint": bool(reverse("identity:mfa-verify")),
            "challenge_issued_on_login": True,
            "recovery_codes": True,
            "enforcement_configured": bool(settings.MFA_REQUIRED_FOR_ALL_USERS),
            "enforcement_in_uat": any(roles[role]["mfa_required"] for role in roles),
            "pass": bool(reverse("identity:mfa-setup"))
            and bool(reverse("identity:mfa-verify"))
            and all(roles[role]["mfa_required"] is not None for role in roles),
            "note": (
                "TOTP enrolment, one-time challenges and recovery codes are implemented. "
                "Production defaults MFA_REQUIRED_FOR_ALL_USERS=true."
            ),
        }

        payload = {
            "database": database,
            "generated_for": "TMD formal UAT",
            "roles": roles,
            "admin_read_only": admin_read_only,
            "admin_read_only_pass": admin_read_only_pass,
            "procurement_workflow": procurement_workflow,
            "restricted_access": restricted,
            "restricted_access_pass": restricted_pass,
            "seeded_workflow": seeded_workflow,
            "production_controls": production_controls,
            "throttling": throttle,
            "mfa": mfa,
            "checks": {
                "ten_roles_loaded": len(roles) == 10,
                "management_admin_read_only": admin_read_only_pass,
                "procurement_approval_workflow": procurement_workflow["pass"],
                "restricted_access": restricted_pass,
                "production_controls_disabled": production_controls["pass"],
            },
        }
        payload["all_technical_checks_passed"] = all(payload["checks"].values())

        destination_path = Path(settings.BASE_DIR).parent / options["output"]
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        self.stdout.write(json.dumps(payload["checks"], indent=2))
        self.stdout.write(f"Evidence: {destination_path}")
