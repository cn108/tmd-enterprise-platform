# TMD Enterprise System — Final Business Acceptance Report

**Date:** 13 November 2026  
**Business owner:** Owner / Managing Director  
**Technical owner:** Software Developer / Technical Administrator  
**Status:** **technical and browser UAT evidence complete; Managing Director signature pending**  
**Open business decision:** UAT-D-004 (role matrix and no separate General Requester role)

## 1. Acceptance model

TMD currently has two accountable people: the Managing Director and the Software Developer. The acceptance programme is therefore simplified to those two roles, not a fictional department sign-off board:

- **Managing Director:** procurement/purchasing, suppliers/customers, invoices/payments, inventory, projects/equipment, approvals and financial reports.
- **Software Developer:** functionality, security/permissions, database integrity, backups/restoration, deployment preparation, performance/monitoring.

All ten application roles remain configured for future expansion. They were exercised with synthetic accounts, not removed because TMD currently has few staff. The platform supports future departments, delegated responsibilities and approval hierarchies.

Scripts and records:

- `docs/uat/owner-acceptance.md` — 23 Managing Director checks and acceptance decision.
- `docs/uat/developer-acceptance.md` — 38 technical checks and limitations.
- Existing formal UAT: `docs/uat/final-uat-summary.md`, `docs/uat/uat-defect-register.md`, role scripts and evidence.

## 2. Browser and API evidence completed

| Evidence                                              | Result                                                 |
| ----------------------------------------------------- | ------------------------------------------------------ |
| Playwright formal UAT                                 | **9/9 passed**                                         |
| MFA Playwright                                        | **1/1 passed** — enrolment, TOTP, recovery and replay  |
| UAT API probe                                         | **5/5 checks passed**                                  |
| Ten roles loaded                                      | Pass                                                   |
| Management/Auditor read-only administration           | Pass                                                   |
| Procurement request → independent Management approval | Pass (`PR-2026-0002`)                                  |
| Restricted module access                              | Pass (no data/403 console noise)                       |
| Production controls disabled                          | Pass                                                   |
| Backend suite                                         | 348 passed                                             |
| Frontend suite                                        | 73 passed                                              |
| Accessibility/responsive checks                       | Prior acceptance reports; no new regression identified |

The nine browser workflows cover Management, Procurement, Warehouse, Finance, Project, Operations, Administration, Audit and restricted-access security. Screenshots and JSON evidence are under `docs/uat/evidence/` and `docs/reports/evidence/`.

## 3. Business workflows accepted in evidence

### Procurement and purchasing

- Purchase request created by Procurement, submitted and independently approved by Management.
- Creator cannot approve their own request; repeat approval is refused.
- Purchase orders, goods receipts, partial receipt and rejected/damaged quantity are traceable.
- Approval bands are applied; high-value two-approver behaviour is tested in the backend.

### Suppliers and customers

- Supplier/customer master data, contacts, addresses and credit position are available.
- Supplier bank details are masked to the last four digits.
- Bank-detail changes and compliance records are permission-controlled.
- Customer statements and receivables ageing derive from approved invoices, notes, receipts and allocations.

### Invoices and payments

- Customer and supplier invoice lifecycles, approval, PDF and email controls are implemented.
- Supplier payments are recorded/allocated; payment execution is absent by design.
- Customer receipts support partial/multiple allocation, unapplied funds, cancellation, individual allocation reversal and ledger posting.
- Invoice, payment and receipt posting is idempotent and transactional.
- Approved notes/WHT block gross posting until their accounting treatment is approved.

### Inventory

- Receipts, issues, transfers, returns, adjustments, damage, counts, reservations and valuation are implemented.
- Negative stock is blocked at database level.
- Project issues create project cost; transfers and reservations are not treated as consumption.
- The synthetic reconciliation agrees inventory value to stock records.

### Projects, services and equipment

- Project budgets, milestones, direct costs, commitments and profitability are available.
- Service work orders run from request to completion/acceptance.
- Equipment/leasing supports reservations, agreements, dispatch, return, inspection and maintenance.
- Project margin is not presented as recognised revenue.

### Approvals and reports

- Journals, purchase documents, invoices, notes and payments use independent approval rules.
- Trial balance, financial statements, general ledger, cash flow, ageing and journal register are available.
- Formal statements come from posted journals only; warnings identify incomplete configuration.

## 4. Open business decisions

| ID         | Decision                                                                                     | Why it matters                                                             | Owner                       | State       |
| ---------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------------- | ----------- |
| UAT-D-004  | Ratify the ten-role matrix and the decision that there is no separate General Requester role | Determines who may raise requests and how future departments are onboarded | Managing Director           | **OPEN**    |
| F-11       | Confirm the ₦5,000,000 approval band and the document value it applies to                    | Controls who can commit spend                                              | Managing Director / Finance | **OPEN**    |
| F-01–F-15  | Chart, mappings, tax, revenue, inventory, opening balances                                   | Without these, live posting must remain disabled                           | External accountant / MD    | **OPEN**    |
| Acceptance | Sign the owner and developer acceptance records                                              | Converts testing into formal acceptance                                    | MD / Developer              | **PENDING** |

MFA and API throttling were previously UAT decisions; they are now implemented and removed from the open decision list (UAT-D-002 and UAT-D-003 closed).

## 5. What the Managing Director is being asked to accept

Acceptance is of the **business workflows on synthetic data**, not of production readiness. Specifically:

- The procurement, supplier/customer, invoice/payment, inventory, project/equipment, approval and reporting flows reflect how TMD intends to operate.
- The ten-role model and the no-General-Requester decision are acceptable for future expansion.
- The remaining accounting, tax and opening-balance decisions will be made with the external adviser before live posting.
- Production go-live, invoice issuance, financial activation, bank execution and NRS submission remain separately authorised.

## 6. Acceptance record

| Field                              | Entry                                                |
| ---------------------------------- | ---------------------------------------------------- |
| Managing Director name             | ________________________________                     |
| Business workflows                 | ☐ Accepted ☐ Accepted with conditions ☐ Not accepted |
| Role matrix / no General Requester | ☐ Approved ☐ Amend ☐ Defer                           |
| Conditions                         | ________________________________                     |
| Date                               | ________________________________                     |
| Signature                          | ________________________________                     |

| Field                | Entry                                                |
| -------------------- | ---------------------------------------------------- |
| Developer name       | ________________________________                     |
| Technical acceptance | ☐ Accepted ☐ Accepted with conditions ☐ Not accepted |
| Date                 | ________________________________                     |
| Signature            | ________________________________                     |

## 7. Conclusion

The system is ready for the Managing Director's structured acceptance session and for external accounting review. It is **not** ready for production use and no production launch is authorised by this report. The remaining acceptance gap is a human signature and the open role/accounting decisions, not missing application screens.
