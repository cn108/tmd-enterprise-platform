# Software Requirements Specification (SRS)

**Version:** 0.1 — draft, 11 November 2026
**Companion documents:** `02-brd.md`, `04-workflows.md`, `06-data-model.md`, `14-backlog.md`
**Notation:** Every requirement has a stable ID used by the backlog and the traceability table (§9). Statements tagged as unresolved, with a question reference such as Q-09, cannot be implemented until that question is answered.

---

## 1. System purpose

A single internal web application that records TMD's procurement, delivery, stock, project cost, billing, payment and accounting activity, enforces authority, and produces traceable financial and operational reporting.

Architectural rules that apply to every requirement:

- Backend is authoritative. The frontend never computes stock balances or accounting entries.
- All money and quantity arithmetic uses fixed-precision decimals (`Decimal`), never floats.
- All sensitive operations are permission-checked server-side.
- Business rules live in explicit domain services, not in views/serialisers or UI components.
- Every posting, approval and stock movement is transactional and atomic with its audit event.

## 2. Functional requirements

### 2.1 Organisation, identity and access (`ADM`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| ADM-01 | Users can be created, updated, disabled and offboarded by an administrator; accounts are never hard-deleted once they have activity | Disabled user cannot authenticate or call any API; history retained |
| ADM-02 | Authentication uses Django's password hashing with configurable policy (length, rotation optionally) and lockout/rate limiting | Repeated failures lock or throttle per policy; policy value configured, not hard-coded |
| ADM-03 | Password reset uses a time-limited token delivered out-of-band | Token single-use, expires, invalidated on password change |
| ADM-04 | Sessions/tokens are securely handled; cookie-based auth uses CSRF protection and secure cookies in deployed environments | Automated check: unauthenticated request returns 401/403 on every private endpoint |
| ADM-05 | Roles bundle permissions; users may hold more than one role per department [UNRESOLVED: Q-08] | Permission set resolution tested per role combination |
| ADM-06 | Permission checks apply at module, action and, where required, record level | Test proves a Warehouse user cannot approve a payment or view another department's records where policy forbids it |
| ADM-07 | Maker-checker is enforced: a creator cannot approve their own document where the policy requires separate approval | Self-approval attempt returns 403 with a clear reason; attempt is logged |
| ADM-08 | Approval limits are data-driven (amount, department, project, document type) [UNRESOLVED: Q-09, Q-10] | Limits changeable by configuration with an audit record; no hard-coded amounts |
| ADM-09 | Delegated authority can be granted for a bounded period, with delegation recorded and visible on approvals | Delegated approval records both the delegate and the delegator |
| ADM-10 | Append-only audit events are written for authentication, master-data change, approval, posting, reversal, export, permission change and document access where appropriate | Audit rows cannot be updated/deleted by ordinary users; contain actor, timestamp, action, record, before/after where appropriate, reason, correlation ID |
| ADM-11 | Users can be assigned to departments and cost centres; record visibility can be restricted by department/project membership [UNRESOLVED: Q-07] | Cross-department access test passes |

### 2.2 Master data (`MAS`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| MAS-01 | Customers: legal name, addresses, contacts, tax identifiers, payment terms, credit controls, contracts, statement history | Duplicate detection on name/tax ID; deactivation blocked only where policy requires; history retained |
| MAS-02 | Suppliers: identity, contacts, bank details with restricted access, tax/compliance documents with expiry, terms, currencies, approved categories, performance history, due-diligence status | Bank detail change requires elevated permission and is audited; expired compliance document blocks new PO where policy permits [UNRESOLVED: Q-16] |
| MAS-03 | Products and services catalogue: SKU/service code, description, UoM, specification, brand/manufacturer, category, tax classification, preferred suppliers, active flag, controlled price history | Price change creates a new history row with effective date; historical documents keep original price |
| MAS-04 | Units of measure with conversion where needed [UNRESOLVED: Q-14] | Conversion applied consistently on documents |
| MAS-05 | Tax codes are configuration records: name, rate, treatment, effective dates, source/version/approval owner, optional GL role mapping [UNRESOLVED: Q-24] | No tax rate literal exists in source code; changing a tax code does not alter historical documents |
| MAS-06 | Warehouses and storage locations (bins) with active flags | Location-level on-hand queryable |
| MAS-07 | Document categories with access rules, versioning and retention metadata [UNRESOLVED: Q-28] | Upload restricted by type/size; download requires permission; no public URL |
| MAS-08 | Master records referenced by transactions cannot be deleted, only deactivated | Deactivation of a referenced record is permitted; deletion is refused |

### 2.3 Projects and contracts (`PRJ`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| PRJ-01 | Projects have a code, client, name, managers, locations, dates, status (lifecycle validated) | Unique project code per organisation; lifecycle transitions rejected when illegal |
| PRJ-02 | Contracts hold value, currency, terms, start/end, with revisions preserved | Revision creates a new version; previous version retrievable |
| PRJ-03 | Budgets are versioned by cost code/line with approval and effective dates | Only one approved active budget version; revisions require approval |
| PRJ-04 | Cost codes/cost centres are configurable and used on PO lines, stock issues, invoices and timesheets | Reports group by cost code consistently |
| PRJ-05 | Milestones define billing triggers and completion evidence | Milestone completion requires evidence and permission |
| PRJ-06 | Project closure prevents new commitments/issues while retaining history | Closed project rejects new POs/requests with a clear message |
| PRJ-07 | Project cost view shows budget, committed, received-not-invoiced, actual, stock reserved, stock issued, revenue and margin | Figures reconcile to source documents; a drill-through shows the underlying transactions |

### 2.4 Procurement (`PRC`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| PRC-01 | Purchase requests with lines, project/budget line, destination (warehouse or site), required date, justification | Cannot submit without a project or a stock-replenishment reason; validation server-side |
| PRC-02 | Budget/authority check at submission and approval [UNRESOLVED: Q-11] | Over-budget request routes to exception or is blocked per approved policy |
| PRC-03 | Approval workflow with configurable levels, rejection reasons and resubmission | Rejection requires a reason; resubmission keeps full history |
| PRC-04 | RFQ creation and issue to multiple suppliers; quotation capture with comparison criteria and recommendation | Comparison shows line-level price/lead-time/spec differences; recommendation requires justification |
| PRC-05 | Purchase orders generated from an approved request or directly by authorised users; support schedules, amendments, cancellation | Amendment creates a revision; received quantities preserved; cancelled PO blocks further receipts |
| PRC-06 | PO lines carry item/service, quantity, price, currency, tax code, project, cost code, delivery location, terms | Totals validated server-side; tax computed from the tax code record |
| PRC-07 | Delivery schedules and fulfilment records per PO line, supporting partial deliveries and split destinations (warehouse vs site) by explicit split quantities | Over-receipt blocked beyond a configured tolerance without exception approval |
| PRC-08 | Direct-to-site delivery confirmations capture quantities, condition, date, evidence and receiver | Acceptance quantity may be less than delivered (rejections recorded separately) |
| PRC-09 | Warehouse goods receipt notes (GRN) capture accepted/rejected quantities, condition, location, batch/serial where required, evidence | Accepted quantity posts a stock receipt; rejected quantity does not become available stock |
| PRC-10 | Supplier returns, substitutions, backorders and shortages are explicit recorded events | Each has its own state and reference; quantities reconcile to the PO |
| PRC-11 | Three-way match compares PO, receipt/service confirmation and supplier invoice, producing a match status and exception queue | Quantity/price/tax mismatches produce exceptions, never silent acceptance |
| PRC-12 | Supplier performance history (delivery, quality, price) is derived from records, not typed freehand | Values trace to receipts and exceptions |
| PRC-13 | Every procurement document has a lifecycle with server-validated transitions (`04-workflows.md` §5) | Illegal transition returns 409/422 with reason; transition logged |

### 2.5 Warehouse and inventory (`INV`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| INV-01 | Stock ledger records immutable movements: receipt, put-away, transfer out/in, reservation, release, issue, return, adjustment, count correction | No endpoint sets a balance directly; balance is a projection of movements |
| INV-02 | Quantities tracked per item, warehouse, location and (where enabled) lot/serial; states available, reserved, in-transit, damaged, quarantined distinguished | Queries return each state separately; totals reconcile to movements |
| INV-03 | Reservations prevent overselling; issue cannot exceed available (available = on-hand − reserved − quarantined) | Concurrent issue test: two simultaneous issues cannot both succeed beyond availability |
| INV-04 | Transfers record source and destination; stock in transit is unavailable at both ends until receipt | Reconciliation test proves no double-count during transit |
| INV-05 | Stock valuation per accountant-approved method [UNRESOLVED: Q-18] with valuation snapshots per movement | Valuation report reconciles to ledger and movement history |
| INV-06 | Stock counts capture counted vs system quantity, variance, reason and approval before any adjustment posts | Variance adjustment requires approval and creates an auditable movement |
| INV-07 | Issue to project/customer records project, cost code, recipient and evidence; cost is recognised once at issue | Project cost increases exactly once per issue; no re-expense at invoice payment |
| INV-08 | Reorder levels and low-stock indicators are configurable per item/warehouse | Report lists items at/below reorder level |
| INV-09 | Returns to supplier and returns from project are separate movements with references | Balances and project costs adjust correctly |
| INV-10 | Negative stock is refused unless an approved exception policy exists [UNRESOLVED: Q-19] | Attempt returns a validation error naming availability |

### 2.6 Accounts payable and receivable (`AP`, `AR`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| AP-01 | Supplier invoices captured with supplier, number, date, due date, currency, lines (item/service, quantity, price, tax), project/cost code, attachments | Required fields enforced; totals validated; attachment optional/required per policy [UNRESOLVED: Q-20] |
| AP-02 | Duplicate invoice detection on supplier + invoice number (with configurable exceptions) | Duplicate attempt blocked with the original document referenced; override requires elevated approval and is audited |
| AP-03 | Invoices require match status (PO/receipt/service) per policy; unmatched invoices go to exception queue | Cannot post an unmatched invoice unless policy explicitly allows with approval |
| AP-04 | Invoice approval follows maker-checker and approval limits | Creator cannot approve; approver recorded with timestamp |
| AP-05 | Posting is atomic: invoice status, journal, journal lines and audit event commit together | Simulated failure leaves no partial posting |
| AP-06 | Supplier credit notes and debit notes support reversal and adjustment flows | Each links to an invoice or reason; journals balance |
| AP-07 | Payment records capture method, reference, amount, date, bank/cash account, evidence; online banking credentials are never stored | Reference uniqueness enforced; no credential fields exist |
| AP-08 | One payment can settle many invoices; one invoice can receive many partial payments; over-allocation blocked | Allocation totals reconcile to invoice balance; over/under-allocation visible |
| AP-09 | Advances, deposits and prepayments held separately from invoice settlement | Advance ledger per supplier; allocation converts advance to settlement with audit |
| AP-10 | Payment approval and execution are separate steps where policy requires; execution is idempotent | Re-submitting the same execution request does not create a second payment |
| AP-11 | Bounced payments, refunds, bank charges and payment reversals have controlled workflows and correct journals | Each scenario produces balanced entries and a reversal trail |
| AP-12 | AP ageing and supplier statements produced from posted balances | Totals reconcile with GL control account |
| AR-01 | Customer invoices created from milestones/delivery/service acceptance, with tax per tax code | Cannot invoice a milestone without completion evidence where policy requires |
| AR-02 | Invoice draft → validation (tax, commercial, credit) → approval → posting → delivery status | Illegal transitions rejected; posting atomic |
| AR-03 | Customer credit notes and debit notes with reason and linkage | Balances update; journals balance |
| AR-04 | Receipts captured with date, amount, method, bank account, reference, evidence | Duplicate bank reference detected where possible |
| AR-05 | Receipts allocated to one or many invoices, or held as customer advance | Allocation sums reconcile; unallocated amount visible |
| AR-06 | Customer statements and AR ageing from posted data | Reconciles with GL control account |
| AR-07 | Disputed invoices can be flagged with reason, owner and resolution | Disputed amount excluded from collections reminders per policy |
| AR-08 | Credit control: configurable limit/overdue rules [UNRESOLVED: Q-21] | Blocking behaviour configurable, not hard-coded |

### 2.7 General ledger and accounting (`GL`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| GL-01 | Chart of accounts maintained as configuration, supplied and approved by the accountant [UNRESOLVED: Q-22] | No account is created by the build team as company policy |
| GL-02 | Accounting periods with status (open/soft-closed/locked) and control of posting dates | Posting into a locked period is rejected; reopen requires elevated permission and is audited |
| GL-03 | Journals have ≥2 lines and must balance in transaction and base currency per approved rules | Unbalanced journal is rejected by service **and** database constraint where feasible |
| GL-04 | A single central posting service owns journal creation; no other module writes journals | Code review + tests: only posting service inserts journal rows |
| GL-05 | Journal lines link to source document type/id and business event; every posted balance is explainable | Drill-through from trial balance to source document |
| GL-06 | Posted journals are immutable; correction via reversal (linked) and replacement | Edit/delete attempts refused at API and model level |
| GL-07 | Posting is idempotent per source event to prevent duplicate journals on retry | Same event retried creates no second journal |
| GL-08 | Trial balance, general ledger detail, income statement and balance sheet from approved account mappings | Report totals reconcile to journals; period filters correct |
| GL-09 | Source-event-to-journal mappings configured per approved posting matrix (`07-accounting-events.md`) | Mappings visible and auditable as configuration |
| GL-10 | Multi-currency support with rate capture and revaluation policy [UNRESOLVED: Q-25] — features disabled until approved | Enabling requires documented policy; historical rates preserved |
| GL-11 | Opening balances loaded only after accountant sign-off, through a controlled import with reconciliation | Import rejects invalid rows; trial balance reconciles before release |

### 2.8 Banking and reconciliation (`BNK`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| BNK-01 | Bank and cash accounts as master records linked to GL accounts | One GL account per bank account enforced per policy |
| BNK-02 | Statement import via validated templates (CSV/XLSX) with rejected-row reporting | Invalid rows reported, never silently skipped |
| BNK-03 | Statement lines matched to receipts, payments, transfers, fees; unmatched lines remain visibly unresolved | No forced balancing; unmatched count reported |
| BNK-04 | Transfers between accounts modelled as paired entries | Both sides posted atomically |
| BNK-05 | Reconciliation has review/approval and period-close reporting | Reconciliation cannot be approved with unexplained lines unless an approved exception exists |
| BNK-06 | Adjustments for bank charges/interest use controlled workflow with approval | Journals balance and link to the statement line |

### 2.9 Tax and fiscalisation (`TAX`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| TAX-01 | Tax codes configurable with rate, treatment, effective dates and approval metadata; historical invoices unaffected by later changes [UNRESOLVED: Q-24] | Changing a tax code does not mutate posted documents |
| TAX-02 | Invoice documents include all fields required by the confirmed regulatory regime | Field set reviewed by TMD's tax adviser |
| TAX-03 | NRS/fiscalisation submission adapter with response tracking, retries, duplicate-submission prevention and reconciliation [UNRESOLVED: Q-26] | Retry does not double-submit; statuses visible per invoice |
| TAX-04 | Tax reporting extract per approved definition | Totals reconciled to posted tax lines |
| TAX-05 | Integration is feature-flagged; the system is fully usable for core accounting while the integration is unapproved | Flag off leaves no broken invoice flow |

### 2.10 Project cost, services and equipment (`PCS`, `SVC`, `AST`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| PCS-01 | Project cost ledger captures direct purchases, stock issues, labour, logistics, subcontractors and equipment hire | Each cost traces to a source document; totals by cost code |
| PCS-02 | Committed cost from open POs is reported separately from actual cost | Reports never mix commitment with expense |
| PCS-03 | Budget revisions and change control preserve prior versions and approvals | Only approved version drives variance reporting |
| PCS-04 | Project profitability statement distinguishes invoiced revenue from recognised revenue per approved policy [UNRESOLVED: Q-23] | Report labels both; policy documented |
| SVC-01 | Work orders/services carry scope, assignment, checklist, materials/labour used and service report | Service lines never create stock quantities |
| SVC-02 | Client acceptance recorded as evidence supporting billing | Invoice creation can require acceptance |
| AST-01 | Equipment register with ownership (owned/rented), location, condition, maintenance history | Asset state transitions validated |
| AST-02 | Rental periods, dispatch, return and inspection recorded; utilisation reported | Overlapping rentals for the same unit prevented |
| AST-03 | Asset maintenance schedule and records | Due/overdue maintenance reportable |

### 2.11 Reporting and dashboards (`REP`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| REP-01 | Financial reports: trial balance, GL detail, income statement, balance sheet | Reconcile to journals |
| REP-02 | Operational KPIs: procurement status, open POs, receipts pending invoice, stock levels, project performance | Each KPI drill-through to source |
| REP-03 | AP/AR ageing and statements | Reconcile to control accounts |
| REP-04 | Exception queues: unmatched invoices, over-receipts, stock variances, unmatched statement lines, failed submissions, overdue approvals | Each item shows owner and required action |
| REP-05 | Exports (XLSX/PDF) respect permissions and are audited | Export of restricted reports logged |
| REP-06 | Report definitions approved by the accountant before being relied upon for statutory reporting | Report pack versioned |

### 2.12 Documents and audit (`DOC`, `AUD`)

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| DOC-01 | Private file storage with authenticated download endpoints; MIME/size/extension validation | Direct URL access fails; oversized or wrong-type upload refused |
| DOC-02 | Attachments link to their transactions and appear in the transaction view | Retrieval permission enforced |
| DOC-03 | Generated PDFs (PO, GRN, invoice, statements) use approved company details and numbering | Templates configurable without code change where feasible |
| AUD-01 | Audit events append-only with actor, timestamp, action, entity, before/after (where appropriate), reason, correlation ID | Tamper attempts refused; export requires permission |
| AUD-02 | Document access to sensitive categories is logged | Log retained per retention policy |

## 3. Non-functional requirements

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| NFR-01 | Fixed-precision monetary storage (decimal), explicit currency precision and documented rounding policy | Money fields are `NUMERIC`; no float in models/serialisers; rounding test set passes |
| NFR-02 | Quantities stored with documented precision (proposed 4 dp) | Test: fractional quantities survive round trips |
| NFR-03 | Atomic multi-record operations via transactions; row locking/optimistic concurrency where concurrent updates are likely | Concurrency test on stock issue and payment allocation passes |
| NFR-04 | Response time target for standard list/detail pages [UNRESOLVED: Q-37] — proposal: p95 < 1s for typical lists, heavy reports asynchronous | Performance test on seeded dataset, evidence recorded |
| NFR-05 | Every mutating API is permission-checked and object-scope checked | Automated permission matrix test covers all sensitive endpoints |
| NFR-06 | Structured logs with correlation/request IDs; no secrets or sensitive personal data in logs | Log review checklist completed |
| NFR-07 | Health endpoints, error reporting and backup/restore procedures documented and tested | Restore test evidence recorded |
| NFR-08 | RPO/RTO defined with management — **must not be invented** [UNRESOLVED: Q-35] | Written decision before production |
| NFR-09 | Accessibility and usability for non-technical staff: clear labels, validation messages, keyboard navigation | UAT feedback from storekeeper and accounts users |
| NFR-10 | Data retention and legal hold rules per adviser guidance [UNRESOLVED: Q-28] | Retention configuration documented and approved |
| NFR-11 | The system must remain operable during third-party outage (tax adapter, notification) | Feature-flag/degrade path test |
| NFR-12 | File uploads limited by type/size; served through authenticated endpoints with safe headers | Security test: stored-XSS via upload blocked, path traversal blocked |

## 4. Lifecycle states (PROPOSED — confirm in review)

State machines are enumerated in `04-workflows.md` §5. Each transition must have: permitted role, guard conditions, side effects and audit event. Transitions are validated server-side; the API returns a domain error for illegal transitions.

## 5. Validation rules (selection)

- Quantity: > 0 on transactions; ≤ ordered + approved tolerance on receipt.
- Money: ≥ 0 where refunds are not allowed; sign conventions documented per document type.
- Dates: document date not in a locked period; due date ≥ invoice date where policy requires; required date ≥ request date.
- Uniqueness: PO number, GRN number, invoice number (per supplier), payment reference, receipt reference, journal number — company-scoped and generated by a numbering service, never typed.
- Cross-reference integrity: posted documents always reference an approved upstream document where the workflow requires it.

## 6. API conventions

- Versioned path (`/api/v1/...`), OpenAPI schema published, consistent error envelope (`code`, `message`, `field_errors`, `correlation_id`).
- Pagination, filtering and ordering server-side; no unbounded list endpoints.
- Mutations accept idempotency keys where retry is plausible (posting, payment execution, integration callbacks).
- Errors are useful but non-sensitive; internal exceptions logged with correlation ID, never returned raw.
- State changes use explicit action endpoints (`/post`, `/approve`, `/reverse`) rather than writable status fields.

## 7. Out of scope for release 1

See `02-brd.md` §3.2. In addition: no direct database access for end users, no spreadsheet-as-database patterns, no email-driven approvals (notifications only), no offline mode.

## 8. Dependencies

PostgreSQL, Redis (Celery broker), private object/file storage, PDF renderer, XLSX library, email/SMS provider (optional), NRS adapter (unapproved). See `12-integrations.md`.

## 9. Traceability

| Requirement group | BRD objective | Backlog phase | Workflow reference | Data model reference |
| --- | --- | --- | --- | --- |
| ADM | BO-06, BO-08 | Phase 2 | §5.6 | Organisation/User/Role/Permission/Approval |
| MAS | BO-01, BO-09 | Phase 3 | — | Partners, Catalogue, Documents |
| PRJ | BO-07 | Phase 3 | §2 | Projects, Budgets, Milestones |
| PRC | BO-02 | Phase 4 | §1, §3 | PurchaseRequest → PO → GRN |
| INV | BO-03 | Phase 5 | §2, §5 | StockMovement, Reservation, Count |
| GL | BO-04 | Phase 6 | §6 | Account, Journal, JournalLine, Period |
| AP/AR | BO-05 | Phases 7–8 | §1, §4 | SupplierInvoice, CustomerInvoice, Payments |
| BNK | BO-05 | Phase 9 | §6 | BankStatement, Reconciliation |
| TAX | BO-09 | Phase 7 | §4 | TaxCode, submission records |
| PCS/SVC/AST | BO-07 | Phase 10 | §3 | CostLedger, WorkOrder, Asset |
| REP | BO-01, BO-07 | Phases 6–11 | §7 | Read models over all domains |
| DOC/AUD | BO-08 | Phases 1–2, extended continuously | §8 | Document, AuditEvent |
| NFR | All | Phases 1, 11 | — | Cross-cutting |

## 10. Open questions affecting this SRS

All **[UNRESOLVED]** markers resolve to entries in `11-questions.md`; each also appears in `13-decision-register.md` with an owner and the phase it blocks. No requirement above will be implemented as policy before its answer is recorded.
