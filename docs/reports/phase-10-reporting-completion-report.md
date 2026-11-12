# Phase 10 — Reporting and business intelligence completion report

**Date:** 12 November 2026
**Status:** implementation complete; operational use limited by missing approved accounting configuration
**Scope:** `backend/apps/reporting`, reporting APIs and exports, Angular reporting workspace, tests and browser evidence.

## 1. Outcome

A dedicated read-only reporting module now serves management information from the existing source modules. Formal financial statements are calculated from **posted journal lines** through `apps.accounting.services`; the reporting module does not recalculate a profit and loss statement from invoice totals.

The Angular workspace has eleven report tabs, period controls, summary cards, bars, tables, empty/error/loading states, CSV/PDF export, print and permission-hidden tabs. The server enforces every permission regardless of which tab the browser shows.

The live development database currently has **no chart of accounts, no approved account mappings and no posted journals**. The workspace therefore correctly reports **₦0.00 posted results** and displays completeness warnings rather than inventing figures. This is the required behaviour, not a failure of Phase 10.

## 2. Backend deliverables

### 2.1 Module

- `apps/reporting/services.py`: calculations for financial, receivable/payable, procurement, inventory, project, service/equipment, banking, tax and period reports.
- `apps/reporting/views.py`: read-only report and export views, date validation, permission checks, audit records, CSV/PDF generation.
- `apps/reporting/models.py`: `ReportExport` audit record and reporting permissions.
- `apps/reporting/urls.py`: `/api/v1/reporting/<name>/` and `/export/`.
- Migration `0001_initial` applied locally.
- Registered in `config/settings/base.py` and `config/urls.py`.

### 2.2 Report coverage

| Area | Reports |
| --- | --- |
| Financial | Profit or loss, balance sheet, cash flow, trial balance, general ledger, journal register, receivables ageing, payables ageing, bank reconciliation summary, inventory valuation, tax, period status |
| Procurement | Purchase orders by status, committed value, supplier history, outstanding deliveries, damaged/rejected quantity, quote lead time, approved invoice document value |
| Inventory | Valuation, balances, movements, project issues, ageing, low stock, damage, adjustments, warehouse activity |
| Projects | Budget vs actual, commitments, available budget, estimated margin, milestones, approved cost by category |
| Services/leasing | Work orders by status, completion rate, maintenance, equipment utilisation, rental agreements, overdue returns |
| Banking | Accounts, book movements, reconciliations, statements, cash accounts |
| Tax | Input/output VAT, recoverable VAT, WHT, notes and configuration register |
| Management | Executive overview with posted results, cash availability, document receivables/payables, inventory, projects, commitments and operational counts |

### 2.3 Integrity rules implemented

1. Formal statements use only `JournalEntry.Status.POSTED` lines.
2. Unposted journals are excluded from statements and labelled in the journal register.
3. Trial balance debit and credit totals are calculated from posted lines and compared.
4. Balance sheet exposes `unclosed_result` and `balanced`; it is not forced to balance.
5. Purchase order values are commitments, never expenses.
6. Receivables and payables are labelled as **approved document balances**, not ledger balances.
7. Inventory valuation is unavailable when no valuation policy exists.
8. Project margin is labelled an estimate; revenue recognition is not calculated.
9. Cash flow refuses to guess cash accounts unless an active bank account is linked to a GL account.
10. Cash-flow classification uses approved account-role mappings. An unmapped balance-sheet counterpart is shown as **Unclassified**, and the statement is marked incomplete rather than forcing it into investing or financing.
11. Gross profit is available only when an approved `COST_OF_SALES` mapping exists; it is never substituted with net result.
12. Multi-currency invoice totals are not added together. If more than one currency is present, totals are shown per currency and mixed totals are withheld.
13. Reporting warnings explicitly state when figures are incomplete.
14. Exports are audited; CSV values that could be interpreted as spreadsheet formulas are neutralised; PDF truncation beyond 2,000 values is stated.
15. General-ledger report requires an account and returns opening/closing balances from posted lines.

### 2.4 Permissions

Added:

- `reporting.view_reporting`
- `reporting.view_financialreporting`
- `reporting.export_reporting`

The provisional role matrix was corrected for Banking, Services, Leasing and reporting. Operational roles do not automatically receive formal financial statements. A dedicated regression test (`apps/core/tests/test_role_matrix.py`) detects future drift.

## 3. Frontend deliverables

`frontend/src/app/features/reports/` now provides:

- Executive, financial statements, ledger, receivables, payables, procurement, inventory, projects, services/equipment, banking and tax tabs.
- From/To dates and Run report.
- KPI cards with source labels.
- Interactive comparison bars and a selected-value announcement.
- Data tables with currency/count formatting, 250-row display bound and explicit notice when truncated.
- Completeness warnings and definitions of each figure.
- CSV/PDF export, print and API reference.
- Loading, empty and error states.
- Permission-based tab visibility from `/api/v1/auth/me/`.
- Mixed-currency ageing and tax summaries that avoid adding currencies.

`reports.component.spec.ts` covers rendering, permission filtering, export parameters and empty states. Frontend suite: 50 tests passing; production build and lint pass.

## 4. Defects found and corrected during Phase 10/audit

| ID | Severity | Defect | Correction | Regression |
| --- | --- | --- | --- | --- |
| D-10-01 | High | Export `?format=csv` returned 404 because DRF reserves `format` | Switched to `?output=csv` | Reporting export tests |
| D-10-02 | High | Any authenticated user could read formal financial reports | Added reporting permissions and role bundles | Permission tests |
| D-10-03 | High | Operational counts displayed as currency (e.g. `₦0.00` work orders) | Per-row formatting kind | Browser recheck |
| D-10-04 | High | Gross profit overwritten with net result | Gross profit computed only from approved `COST_OF_SALES`; otherwise unavailable | `test_gross_profit_requires_an_approved_cost_of_sales_mapping` |
| D-10-05 | High | Cash flow classified every asset counterpart as investing, including receivables | Role-based operating/investing/financing classification; Unclassified warning | Cash-flow role and incomplete tests |
| D-10-06 | High | Receivable/payable and tax totals silently added different currencies | Per-currency reporting, mixed totals withheld | Multi-currency safeguards (implementation and code review) |
| D-10-07 | Medium | CSV export allowed spreadsheet formula injection | Formula neutralisation without changing numeric values | `test_csv_export_neutralises_spreadsheet_formulas` |
| D-10-08 | Medium | PDF silently truncated after 2,000 values | PDF now states truncation and points to CSV | Export code review |
| D-10-09 | Medium | Procurement supplier invoice totals ignored report dates | Date filters applied | Report code review |
| D-10-10 | Medium | Outstanding deliveries excluded overdue schedules before the period start | Report uses all schedules due by period end | Report code review |
| D-10-11 | Medium | Inventory ageing used today's date instead of report end date | Ageing calculated against report end | Report code review |
| D-10-12 | Low | Ageing bucket labels inconsistent (`31–60`, `Over 90`) | Standardised labels | Report code review |

## 5. Test evidence

Executed on 12 November 2026:

- Backend full suite: **295 passed** (`pytest -q`).
- Reporting suite: **19 passed** (authorization, posted-only statements, trial balance, cash-flow role classification, unmapped cash flow, gross profit, ageing, inventory availability, overview separation, exports, formula injection).
- Role matrix suite: included in full backend run.
- Frontend: **50 passed**, production build passed, lint passed.
- Browser: live Angular `/reports` loaded with no console errors; all eleven tabs returned data/empty states without error; executive and financial statement screenshots captured.
- Live API requests observed: `/api/v1/accounts/`, `/reporting/overview/`, `/reporting/periods/`, `/reporting/trial-balance/`, `/reporting/financial-statements/`, `/reporting/inventory/` all HTTP 200.

Evidence:

- `docs/reports/evidence/phase-10-reporting-overview.png`
- `docs/reports/evidence/phase-10-financial-statements.png`

## 6. Limitations and blockers

1. **No live financial statements can be presented as complete** because no chart of accounts, approved mappings, opening balances or posted journals exist.
2. The Finance Controller posting review has not occurred; pending financial events are excluded.
3. No bank account is linked to a GL account, so GL cash flow is unavailable. Recorded bank opening balances are shown separately.
4. Tax figures are approved-document totals, not a tax return or remittance report.
5. Multi-currency amounts are not converted or revalued.
6. Reports are synchronous and read-only; very large exports can take time.
7. Reporting does not replace approved accounting policy, opening balances or management review.

## 7. Phase 10 conclusion

**Phase 10 implementation: COMPLETE.**

The reporting feature is technically functional, permission-controlled, tested and honest about missing accounting configuration. It is suitable for UAT and management review once synthetic or approved test journals are posted. It is **not** evidence that TMD's production financial statements are complete, because the required accounting configuration and approvals do not exist.
