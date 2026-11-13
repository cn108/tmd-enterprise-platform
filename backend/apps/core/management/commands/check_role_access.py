"""Exercise every staging role through the real API and record the matrix."""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from rest_framework.test import APIClient

from apps.core.role_matrix import ROLE_NAMES
from apps.identity.models import User
from apps.leasing.models import RentalAgreement
from apps.procurement.models import PurchaseOrder
from apps.services.models import WorkOrder

STAGING_DB = "tmd_staging"
EMAILS = {
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
READ_ALL = ("procurement", "inventory", "services", "leasing")
READ_FINANCE = {"Management", "Accountant", "Finance Controller", "Finance Officer", "Auditor"}
READ_BANK = READ_FINANCE
WRITE_PR = {
    "Management",
    "Accountant",
    "Finance Controller",
    "Finance Officer",
    "Procurement Officer",
    "Project Manager",
    "Storekeeper",
    "Operations / HSE",
}
BANK_IMPORT = {"Finance Officer"}
RECEIVE = {"Procurement Officer", "Project Manager", "Storekeeper"}
ISSUE = {"Storekeeper"}
SERVICE_ACCEPT = {"Management", "Project Manager"}
RENTAL_DISPATCH = {"Project Manager", "Operations / HSE"}


class Command(BaseCommand):
    help = "Exercise all staging roles through the API for read, write and approval access."

    @staticmethod
    def _check(row, role, name, response, allowed, failures):
        if role == "System Administrator":
            allowed = True
        status = response.status_code
        passed = (status != 403) if allowed else (status == 403)
        row["checks"][name] = {"status": status, "allowed": allowed, "pass": passed}
        if not passed:
            failures.append(f"{role}: {name} returned {status}, allowed={allowed}")

    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != STAGING_DB:
            raise CommandError(f"This command only runs against {STAGING_DB}.")
        po = PurchaseOrder.objects.get()
        work_order = WorkOrder.objects.get()
        rental = RentalAgreement.objects.get()
        endpoints = {
            "procurement": "/api/v1/purchase-orders/",
            "inventory": "/api/v1/stock-movements/",
            "services": "/api/v1/work-orders/",
            "leasing": "/api/v1/equipment/",
        }
        financial = "/api/v1/reporting/financial-statements/?start=2026-11-01&end=2026-11-30"
        bank = "/api/v1/company-bank-accounts/"
        results = []
        failures = []
        for role in ROLE_NAMES:
            user = User.objects.get(email=EMAILS[role])
            client = APIClient(HTTP_HOST="localhost")
            client.force_authenticate(user)
            row = {"role": role, "checks": {}}

            def check(name, response, allowed, row=row, role=role):
                self._check(row, role, name, response, allowed, failures)

            for name in READ_ALL:
                check(f"read_{name}", client.get(endpoints[name]), True)
            check(
                "read_financial_report",
                client.get(financial),
                role in READ_FINANCE or role == "System Administrator",
            )
            check(
                "read_bank_accounts",
                client.get(bank),
                role in READ_BANK or role == "System Administrator",
            )
            check(
                "create_purchase_request",
                client.post("/api/v1/purchase-requests/", {}, format="json"),
                role in WRITE_PR,
            )
            check(
                "receive_goods",
                client.post(f"/api/v1/purchase-orders/{po.pk}/receive/", {}, format="json"),
                role in RECEIVE,
            )
            check(
                "issue_stock",
                client.post("/api/v1/stock-issues/", {}, format="json"),
                role in ISSUE,
            )
            check(
                "import_bank_statement",
                client.post("/api/v1/bank-statements/", {}, format="json"),
                role in BANK_IMPORT,
            )
            check(
                "accept_work_order",
                client.post(f"/api/v1/work-orders/{work_order.pk}/accept/", {}, format="json"),
                role in SERVICE_ACCEPT,
            )
            check(
                "dispatch_rental",
                client.post(f"/api/v1/rental-agreements/{rental.pk}/dispatch/", {}, format="json"),
                role in RENTAL_DISPATCH,
            )
            check(
                "export_financial_report",
                client.get(
                    "/api/v1/reporting/financial-statements/export/?start=2026-11-01&end=2026-11-30"
                ),
                role in READ_FINANCE or role == "System Administrator",
            )
            results.append(row)

        evidence = Path(settings.BASE_DIR).parent / "docs" / "reports" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        payload = {
            "database": connection.settings_dict["NAME"],
            "roles": len(results),
            "checks": len(results) * len(results[0]["checks"]),
            "failures": failures,
            "all_passed": not failures,
            "matrix": results,
        }
        (evidence / "role-access-matrix.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        lines = [
            "# Role-based access acceptance",
            "",
            f"Staging database: `{connection.settings_dict['NAME']}`",
            f"Roles exercised: {len(results)}; checks: {payload['checks']}",
            f"All checks passed: **{payload['all_passed']}**",
            "",
            "Expected access: allowed actions must not return 403; denied actions must return 403.",
            "",
            "| Role | Checks passed |",
            "| --- | ---: |",
        ]
        for row in results:
            passed = sum(1 for item in row["checks"].values() if item["pass"])
            lines.append(f"| {row['role']} | {passed}/{len(row['checks'])} |")
        if failures:
            lines += ["", "## Failures", ""] + [f"- {item}" for item in failures]
        (evidence / "role-access-matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(
            json.dumps(
                {"roles": len(results), "checks": payload["checks"], "failures": failures},
                indent=2,
            )
        )
        if failures:
            raise CommandError("Role acceptance failures; see docs/reports/evidence.")
        self.stdout.write(self.style.SUCCESS("All role acceptance checks passed."))
