# Full-system defect register

**Date:** 12 November 2026
**Scope:** Phases 0–11 implementation and audit findings.
**Rule applied:** fix safe critical/high defects; do not hide unresolved items;
do not weaken tests or suppress errors.

## 1. Summary

| Severity | Found | Fixed | Open | Accepted boundary |
| --- | ---: | ---: | ---: | ---: |
| Critical | 2 | 2 | 0 | 0 |
| High | 10 | 5 | 5 | 0 |
| Medium | 15 | 6 | 7 | 2 |
| Low | 3 | 1 | 1 | 1 |
| **Total** | **30** | **14** | **13** | **3** |

Open items are policy/operational blockers, not silently accepted defects. No
critical defect remains open.

## 2. Critical and high defects

### D-AUD-01 — Master-data endpoints accepted any authenticated user

- **Severity:** Critical
- **Module:** Parties, catalogue, organisation, warehousing
- **Description:** Any signed-in employee could list, create and update
  suppliers, customers, catalogue items, warehouses, departments and cost
  centres. Hiding buttons did not protect the API.
- **Reproduction:** Sign in as a user with no `parties` permission and POST
  `/api/v1/suppliers/`; previously returned 201.
- **Root cause:** `MasterDataViewSet`/`NoDeleteViewSet` inherited the global
  `IsAuthenticated` default and only transaction viewsets had explicit checks.
- **Files:** `backend/shared/permissions.py` (new),
  `backend/shared/viewsets.py`, `apps/parties/views.py`,
  `apps/catalogue/views.py`, `apps/organisation/views.py`,
  `apps/warehousing/views.py`.
- **Correction:** Model permission class maps GET to `view_*`, POST to `add_*`,
  PUT/PATCH to `change_*`; DELETE remains a controlled 409. Custom actions keep
  their own authorization.
- **Regression:** `test_master_data_requires_model_permissions` (403 read/write,
  200 read with view, 403 write with read-only).
- **Verification:** Targeted and full suites pass; Ruff passes.

### D-AUD-02 — Accounting and financial statements readable by any employee

- **Severity:** Critical (ledger confidentiality)
- **Module:** Accounting / reporting
- **Description:** Accounts, journals, periods, mappings, posting rules, trial
  balance, financial statements and general ledger were readable by any
  authenticated user.
- **Root cause:** APIViews and accounting viewsets had action-specific write
  checks but no read permission.
- **Files:** `apps/accounting/views.py`, `backend/conftest.py`.
- **Correction:** `AccountingReadMixin` requires model `view_*`; trial balance,
  financial statements and general ledger require `accounting.view_account`.
- **Regression:** `test_financial_views_require_accounting_permission`.
- **Verification:** Accounting suite 31 tests pass; full suite 295 pass.

### D-10-01 — Export format parameter returned 404

- **Severity:** High
- **Module:** Reporting exports
- **Description:** `?format=csv` was consumed by DRF content negotiation and did
  not reach the export view.
- **Root cause:** Reserved DRF query parameter.
- **Files:** `apps/reporting/views.py`, `frontend/.../reports.component.ts`.
- **Correction:** Use `?output=csv|pdf`.
- **Regression:** Reporting export tests.
- **Verification:** Browser/API export checks pass.

### D-10-02 — Formal financial reports open to any authenticated user

- **Severity:** High
- **Module:** Reporting
- **Description:** Financial reports could be read without reporting permission.
- **Root cause:** Reporting views used a generic authenticated check.
- **Files:** `apps/reporting/views.py`, `apps/core/role_matrix.py`.
- **Correction:** `view_reporting`, `view_financialreporting`, `export_reporting`;
  financial reports require the financial permission.
- **Regression:** Reporting permission tests.
- **Verification:** Unauthorised 403; authorised 200.

### D-10-04 — Gross profit copied from net result

- **Severity:** High
- **Module:** Reporting
- **Description:** When no cost-of-sales mapping existed, gross profit showed the
  net result, overstating/understating margin.
- **Root cause:** Fallback calculation.
- **Files:** `apps/reporting/services.py`.
- **Correction:** Gross profit is computed only from an approved
  `COST_OF_SALES` mapping; otherwise it is unavailable with a warning.
- **Regression:** `test_gross_profit_requires_an_approved_cost_of_sales_mapping`.
- **Verification:** Passing.

### D-10-05 — Cash flow guessed account classification

- **Severity:** High
- **Module:** Reporting
- **Description:** Every asset counterpart was classified as investing,
  including receivables; liabilities were forced into financing.
- **Root cause:** Type-based guess instead of approved roles.
- **Files:** `apps/reporting/services.py`.
- **Correction:** Approved role mapping; unmapped amounts shown as
  **Unclassified** and the statement marked incomplete.
- **Regression:** Cash-flow role and incomplete-statement tests.
- **Verification:** Passing.

### D-10-06 — Mixed currencies silently summed

- **Severity:** High
- **Module:** Reporting (receivables, payables, tax, overview)
- **Description:** Totals added different currencies without conversion.
- **Correction:** Per-currency totals; mixed totals withheld and labelled.
- **Files:** `apps/reporting/services.py`, reports component.
- **Regression:** Service/report tests and code inspection.
- **Verification:** Mixed-currency paths return separated figures.

### D-10-03 — Counts formatted as currency

- **Severity:** Medium
- **Module:** Reporting frontend
- **Description:** Work-order and other counts displayed as `₦0.00`.
- **Correction:** Per-row `kind` formatting.
- **Files:** `frontend/src/app/features/reports/reports.component.*`.
- **Regression:** Component tests.
- **Verification:** Browser recheck.

### D-10-07 — CSV formula injection

- **Severity:** Medium
- **Module:** Reporting export
- **Description:** Cells beginning `=`, `+`, `-`, `@` could execute in a
  spreadsheet.
- **Correction:** Neutralise formula-leading text without altering numeric
  values.
- **Files:** `apps/reporting/views.py`.
- **Regression:** `test_csv_export_neutralises_spreadsheet_formulas`.
- **Verification:** Passing.

### D-10-08 — PDF silently truncated

- **Severity:** Medium
- **Module:** Reporting export
- **Description:** PDF stopped after 2,000 values with no notice.
- **Correction:** Explicit truncation notice; CSV remains complete.
- **Files:** `apps/reporting/views.py`.
- **Regression:** Export code review.
- **Verification:** Notice present in generated PDF.

### D-10-09 — Procurement report ignored date range

- **Severity:** Medium
- **Module:** Procurement reporting
- **Description:** Supplier invoice totals did not apply report dates.
- **Correction:** Date filters applied.
- **Files:** `apps/reporting/services.py`.
- **Regression:** Report tests/code review.
- **Verification:** Date-bounded totals.

### D-10-10 — Outstanding deliveries excluded overdue items

- **Severity:** Medium
- **Module:** Procurement reporting
- **Description:** Schedules overdue before period start were omitted.
- **Correction:** Include all schedules due by period end.
- **Files:** `apps/reporting/services.py`.
- **Verification:** Query inspection and report test data.

### D-10-11 — Inventory ageing used today instead of report end

- **Severity:** Medium
- **Module:** Inventory reporting
- **Correction:** Ageing calculated against report end date.
- **Files:** `apps/reporting/services.py`.
- **Verification:** Date-boundary tests.

### D-10-12 — Inconsistent ageing labels

- **Severity:** Low
- **Module:** Reporting
- **Correction:** Standardised bucket labels.
- **Files:** `apps/reporting/services.py`.
- **Verification:** UI/table inspection.

## 3. Other audit and security findings

| ID | Severity | Finding | State | Evidence / owner |
| --- | --- | --- | --- | --- |
| D-AUD-03 | High | No production-scale load/concurrency/failure test | **Open** | Phase 11 B-11-07; technical owner |
| D-AUD-04 | High | No production monitoring, alerting or off-host encrypted backup | **Open** | Phase 11 B-11-04/05; infrastructure |
| SEC-01 | High | MFA field exists but no MFA enforcement | **Open** | Security audit; management/technical owner |
| SEC-04 | High | Inventory/procurement read endpoints remain authentication-based | **Open** | Requires access-policy decision |
| SEC-05 | Medium | Global default permission is `IsAuthenticated`, so a forgotten class exposes data | **Open** | Architecture hardening |
| SEC-06 | Medium | No general API throttling beyond password reset | **Open** | Add report/export/auth throttles |
| D-AUD-05 | Medium | No background worker/task queue; all work synchronous | **Open** | Phase 11 B-11-06 |
| D-AUD-06 | Medium | Some backend workflows lack dedicated Angular screens | **Open** | UAT usability backlog |
| D-AUD-07 | Medium | 165 OpenAPI schema warnings for plain APIViews | **Open** | Documentation backlog |
| D-AUD-08 | Low | Phase 3–6 reports stale about permissions/screens | **Open** | Documentation correction |
| D-AUD-09 | Low | Very large report exports are synchronous; UI tables truncate at 250 rows with notice | Accepted limitation | Documented in reporting manual |
| FI-05 | High | No approved chart, mappings, rules, tax policy or opening balances | **Open** | Finance Controller/management |
| FI-06 | Medium | No FX conversion/revaluation | **Open** | Accounting policy |
| FI-07 | Medium | Tax report is document-based, not a tax return | Accepted boundary | Labelled in UI/manual |
| FI-08 | Medium | No revenue recognition, lease accounting or interest | Accepted boundary | Requires policy/authorisation |
| FI-09 | Medium | No reconciled opening balance/migration | **Open** | Migration blocker |

## 4. Verification of corrections

- `test_master_data_requires_model_permissions`: 403 without permission, 200
  read with `view_party`, 403 write with read-only permission.
- `test_financial_views_require_accounting_permission`: 403 for accounts/trial
  balance/statements without permission, 200 with `view_account`.
- Existing rollback test: failed invoice transaction leaves no partial records.
- Existing reporting tests: posted-only statements, cash-flow mapping, gross
  profit, export formulas.
- Full backend: 295 passed; frontend 50 passed; build/lint/Ruff/migrations pass.

## 5. Defect-management conclusion

All safe critical and high defects identified in the code were corrected. The
remaining high items are operational or policy blockers that cannot be resolved
without a host, credentials, management decisions or professional accounting
approval. They are explicitly carried into the acceptance report.
