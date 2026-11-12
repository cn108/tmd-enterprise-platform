# TMD portal: delivery status, gaps and phase assessment

**Updated:** 12 November 2026 (session 4)
**Controlling documents:** TMD Enterprise System Master Implementation Specification v2.0 and the TMD Backend and Interactive Frontend Development Standard.
**Scope:** Django/DRF/PostgreSQL backend and Angular employee portal verified against this workspace.

## Position

The functional scope of **Phases 3–6 and Stage 7A is now reachable from the portal**: master data and project records, the full procurement chain from request to goods receipt, the inventory movement set, accounting periods and journals, the accounting and valuation reports, and test-only invoice/payment workflows.

No module is yet **COMPLETE** under the specification's definition. Three things are still missing, and none is a screen:

1. **The role matrix is provisional.** Nine operational roles and permission bundles plus an unassigned Finance Controller are applied, but no named holders are recorded and the reduction from the earlier eleven-role draft needs written confirmation. Approval limits are applied as a ₦5,000,000 band.
2. **The accountant's chart and opening balances are outstanding.** No account, account-role mapping, opening balance or tax rate exists. The posting engine therefore refuses role-based postings, and automatic postings remain in an outbox.
3. **Production posting is not reviewed.** The provisional policy, approval bands, valuation rule and event mappings are configuration, not a Finance Controller's signed accounting policy. The audit trail and database immutability triggers are implemented, but not every sensitive action is yet covered.

Everything else in Phases 3–6 and Stage 7A that policy does not block has been implemented and tested. Stage 7B activation, live issuance and ledger posting remain blocked.

### What changed in this session

| Area | Delivered |
|---|---|
| Access administration | Django-group roles with explicit permission bundles; user administration with role assignment; `/auth/me/` now reports real roles and effective permissions; administration portal |
| Phase 3 relationships | Supplier categories, contacts, addresses, tax registrations, masked bank accounts, two-person bank changes, compliance documents, document categories, private document upload/download |
| Catalogue support | Product categories, units of measure, manufacturers, item prices, specifications, batches, serial numbers, certificates |
| Organisation and projects | Storage locations, departments, cost centres, destinations, project locations, contracts, contract revisions, **project budgets with lines and separate approval**, milestones |
| Phase 4 portal | RFQ creation/issue, invitations, quotations with lines, supplier selection, purchase-order creation (manual or from a selection), draft amendments with revision history, delivery schedules, goods-receipt entry |
| Phase 5 portal | Direct receipts, transfers (dispatch/receive/cancel), issues, returns, adjustments, damaged-stock write-offs, stock counts (create/post), reservations (create/release), reorder-level maintenance |
| Phase 6 portal | Fiscal years, accounting periods and closing, opening balances, posting-rule authoring and approval, trial balance, general ledger, income statement and balance sheet |
| Accounting integrity | PostgreSQL triggers make posted journals and their lines immutable to raw SQL as well as to the API |
| Stage 7A invoices | Supplier/customer invoices, matching, duplicate checks, VAT/WHT, notes, PDF test previews, payment recording/allocation, NRS adapter state and invoicing workspace |
| Reports | Dedicated report workspace for trial balance, GL detail, financial statements and inventory valuation |
| API usability | Read-only display labels on related records; request-line and order-line endpoints; party lookup; ISO pagination and search retained |
| Provisional policy | Nine roles; ₦5m approval bands; account-role mappings; monthly periods; weighted-average/specific-identification valuation; GRNI; E-02/E-04/E-16/E-21/E-22; tax and numbering configuration; hash-chained audit; stock-movement trigger; configuration report |

## Access-control model

A **role** is a Django group. An access administrator names it and selects its backend permission codes. A **user** is an identity account; assigning roles grants the union of their permissions. `GET /auth/me/` returns role names and effective permission codes.

The system applies **nine provisional roles** from the 12 November 2026 instruction: System Administrator, Management, Accountant, Finance Officer, Procurement Officer, Project Manager, Storekeeper, Operations / HSE and Auditor. No user is assigned to them. Management still needs to confirm the reduction from the earlier eleven-role draft (HSE folded into Operations / HSE; Requester is not a separate role).

The access administrator needs `auth.view_group` / `auth.add_group` / `auth.change_group` for roles and `identity.view_user` / `identity.add_user` / `identity.change_user` for accounts. A superuser can bootstrap the first administrator; after that the permissions can be delegated.

## Phase assessment

Statuses: NOT STARTED, IN PROGRESS, BLOCKED, PARTIAL, COMPLETE. COMPLETE requires backend, interactive frontend, integration, tests and documentation.

| Phase | Status | Evidence | Remaining gate |
|---|---|---|---|
| 0 — Audit and discovery | COMPLETE | This document and the live verification flow | — |
| 1 — Foundation and environments | PARTIAL | Settings split, PostgreSQL/Redis, health, OpenAPI, migrations, lint/test commands | CI and staging/production separation not re-verified |
| 2 — Identity, access, audit | PARTIAL | Session auth, lockout, password lifecycle; nine provisional roles, approval bands, user administration; hash-chained audit and database immutability | Confirmed role matrix and named holders; delegation; broader audit coverage |
| 3 — Master data and projects | PARTIAL | All relationship, catalogue, organisation, project and document screens; budgets, milestones, contracts; referenced records cannot be deleted | Audit history; approved retention rules; supplier bank permissions in the matrix |
| 4 — Procurement and fulfilment | PARTIAL | Request → RFQ → quotation → selection → order → schedule → GRN, all interactive; ₦5m single/dual approval band; draft amendments revised | Confirmed approval policy; three-way match (needs Phase 7); supplier returns |
| 5 — Inventory and stock ledger | PARTIAL | Receipts, transfers, issues, returns, adjustments, damages, counts, reservations, reorder levels; weighted average + specific identification; E-04/E-16 outbox | Finance Controller review; damaged/quarantine/in-transit buckets (Q-19); automatic posting enablement |
| 6 — General ledger and posting engine | PARTIAL/BLOCKED | Chart roles, monthly periods, journals, reversals, opening balances, posting rules, reports; DB-enforced immutability; role-based event rules | Approved chart/mappings and opening balances; posting review; multi-currency; confirmed period policy |
| 7 — AP / AR | PARTIAL (Stage 7A) | Supplier/customer invoices, duplicate detection, PO/receipt matching, VAT/WHT, approvals, notes, PDF test previews, payment recording/allocation, NRS adapter state; 15 invoicing tests | Stage 7B activation: D-07, D-08, D-19, D-21, D-23, chart/mappings, finance review |
| 8 — Payments and reconciliation | NOT STARTED | No endpoints | D-25, Q-33 |
| 9 — Services, equipment, leasing | NOT STARTED | Catalogue service kind only | D-24, Q-27 |
| 10 — Reporting | PARTIAL | Accounting and valuation reports in the portal; live dashboard queues | Saved report parameters, exports, role dashboards (D-26) |
| 11 — Integrations | NOT STARTED | — | NRS onboarding and adviser input |
| 12 — Migration, UAT, go-live | NOT STARTED | — | D-11, Q-30, Q-32 |
| 13 — Operations | NOT STARTED | — | RPO/RTO and support ownership |

## Module matrix

| Module | Backend | Frontend | Integration | Tests | Docs | Overall |
|---|---|---|---|---|---|---|
| Identity / Administration | Auth complete; nine operational roles plus unassigned Finance Controller, approval bands and user administration; hash-chained audit | Login, session, administration screen | Roles and effective permissions verified live; high-value dual approval tested | 224 backend tests, 39 UI tests | This document and configuration report | PARTIAL (matrix provisional, holders unnamed) |
| Master Data | Parties, relationships, catalogue, organisation, warehousing, documents | CRUD, relationships, documents, search/sort/pagination | Live role and budget flow; API tests | 224 backend tests, 39 UI tests | This document | PARTIAL |
| Projects / Contracts | Projects, contracts, revisions, budgets, milestones | All project-related records and budget approval | Budget create/approve verified live | Backend + UI tests | This document | PARTIAL |
| Procurement | Full request-to-GRN lifecycle | Requests, RFQs, quotes, selection, orders, schedules, receipts | Live approval/permission path; API suite | Backend + UI tests | Phase 4 report | PARTIAL |
| Inventory | Immutable ledger, all movement documents, valuation | Receipts, transfers, issues, returns, adjustments, damages, counts, reservations, reorder levels | API suite; valuation refusal verified live | Backend + UI tests | Phase 5 report | PARTIAL |
| Accounts Payable | Supplier invoices, matching, duplicate detection, approvals, notes | Supplier invoice and notes tabs with PDF previews | Test-only; posting disabled | 15 invoicing tests | Phase 7A report | PARTIAL (Stage 7A) |
| Accounts Receivable | Customer invoice drafts, approvals, notes | Customer invoice and notes tabs with PDF previews | Test-only; issuance disabled | Invoicing tests | Phase 7A report | PARTIAL (Stage 7A) |
| Payments / Receipts | Supplier payment recording, approval, allocation; no execution | Payments tab with allocation dialog | Idempotent recording only; no bank execution | Invoicing tests | Phase 7A report | PARTIAL (Stage 7A) |
| Accounting / GL | Engine, periods, rules, opening balances, reports, DB immutability | Accounts, journals, periods, opening balances, rules, reports | Posted-journal trigger and report calls verified | Backend + UI tests | Phase 6 report | PARTIAL (configuration/approval required) |
| Banking / Reconciliation | No endpoints | None | None | None | Backlog | NOT STARTED |
| Services / Work Orders | Catalogue service kind only | None | None | None | Backlog | NOT STARTED |
| Assets / Leasing | No endpoints | None | None | None | Backlog | NOT STARTED |
| Reporting / Dashboard | Report endpoints; dashboard queues | Report workspace, live queues | Reports return live data | Backend + dashboard tests | This document | PARTIAL |
| Documents / Audit / Notifications | Private upload/download; hash-chained append-only audit | Document upload/download; audit API | Download is authenticated; no public media route | API tests | This document | PARTIAL (coverage still expanding) |

## API surface added or extended

All routes are under `/api/v1/`.

| Endpoint | Purpose |
|---|---|
| `access/roles/`, `access/permissions/`, `access/users/` | Role authoring, permission catalogue, user/role administration |
| `parties/` | Read-only lookup for contacts, addresses and tax registrations |
| `purchase-request-lines/?request=`, `purchase-order-lines/?order=` | Quotation and delivery-schedule entry |
| `project-budgets/` (+ `approve`), `project-milestones/` | Project budgets and dates |
| `rfqs/?status=` | Issued-RFQ filtering used by quotation and selection forms |
| `purchase-orders/{id}/` PATCH | Draft amendment with revision increment |
| `documents/{id}/download/` | Authenticated private download |
| Existing list viewsets | Pagination, `search`, `ordering`; status filters on requests, orders, transfers and periods |
| `trial-balance/`, `general-ledger/`, `financial-statements/`, `inventory-valuation/` | Report workspace |

## Deliberate deviations

1. **One configuration-driven workspace rather than feature folders.** The specification forbids moving working code for cosmetic compliance. The configuration now covers a large surface; splitting is warranted only when a workflow outgrows declarative forms (the goods-receipt selector is the first candidate).
2. **Report endpoints paginate computed rows in Python.** Stock balances, reorder alerts and valuation derive from the ledger, so rows are sliced after computation while returning the full-set count and totals.
3. **Primary keys remain `BigAutoField`.** UUIDs remain a recorded risk before external integrations.
4. **No Celery/PDF/export work.** No module in Phases 3–6 requires a background job yet; report exports are Phase 10.
5. **No idempotency keys yet.** Posting is protected by state transitions and event references; payment execution will need explicit keys.
6. **The goods-receipt dialog lists all schedules and order lines.** The backend validates that they belong together. A schedule-scoped picker is a usability improvement, not a correctness gap.
7. **No multi-currency ledger or period reopening.** Both are outside the Phase 6 baseline and need accounting policy.

## Risk register

| Risk | Impact | Mitigation / next action |
|---|---|---|
| Role matrix unapproved (W4/D-03/D-04) | Approvals and postings remain unusable for ordinary users | Management signs the matrix; an administrator creates the roles; thresholds remain unimplemented until D-04 |
| No append-only audit trail (W7) | Sensitive changes lack a defensible history | Implement before production; current records carry creator/approver timestamps only |
| Chart/posting matrix unapproved (D-05/Q-22) | No production accounting | Only accountant-supplied configuration may be entered; posting refuses unapproved accounts/rules |
| Valuation unconfigured (D-06/Q-18) | Issues and valuation report refuse | Record an approved method; method is locked once movements exist |
| No damaged/quarantine/in-transit buckets (Q-19) | Stock location reporting is coarser than the specification's target | Add buckets when Q-19 defines them; do not guess |
| Three-way match absent | Invoice exceptions cannot be detected | Belongs with Phase 7 AP; needs D-07/D-08 |
| UUID preference not followed | External referencing is harder | Decide before invoice/payment integrations |
| No idempotency on posting | Retry could duplicate an event | Add idempotency records with payment work |
| CI/staging not re-verified | Release confidence gap | Verify workflows and environment separation |
| Portal not visually reviewed in a browser this session | Layout/accessibility regressions may be unseen | Human/browser review of the new Material screens |

## Verification evidence

```
frontend:  npm run build                      -> success
frontend:  npm run lint                       -> all files pass
frontend:  npm test -- --watch=false          -> 39 tests pass (7 files)
backend:   ruff check .                       -> all checks pass
backend:   python -m pytest                   -> 224 tests pass
```

Live HTTP flow against Django/PostgreSQL (temporary users and records, removed afterwards):

- superuser `/auth/me/` reports 367 effective permissions;
- role `QA Budget Approver` created with `projects.approve_projectbudget`;
- role assigned to a normal user; that user's `/auth/me/` reports the role and permission;
- budget created with two lines, total `1250.75`, version 1;
- the creator's approval attempt was refused `409` by the segregation-of-duties rule;
- an independent approver succeeded; `approved_by` recorded;
- `parties/`, `purchase-request-lines/` and `purchase-order-lines/` return `200`;
- trial balance returns `200` and `balanced: true` with no posted entries;
- inventory valuation returns `409` with the explicit "no method configured" message.

Posted-journal immutability is proven in the suite with raw ORM `UPDATE`/`DELETE` attempts against a posted journal and its lines.

**Limitation:** the new Material screens were compiled and unit-tested but not visually inspected in a browser this session.

## Session 4 report — 12 November 2026 (Stage 7A)

**What changed:** a new `invoicing` module and Angular invoicing workspace implement supplier invoice capture, duplicate detection, PO/receipt matching, configurable VAT/WHT, independent approvals, supplier/customer credit and debit notes, PDF test previews, supplier payment recording and allocation, idempotency and NRS adapter state. A Finance Controller permission bundle was created and left unassigned.

**Controls:** all Stage 7A documents are stamped test-only; PDFs carry a test banner; posting returns `409`; NRS is disabled; payment recording never executes a bank payment. Duplicate numbers are reserved after cancellation, allocations cannot exceed payment or invoice balances, and every lifecycle action writes an audit event.

**Tests:** 224 backend tests, 39 frontend tests; build and lint clean. `scripts/verify-phase7a-invoicing.mjs` also passed 31 live session/API/PDF checks, including independent approval, payment recording/allocation, activation and posting refusal. Invoicing tests cover the full Stage 7A lifecycle.

**Not done:** no live issuance, ledger posting, bank execution, NRS submission or customer receipts. These remain Stage 7B/Phase 8 work. Reports: [`reports/phase-7a-completion-report.md`](reports/phase-7a-completion-report.md) and [`reports/phase-7b-activation-blockers.md`](reports/phase-7b-activation-blockers.md).

## Session 3 report — 12 November 2026

**What changed:** the 12 November 2026 provisional accounting and governance decisions were applied as versioned configuration, not as signed historical books. The full report is [`reports/configuration-report-2026-11-12.md`](reports/configuration-report-2026-11-12.md).

**Backend:** nine role groups and permission bundles; ₦5,000,000 purchase-order and budget bands with independent approval records; account roles and effective-dated approved mappings; role-based posting-rule lines; monthly-period generation; weighted-average/specific-identification valuation; E-02/E-04/E-16/E-21/E-22 handling through an outbox and controlled documents; tax and numbering configuration; hash-chained audit; PostgreSQL triggers on audit events and stock movements; configuration-report API.

**Frontend:** approval counts and band displayed on requests, orders and budgets; first approval reports “recorded, another approver required” instead of claiming the document is approved.

**Migrations:** `core.0001–0003`, `accounting.0003–0004`, `inventory.0002–0003`.

**Tests:** 209 backend tests, 39 frontend tests, lint/build clean. New tests cover the nine-role seed, dual approval at ₦5m, creator exclusion, role-based posting, audit immutability, stock-movement immutability, sequential/year-reset numbering, tax-review segregation, monthly periods, the posting-review gate and the configuration report.

**Not done:** no account, account-role mapping, opening balance, tax rate, Tax ID or NRS credential exists; no user holds a role; no Finance Controller review is recorded. Invoice and payment modules are absent. Stock adjustments remain permission-gated rather than two-person approved. The nine-role reduction and threshold interpretation are assumptions.

## Session 2 report — 11 November 2026

**What changed and why:** completed the Phase 3–6 vertical surface that policy does not block, and made access administration real so approvals can be assigned once management signs the matrix.

**Backend:** access serializers/views/URLs; project budgets, budget lines and milestones; draft order amendment with revision; purchase-request draft editing; request/order line endpoints; party lookup; additive display labels; PostgreSQL posted-journal trigger; status filters.

**Frontend:** all master-data, procurement, inventory and accounting tabs; action dialogs with payloads; file upload/download; server-scoped option loading; report workspace; administration workspace; routes and navigation.

**Migrations:** `projects.0002`, `procurement.0002`, `accounting.0002` (trigger). No data was seeded.

**APIs changed:** new access, project-budget/milestone and line endpoints; `revision` on orders; role/permission output on `/auth/me/`; additive read-only labels; status filters. No existing field was removed.

**Unresolved decisions:** W4 matrix, D-04 thresholds, D-05/Q-22 chart and postings, D-06/Q-18 valuation, Q-19 buckets, W7 audit, UUID strategy, idempotency, multi-currency, period reopening.

**Known issues:** no permission data until roles are created; no audit timeline; no three-way match; goods-receipt picker is not order-scoped; no visual browser review.

**Module status:** Master Data PARTIAL; Projects PARTIAL; Procurement PARTIAL; Inventory PARTIAL; Accounting PARTIAL (production BLOCKED); Identity/Administration PARTIAL. No module is COMPLETE.

## Constraints retained

- No invented account code, tax rate, opening balance, historical balance or statutory filing; the supplied role and approval policies remain labelled provisional.
- Backend authorisation and validation remain authoritative; UI controls are affordances.
- Posted financial records are immutable at the API and in PostgreSQL.
- Master data is deactivated, never deleted; referenced records are protected.
