# Full-system technical audit — Phases 0–11

**Date:** 12 November 2026
**Scope:** Django API, Angular portal, PostgreSQL schema, background/runtime behaviour, deployment assets and documentation.
**Method:** Repository inspection, model/view/serializer review, endpoint permission tracing, full test execution, migration check, live development database inspection and review of prior phase evidence. No production system was accessed.

## 1. Overall technical status

The application is a coherent modular monolith with 16 Django apps and a single
Angular SPA. It is not a collection of disconnected demos: procurement,
inventory, accounting, invoicing, banking, projects, services, leasing and
reporting share real foreign keys and transactional services. The backend suite
(295 tests), frontend suite (50 tests), lint, production build and migration
drift check all pass.

The system is suitable for staging/UAT with synthetic data. It is **not**
production-ready because the accounting configuration, production operations
and several verification activities are incomplete.

## 2. Architecture

| Layer | Implementation | Assessment |
| --- | --- | --- |
| API | Django 5.2 + DRF, versioned `/api/v1/`, session auth, CSRF, OpenAPI schema | Coherent; schema generation has warnings for plain `APIView` endpoints |
| Domain | Separate apps: identity, core, organisation, parties, catalogue, warehousing, procurement, inventory, accounting, invoicing, banking, documents, projects, services, leasing, reporting | Good bounded contexts; no microservice split imposed |
| Data | PostgreSQL 16, decimal fields, check/unique constraints, PROTECT on historical references | Strong for financial and stock records |
| Frontend | Angular standalone SPA: dashboard, login, generic workspace, administration, 11-tab reporting workspace | Functional; not every backend action has a dedicated screen |
| Deployment | Docker Compose, nginx TLS, Gunicorn, private Postgres/Redis | Assets present; not deployed or load-tested |
| Observability | Structured JSON logs, request IDs, health endpoints | Basic; no metrics, tracing, error tracker or alerts |

The monolith is appropriate for TMD's size. Splitting into services now would
add operational cost without solving a demonstrated problem.

## 3. Module findings

### 3.1 Identity and access

- Session authentication, CSRF enforcement, Argon2 hashing and Axes lockout are
  configured.
- Role bundles are data-driven in `apps/core/role_matrix.py`; a drift test
  compares the provisional matrix with actual permissions.
- **Fixed:** master-data viewsets (parties, catalogue, organisation,
  warehousing) previously inherited `IsAuthenticated` only. Any signed-in user
  could read and modify suppliers, customers, items, warehouses, departments
  and cost centres. They now use `ModelPermission`; reads require `view_*`,
  creates `add_*`, updates `change_*`, and deletes remain controlled
  deactivations/409 responses.
- **Fixed:** accounting list/read endpoints (accounts, journals, periods,
  mappings, posting rules, financial events) and trial balance, financial
  statements and general ledger were readable by any authenticated user. They
  now require the corresponding `accounting.view_*` permission.
- Document categories, documents and links already enforce document
  permissions and were re-verified.
- Residual: inventory and procurement read endpoints still use authentication
  plus action-specific controls. Tightening them needs a policy decision about
  which employees may see stock, supplier quotes and purchase history.

### 3.2 Master data

Parties use one table with supplier/customer flags, preventing duplicate
companies. Codes are normalised and unique. Categories, contacts, addresses,
tax registrations, bank accounts and compliance documents have validation.
Bank account numbers are encrypted and masked. Deletion is blocked; records are
deactivated. The new model-permission layer closes the largest authorization
gap found in the audit.

### 3.3 Procurement

Purchase request → approval → RFQ → quote → supplier selection → purchase order
→ receipt is implemented with state checks. Approval is separated from creation;
self-approval restrictions exist on controlled approval paths. Partial
deliveries, rejected quantities, closure and receipt lines are modelled.
Commitments are reported separately from expenses. No double-counting of a PO
as spend was found.

Residual: not every procurement action has a bespoke Angular screen; some are
available through the workspace/API only. This is a usability gap, not a
financial correctness defect.

### 3.4 Inventory and warehousing

Stock receipts, transfers, issues, returns, adjustments, damage, counts and
reservations are separate documents with movement rows and valuation layers.
Database checks prevent negative remaining quantities. Valuation is blocked
when no policy exists. Warehouse and storage-location scope is modelled.

Residual: there is no dedicated UI for every document type; API coverage exceeds
screen coverage. Procurement/inventory read authorization remains policy-open.

### 3.5 Accounting

The double-entry engine posts balanced journals only, enforces periods and
immutability after posting, supports reversal, opening balances and posting
rules. Financial statements and trial balance derive from posted lines, not
invoice totals. Posting rules/account mappings require approval; no mappings are
supplied.

Live database reality: 0 accounts and 0 posted journals. Statements therefore
show zero with warnings. This is correct fail-safe behaviour, not a calculation
bug.

### 3.6 Invoicing and accounts payable

Supplier/customer invoices, credit/debit notes, payments, allocations and NRS
submission records exist. Invoice creation/update is atomic. A rollback test
proves a failed write leaves no partial header/lines. PDF generation and exports
are present. Payment allocation, duplicate approval and state transitions are
tested.

Residual: no live invoice issuance or NRS submission is authorised.

### 3.7 Banking

Bank accounts, statements, imported lines, matching and reconciliation approval
exist. Manual matching and reconciliation rules are tested. Bank execution is
not implemented/enabled, by design.

### 3.8 Projects, services and leasing

Project budgets, costs, commitments, milestones and profitability views exist;
costs require approval. Service contracts, work orders, checklists, HSE records
and completion/acceptance flows exist. Equipment, rates, reservations,
agreements, dispatch/return, inspections and maintenance exist. Revenue
recognition and lease accounting are deliberately excluded.

Residual: dedicated screens do not cover every workflow; some operations remain
API/workspace only.

### 3.9 Reporting

Eleven tabs and 15 report names derive from source modules. Formal statements
use posted journals. Warnings identify missing mappings, mixed currencies and
incomplete cash-flow classification. CSV injection is neutralised and PDF
truncation is disclosed. Exports are audited.

### 3.10 Deployment and operations

See `phase-11-production-readiness-report.md`. Docker, nginx, backup and restore
assets exist. Monitoring, off-host encrypted backups, worker topology and load
testing are missing.

## 4. Database and data-integrity findings

- Migration drift: none (`No changes detected`).
- 63 migrations are applied in development.
- No negative stock layers.
- No unbalanced posted journals (there are no posted journals in live data).
- Check constraints exist for non-negative stock and balanced journal lines.
- Unique constraints cover journal/account/period keys, document lines and
  stock count items.
- Cascades are limited to child lines owned by a transaction header; master and
  historical references use PROTECT.
- No orphan/duplicate repair was required; no destructive operation was run.
- Live data has 4 supplier invoices, 3 customer invoices and no accounting
  configuration.

## 5. Frontend findings

- The SPA builds cleanly (307.61 kB initial raw, 82.77 kB estimated transfer).
- Lazy loading separates reports, workspace, administration, dashboard and
  login chunks.
- Reporting has loading, empty, error and permission-hidden states.
- The workspace uses a generic record form/table and server pagination; it is
  not a bespoke screen per document type.
- No broken navigation or console errors were observed in the reporting browser
  run. Earlier phases recorded portal browser reviews.
- Not performed: a fresh click-through of every module in this audit. That
  remains a UAT activity; it is not claimed as complete.

## 6. Defects found in this audit

| ID | Severity | Finding | State |
| --- | --- | --- | --- |
| D-AUD-01 | Critical | Any authenticated user could create/update suppliers, customers, catalogue, warehouses, departments and cost centres | Fixed; regression test added |
| D-AUD-02 | High | Any authenticated user could read accounting records, trial balance, financial statements and general ledger | Fixed; regression test added |
| D-AUD-03 | High | No staged performance/concurrency/failure test evidence | Open; Phase 11 blocker |
| D-AUD-04 | High | No monitoring/alerting or off-host encrypted backup | Open; operational blocker |
| SEC-04 | High | Inventory/procurement read policy unresolved | Open; requires management decision |
| D-AUD-05 | Medium | No background worker/task queue; all work synchronous | Open design decision |
| D-AUD-06 | Medium | Some backend workflows lack dedicated Angular screens | Open usability gap |
| D-AUD-07 | Medium | OpenAPI schema omits/flags many plain `APIView` endpoints (165 warnings) | Open documentation gap |
| D-AUD-08 | Low | Phase 3–6 reports still say permissions/screens do not exist although later phases added them | Documentation drift |
| D-AUD-09 | Low | Reporting for very large exports is synchronous and display truncates at 250 rows with notice | Accepted limitation |

## 7. Verification executed

| Check | Result |
| --- | --- |
| Backend suite | 295 passed |
| Frontend suite | 50 passed |
| Frontend production build | Passed |
| Frontend lint | Passed |
| Backend Ruff | Passed |
| Migration drift | No changes detected |
| Python dependency check | No broken requirements |
| npm production audit (high) | 0 vulnerabilities |
| Production `check --deploy` with required env | Exit 0; 165 OpenAPI warnings plus one warning caused by the deliberately weak throwaway check key |
| Secret scan | No real credentials; only synthetic test passwords |
| Restore rehearsal | PASS with 1 journal / 2 lines / ₦125.50 / 101 documents |

## 8. Technical conclusion

The core architecture and financial controls are credible and the two
authorization defects that could have allowed ordinary employees to alter master
data or read the ledger were corrected and regression-tested. The remaining
blockers are operational and policy-driven rather than evidence of a broken
application.

**Technical readiness: B — suitable for controlled staging/UAT, not production
approval.**
