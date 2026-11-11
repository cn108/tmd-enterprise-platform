# Roles, Permissions and Approval Matrix (Draft)

**Version:** 0.1 — 11 November 2026
**Status:** **No approval threshold in this document is a company policy.** All monetary and structural limits are UNRESOLVED and marked ⚠ with a question reference in `11-questions.md`.
**Guide references:** §4, §8, §9 Phase 2, §15.5

---

## 1. How to read this

Two separate mechanisms exist and must not be confused:

1. **Permissions** (can this user perform this action at all) — role-based, enforced on the backend per endpoint and per object.
2. **Approval authority** (may this user approve *this* transaction) — amount/department/project driven, configured as data, with maker-checker.

A role having "approve invoices" permission does not grant unlimited approval; the approval policy layer decides whether the amount is within the user's authority. Both checks are required.

## 2. Proposed roles

| Code | Role | Purpose |
| --- | --- | --- |
| R-ADM | System Administrator | User lifecycle, roles, master-data maintenance, configuration (no transaction approval rights by default) |
| R-MGT | Management / MD | Commercial oversight, high-value approvals, budget approval, period sign-off |
| R-ACC | Accountant / Finance Lead | Chart of accounts, posting matrix, period control, invoice posting approval, report definitions |
| R-FIN | Finance / Accounts Officer | Invoice capture, payment preparation, allocation, reconciliation, reports |
| R-PRC | Procurement Officer | Requests processing, RFQ, quotes, PO drafting, supplier records |
| R-PM | Project Manager | Requests against own project, budget monitoring, site acceptance, milestone completion |
| R-STO | Warehouse / Storekeeper | GRN, put-away, reservation, issue, transfer, counts |
| R-OPS | Operations / Work-order supervisor | Work orders, service reports, equipment dispatch/return |
| R-HSE | HSE / Compliance officer | Compliance documents, certificates, inspection records |
| R-AUD | Auditor / Read-only | Read access to transactions, ledger and audit trail; no mutations |
| R-REQ | Requester (any employee) | Raise purchase requests, view own documents |

Whether all of these roles are needed, and whether one person holds several, is Q-08. Mapping the proposed roles onto TMD's actual job titles is a Phase 0 interview task.

## 3. Permission matrix (proposed)

Legend: **C** create · **R** read · **U** update (before approval only) · **A** approve · **P** post/reverse · **X** no access · **Ⓡ** read-only when scoped to their own project/department.

| Capability | R-ADM | R-MGT | R-ACC | R-FIN | R-PRC | R-PM | R-STO | R-OPS | R-HSE | R-AUD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Users, roles, permissions | C R U | R A | X | X | X | X | X | X | X | R |
| Company / department / cost-centre setup | C R U | A | R | X | X | X | X | X | X | R |
| Chart of accounts & posting mappings | X | R A | C R U A | R | X | X | X | X | X | R |
| Accounting period open/lock | X | A | C R U A | R | X | X | X | X | X | R |
| Tax code configuration | R | A | C R U A | R | X | X | X | X | X | R |
| Customers / suppliers master | C R U | R A | A (financial terms) | R U | C R U | Ⓡ | R | R | R (compliance docs) | R |
| Supplier bank details | X | R U | R U A | Ⓡ | X | X | X | X | X | X |
| Products / services catalogue | C R U | R | R | R | C R U | R | R | R | X | R |
| Projects / contracts / budgets | C R U | A | R | R | R | C R U A (own) | R | Ⓡ | X | R |
| Purchase request | X | A (per limit) | R | R | C R U | C R U (own) | C R (stock req) | C R | X | R |
| RFQ / quotations / comparison | X | R | X | X | C R U | R (own) | X | X | X | R |
| Purchase order | X | A (per limit) | R | R | C R U | R (own) | R | R | X | R |
| GRN / site acceptance | X | X | R | R | R | C R (site) | C R U (warehouse) | C R (equipment) | X | R |
| Supplier invoice capture | X | R | R | C R U | R | R | X | X | X | R |
| Supplier invoice approve / post | X | A (per limit) | A P | X | X | X | X | X | X | R |
| Supplier invoice reverse | X | A | A P | X | X | X | X | X | X | R |
| Payment preparation | X | R | R | C R U | X | X | X | X | X | R |
| Payment approval / execution | X | A (per limit) | A | X (execute ⚠Q-33) | X | X | X | X | X | R |
| Payment allocation / advance | X | R | A | C R U | X | X | X | X | X | R |
| Stock movement (receipt/issue/transfer) | R | R | R | X | R | R (view own project issues) | C R U | C R (equipment) | X | R |
| Stock count & adjustment | X | A | A | R | X | X | C R U | X | X | R |
| Customer invoice | X | A (per limit) | A P | C R U | X | C R U (milestone evidence) | X | C R (service report) | X | R |
| Customer receipt / allocation | X | R | A | C R U | X | X | X | X | X | R |
| Bank statement import / matching | X | R | A | C R U | X | X | X | X | X | R |
| Reconciliation approval | X | A | A | C R U | X | X | X | X | X | R |
| Documents (upload/download) | C R U | R | R | R | R | R | R | R | C R U (compliance) | R |
| Audit trail | R | R | R | X | X | X | X | X | X | R |
| Financial reports | R | R | R | R | X | X | X | X | X | R |
| Operational dashboards | R | R | R | R | R | Ⓡ | R | R | R | R |

**Rules that are confirmed by the brief and therefore mandatory regardless of role design:**

- Storekeepers must not approve payments (Guide §8, least privilege).
- An invoice creator must not approve their own invoice where maker-checker applies (Guide §8).
- Supplier bank details, employee personal data, financial reports and document downloads are restricted by role (Guide §8).
- Backend enforcement only — hiding a button is not a control (Guide §1, §8).
- Permission changes are audited (Guide §8).

## 4. Maker-checker (proposed)

| Document | Creator may approve own? | Minimum distinct approvers | Proposed |
| --- | --- | --- | --- |
| Purchase request | No (where value above a threshold ⚠Q-09) | 1–2 | UNRESOLVED |
| Purchase order | No | 1–2 | UNRESOLVED |
| GRN / acceptance | No — the receiver records, a supervisor reviews where policy requires | 1 | UNRESOLVED |
| Supplier invoice | No | 1 (Finance officer) + 1 (Accountant/MD per value) | UNRESOLVED |
| Payment | No | 1–2 | UNRESOLVED |
| Customer invoice | No | 1 | UNRESOLVED |
| Credit note / write-off | No | 2 | UNRESOLVED |
| Journal / adjustment | No | 1 (Accountant) | UNRESOLVED |
| Stock adjustment | No | 1 (supervisor/Finance) | UNRESOLVED |

Two design decisions follow, and both need confirmation:

- **D-04a** Whether TMD wants strict dual approval across the board (slower, stronger control) or single approval with dual only above a value threshold (faster, weaker).
- **D-04b** Whether the approver set is determined by amount, department, project, procurement type, or a combination.

## 5. Approval matrix — structure (values UNRESOLVED)

The system will store approval policy as **data**: `ApprovalPolicy(document_type, scope_type, scope_ref, min_amount, max_amount, currency, required_roles, approval_count, escalation_minutes, active_from, active_to)`. This avoids hard-coding limits and allows change with an audit record.

Template to be completed by management (⚠Q-09, ⚠Q-10):

| Document type | Band (NGN) | Approver role(s) | Approvals required | Escalation |
| --- | --- | --- | --- | --- |
| Purchase request | 0 – [value] | [role] | [n] | [hours] |
| Purchase request | [value] – [value] | [role] | [n] | [hours] |
| Purchase order | … | … | … | … |
| Supplier invoice | … | … | … | … |
| Payment | … | … | … | … |
| Customer invoice / credit note | … | … | … | … |
| Journal / stock adjustment | … | … | … | … |
| Budget revision | … | … | … | … |

**No values are proposed here.** Proposing amounts would be inventing company policy, which the brief explicitly forbids. If management cannot decide immediately, the fallback is one documented default policy (single approval by a named role for every amount) recorded as an explicit decision with a review date — not an unmarked assumption.

## 6. Delegation

- Delegation is time-bounded, granted by an authorised person, and records delegator, delegate, scope (document types), limit and period.
- Every approval made under delegation shows both identities.
- Delegation cannot exceed the delegator's own authority and cannot be self-granted.
- Expired delegation immediately removes authority.
- ⚠Q-10: which roles may delegate, and does management approve it?

## 7. Segregation-of-duties rules (proposed, testable)

| Rule | Rationale |
| --- | --- |
| Supplier creation ≠ payment approval for that supplier | Prevents fictitious supplier fraud |
| Supplier bank detail change ≠ payment approval | Prevents bank-detail substitution fraud |
| GRN recording ≠ invoice approval where receiving and accounts are separate | Prevents phantom deliveries |
| Customer invoice creation ≠ write-off approval | Prevents revenue manipulation |
| Journal posting ≠ period reopen | Prevents concealing adjustments |
| User administration ≠ transaction approval | Prevents privilege escalation to approve own work |

Each rule becomes an automated test in Phase 2; a violation must be impossible even by direct API call.

## 8. Session and account controls

- Passwords hashed with a modern algorithm; minimum length/complexity configured, not hard-coded.
- Lockout or throttling after repeated failures; administrator unlock audited.
- Account disablement takes effect immediately on the next request.
- Optional MFA — ⚠Q-36 (staff capability and device constraints determine feasibility).
- Idle session timeout configured per policy.
- Offboarding checklist: disable account, reassign approvals, revoke delegations, review documents created — all audited.

## 9. Unresolved items summary

| ID | Item | Owner | Blocks |
| --- | --- | --- | --- |
| Q-07 | Record-level visibility rules by department/project | Management | Permissions implementation (Phase 2) |
| Q-08 | Actual roles and holders; who holds multiple roles | Management + department heads | Permission matrix sign-off |
| Q-09 | Approval limits by amount/type | Management + Finance | Approval engine (Phase 2) |
| Q-10 | Delegation rules and escalation times | Management | Approval engine |
| Q-13 | Direct-PO authority (PO without request) | Management + Procurement | Procurement phase 4 |
| Q-33 | Whether finance executes bank payments in-system | Finance | Payments phase 8 |
| Q-36 | MFA availability | IT | Security configuration |
