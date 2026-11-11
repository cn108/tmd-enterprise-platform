# Business Requirements Document (BRD)

**Project:** TMD Enterprise System
**Business:** Tico McDon Limited (TMD), Nigeria
**Currency:** NGN (initial operating and reporting currency)
**Version:** 0.1 — draft for management review, 11 November 2026
**Status:** Not approved. Items marked UNRESOLVED require a named owner's decision.

---

## 1. Business context

TMD delivers engineering, procurement, project management, equipment leasing, maintenance, HSE, construction and related services. Work is organised around **projects**, and each project carries a contract value, a budget and a cost structure. Materials are purchased either for a specific project (delivered to site) or into a TMD warehouse and later issued to a project or customer order.

Today those activities are assumed to be captured across documents, spreadsheets and manual records (ASSUMPTION — to be verified in the Phase 0 interviews; see Q-01 in `11-questions.md`). The consequence of a manual, disaggregated process is the absence of a single answer to: *what did this project actually cost, what is committed on it, what stock exists, what do we owe, and what is owed to us?*

## 2. Business objectives

| ID | Objective | Measure of success (proposed) |
| --- | --- | --- |
| BO-01 | One source of truth for commercial operations | A project's cost, commitments and margin can be traced from contract to cash in one system without re-keying |
| BO-02 | Control purchasing | Every purchase is traceable to an approved request, an approved PO and a receipt or service confirmation |
| BO-03 | Control stock | On-hand quantities are always derived from posted movements; physical count variances are explained and approved |
| BO-04 | Correct, auditable accounting | Every posted balance traces to an approved source transaction and supporting document; all journals balance |
| BO-05 | Protect cash | No duplicate invoices are accepted; no duplicate payment can be executed; allocations are explicit |
| BO-06 | Enforce authority | Approvals happen at the correct level, by the correct person, recorded with timestamp and reason |
| BO-07 | Know project profitability | Budget vs committed vs actual vs invoiced, per project and cost code, updated as events occur |
| BO-08 | Be audit- and inspection-ready | Any transaction can be reconstructed with its actor, evidence and history |
| BO-09 | Tax and regulatory compliance | Invoices are issued with the correct fields and submitted through approved channels (scope confirmed by tax adviser) |

Success measures require baseline figures from management; the numbers above are **PROPOSED** and will be re-stated after discovery interviews.

## 3. Scope

### 3.1 In scope (confirmed by the brief)

- Internal employee users only. No supplier or customer self-service portal in the first release.
- Purchase requests, quotations and comparison, purchase orders, delivery/GRN, supplier invoices, three-way match, supplier payments and allocations.
- Direct-to-project purchasing and warehouse purchasing with stock issue to projects/customers.
- Customer contracts and projects, budgets and budget revisions, milestones, customer invoices, credit notes, receipts, allocations, ageing.
- Warehouses, storage locations, receipts, reservations, issues, transfers, returns, counts, adjustments.
- Services, labour, logistics, subcontractors and equipment leasing as non-inventory deliverables.
- Accounts payable, accounts receivable, general ledger, periods, reversals, trial balance, income statement and balance sheet.
- Bank and cash accounts, statement import and reconciliation.
- Tax codes and a fiscalisation/NRS submission adapter (integration status unresolved).
- Document management with private storage, permissions and retention rules.
- Reporting: financial, operational, project performance, exception queues.
- Audit trail across all sensitive actions.

### 3.2 Explicitly out of scope for release 1 (unless separately approved)

- Supplier and customer portals, marketplace features, public price lists.
- Mobile applications (responsive web is assumed sufficient; to be confirmed — Q-38).
- Payroll, HR leave management, full fixed-asset depreciation (equipment leasing asset records are in scope; depreciation policy is not configured until approved).
- Manufacturing/BOM, MRP scheduling, barcode/RFID hardware integration.
- Online banking credential storage or any automated bank payment initiation.
- Multi-entity consolidation (single legal entity assumed — Q-04).

### 3.3 Deferred, configurable

- Foreign-currency transactions (model supports currency fields; enabling requires an exchange-rate policy).
- Batch/lot, serial and expiry tracking (schema supports it; per-category requirement unresolved — Q-17).
- Multi-warehouse transfers in transit (in scope for modelling; operational validity to confirm).

## 4. Organisational context (to be confirmed)

| Item | Status |
| --- | --- |
| Legal entities | Single entity **ASSUMED** (Q-04) |
| Offices, warehouses, project sites | **UNRESOLVED** (Q-05, Q-06) |
| Departments | **UNRESOLVED** — likely candidates to verify: Management, Procurement, Projects/Engineering, Warehouse/Stores, Finance/Accounts, HSE, Operations, Equipment/Leasing, IT |
| Approval authorities | **UNRESOLVED** (Q-09, Q-10) |
| Staff numbers and concurrent users | **UNRESOLVED** (Q-37) |

No org chart is fabricated here. Section 4 of `11-questions.md` collects exactly this.

## 5. Business workflows (business-level summary)

Detailed steps, decision points and exception paths are in `04-workflows.md`.

1. **Direct-to-project purchase:** request → budget/authority check → approval → RFQ and quotes → supplier selection → PO approval and issue → delivery to site with acceptance → supplier invoice → three-way match → invoice approval → AP posting → payment approval → payment → allocation → reconciliation → project cost reporting.
2. **Warehouse purchase:** request (replenishment or forecast) → approval → RFQ → PO → goods to warehouse with GRN → accepted stock posted → invoice match against PO + accepted GRN → AP posting → reservation → issue/dispatch to project or customer → cost recognised once, at issue.
3. **Service and leasing delivery:** request or work order → service scope/milestones → supplier selection → PO → service confirmation (no stock quantity) → invoice match against PO + acceptance → AP posting → cost to project; equipment availability, dispatch, return and inspection recorded on the asset record.
4. **Order-to-cash:** customer enquiry/contract → project or sales order → scope and pricing approval → milestones/delivery → customer acceptance → invoice draft → tax/commercial validation → invoice approval → AR posting → delivery → receipt capture → allocation → reconciliation → ageing and statements.
5. **Stock control:** receipt → quality/condition check → accepted stock → put-away → reservation → pick/issue → dispatch with proof of delivery → returns, transfers, counts and approved adjustments.
6. **Cash control:** receipts and payments → allocations to invoices or advances → statement import → matching → investigation of unmatched items → reconciliation approval → period close.

## 6. Business rules (see SRS for testable statements)

| ID | Rule | Source |
| --- | --- | --- |
| BR-01 | Every material operation has an accountable user, timestamp, status and history | Guide §1 |
| BR-02 | Posted financial transactions are never edited or deleted; corrections use reversal, credit/debit note or approved adjustment | Guide §1, §6 |
| BR-03 | Inventory changes are represented only by posted stock movements; no direct balance overwrite | Guide §1 |
| BR-04 | All journals balance; money uses fixed-precision decimals, never binary floating point | Guide §1, §6 |
| BR-05 | Permissions are enforced by the backend, not by hidden UI | Guide §1, §8 |
| BR-06 | Received quantity may not exceed ordered quantity without a documented tolerance/exception approval | Guide §2 |
| BR-07 | Ordered, received, accepted, rejected, invoiced and paid quantities/amounts are always distinct | Guide §2 |
| BR-08 | A warehouse purchase is charged to cost exactly once — at issue, not also at invoice posting | Guide §6 |
| BR-09 | A PO commitment is not an actual expense | Guide §6 |
| BR-10 | Unallocated advances and deposits are held separately from invoice settlement | Guide §3 |
| BR-11 | Duplicate supplier invoices are detected on number + supplier (+ optional exceptions) | Guide §5 |
| BR-12 | Duplicate payment execution is prevented by idempotency keys and unique payment references | Guide §3 |
| BR-13 | A transfer in transit is not available stock at either location | Guide §3 |
| BR-14 | Every exception has an owner and a required action | Guide §3 |
| BR-15 | Lifecycle transitions are validated server-side; illegal transitions rejected | Guide §5 |
| BR-16 | Master records referenced historically are deactivated, never deleted | Guide §5 |
| BR-17 | No financial, tax or approval rule is invented by the system; unresolved items stay disabled | Guide §1, §6 |

## 7. Stakeholders

| Group | Interest | Phase 0 participation needed |
| --- | --- | --- |
| Management / MD | Control, profitability visibility, authority enforcement | Approve scope, roles, limits, gate |
| Accountant / finance lead | Correct postings, period control, reports, tax | Approve CoA, policies, posting matrix, numbering |
| Tax adviser / consultant | NRS e-invoicing, VAT/WHT treatment, retention | Confirm scope and integration status |
| Procurement | Requests, RFQs, comparison, PO issue, supplier performance | Walkthrough of route 1 and 2 |
| Project managers | Budgets, commitments, cost codes, milestone billing | Confirm project/cost-code model |
| Warehouse / storekeepers | GRN, put-away, reservations, issues, counts | Confirm stock processes and traceability needs |
| Operations / equipment leasing | Work orders, asset availability, rental periods | Confirm service and leasing model |
| HSE / compliance | Certificates, compliance documents | Confirm document and expiry needs |
| IT / support owner | Hosting, backup, access | Confirm infrastructure constraints |
| External auditor (later) | Traceability, immutability, evidence | Not required at Phase 0 |

## 8. Constraints and dependencies

- No internet-independent operation requirement is known yet; site connectivity is UNRESOLVED (Q-39).
- All regulatory configuration must be sourced from current official documentation and approved by TMD's advisers (Guide Appendix B). No rates or thresholds are embedded in code.
- Data migration depends on the quality of existing registers, which are unknown (Q-30 to Q-32).
- Timeline and budget: **UNRESOLVED** — management has not stated a target date; the brief warns that financial correctness must never be waived to meet a date.

## 9. Assumptions register (summary)

| ID | Assumption | Impact if wrong |
| --- | --- | --- |
| A-01 | Single legal entity | Multi-entity consolidation needed: schema and reporting change in Phase 3 |
| A-02 | Internal users only, browser-based, desktop-first | Portal or mobile requirement changes Phase 8+ |
| A-03 | One warehouse at launch, possibly more later | Warehouse model already supports many; minimal impact |
| A-04 | Stock items are largely consumables/materials without serialisation | Enabling serial/batch per category needed; schema supports it |
| A-05 | Invoice approval is maker-checker, not single-person | Approval matrix change only (configuration) |
| A-06 | NGN only at launch | FX policy and rate master required before enabling |
| A-07 | Manual bank payment execution outside the system, with reference capture inside | Payment initiation is out of scope; no change |
| A-08 | Projects are billed by milestone and/or on completion | Revenue recognition timing needs accountant confirmation |

Assumptions are carried in `13-decision-register.md` with owners; each must become CONFIRMED or be replaced before the phase that depends on it.

## 10. Approval

This BRD requires sign-off from Management (scope, objectives, authority) and the Accountant (financial scope). Until signed, requirements in `03-srs.md` remain draft and no posting logic will be enabled.
