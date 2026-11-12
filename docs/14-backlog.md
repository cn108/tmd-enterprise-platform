# Phased Delivery Backlog

**Version:** 0.1 — 11 November 2026
**Guide references:** §9 (development phases), §14 (working rules), §16 (release checklist)
**Note:** Sizes are relative (S/M/L/XL) and deliberately exclude calendar estimates until D-01 and D-10 are decided. No phase closes while its exit gate is unmet.

---

## Phase 0 — Discovery and current-state mapping (complete)

**Produced:** this pack. **Exit gate:** management review and approval of D-01. **Size:** S (done).

## Phase 1 — Engineering foundations and standards

**Requirements:** NFR-01…NFR-12 (foundations), guide §9 Phase 1
**Scope:** Git repository with branching rules, PR template and code owners; Django project + Angular workspace; PostgreSQL and Redis via Docker Compose; settings split (base/dev/staging/prod); `.gitignore` and secret handling; linting, formatting, type checks; test framework; CI pipeline (lint, type, tests, secret scan, migration check); health endpoints; structured logging with request IDs; OpenAPI schema generation; developer onboarding notes.
**Deliverables:** runnable skeleton, green CI, documented local setup, no secrets committed.
**Exit gate:** a clean checkout builds and tests from documentation alone; CI green; secret scan clean; work rule 9 report filed.
**Size:** M. **Blocked by:** D-01 (and D-09/D-10 for stack/hosting finality).

## Phase 2 — Identity, roles, permissions, audit

**Requirements:** ADM-01…ADM-11, S-01…S-11, AUD-01, AUD-02, NFR-05
**Scope:** user lifecycle, authentication, password reset, lockout, session controls; roles/permissions/departments; approval policy data model + maker-checker + delegation; append-only audit service; permission matrix test suite; negative tests (unauthorised access, cross-department, disabled account, privilege escalation, self-approval).
**Exit gate:** every sensitive endpoint covered by permission tests; segregation-of-duties rules proven impossible to bypass by API; audit events written for all sensitive actions.
**Design:** [`16-phase2-access-control-design.md`](16-phase2-access-control-design.md) — schema, enforcement layers, approval algorithm, audit integrity, API surface and the matrix test plan.
**Size:** L. **Blocked by:** D-03, D-04, D-17, D-18.
**Status (12 November 2026, session 3):** the **nine provisional roles** are applied as Django groups with explicit permission bundles, and the ₦5,000,000 approval bands are active for purchase orders and budgets. Users can be assigned roles; `/auth/me/` returns real roles and effective permissions. The audit trail is now hash-chained and append-only at the database; role and user changes are audited. No user has been assigned a role and the nine-role reduction (HSE folded into Operations / HSE; Requester not a separate role) still needs confirmation. Delegation and escalation remain outstanding. See [`reports/configuration-report-2026-11-12.md`](reports/configuration-report-2026-11-12.md).

## Phase 3 — Master data

**Requirements:** MAS-01…MAS-08, PRJ-01…PRJ-05, DOC-01…DOC-02
**Scope:** customers, suppliers (with restricted bank details and compliance documents), contacts, addresses, tax registrations; products/services catalogue with price history; units of measure; warehouses and locations; projects, contracts, contract revisions, budgets and budget lines, cost centres, milestones, project locations; document categories, private upload/download, versioning metadata; validation, duplicate checks, deactivation, import templates.
**Exit gate:** authorised users maintain all master data with history and valid references; referenced records cannot be deleted; document access restricted and logged.
**Size:** L. **Blocked by:** D-02, cost-code structure (Q-14b).
**Status (11 November 2026, session 2):** master-data APIs and portal screens now cover suppliers, customers, supplier categories, contacts, addresses, tax registrations, masked bank accounts and two-person bank account changes, compliance documents, catalogue items, product categories, units of measure, manufacturers, item prices, specifications, batches, serial numbers, certificates, warehouses, storage locations, destinations, departments, cost centres, projects, project locations, customer contracts and revisions, project budgets with lines and separate approval, milestones, document categories and private documents with authenticated upload/download. Referenced records are deactivated, never deleted. Outstanding: append-only audit history (W7), approved retention rules (Q-28), and the role matrix that decides who may change restricted records. Report: [`reports/phase-3-master-data-report.md`](reports/phase-3-master-data-report.md).

## Phase 4 — Procurement and fulfilment

**Requirements:** PRC-01…PRC-13 (plus the receipt side of INV-01), BR-06, BR-07
**Scope:** purchase requests with budget references and destination; approval workflow; RFQ/quotations/comparison/recommendation; PO generation, revision, approval, issue, cancellation; delivery schedules; site acceptance and warehouse GRN with accepted/rejected quantities; partial deliveries, shortages, substitutions, damage, backorders, supplier returns; three-way match producing exceptions.
**Exit gate:** full lifecycle tested for direct purchase, warehouse replenishment and split/partial delivery; over-receipt blocked without approved tolerance; rejected quantities never increase available stock.
**Size:** XL. **Blocked by:** D-04, D-14, D-15, Q-15…Q-20b.
**Status (12 November 2026, session 3):** the lifecycle is interactive end to end — purchase requests, RFQs and invitations, quotations, supplier selection, purchase orders, draft amendments, delivery schedules and receiving. The **provisional ₦5,000,000 band** requires one independent approval below the threshold and two at or above it; the creator/requester cannot approve and the same person cannot decide twice. Over-receipt is refused because no tolerance is approved; accepted warehouse receipts post stock. Outstanding: confirmed approval policy, supplier invoice/payment bands (Phase 7), three-way match and supplier returns. Report: [`reports/phase-4-procurement-report.md`](reports/phase-4-procurement-report.md).

## Phase 5 — Inventory and stock ledger

**Requirements:** INV-01…INV-10, BR-03, BR-08, BR-13
**Scope:** immutable stock movements (receipt, put-away, transfer, reservation, issue, return, adjustment, count); on-hand/available/reserved/in-transit/damaged/quarantined views; batch/serial/expiry fields where enabled; valuation per approved method; stocktake workflow with variance approval; reorder levels; project issue with cost-code capture; reconciliation of balances to movements.
**Exit gate:** concurrent issues cannot oversell; balances equal movement sums at every location; valuation report reconciles; full movement history traceable.
**Size:** XL. **Blocked by:** D-06, Q-18, Q-19.
**Status (12 November 2026, session 3):** the ledger is fully interactive — receipts, transfers, reservations, project issues, returns, adjustments, damages, counts, reorder levels, balances and valuation. The provisional policy uses **weighted average for ordinary stock and specific identification for batch- or serial-tracked items**, locked after the first movement. E-04 and E-16 events are queued for accounting; transfers and reservations do not create a consumption event. Outstanding: Finance Controller review, damaged/quarantine/in-transit buckets (Q-19), supplier returns and enabling automatic postings. Report: [`reports/phase-5-inventory-report.md`](reports/phase-5-inventory-report.md).

## Phase 6 — General ledger and posting engine

**Requirements:** GL-01…GL-11, C-01…C-10
**Scope:** approved chart of accounts; periods and period controls; journal/journal lines with balance constraints; central posting service with rule-driven mappings, idempotency and atomicity; reversal and correction; trial balance, GL detail, income statement, balance sheet from approved mappings; opening balance import.
**Exit gate:** automated tests prove every posting balances, duplicates are blocked, posted journals are immutable, reversals traceable, locked periods enforced, subledgers reconcile to control accounts.
**Size:** XL. **Blocked by:** D-05 (hard blocker), D-19…D-23, D-26.
**Status (12 November 2026, session 3):** the engine and screens are delivered — chart with separate approval, fiscal years, monthly periods and controlled closure/reopen, journals with submit/approve/post/reverse, opening balances, role-based posting rules, retained earnings, trial balance, general ledger, income statement and balance sheet. The chart structure is **19 configurable account roles** with effective-dated approved mappings; **no account is seeded**, so no mapping or role-based rule can yet be approved. The five events are implemented through an outbox and controlled documents; automatic posting is double-gated by approved mappings and a recorded Finance Controller review. A PostgreSQL trigger makes posted journals immutable. Outstanding: the actual chart and mappings, opening balances, posting review, multi-currency and idempotency. Report: [`reports/phase-6-accounting-report.md`](reports/phase-6-accounting-report.md).

## Phase 7 — Accounts payable and invoice issuance

**Status (12 November 2026, session 3):** **Stage 7A implemented** — supplier invoice capture, duplicate detection, PO/receipt matching, configurable VAT/WHT calculation, independent approvals, credit/debit notes, PDF test previews, supplier payment recording and allocation, idempotency, NRS adapter state and the unassigned Finance Controller role. The Angular invoicing module exposes all of it. **Stage 7B is not authorised**: production issuance and ledger posting remain disabled. Completion report: [`reports/phase-7a-completion-report.md`](reports/phase-7a-completion-report.md); activation blockers: [`reports/phase-7b-activation-blockers.md`](reports/phase-7b-activation-blockers.md).

**Requirements:** AP-01…AP-12, TAX-01…TAX-05, DOC-03
**Scope:** supplier invoice capture with duplicate detection; match status; approval and atomic posting; credit/debit notes; PDF layouts with confirmed company/legal details; customer invoice issuance (shared document engine where practical); tax codes as configuration; fiscal adapter skeleton behind a flag.
**Exit gate:** partial and split payments reconcile to invoice balances; duplicates blocked; tax codes drive document amounts; adapter off leaves core working.
**Size:** L. **Blocked by:** D-07, D-08, D-19, D-21, D-23.

## Phase 8 — Accounts receivable, receipts and payments

**Requirements:** AR-01…AR-08, AP-07…AP-11 (payment execution side), BR-10, BR-12
**Scope:** customer invoices from milestones/completion with approval and posting; credit notes; receipts; allocations (one-to-many, partial, advances); supplier payments with approval, idempotent execution, allocation, advances, reversals, bounces, fees; statements and ageing; credit-hold rules if approved.
**Exit gate:** allocation arithmetic proven under partial/over/under cases; idempotent execution demonstrated; AP/AR control accounts reconcile; statements match.
**Size:** XL. **Blocked by:** D-25, Q-33, D-19.

## Phase 9 — Banking and reconciliation

**Requirements:** BNK-01…BNK-06
**Scope:** bank/cash accounts; validated statement import with rejected-row reporting; matching to receipts, payments, transfers, fees; unmatched queue with investigation; reconciliation review/approval; period-close report.
**Exit gate:** every statement line is reconciled, explained or visibly unresolved; no forced balancing; approval blocked with unexplained lines.
**Size:** M/L. **Blocked by:** D-10 (statement formats), Q-33b.

## Phase 10 — Project cost, services and equipment

**Requirements:** PCS-01…PCS-04, SVC-01…SVC-02, AST-01…AST-03
**Scope:** project cost ledger views (budget/committed/received-not-invoiced/actual/reserved/issued); budget revisions and change control; work orders, checklists, service reports, client acceptance; equipment register with rentals, dispatch/return, inspection, maintenance and utilisation.
**Exit gate:** project cost figures trace to source documents and reconcile; commitments never mixed with actuals; rental overlaps prevented; service lines create no stock quantities.
**Size:** L. **Blocked by:** D-24, Q-27, Q-27b.

## Phase 11 — Reporting, dashboards, exports

**Requirements:** REP-01…REP-06
**Scope:** approved financial reports; operational KPIs with drill-through; AP/AR ageing; exception queues with owners and required actions; permissioned exports (XLSX/PDF) with audit; dashboard landing per role.
**Exit gate:** every report reconciles to journals or source documents; exports respect permissions; export actions audited.
**Size:** M/L. **Blocked by:** D-26.

## Phase 12 — Operational readiness

**Requirements:** NFR-06…NFR-08, S-12…S-15, guide §12, §16
**Scope:** monitoring and alerting; automated encrypted backups with restore tests; environment separation verified; runbooks (deploy, rollback, restore, incident, failed job retry); access review process; dependency patching process; security review and remediation; performance test evidence.
**Exit gate:** restore test passed with evidence; RPO/RTO agreed; security findings resolved or formally accepted; runbooks tested by someone other than the author.
**Size:** M. **Blocked by:** D-10, D-12, Q-35 (RPO/RTO — must not be invented).

## Phase 13 — Data migration and go-live

**Requirements:** all of `15-migration-and-golive.md`
**Scope:** source inventory; cleaning; opening balances; open document schedules; staging loads with rejected-row reporting; reconciliations; parallel run; sign-offs; training; cutover; first period close under supervision.
**Exit gate:** Guide §16 checklist fully satisfied with written sign-offs; management authorises go-live.
**Size:** XL. **Blocked by:** D-11, Q-30, Q-32.

---

## Requirement coverage summary

| Phase | Requirement groups |
| --- | --- |
| 1 | NFR foundations |
| 2 | ADM, AUD, permission NFRs |
| 3 | MAS, PRJ, DOC |
| 4 | PRC |
| 5 | INV |
| 6 | GL |
| 7 | AP, TAX, DOC-03 |
| 8 | AR, payments |
| 9 | BNK |
| 10 | PCS, SVC, AST |
| 11 | REP |
| 12 | NFR ops, security |
| 13 | migration, acceptance |

Every requirement in `03-srs.md` appears in exactly one primary phase above (plus extensions), so nothing silently drops out of the plan.

## Delivery rules carried into every phase

1. State objective, requirements, proposed files and test plan before coding (work rule 3).
2. Write tests with each business rule, not at the end.
3. Small, reviewable changes; explain every migration.
4. No invented financial policy; unresolved items stay disabled.
5. Phase report in the format of `templates/phase-completion-report.md`.
6. Do not declare production-ready without the specified acceptance evidence and management approval.
