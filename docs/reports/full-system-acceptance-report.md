# Full-system acceptance report — Phases 0–11

**Date:** 12 November 2026
**System:** TICO MCDON LIMITED enterprise application
**Assessment basis:** Direct repository inspection, automated tests, live
development data, browser evidence, restore rehearsal and migration-template
validation.
**Assignment boundary:** production go-live, financial activation, bank
execution and NRS submission were not authorised and were not performed.

## 1. Overall status

**Classification: B — READY FOR STAGING/UAT BUT NOT PRODUCTION.**

The application is a substantial, testable enterprise system with working
procurement, inventory, accounting, invoicing, banking, projects, services,
leasing and reporting modules. The most serious authorization defects were
found and fixed during this audit. The full backend and frontend suites pass.

It is not classified A because:

1. There is no approved chart of accounts, account mapping, posting rule, tax
   policy or opening balance; formal statements therefore show zero with
   warnings.
2. No staging/production deployment has been executed; TLS, production secrets,
   monitoring and off-host encrypted backups are not configured.
3. No production-scale load, concurrency or failure testing has been performed.
4. UAT by TMD department leads has not been completed.
5. MFA is not enforced and inventory/procurement read access is policy-unresolved.
6. Migration has not been trial-imported and reconciled to source documents.

## 2. Phase and module completion

| Phase | Scope | State | Evidence / gap |
| --- | --- | --- | --- |
| 0 | Business discovery and requirements | Documents exist; assumptions recorded | Configuration/decision reports; not a software deliverable |
| 1 | Engineering foundations | Ready for review | 295 backend tests, lint, migrations |
| 2 | Identity and authentication (W1/W2) | Partial | Login, lockout, sessions, roles; original exit gate not claimed complete |
| 3 | Master data | Backend complete; UI generic | Parties/catalogue/warehousing APIs and workspace; broad audit trail partial |
| 4 | Procurement | Backend lifecycle complete; UI partial | Request→RFQ→PO→receipt tests; dedicated screens incomplete |
| 5 | Inventory/warehouse | Backend complete; UI partial | Stock ledger, valuation, documents, constraints; dedicated screens incomplete |
| 6 | Accounting | Engine complete; configuration absent | Double-entry, posting, periods, reports; no approved data |
| 7A | AP and invoice issuance | Complete for controlled use | Browser-reviewed; live issuance not authorised |
| 7B | Financial activation | **Blocked** | Missing Finance Controller, mappings, tax policy, opening balances |
| 8 | Banking/reconciliation | Complete; execution disabled | Reconciliation tests; no live bank execution |
| 9 | Projects/services/leasing | Complete; accounting recognition excluded | Module tests and prior browser review |
| 10 | Reporting/BI | Complete | 19 reporting tests, 11 UI tabs, screenshots |
| 11 | Production readiness | **Prepared, not production-ready** | Docker/nginx/backup/manuals; monitors, TLS, load test missing |

Backend functionality is generally ahead of dedicated frontend screens.
Generic workspace/API access exists for several document types, but that is not
equivalent to a purpose-built screen for every role. This is a UAT/usability
gap, not evidence that APIs are missing.

## 3. Exact verification results

Executed on 12 November 2026 on the local workspace:

| Check | Command | Result |
| --- | --- | --- |
| Backend full suite | `python -m pytest -q` | **295 passed** |
| Reporting suite | `pytest apps/reporting/tests -q` | **19 passed** |
| Frontend unit suite | `npm test -- --watch=false` | **50 passed / 8 files** |
| Frontend production build | `npm run build` | **Passed** (307.61 kB initial raw / 82.77 kB transfer) |
| Frontend lint | `npm run lint` | **Passed** |
| Backend Ruff | `python -m ruff check .` | **Passed** |
| Migration drift | `manage.py makemigrations --check --dry-run` | **No changes detected** |
| Python dependencies | `pip check` | **No broken requirements** |
| npm production audit | `npm audit --omit=dev --audit-level=high` | **0 vulnerabilities** |
| Production deployment check | `manage.py check --deploy` with required env | **Exit 0**; 165 OpenAPI schema warnings plus one weak placeholder-key warning |
| Secret scan | pattern scan of source/config/scripts | No real credentials; synthetic test passwords only |

The production check used a throwaway Fernet key and a deliberately obvious
test secret. A real deployment must supply a strong random secret and real TLS
certificates. The 165 warnings are API-schema warnings for plain `APIView`
endpoints, not failed security checks.

## 4. Browser evidence

- All 11 reporting tabs were exercised in the Angular portal with no console
  errors; loading/empty/error states and permission-based tab visibility were
  checked.
- Screenshots:
  - `docs/reports/evidence/phase-10-reporting-overview.png`
  - `docs/reports/evidence/phase-10-financial-statements.png`
- Earlier phases 7A, 8 and 9 recorded browser reviews in their reports.
- **Not performed in this audit:** a fresh click-through of every module,
  every form and every role. That remains UAT scope. The build and component
  tests do not prove every interactive workflow.

## 5. Defects discovered and corrected

| ID | Severity | Defect | Correction |
| --- | --- | --- | --- |
| D-AUD-01 | Critical | Any authenticated user could create/update master data | Model permissions added; regression test |
| D-AUD-02 | Critical | Any authenticated user could read the ledger/statements | Accounting read permissions added; regression test |
| D-10-02 | High | Financial reports open to any authenticated user | Reporting permissions |
| D-10-04 | High | Gross profit copied from net result | Only approved cost-of-sales mapping |
| D-10-05 | High | Cash flow guessed account classification | Approved role mapping + incomplete warning |
| D-10-06 | High | Mixed currencies silently summed | Per-currency totals |
| D-10-01 | High | Export `?format=csv` returned 404 | `?output=csv` |
| D-10-07/08 | Medium | CSV formula injection / silent PDF truncation | Neutralisation and truncation notice |
| D-10-09/10/11 | Medium | Date/overdue/ageing report errors | Date-correct calculations |
| D-10-03/12 | Medium/Low | Counts shown as currency; inconsistent labels | Formatting/labels corrected |

Plus atomicity for invoice/note/payment/request/quote/PO/opening-balance/posting
writes and a rollback regression test.

Full details and open items: `full-system-defect-register.md`.

## 6. Security findings

### Closed

- Master-data and accounting read/write authorization gaps (above).
- Document API already permissioned; reverified.
- Bank account data encrypted and masked; change approval self-approval blocked.
- Production settings fail closed without secrets; security headers configured.
- No real secrets in source; npm high-severity audit clean.

### Open

| ID | Severity | Finding |
| --- | --- | --- |
| SEC-01 | High | MFA not enforced despite `mfa_required` field |
| SEC-04 | High | Inventory/procurement read-access policy unresolved |
| SEC-05 | Medium | Default `IsAuthenticated` can expose future endpoints |
| SEC-06 | Medium | No general API throttling beyond password reset |
| D-AUD-04 | High | No monitoring, alerting or off-host encrypted backup |

## 7. Financial integrity findings

- Formal reports use posted double-entry lines, not invoice totals.
- Unbalanced journals, posted edits and negative stock are blocked by
  constraints/tests.
- No unbalanced posted journal or negative stock layer exists in live data.
- Mixed currencies, gross profit, cash-flow classification and CSV/PDF export
  defects were corrected.
- **No approved accounting configuration exists.** Live figures are ₦0.00 with
  warnings and cannot be certified as TMD's financial position.
- Opening balances, mappings, tax policy, WHT/VAT treatment and inventory
  valuation require professional approval.
- No live payment, bank transfer or NRS submission was performed.

## 8. Backup and restoration evidence

Restore test: **PASS** (`docs/reports/evidence/phase-11-restore-test.txt`).

| Measure | Source | Restored |
| --- | ---: | ---: |
| Migrations | 63 | 63 |
| Journals | 1 | 1 |
| Journal lines | 2 | 2 |
| Debit / credit | ₦125.50 | ₦125.50 |
| Private documents | 101 | 101 |
| Balanced | yes | yes |

The source was an isolated synthetic database, not live records, and the test
databases were removed. This proves the restore procedure, not that automated
production backups, encryption, off-host retention or monitoring exist.

## 9. Migration readiness

- 11 CSV templates, 12 rows, 0 errors and 0 warnings in structural validation.
- No trial import, source-document reconciliation, opening-balance approval or
  production cut-over has occurred.
- Migration is **not ready for financial use**; the templates are ready for a
  controlled staging exercise.

## 10. Production deployment readiness

| Requirement | State |
| --- | --- |
| Reproducible Docker/nginx/Gunicorn assets | Present |
| Separate staging/production configuration pattern | Present |
| Fail-closed secrets and TLS config | Present; certificates/secrets not supplied |
| Automated backup/restore scripts | Present; restore tested |
| Off-host encryption/monitoring/scheduling | Missing |
| Performance/concurrency/failure tests | Missing |
| Monitoring/alerting | Missing |
| Operational manuals | Present (13 documents) |
| Management go-live authorisation | Not given |

## 11. Outstanding management and accounting approvals

1. Approve the provisional role matrix and access policy, including inventory
   and procurement read access and MFA requirements.
2. Appoint a Finance Controller and approve chart of accounts, mappings,
   posting rules, tax policy and inventory valuation.
3. Approve opening balances and the financial cut-off date.
4. Approve the migration reconciliation and trial import.
5. Approve RPO/RTO and fund encrypted off-host backup, monitoring and on-call.
6. Complete UAT with procurement, warehouse, finance, projects, banking and
   reporting leads.
7. Authorise any live bank/NRS integration separately; it remains disabled.
8. Record written go-live authorisation.

## 12. Recommended next action

Do **not** go live. Proceed to a controlled staging/UAT programme:

1. Provision staging with TLS, secret manager and private Postgres/Redis.
2. Configure encrypted off-host backups, monitoring and alerts.
3. Run load/concurrency/failure tests and fix findings.
4. Decide the inventory/procurement access policy and implement MFA.
5. Complete accounting configuration and trial-import/reconcile the migration.
6. Run department UAT and close usability/API-schema gaps.
7. Re-audit the staging evidence, then seek management production approval.

## 13. Final statement

The application is technically credible and materially safer after this audit,
but it is **not** a production-ready financial system today. The dominant
blockers are missing approved accounting data, missing operational controls and
unfinished UAT — not a failing build.

**Final classification: B — READY FOR STAGING/UAT, NOT PRODUCTION.**
