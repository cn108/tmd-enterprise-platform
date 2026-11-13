# TMD Enterprise System — Final Data Migration Report

**Date:** 13 November 2026  
**Status:** **templates and validation complete; no real data imported; no production migration approved**  
**Environment used:** local template validation only; isolated QA database used for application testing, not for a company-data import

## 1. Outcome

The migration tooling now covers the requested data domains:

| Domain                                  | Template                    |
| --------------------------------------- | --------------------------- |
| Company legal information and Tax IDs   | `company_profile.csv`       |
| Employees and role/MFA assignment       | `employees.csv`             |
| Suppliers                               | `suppliers.csv`             |
| Customers                               | `customers.csv`             |
| Products and services                   | `products.csv`              |
| Projects and contracts (project header) | `projects.csv`              |
| Warehouses                              | `warehouses.csv`            |
| Equipment and assets                    | `equipment.csv`             |
| Opening inventory                       | `inventory_balances.csv`    |
| Outstanding purchase commitments        | `commitments.csv`           |
| Supplier invoices                       | `supplier_invoices.csv`     |
| Customer invoices                       | `customer_invoices.csv`     |
| Customer and supplier advances          | `advances.csv`              |
| Bank and cash opening balances          | `bank_balances.csv`         |
| Opening trial balance                   | `opening_trial_balance.csv` |

Validation result on 13 November 2026:

```
Templates: 15 files, 17 data rows
Errors: 0
Warnings: 0
Result: PASS
```

Evidence: `docs/reports/evidence/phase-11-migration-template-validation.md`.

A PASS means the files are structurally and arithmetically consistent. It is **not** a trial import, source reconciliation or approval.

## 2. What the validator checks

`scripts/validate_migration.py` checks:

- exact header order and column count for every template;
- required text, decimal, date, currency and boolean values;
- duplicate supplier/customer/project/product/warehouse/equipment codes;
- duplicate employee emails and advance references;
- supplier/customer/warehouse/item references;
- project customer and dates;
- invoice `total = subtotal + VAT − WHT`;
- `amount_paid <= total`;
- bank balance dates/currency;
- opening trial balance debits equal credits, each line using debit or credit but not both;
- company profile exactly one record and valid `MM-DD` year end;
- equipment status vocabulary;
- advance party type and reference;
- commitment status vocabulary.

The validator never writes to a database and never treats a clean result as permission to import.

## 3. Staging rehearsal status

**Not performed as a real import.** The repository has no enabled migration importer. The templates are the controlled input contract, and the validation run is a structural rehearsal only.

A true staging rehearsal is blocked by:

1. No real source extracts or opening balances were supplied.
2. No approved chart of accounts or account-role mappings exist, so the opening trial balance cannot be accepted.
3. No approved tax IDs, VAT/WHT treatment, numbering or cut-off policy exists.
4. No named data owner has certified the source records.
5. No importer has been enabled in this release; adding one without the above would encourage unverified financial data to enter the system.

This is a deliberate safety boundary, not a claim that migration has been completed.

## 4. Required migration procedure

### Phase A — preparation

1. Name the data owner, preparer, reviewer and approver.
2. Freeze the source cut-off date and preserve original exports and checksums.
3. Obtain the approved chart of accounts, mappings, tax configuration and numbering.
4. Reconcile source control accounts: bank, AP, AR, inventory, VAT/WHT and payroll if applicable.
5. Populate every template from source records; do not invent missing values.
6. Record every rejected/unmapped source row in the exception log.

### Phase B — validation

1. Run `python scripts/validate_migration.py --templates <folder> --report <evidence.md>`.
2. Fix source data, not the validator.
3. Obtain a second-person review of the row counts and key totals.
4. Compare each control total to the source trial balance and subledgers.

### Phase C — isolated staging trial

1. Restore a verified production-like backup into an isolated staging database.
2. Import master data first: company, employees, suppliers, customers, products, warehouses, equipment.
3. Import projects and opening stock; reconcile quantities and valuation.
4. Import outstanding commitments and invoices; reconcile AP/AR control totals.
5. Import bank/cash balances and advances.
6. Post the opening trial balance through the controlled opening-balance document, not SQL.
7. Run the application trial balance, balance sheet and ageing reports.
8. Compare every control account to its source schedule and record differences.

### Phase D — discrepancy resolution

Produce a discrepancy report containing:

| Field                       | Requirement                                              |
| --------------------------- | -------------------------------------------------------- |
| Source row/reference        | Exact source identifier                                  |
| Target record               | Created record ID or rejection                           |
| Field                       | Difference                                               |
| Source value / target value | Exact values                                             |
| Reason                      | Missing source, mapping, duplicate, policy or data error |
| Owner / resolution          | Person and action                                        |
| Status                      | Open / corrected / accepted by Finance                   |

No row may be silently dropped. Historical documents remain in the original source system until written acceptance.

### Phase E — production cut-over

1. Obtain signed staging reconciliation and management approval.
2. Take and verify a pre-migration production backup.
3. Freeze legacy writes.
4. Import in the controlled order; record every batch and row count.
5. Post the approved opening trial balance.
6. Reconcile bank, AP, AR, inventory, tax and advances.
7. Run smoke tests; keep invoices/posting/NRS disabled unless separately authorised.
8. Obtain sign-off; preserve source data for the agreed retention period.
9. If reconciliation fails, stop and restore; do not patch balances manually.

## 5. Data-quality rules for TMD

- Use ISO dates and dot decimals; no formulas, totals or blank spacer rows.
- Invoice totals must equal subtotal plus VAT minus WHT.
- The opening trial balance must balance before import.
- Every supplier/customer/project/product/warehouse/equipment code must be unique.
- Employee roles must come from the approved role matrix; MFA requirement must be explicit.
- Do not import a bank balance without the corresponding bank account and statement date.
- Do not import an opening balance without an approved account code.
- Do not use a personal email address for company or employee records.
- Do not import live data into the development or QA database.

## 6. Reconciliation evidence required before approval

| Schedule               | Reconciled to                                                      |
| ---------------------- | ------------------------------------------------------------------ |
| Accounts payable       | Supplier statements/invoices, net of approved credits and payments |
| Accounts receivable    | Customer invoices, receipts, approved credits and advances         |
| Inventory              | Count sheets/stock records and valuation                           |
| Bank/cash              | Bank statements, cash count and unreconciled items                 |
| VAT                    | Sales/purchase tax listings and return position                    |
| WHT                    | Deductions, certificates and remittance position                   |
| Fixed assets/equipment | Asset register and physical verification                           |
| Opening trial balance  | Sum of reconciled control accounts and signed source accounts      |

## 7. Current limitations

- No real company, employee, supplier, customer, stock, asset or financial data was supplied.
- No approved opening balances exist.
- No data migration has been executed.
- No source-document reconciliation has been performed.
- The QA synthetic ledger is for application testing only and must not be used as company records.
- Migration templates do not replace a signed cut-over plan or professional accounting review.

## 8. Sign-off

| Role                            | Name | Decision                                  | Date | Signature |
| ------------------------------- | ---- | ----------------------------------------- | ---- | --------- |
| Data owner / Finance Controller |      | Source data certified                     |      |           |
| External accountant             |      | Opening balances and mappings approved    |      |           |
| Software Developer              |      | Validation and technical import readiness |      |           |
| Managing Director               |      | Migration and cut-over authorised         |      |           |
