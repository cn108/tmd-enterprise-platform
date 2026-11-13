# System architecture (implemented)

## 1. Shape

TMD is a modular monolith:

- Angular 22 single-page application.
- Django 5 / Django REST Framework API under `/api/v1`.
- PostgreSQL as the transactional source of truth.
- Redis reserved for cache/background work; no production worker topology is deployed yet.
- Private media storage served only through authenticated API downloads.
- nginx terminates TLS and serves the compiled Angular bundle.

The frontend never calculates a financial total for a formal report. It renders server-calculated rows so a stale browser cannot disagree with the ledger.

## 2. Backend modules

| App | Responsibility |
| --- | --- |
| `identity` | Users, sign-in/out, TOTP MFA, recovery codes, password change/reset, roles, access review, session timeout |
| `core` | Health, audit events, policy decisions, approvals, numbering, governance API |
| `organisation` | Departments, cost centres, destinations |
| `parties` | Suppliers, customers, contacts, addresses, tax registrations, bank accounts, bank-change requests, compliance documents |
| `catalogue` | Products/services, categories, units, manufacturers, prices, batches, serials, certificates |
| `warehousing` | Warehouses and storage locations |
| `projects` | Projects, locations, contracts, revisions, budgets, milestones, direct costs, costing |
| `procurement` | Requests, RFQs, quotations, selection, purchase orders, schedules, goods receipts |
| `inventory` | Stock movements, layers, valuation, transfers, issues, returns, adjustments, damage, counts, reservations, reorder levels |
| `accounting` | Chart of accounts, role mappings, fiscal years, periods, journals, posting rules, opening balances, financial statements |
| `invoicing` | Supplier/customer invoices, notes, matching, duplicate checks, payments, allocations, settings, NRS boundary |
| `banking` | Company bank accounts, statements, lines, matching, reconciliations, transfers, cash vouchers, petty cash |
| `services` | Work orders, assignments, progress, reports, checklists, service contracts |
| `leasing` | Equipment, rates, reservations, agreements, movements, inspections, maintenance |
| `reporting` | Read-only financial and operational reports, CSV/PDF export, export audit |
| `documents` | Private document metadata, links, authenticated download |

Apps communicate through model relationships and service functions. There is no separate event bus or microservice split.

## 3. Key flows

### Procurement to inventory

`PurchaseRequest → approval → RFQ/quotes → PurchaseOrder → DeliverySchedule → GoodsReceipt → StockMovement`

The stock movement ledger, not the purchase order, drives inventory balances. Receipts may create a financial event for later posting.

### Invoice to ledger

`SupplierInvoice draft → duplicate/match checks → approval → posting rule → JournalEntry → approval → posting`

A posted journal is immutable. A business event must not create a duplicate journal; invoice and payment paths use transactional services and idempotency where implemented.

### Bank reconciliation

`Statement import → lines → match to BankTransaction → exception/exclusion → Reconciliation → independent approval`

### Project cost

Approved supplier invoices, project stock issues and approved direct costs contribute actual cost. Open purchase orders are commitments, not actual cost. Estimated margin is not recognised revenue.

## 4. Data integrity

- Money uses `Decimal`, quantised to two places at boundaries.
- Journal lines enforce debit/credit balance and posted-journal immutability.
- Transactional services use `transaction.atomic` and row locks for state changes.
- Master data is deactivated, not deleted; transaction deletes return 409.
- Foreign keys use `PROTECT` for business history.
- Migrations are committed and checked with `makemigrations --check`.
- Audit events record actor, action, entity, before/after where appropriate and request metadata.

## 5. Security architecture

- Session authentication with CSRF for mutations; no token in browser storage.
- Fail-closed default permission: authenticated only.
- Model/action permissions and approval checks in services; hiding a button is not a control.
- Login lockout, password validators, absolute and inactivity session timeouts.
- TOTP MFA with encrypted device secrets, one-time login challenges and recovery codes; production enforcement is on by default.
- Configurable per-user, anonymous, login and MFA throttles alongside Axes lockout.
- Private uploads, extension and size validation, checksums and audited downloads.
- Production HTTPS, HSTS, secure cookies, CSRF trusted origins, CSP and security headers.
- Secrets from environment/secret store; production settings refuse missing secrets.

## 6. Deployment architecture

Docker Compose with private PostgreSQL/Redis, Gunicorn backend, nginx TLS frontend. Only 80/443 are published. Backups dump PostgreSQL and media to a protected directory; restores are tested in an isolated database.

## 7. Known architectural constraints

- No production monitoring/alerting integration.
- No executed background worker topology; long PDF/report work is synchronous.
- No NRS network adapter.
- No foreign-currency conversion or revaluation.
- Document-level access control is authenticated-user based; entity-level sharing policy is not final.
- Reporting queries are read-only but large date ranges can be slow; CSV export is the full-data path.
- The generic Angular workspace is configuration-driven; some specialised workflows are exposed through actions and related tabs rather than dedicated pages.

## 8. Scaling position

The monolith is appropriate for TMD's current size. Add indexes and pagination before splitting services. If reporting load grows, introduce read replicas or scheduled snapshots rather than weakening transactional consistency.
