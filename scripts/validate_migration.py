#!/usr/bin/env python3
"""Validate TMD migration CSV templates without touching a database.

This is a pre-import control, not an importer. It checks structure, types,
referential consistency between template files, duplicate business keys and
financial arithmetic. A clean result means the files are ready for a controlled
staging trial; it does not approve the opening balances.
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = ROOT / "docs" / "templates" / "migration"
DEFAULT_REPORT = (
    ROOT / "docs" / "reports" / "evidence" / "phase-11-migration-template-validation.md"
)

HEADERS = {
    "company_profile.csv": [
        "legal_name",
        "trading_name",
        "rc_number",
        "tin",
        "vat_registration_number",
        "registered_address",
        "email",
        "phone",
        "financial_year_end",
        "reporting_currency",
    ],
    "employees.csv": [
        "email",
        "full_name",
        "role",
        "department",
        "is_active",
        "mfa_required",
    ],
    "suppliers.csv": [
        "code",
        "legal_name",
        "trading_name",
        "supplier_category",
        "payment_terms_days",
        "default_currency",
        "due_diligence_status",
        "email",
        "phone",
        "is_active",
    ],
    "customers.csv": [
        "code",
        "legal_name",
        "trading_name",
        "payment_terms_days",
        "default_currency",
        "credit_limit",
        "credit_hold",
        "email",
        "phone",
        "is_active",
    ],
    "projects.csv": [
        "code",
        "name",
        "customer_code",
        "status",
        "start_date",
        "end_date",
        "currency",
        "budget_total",
    ],
    "products.csv": ["code", "name", "kind", "uom_code", "category_code", "is_active"],
    "warehouses.csv": ["code", "name", "site_name", "address"],
    "equipment.csv": [
        "code",
        "name",
        "category",
        "ownership",
        "serial_number",
        "location",
        "acquisition_date",
        "acquisition_cost",
        "currency",
        "status",
    ],
    "inventory_balances.csv": [
        "warehouse_code",
        "item_code",
        "quantity",
        "unit_cost",
        "valuation_date",
    ],
    "supplier_invoices.csv": [
        "supplier_code",
        "supplier_invoice_number",
        "invoice_date",
        "due_date",
        "currency",
        "subtotal",
        "vat_total",
        "wht_total",
        "total",
        "amount_paid",
        "po_number",
    ],
    "customer_invoices.csv": [
        "customer_code",
        "invoice_date",
        "due_date",
        "currency",
        "subtotal",
        "vat_total",
        "wht_total",
        "total",
        "amount_paid",
        "project_code",
    ],
    "bank_balances.csv": ["bank_account_code", "statement_date", "balance", "currency"],
    "opening_trial_balance.csv": ["account_code", "debit", "credit", "as_of"],
    "commitments.csv": [
        "po_number",
        "supplier_code",
        "order_date",
        "currency",
        "total_value",
        "status",
    ],
    "advances.csv": [
        "party_type",
        "party_code",
        "reference",
        "as_of",
        "amount",
        "currency",
        "notes",
    ],
}

PROJECT_STATUSES = {"draft", "active", "on_hold", "closed"}
ITEM_KINDS = {"product", "service"}
COMMITMENT_STATUSES = {"draft", "approved", "issued", "partially_received", "received"}
EQUIPMENT_STATUSES = {"available", "reserved", "on_hire", "maintenance", "retired"}
PARTY_TYPES = {"supplier", "customer"}


class Validator:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.rows: dict[str, list[dict[str, str]]] = {}
        self.counts: dict[str, int] = {}

    def error(self, filename: str, line: int, message: str) -> None:
        self.errors.append(f"{filename}:{line}: {message}")

    def warning(self, filename: str, line: int, message: str) -> None:
        self.warnings.append(f"{filename}:{line}: {message}")

    def load(self) -> None:
        for filename, expected in HEADERS.items():
            path = self.folder / filename
            if not path.exists():
                self.errors.append(f"{filename}: missing template file")
                self.rows[filename] = []
                self.counts[filename] = 0
                continue
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                try:
                    header = next(reader)
                except StopIteration:
                    self.errors.append(f"{filename}: file is empty")
                    self.rows[filename] = []
                    self.counts[filename] = 0
                    continue
                header = [column.strip() for column in header]
                if header != expected:
                    self.errors.append(
                        f"{filename}: header mismatch. Expected {expected}; found {header}"
                    )
                if len(set(header)) != len(header):
                    self.errors.append(f"{filename}: duplicate columns in header")
                records: list[dict[str, str]] = []
                for line, raw in enumerate(reader, start=2):
                    if not any(cell.strip() for cell in raw):
                        continue
                    if len(raw) != len(header):
                        self.error(
                            filename,
                            line,
                            f"expected {len(header)} columns, found {len(raw)}",
                        )
                        continue
                    records.append(
                        {key: value.strip() for key, value in zip(header, raw, strict=False)}
                    )
                self.rows[filename] = records
                self.counts[filename] = len(records)

    def text(self, filename: str, line: int, row: dict[str, str], field: str) -> str:
        value = row.get(field, "").strip()
        if not value:
            self.error(filename, line, f"{field} is required")
        return value

    def decimal(
        self,
        filename: str,
        line: int,
        row: dict[str, str],
        field: str,
        *,
        minimum: Decimal | None = Decimal("0"),
    ) -> Decimal:
        raw = row.get(field, "").strip()
        if raw == "":
            self.error(filename, line, f"{field} is required")
            return Decimal("0")
        try:
            value = Decimal(raw)
        except InvalidOperation:
            self.error(filename, line, f"{field} is not a valid decimal: {raw!r}")
            return Decimal("0")
        if not value.is_finite():
            self.error(filename, line, f"{field} must be finite")
            return Decimal("0")
        if minimum is not None and value < minimum:
            self.error(filename, line, f"{field} must be at least {minimum}")
        return value

    def integer(
        self, filename: str, line: int, row: dict[str, str], field: str, *, minimum: int = 0
    ) -> int:
        raw = row.get(field, "").strip()
        try:
            value = int(raw)
        except ValueError:
            self.error(filename, line, f"{field} is not a whole number: {raw!r}")
            return 0
        if value < minimum:
            self.error(filename, line, f"{field} must be at least {minimum}")
        return value

    def date(self, filename: str, line: int, row: dict[str, str], field: str) -> date | None:
        raw = row.get(field, "").strip()
        if raw == "":
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            self.error(filename, line, f"{field} must use YYYY-MM-DD: {raw!r}")
            return None

    def boolean(self, filename: str, line: int, row: dict[str, str], field: str) -> None:
        raw = row.get(field, "").strip().lower()
        if raw not in {"true", "false"}:
            self.error(filename, line, f"{field} must be true or false")

    def currency(self, filename: str, line: int, row: dict[str, str], field: str) -> str:
        raw = self.text(filename, line, row, field).upper()
        if raw and (len(raw) != 3 or not raw.isalpha()):
            self.error(filename, line, f"{field} must be a three-letter currency code")
        return raw

    def unique(
        self, filename: str, rows: list[dict[str, str]], fields: tuple[str, ...]
    ) -> None:
        seen: dict[tuple[str, ...], int] = {}
        for index, row in enumerate(rows, start=2):
            key = tuple(row.get(field, "").strip().upper() for field in fields)
            if not all(key):
                continue
            if key in seen:
                self.error(
                    filename,
                    index,
                    f"duplicate {'/'.join(fields)} {key}; first seen on line {seen[key]}",
                )
            else:
                seen[key] = index

    def validate(self) -> None:
        company = self.rows["company_profile.csv"]
        if len(company) != 1:
            self.errors.append(
                "company_profile.csv: exactly one legal company record is required "
                f"(found {len(company)})"
            )
        for line, row in enumerate(company, start=2):
            self.text("company_profile.csv", line, row, "legal_name")
            self.text("company_profile.csv", line, row, "tin")
            self.text("company_profile.csv", line, row, "registered_address")
            self.text("company_profile.csv", line, row, "email")
            self.currency("company_profile.csv", line, row, "reporting_currency")
            year_end = row.get("financial_year_end", "").strip()
            if year_end and not re.fullmatch(r"\d{2}-\d{2}", year_end):
                self.error("company_profile.csv", line, "financial_year_end must use MM-DD")

        employee_emails: set[str] = set()
        for line, row in enumerate(self.rows["employees.csv"], start=2):
            email = self.text("employees.csv", line, row, "email").lower()
            if email and "@" not in email:
                self.error("employees.csv", line, "email is not a valid address")
            if email in employee_emails:
                self.error("employees.csv", line, f"duplicate employee email {email}")
            employee_emails.add(email)
            self.text("employees.csv", line, row, "full_name")
            self.text("employees.csv", line, row, "role")
            self.text("employees.csv", line, row, "department")
            self.boolean("employees.csv", line, row, "is_active")
            self.boolean("employees.csv", line, row, "mfa_required")

        for line, row in enumerate(self.rows["equipment.csv"], start=2):
            self.text("equipment.csv", line, row, "name")
            self.text("equipment.csv", line, row, "category")
            self.text("equipment.csv", line, row, "location")
            self.date("equipment.csv", line, row, "acquisition_date")
            self.decimal("equipment.csv", line, row, "acquisition_cost")
            self.currency("equipment.csv", line, row, "currency")
            status = row.get("status", "").strip()
            if status not in EQUIPMENT_STATUSES:
                self.error("equipment.csv", line, f"unknown equipment status {status!r}")
        self.unique("equipment.csv", self.rows["equipment.csv"], ("code",))

        suppliers = self.rows["suppliers.csv"]
        customers = self.rows["customers.csv"]
        projects = self.rows["projects.csv"]
        products = self.rows["products.csv"]
        warehouses = self.rows["warehouses.csv"]
        for filename, rows in (
            ("suppliers.csv", suppliers),
            ("customers.csv", customers),
            ("projects.csv", projects),
            ("products.csv", products),
            ("warehouses.csv", warehouses),
        ):
            self.unique(filename, rows, ("code",))

        for filename, rows in (("suppliers.csv", suppliers), ("customers.csv", customers)):
            for line, row in enumerate(rows, start=2):
                self.text(filename, line, row, "code")
                self.text(filename, line, row, "legal_name")
                self.integer(filename, line, row, "payment_terms_days")
                self.currency(filename, line, row, "default_currency")
                self.boolean(filename, line, row, "is_active")
                if filename == "customers.csv":
                    self.decimal(filename, line, row, "credit_limit")
                    self.boolean(filename, line, row, "credit_hold")

        supplier_codes = {row.get("code", "").strip().upper() for row in suppliers}
        customer_codes = {row.get("code", "").strip().upper() for row in customers}
        project_codes = {row.get("code", "").strip().upper() for row in projects}
        item_codes = {row.get("code", "").strip().upper() for row in products}
        warehouse_codes = {row.get("code", "").strip().upper() for row in warehouses}

        for line, row in enumerate(self.rows["advances.csv"], start=2):
            party_type = row.get("party_type", "").strip().lower()
            party_code = row.get("party_code", "").strip().upper()
            if party_type not in PARTY_TYPES:
                self.error("advances.csv", line, "party_type must be supplier or customer")
            elif party_type == "supplier" and party_code not in supplier_codes:
                self.error("advances.csv", line, f"unknown supplier_code {party_code}")
            elif party_type == "customer" and party_code not in customer_codes:
                self.error("advances.csv", line, f"unknown customer_code {party_code}")
            self.text("advances.csv", line, row, "reference")
            self.decimal("advances.csv", line, row, "amount")
            self.currency("advances.csv", line, row, "currency")
            self.date("advances.csv", line, row, "as_of")
        self.unique(
            "advances.csv",
            self.rows["advances.csv"],
            ("party_type", "party_code", "reference"),
        )

        for line, row in enumerate(projects, start=2):
            self.text("projects.csv", line, row, "name")
            customer = row.get("customer_code", "").strip().upper()
            if customer and customer not in customer_codes:
                self.error("projects.csv", line, f"unknown customer_code {customer}")
            status = row.get("status", "").strip()
            if status not in PROJECT_STATUSES:
                self.error("projects.csv", line, f"unknown project status {status!r}")
            start = self.date("projects.csv", line, row, "start_date")
            end = self.date("projects.csv", line, row, "end_date")
            if start and end and end < start:
                self.error("projects.csv", line, "end_date precedes start_date")
            self.currency("projects.csv", line, row, "currency")
            self.decimal("projects.csv", line, row, "budget_total")

        for line, row in enumerate(products, start=2):
            self.text("products.csv", line, row, "name")
            if row.get("kind", "").strip() not in ITEM_KINDS:
                self.error("products.csv", line, "kind must be product or service")
            self.text("products.csv", line, row, "uom_code")
            self.boolean("products.csv", line, row, "is_active")

        for line, row in enumerate(warehouses, start=2):
            self.text("warehouses.csv", line, row, "name")

        for line, row in enumerate(self.rows["inventory_balances.csv"], start=2):
            warehouse = row.get("warehouse_code", "").strip().upper()
            item = row.get("item_code", "").strip().upper()
            if warehouse not in warehouse_codes:
                self.error("inventory_balances.csv", line, f"unknown warehouse_code {warehouse}")
            if item not in item_codes:
                self.error("inventory_balances.csv", line, f"unknown item_code {item}")
            self.decimal("inventory_balances.csv", line, row, "quantity")
            self.decimal("inventory_balances.csv", line, row, "unit_cost")
            self.date("inventory_balances.csv", line, row, "valuation_date")
        self.unique(
            "inventory_balances.csv",
            self.rows["inventory_balances.csv"],
            ("warehouse_code", "item_code", "valuation_date"),
        )

        self.unique(
            "supplier_invoices.csv",
            self.rows["supplier_invoices.csv"],
            ("supplier_code", "supplier_invoice_number"),
        )
        for line, row in enumerate(self.rows["supplier_invoices.csv"], start=2):
            supplier = row.get("supplier_code", "").strip().upper()
            if supplier not in supplier_codes:
                self.error("supplier_invoices.csv", line, f"unknown supplier_code {supplier}")
            self.text("supplier_invoices.csv", line, row, "supplier_invoice_number")
            invoice_date = self.date("supplier_invoices.csv", line, row, "invoice_date")
            due_date = self.date("supplier_invoices.csv", line, row, "due_date")
            if invoice_date and due_date and due_date < invoice_date:
                self.error("supplier_invoices.csv", line, "due_date precedes invoice_date")
            self.currency("supplier_invoices.csv", line, row, "currency")
            subtotal = self.decimal("supplier_invoices.csv", line, row, "subtotal")
            vat = self.decimal("supplier_invoices.csv", line, row, "vat_total")
            wht = self.decimal("supplier_invoices.csv", line, row, "wht_total")
            total = self.decimal("supplier_invoices.csv", line, row, "total")
            paid = self.decimal("supplier_invoices.csv", line, row, "amount_paid")
            if total != (subtotal + vat - wht).quantize(Decimal("0.01")):
                self.error(
                    "supplier_invoices.csv",
                    line,
                    f"total {total} does not equal subtotal + VAT - WHT "
                    f"({subtotal + vat - wht})",
                )
            if paid > total:
                self.error("supplier_invoices.csv", line, "amount_paid exceeds total")

        for line, row in enumerate(self.rows["customer_invoices.csv"], start=2):
            customer = row.get("customer_code", "").strip().upper()
            if customer not in customer_codes:
                self.error("customer_invoices.csv", line, f"unknown customer_code {customer}")
            project = row.get("project_code", "").strip().upper()
            if project and project not in project_codes:
                self.error("customer_invoices.csv", line, f"unknown project_code {project}")
            invoice_date = self.date("customer_invoices.csv", line, row, "invoice_date")
            due_date = self.date("customer_invoices.csv", line, row, "due_date")
            if invoice_date and due_date and due_date < invoice_date:
                self.error("customer_invoices.csv", line, "due_date precedes invoice_date")
            self.currency("customer_invoices.csv", line, row, "currency")
            subtotal = self.decimal("customer_invoices.csv", line, row, "subtotal")
            vat = self.decimal("customer_invoices.csv", line, row, "vat_total")
            wht = self.decimal("customer_invoices.csv", line, row, "wht_total")
            total = self.decimal("customer_invoices.csv", line, row, "total")
            paid = self.decimal("customer_invoices.csv", line, row, "amount_paid")
            if total != (subtotal + vat - wht).quantize(Decimal("0.01")):
                self.error(
                    "customer_invoices.csv",
                    line,
                    f"total {total} does not equal subtotal + VAT - WHT "
                    f"({subtotal + vat - wht})",
                )
            if paid > total:
                self.error("customer_invoices.csv", line, "amount_paid exceeds total")
        self.unique(
            "customer_invoices.csv",
            self.rows["customer_invoices.csv"],
            ("customer_code", "invoice_date", "subtotal", "total"),
        )

        for line, row in enumerate(self.rows["bank_balances.csv"], start=2):
            self.text("bank_balances.csv", line, row, "bank_account_code")
            self.date("bank_balances.csv", line, row, "statement_date")
            self.decimal("bank_balances.csv", line, row, "balance", minimum=None)
            self.currency("bank_balances.csv", line, row, "currency")
        self.unique(
            "bank_balances.csv",
            self.rows["bank_balances.csv"],
            ("bank_account_code", "statement_date"),
        )

        debit_total = Decimal("0")
        credit_total = Decimal("0")
        for line, row in enumerate(self.rows["opening_trial_balance.csv"], start=2):
            self.text("opening_trial_balance.csv", line, row, "account_code")
            debit = self.decimal("opening_trial_balance.csv", line, row, "debit")
            credit = self.decimal("opening_trial_balance.csv", line, row, "credit")
            if debit > 0 and credit > 0:
                self.error(
                    "opening_trial_balance.csv",
                    line,
                    "a line cannot have both debit and credit",
                )
            debit_total += debit
            credit_total += credit
            self.date("opening_trial_balance.csv", line, row, "as_of")
        if debit_total != credit_total:
            self.errors.append(
                "opening_trial_balance.csv: opening trial balance is not balanced. "
                f"Debits {debit_total}; credits {credit_total}; "
                f"difference {debit_total - credit_total}"
            )
        self.unique(
            "opening_trial_balance.csv",
            self.rows["opening_trial_balance.csv"],
            ("account_code", "as_of"),
        )

        self.unique("commitments.csv", self.rows["commitments.csv"], ("po_number",))
        for line, row in enumerate(self.rows["commitments.csv"], start=2):
            supplier = row.get("supplier_code", "").strip().upper()
            if supplier not in supplier_codes:
                self.error("commitments.csv", line, f"unknown supplier_code {supplier}")
            self.date("commitments.csv", line, row, "order_date")
            self.currency("commitments.csv", line, row, "currency")
            self.decimal("commitments.csv", line, row, "total_value")
            if row.get("status", "").strip() not in COMMITMENT_STATUSES:
                self.error(
                    "commitments.csv",
                    line,
                    f"unknown commitment status {row.get('status', '').strip()!r}",
                )

    def report(self) -> str:
        total_rows = sum(self.counts.values())
        status = "PASS" if not self.errors else "FAIL"
        lines = [
            "# Migration template validation",
            "",
            f"**Result:** {status}",
            f"**Templates:** {len(HEADERS)} files, {total_rows} data rows",
            f"**Errors:** {len(self.errors)}",
            f"**Warnings:** {len(self.warnings)}",
            "",
            "This report validates template structure, data types, cross-file references,",
            "duplicates and invoice/trial-balance arithmetic. It does not import records,",
            "approve account mappings, verify source documents or authorise opening balances.",
            "",
            "## Row counts",
            "",
            "| Template | Rows |",
            "| --- | ---: |",
        ]
        lines += [f"| {name} | {count} |" for name, count in self.counts.items()]
        lines += ["", "## Errors", ""]
        lines += [f"- {item}" for item in self.errors] or ["None."]
        lines += ["", "## Warnings", ""]
        lines += [f"- {item}" for item in self.warnings] or ["None."]
        lines += [
            "",
            "## Boundary",
            "",
            "A PASS is a pre-import structural result only. Trial import into staging,",
            "source-document reconciliation and written Finance/Management approval remain",
            "mandatory before production.",
            "",
        ]
        return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    validator = Validator(args.templates)
    validator.load()
    if not validator.errors:
        validator.validate()
    output = validator.report()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(output, encoding="utf-8")
    print(output)
    return 0 if not validator.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
