"""Run controlled adversarial API probes against an isolated ``tmd_qa_*`` database.

The command never targets staging or a production-looking database. It records
status codes and error envelopes for review; it does not execute a payment,
issue an invoice, send email, post a new journal, or delete a record.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from rest_framework.test import APIClient

from apps.accounting.models import AccountingPeriod, JournalEntry
from apps.banking.models import Reconciliation
from apps.identity.models import User
from apps.invoicing.models import CustomerInvoice, CustomerReceipt, SupplierInvoice
from apps.leasing.models import RentalAgreement
from apps.parties.models import Party
from apps.procurement.models import PurchaseOrder, PurchaseRequest
from apps.services.models import WorkOrder

QA_PREFIX = "tmd_qa_"
ROLES = {
    "system_admin": "admin@staging.tmd.local",
    "management": "management@staging.tmd.local",
    "accountant": "accountant@staging.tmd.local",
    "controller": "controller@staging.tmd.local",
    "finance": "finance@staging.tmd.local",
    "procurement": "procurement@staging.tmd.local",
    "project": "project@staging.tmd.local",
    "store": "store@staging.tmd.local",
    "operations": "operations@staging.tmd.local",
    "auditor": "auditor@staging.tmd.local",
}


def client_for(email: str) -> APIClient:
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(User.objects.get(email=email))
    return client


def response_summary(response) -> dict[str, Any]:
    body: Any
    try:
        body = response.json()
    except Exception:
        body = None
    message = ""
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", ""))
        elif "detail" in body:
            message = str(body.get("detail"))
    return {
        "status": response.status_code,
        "message": message[:240],
    }


class Command(BaseCommand):
    help = "Probe QA access, validation, state and CSRF controls."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="docs/reports/evidence/adversarial/api-probe.json",
            help="Workspace-relative JSON evidence path.",
        )
        parser.add_argument(
            "--base-url",
            default=os.environ.get("QA_BASE_URL", "http://127.0.0.1:8000"),
            help="Running QA API base URL for session/CSRF probes.",
        )

    def _probe(self, results, name, response, expected, **extra):
        summary = response_summary(response)
        passed = response.status_code in expected
        results.append(
            {
                "name": name,
                "expected": sorted(expected),
                "pass": passed,
                **summary,
                **extra,
            }
        )

    def _csrf_and_session(self, base_url: str):
        results = []
        base = base_url.rstrip("/")
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        def call(method: str, path: str, body=None, headers=None):
            payload = json.dumps(body).encode("utf-8") if body is not None else None
            request_headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                **(headers or {}),
            }
            request = urllib.request.Request(  # noqa: S310 - operator-supplied QA base URL
                urljoin(f"{base}/", path.lstrip("/")),
                data=payload,
                headers=request_headers,
                method=method,
            )
            try:
                response = opener.open(request, timeout=10)
                raw = response.read()
                try:
                    parsed = json.loads(raw or b"{}")
                except json.JSONDecodeError:
                    parsed = None
                return response.status, parsed, response.headers
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                try:
                    parsed = json.loads(raw or b"{}")
                except json.JSONDecodeError:
                    parsed = None
                return exc.code, parsed, exc.headers

        def csrf_token() -> str:
            return next((cookie.value for cookie in jar if cookie.name == "csrftoken"), "")

        try:
            csrf_status, csrf_body, _ = call("GET", "/api/v1/auth/csrf/")
            csrf = csrf_token() or (csrf_body or {}).get("csrfToken", "")
            results.append(
                {
                    "name": "csrf_bootstrap",
                    "status": csrf_status,
                    "pass": csrf_status == 200 and bool(csrf),
                }
            )
            login_headers = {
                "X-CSRFToken": csrf,
                "Origin": base,
                "Referer": f"{base}/login",
            }
            login_status, _, login_response_headers = call(
                "POST",
                "/api/v1/auth/login/",
                {
                    "email": "management@staging.tmd.local",
                    "password": "Tmd-Staging-2026!",
                },
                headers=login_headers,
            )
            results.append(
                {
                    "name": "session_login",
                    "status": login_status,
                    "pass": login_status == 200,
                }
            )
            me_status, _, _ = call("GET", "/api/v1/auth/me/")
            session_cookie_names = sorted(cookie.name for cookie in jar)
            login_set_cookies = login_response_headers.get_all("Set-Cookie") or []
            results.append(
                {
                    "name": "session_cookie_attributes",
                    "cookies": session_cookie_names,
                    "set_cookie_headers": [
                        "HttpOnly" if "httponly" in item.lower() else "missing-httponly"
                        for item in login_set_cookies
                        if item.lower().startswith("sessionid=")
                    ],
                    "pass": "sessionid" in session_cookie_names
                    and any(item.lower().startswith("sessionid=") for item in login_set_cookies),
                }
            )
            results.append(
                {
                    "name": "session_me",
                    "status": me_status,
                    "pass": me_status == 200,
                }
            )
            no_token_status, _, _ = call(
                "POST",
                "/api/v1/purchase-requests/",
                {"justification": "QA-CSRF probe"},
                headers={"Origin": base},
            )
            results.append(
                {
                    "name": "mutation_without_csrf",
                    "status": no_token_status,
                    "pass": no_token_status == 403,
                }
            )
            evil_status, _, _ = call(
                "POST",
                "/api/v1/purchase-requests/",
                {"justification": "QA-CSRF origin probe"},
                headers={"X-CSRFToken": csrf_token() or csrf, "Origin": "https://evil.example"},
            )
            results.append(
                {
                    "name": "mutation_with_foreign_origin",
                    "status": evil_status,
                    "pass": evil_status == 403,
                }
            )
            logout_status, _, _ = call(
                "POST",
                "/api/v1/auth/logout/",
                headers={
                    "X-CSRFToken": csrf_token() or csrf,
                    "Origin": base,
                },
            )
            after_logout_status, _, _ = call("GET", "/api/v1/auth/me/")
            results.append(
                {
                    "name": "logout_invalidates_session",
                    "status": logout_status,
                    "post_logout_me": after_logout_status,
                    "pass": logout_status in {200, 204} and after_logout_status == 401,
                }
            )
        except (urllib.error.URLError, OSError) as exc:
            results.append(
                {
                    "name": "session_probe_transport",
                    "status": None,
                    "pass": False,
                    "error": str(exc),
                }
            )
        return results

    def handle(self, *args, **options):
        database = connection.settings_dict["NAME"]
        if not str(database).startswith(QA_PREFIX):
            raise CommandError(
                f"Refusing to run against {database!r}; "
                f"this command requires a {QA_PREFIX}* QA clone."
            )

        results: list[dict[str, Any]] = []
        admin = client_for(ROLES["system_admin"])
        pr = PurchaseRequest.objects.get()
        po = PurchaseOrder.objects.get()
        customer = Party.objects.filter(is_customer=True).first()
        supplier_invoice = SupplierInvoice.objects.get()
        customer_invoice = CustomerInvoice.objects.get()
        reconciliation = Reconciliation.objects.get()
        work_order = WorkOrder.objects.get()
        rental = RentalAgreement.objects.get()
        posted_journal = JournalEntry.objects.filter(status="posted").first()
        closed_period = AccountingPeriod.objects.get(status="closed")
        supplier_count = Party.objects.filter(is_supplier=True).count()

        # Read access separation and direct object tampering.
        access_checks = [
            (
                "operations_cannot_read_bank",
                client_for(ROLES["operations"]).get("/api/v1/company-bank-accounts/"),
                {403},
            ),
            (
                "operations_cannot_read_supplier_invoices",
                client_for(ROLES["operations"]).get("/api/v1/supplier-invoices/"),
                {403},
            ),
            (
                "procurement_cannot_read_access_users",
                client_for(ROLES["procurement"]).get("/api/v1/access/users/"),
                {403},
            ),
            (
                "finance_cannot_write_access_roles",
                client_for(ROLES["finance"]).post(
                    "/api/v1/access/roles/", {"name": "QA-Privilege-Escalation"}, format="json"
                ),
                {403},
            ),
            (
                "management_cannot_create_users",
                client_for(ROLES["management"]).post(
                    "/api/v1/access/users/", {"email": "qa-escalation@example.test"}, format="json"
                ),
                {403},
            ),
            (
                "auditor_cannot_create_supplier",
                client_for(ROLES["auditor"]).post(
                    "/api/v1/suppliers/",
                    {
                        "code": "QA-AUD-READONLY",
                        "legal_name": "QA Audit Attempt",
                        "is_supplier": True,
                    },
                    format="json",
                ),
                {403},
            ),
            (
                "management_cannot_create_supplier",
                client_for(ROLES["management"]).post(
                    "/api/v1/suppliers/",
                    {
                        "code": "QA-MGT-READONLY",
                        "legal_name": "QA Management Attempt",
                        "is_supplier": True,
                    },
                    format="json",
                ),
                {403},
            ),
            ("admin_missing_object_is_404", admin.get("/api/v1/customer-invoices/999999/"), {404}),
            (
                "operations_missing_object_is_forbidden",
                client_for(ROLES["operations"]).get("/api/v1/customer-invoices/999999/"),
                {403},
            ),
            (
                "customer_pdf_requires_invoice_permission",
                client_for(ROLES["operations"]).get(
                    f"/api/v1/customer-invoices/{customer_invoice.pk}/pdf/"
                ),
                {403},
            ),
            (
                "anonymous_cannot_read_invoice",
                APIClient(HTTP_HOST="localhost").get("/api/v1/customer-invoices/"),
                {401, 403},
            ),
        ]
        for name, response, expected in access_checks:
            self._probe(results, name, response, expected)

        # Malformed and hostile-looking input. These calls must not create
        # commercial records unless the payload is deliberately valid.
        invalid_supplier_payloads = {
            "supplier_missing_fields": {},
            "supplier_negative_terms": {
                "code": "QA-NEG-TERMS",
                "legal_name": "QA Negative Terms",
                "is_supplier": True,
                "payment_terms_days": -5,
            },
            "supplier_invalid_email": {
                "code": "QA-BAD-EMAIL",
                "legal_name": "QA Bad Email",
                "is_supplier": True,
                "email": "not-an-email",
            },
            "supplier_overlong_name": {
                "code": "QA-LONG-NAME",
                "legal_name": "Q" * 250,
                "is_supplier": True,
            },
        }
        for name, payload in invalid_supplier_payloads.items():
            before = Party.objects.count()
            self._probe(
                results,
                name,
                admin.post("/api/v1/suppliers/", payload, format="json"),
                {400},
                records_before=before,
                records_after=Party.objects.count(),
            )

        before = Party.objects.count()
        self._probe(
            results,
            "customer_negative_credit_limit",
            admin.post(
                "/api/v1/customers/",
                {
                    "code": "QA-NEG-CREDIT",
                    "legal_name": "QA Negative Credit",
                    "credit_limit": "-1.00",
                },
                format="json",
            ),
            {400},
            records_before=before,
            records_after=Party.objects.count(),
        )

        # Cleaning XSS/SQLi-looking content is tested through harmless supplier
        # records. Existing records are reused on repeat runs.
        xss, _ = Party.objects.get_or_create(
            code="QA-XSS-001",
            defaults={
                "legal_name": "QA <script>window.__qaXss=1</script> Supplier",
                "is_supplier": True,
                "email": "qa-xss@example.test",
                "created_by": User.objects.get(email=ROLES["system_admin"]),
                "updated_by": User.objects.get(email=ROLES["system_admin"]),
            },
        )
        sqli, _ = Party.objects.get_or_create(
            code="QA-SQL-001",
            defaults={
                "legal_name": "QA Robert'); DROP TABLE parties_party;-- Supplier",
                "is_supplier": True,
                "created_by": User.objects.get(email=ROLES["system_admin"]),
                "updated_by": User.objects.get(email=ROLES["system_admin"]),
            },
        )
        self._probe(
            results,
            "supplier_duplicate_code",
            admin.post(
                "/api/v1/suppliers/",
                {"code": xss.code, "legal_name": "QA Duplicate", "is_supplier": True},
                format="json",
            ),
            {400},
        )
        self._probe(
            results,
            "parties_table_survives_sql_like_input",
            admin.get("/api/v1/parties/"),
            {200},
            rows_after_sql_like_record=True,
        )
        self._probe(
            results,
            "sql_like_search_is_data_not_query",
            admin.get("/api/v1/parties/?search=%27%20OR%201%3D1--"),
            {200},
            returned_xss=bool(xss.pk),
            returned_sqli=bool(sqli.pk),
        )

        request_payloads = {
            "purchase_request_empty": {},
            "purchase_request_no_lines": {"destination": 1, "justification": "QA no lines"},
            "purchase_request_zero_quantity": {
                "destination": 1,
                "justification": "QA zero",
                "lines": [{"item": 1, "quantity": "0"}],
            },
            "purchase_request_negative_quantity": {
                "destination": 1,
                "justification": "QA negative",
                "lines": [{"item": 1, "quantity": "-1"}],
            },
            "purchase_request_unknown_item": {
                "destination": 1,
                "justification": "QA unknown item",
                "lines": [{"item": 999999, "quantity": "1"}],
            },
        }
        for name, payload in request_payloads.items():
            before = PurchaseRequest.objects.count()
            self._probe(
                results,
                name,
                admin.post("/api/v1/purchase-requests/", payload, format="json"),
                {400},
                records_before=before,
                records_after=PurchaseRequest.objects.count(),
            )

        invoice_payloads = {
            "customer_invoice_empty": {},
            "customer_invoice_no_lines": {
                "customer": customer.pk,
                "invoice_date": "2026-11-12",
                "currency": "NGN",
                "lines": [],
            },
            "customer_invoice_zero_quantity": {
                "customer": customer.pk,
                "invoice_date": "2026-11-12",
                "currency": "NGN",
                "lines": [{"description": "QA zero", "quantity": "0", "unit_price": "10"}],
            },
            "customer_invoice_negative_price": {
                "customer": customer.pk,
                "invoice_date": "2026-11-12",
                "currency": "NGN",
                "lines": [{"description": "QA negative", "quantity": "1", "unit_price": "-1"}],
            },
            "customer_invoice_invalid_date": {
                "customer": customer.pk,
                "invoice_date": "2026-02-31",
                "currency": "NGN",
                "lines": [{"description": "QA bad date", "quantity": "1", "unit_price": "10"}],
            },
            "customer_invoice_oversized_amount": {
                "customer": customer.pk,
                "invoice_date": "2026-11-12",
                "currency": "NGN",
                "lines": [
                    {
                        "description": "QA huge",
                        "quantity": "1",
                        "unit_price": "999999999999999999999",
                    }
                ],
            },
            "customer_invoice_overlong_description": {
                "customer": customer.pk,
                "invoice_date": "2026-11-12",
                "currency": "NGN",
                "lines": [{"description": "Q" * 300, "quantity": "1", "unit_price": "10"}],
            },
        }
        for name, payload in invoice_payloads.items():
            before = CustomerInvoice.objects.count()
            self._probe(
                results,
                name,
                admin.post("/api/v1/customer-invoices/", payload, format="json"),
                {400},
                records_before=before,
                records_after=CustomerInvoice.objects.count(),
            )

        # Invalid state transitions on seeded approved/closed records.
        transitions = [
            (
                "repeat_submit_purchase_request",
                admin.post(f"/api/v1/purchase-requests/{pr.pk}/submit/"),
                {409},
            ),
            (
                "repeat_approve_purchase_request",
                admin.post(f"/api/v1/purchase-requests/{pr.pk}/approve/"),
                {409},
            ),
            (
                "receive_order_without_lines",
                admin.post(f"/api/v1/purchase-orders/{po.pk}/receive/", {}, format="json"),
                {400, 409},
            ),
            (
                "repeat_submit_supplier_invoice",
                admin.post(f"/api/v1/supplier-invoices/{supplier_invoice.pk}/submit/"),
                {409},
            ),
            (
                "repeat_approve_supplier_invoice",
                admin.post(f"/api/v1/supplier-invoices/{supplier_invoice.pk}/approve/"),
                {409},
            ),
            (
                "edit_approved_supplier_invoice",
                admin.patch(
                    f"/api/v1/supplier-invoices/{supplier_invoice.pk}/",
                    {"notes": "QA tamper"},
                    format="json",
                ),
                {400, 409},
            ),
            (
                "repeat_approve_customer_invoice",
                admin.post(f"/api/v1/customer-invoices/{customer_invoice.pk}/approve/"),
                {409},
            ),
            (
                "repeat_approve_reconciliation",
                admin.post(f"/api/v1/reconciliations/{reconciliation.pk}/approve/"),
                {409},
            ),
            (
                "repeat_accept_work_order",
                admin.post(f"/api/v1/work-orders/{work_order.pk}/accept/"),
                {409},
            ),
            (
                "dispatch_closed_rental",
                admin.post(
                    f"/api/v1/rental-agreements/{rental.pk}/dispatch/",
                    {"equipment": rental.lines.first().equipment_id},
                    format="json",
                ),
                {409},
            ),
            (
                "post_posted_journal",
                admin.post(f"/api/v1/journals/{posted_journal.pk}/post/"),
                {409},
            ),
            (
                "close_closed_period",
                admin.post(f"/api/v1/accounting-periods/{closed_period.pk}/close/"),
                {409},
            ),
        ]
        for name, response, expected in transitions:
            self._probe(results, name, response, expected)

        # Over-allocation and wrong-customer allocation must not create a receipt.
        receipt_before = CustomerReceipt.objects.count()
        self._probe(
            results,
            "receipt_over_allocation",
            admin.post(
                "/api/v1/customer-receipts/",
                {
                    "customer": customer.pk,
                    "receipt_date": "2026-11-12",
                    "currency": "NGN",
                    "amount": "100.00",
                    "method": "bank_transfer",
                    "lines": [{"invoice": customer_invoice.pk, "amount": "999999.00"}],
                },
                format="json",
            ),
            {400},
            records_before=receipt_before,
            records_after=CustomerReceipt.objects.count(),
        )
        other_customer = Party.objects.filter(is_customer=True).exclude(pk=customer.pk).first()
        if other_customer:
            receipt_before = CustomerReceipt.objects.count()
            self._probe(
                results,
                "receipt_wrong_customer_invoice",
                admin.post(
                    "/api/v1/customer-receipts/",
                    {
                        "customer": other_customer.pk,
                        "receipt_date": "2026-11-12",
                        "currency": "NGN",
                        "amount": "100.00",
                        "method": "bank_transfer",
                        "lines": [{"invoice": customer_invoice.pk, "amount": "100.00"}],
                    },
                    format="json",
                ),
                {400},
                records_before=receipt_before,
                records_after=CustomerReceipt.objects.count(),
            )

        # Session/CSRF probes use the live QA API. They deliberately do not
        # submit a valid invoice, payment, receipt, email, or financial posting.
        session_results = self._csrf_and_session(options["base_url"])

        failures = [item["name"] for item in results if not item["pass"]]
        session_failures = [item["name"] for item in session_results if not item["pass"]]
        payload = {
            "database": database,
            "base_url": options["base_url"],
            "test_mode": True,
            "can_issue": False,
            "roles": ROLES,
            "checks": len(results),
            "failures": failures,
            "session_checks": session_results,
            "session_failures": session_failures,
            "results": results,
            "xss_fixture": {"code": xss.code, "legal_name": xss.legal_name},
            "sql_like_fixture": {"code": sqli.code, "legal_name": sqli.legal_name},
            "supplier_count_before_create_probes": supplier_count,
            "supplier_count_after_create_probes": Party.objects.filter(is_supplier=True).count(),
        }
        output = Path(settings.BASE_DIR).parent / options["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        self.stdout.write(
            json.dumps(
                {
                    "checks": len(results),
                    "failures": failures,
                    "session_failures": session_failures,
                },
                indent=2,
            )
        )
        if failures or session_failures:
            raise CommandError("Adversarial probes failed; inspect the evidence JSON.")
        self.stdout.write(self.style.SUCCESS("All adversarial API probes passed."))
