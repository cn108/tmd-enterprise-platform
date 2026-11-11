# Risk Register

**Version:** 0.1 — 11 November 2026
**Guide references:** §9, §15.7
**Scoring:** Likelihood and Impact each Low/Medium/High. Priority focuses on risks that could cause incorrect financial statements, duplicate payments, lost stock, unauthorised approvals, data leakage or failed regulatory reporting (Guide Appendix A).

---

## 1. Live risks

| ID | Risk | Likelihood | Impact | Priority | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R-01 | Posting to an unapproved/incomplete chart of accounts produces incorrect financial statements | High | High | **Critical** | Posting features stay disabled until P-01…P-17 signed; rules are configuration, not code; trial balance reconciliation gate | Accountant | Open |
| R-02 | Duplicate supplier invoice accepted, or duplicate payment executed, causing cash loss | Medium | High | **Critical** | Unique (supplier, invoice number) constraint + override approval; idempotency keys; unique payment reference; execution confirmation | Finance | Open |
| R-03 | Warehouse purchase expensed twice (at invoice and at stock issue), distorting project cost and margin | High | High | **Critical** | Explicit GRNI/inventory flow per approved policy; test asserting single expense point; project cost drill-through | Accountant | Open |
| R-04 | Stock mis-stated or lost because balances are overwritten rather than posted | Medium | High | **Critical** | Append-only stock movements; no balance-write endpoint; count variance approval; reconciliation of balances to movements | Storekeeper lead | Open |
| R-05 | Unauthorised or self-approval bypasses maker-checker | Medium | High | **Critical** | Server-side approval policy; self-approval test; segregation-of-duties tests; audit of every decision | Management | Open |
| R-06 | Supplier bank detail or employee personal data leakage | Low | High | High | Role restriction, masking, audited access, no public file URLs, bank-detail change workflow | IT / Admin | Open |
| R-07 | Tax/fiscalisation configuration wrong, or NRS integration shipped without validation, making invoices non-compliant | Medium | High | **Critical** | Adviser sign-off, feature flag, no hard-coded rates, retain official documentation and test evidence | Tax adviser | Open |
| R-08 | Scope creep into supplier/customer portals delays core delivery | Medium | Medium | High | Explicit out-of-scope list; change control; management sign-off required to add | Management | Open |
| R-09 | Approval limits never decided, blocking procurement go-live | High | High | **Critical** | Escalate as go-live blocker; interim single-approver policy recorded as a decision with review date | Management | Open |
| R-10 | Workflow designed from the brief rather than from TMD's real practice, causing rework and user rejection | High | High | **Critical** | Phase 0 interviews and sample documents mandatory; departmental walkthrough sign-off per route | Dept heads | Open |
| R-11 | Migration data incomplete or unreliable (no registers, mixed formats) | High | Medium | High | Inventory data sources early; staging load with rejected-row reporting; reconciliation before sign-off | Finance | Open |
| R-12 | Site connectivity or device constraints make the system unusable where work happens | Medium | High | High | Confirm constraints (Q-39); low-bandwidth UI; consider offline-friendly print/PDF outputs | IT | Open |
| R-13 | Key-person dependency: only one person understands a workflow or the books | Medium | Medium | Medium | Document processes in BRD/SRS; role cross-training; user manuals | Management | Open |
| R-14 | Concurrency error creates negative stock or over-allocation | Medium | High | High | Row locking/optimistic concurrency; DB constraints; concurrency tests in Phase 5/8 | Engineering | Open |
| R-15 | Period close impossible because unmatched statement lines accumulate | Medium | Medium | Medium | Reconciliation UI with visible unresolved items; reconciliation approval blocked with unexplained lines | Finance | Open |
| R-16 | Reporting performance degrades as transactions grow | Medium | Medium | Medium | Read models/indexes; async exports; measure before optimising | Engineering | Open |
| R-17 | Secrets or production data committed to the repository | Low | High | High | `.gitignore` first, secret scanning in CI, no production exports in dev, review checklist | Engineering | Open |
| R-18 | Audit trail tampered with or insufficient for inspection | Low | High | High | Append-only design, DB-level restrictions, before/after capture, export permissioned | Engineering | Open |
| R-19 | User adoption failure (staff revert to spreadsheets) | Medium | Medium | Medium | Role-specific training, simple screens, parallel run, visible benefits to each role | Management | Open |
| R-20 | Regulatory requirement changes after go-live (tax/e-invoicing) | Medium | Medium | Medium | Configurable tax/fiscal layer with effective dates; retest on change; monitoring of official channels | Tax adviser | Open |
| R-21 | Single environment used for everything, risking production experiments | Medium | High | High | Separate local/staging/production configs from Phase 1; release gate | IT | Open |
| R-22 | Equipment leasing availability double-booked (same unit rented twice) | Medium | Medium | Medium | Overlap constraint on rentals + dispatch confirmation | Operations | Open |
| R-23 | Cost codes not agreed, so project costing cannot be reported meaningfully | High | Medium | High | Agree cost-code structure in Phase 0/3 (Q-14b) | Project managers | Open |
| R-24 | Timetable pressure leads to skipping accounting sign-off | Medium | High | **Critical** | Written rule: financial correctness is not waived for a date; management acceptance required and recorded | Management | Open |
| R-25 | Backups exist but restores untested | Medium | High | High | Scheduled restore tests with recorded evidence; RPO/RTO agreed | IT | Open |

## 2. Risks that must be closed before their phase starts

| Risk | Blocks phase |
| --- | --- |
| R-01, R-03 | Phase 6 (ledger) and Phase 7 (AP/AR) |
| R-09 | Phase 2 (permissions/approvals) — partially; Phase 4 needs it |
| R-07 | Phase 7 (invoice issuance) and go-live |
| R-10 | Phase 3 onward — resolved by Phase 0 interviews |
| R-11 | Phase 13 (migration) |
| R-12, R-21, R-25 | Phase 1 and Phase 12 |

## 3. Accepted-risk log (to be completed by management)

| Risk | Accepted by | Date | Rationale | Review date |
| --- | --- | --- | --- | --- |
| — | — | — | No risks accepted yet | — |

An accepted risk requires a named owner, rationale and review date. Verbal acceptance is not recorded as acceptance.

## 4. Escalation

A risk becomes an escalation when it blocks a phase gate, involves cash/financial misstatement, or concerns unauthorised access. Escalation goes to Management with the accountant informed for financial items, and is logged in the decision register with the date it was raised.
