## Phase: 4 — Procurement management (backend APIs)

**Date:** 11 November 2026
**Prepared by:** Build agent, for review by TMD management and the technical owner
**Status:** ready for review — **partial phase report.** The procurement lifecycle is implemented and tested end to end through the API; screens, role-based permissions and the approval-limit matrix do not exist, so the Phase 4 exit gate is **not** met.

### Requirements addressed

`PRC-01` purchase requests with destination and required date, `PRC-03` approval, rejection and resubmission, `PRC-04` RFQ, quotation capture, comparison and recommendation, `PRC-05` PO generation from an approved request, `PRC-06` PO lines with item, quantity, price, project and cost centre, `PRC-07` delivery schedules with split destinations and partial fulfilment, `PRC-08` site/project delivery confirmations, and `PRC-09` warehouse goods-receipt notes with accepted, rejected and damaged quantities.

**Partially addressed:** `PRC-02` budget/authority checks have no policy to enforce — approval is permission-based only and no limit is applied (D-04, Q-11). `PRC-05` PO amendments create a new revision and cancellation is not yet implemented. `PRC-09` stock posting is not implemented because the inventory ledger arrives in Phase 5; accepted quantities are recorded but do not move stock.

**Not addressed:** `PRC-10` supplier performance, `PRC-11` contract call-offs, `PRC-12` procurement reporting and `PRC-13` direct-PO pathway (Q-13 unanswered). Tax codes on PO lines remain free text because `MAS-05` is blocked by Q-24.

### Implemented

- **Destinations modelled once (B-28).** A `Destination` is a project, a company warehouse, or another authorised location (free-text name, optional address). Purchase requests, purchase orders and delivery schedules all reference this one table, so a project delivery, a warehouse receipt and a named site all use the same vocabulary and split fulfilment needs no child orders.
- **Purchase requests (PRC-01/03).** Numbered `PR-YYYY-NNNN`; lines carry item or service, quantity, project and cost centre; a destination is required. Lifecycle is draft → submitted → approved/rejected → cancelled. Submission requires at least one line. Rejection requires a reason. A rejected request can be resubmitted, retaining the same record and number so history stays intact. Approved, rejected and cancelled requests are read-only.
- **Approval and segregation of duties (D-04 blocked).** Approval requires the Django permission `procurement.approve_purchaserequest`; the service refuses if the approver is the requester. **No value threshold is applied** and no approver-routing rule is invented, because D-04/D-14 are unsigned.
- **RFQs (PRC-04).** An RFQ can only be raised from an approved request. Suppliers are invited explicitly through `RfqSupplier` rows; issuing is refused when no supplier is invited, when the RFQ has no lines, or when it is not a draft. Issued RFQs are immutable.
- **Supplier quotations.** Numbered `QT-YYYY-NNNN`; one quotation per supplier per RFQ. A quotation can only be registered for an invited supplier, can only quote request lines belonging to the RFQ's request, must cover each line once, and cannot quote a quantity above the requested quantity. Price and lead time are client-supplied; no price is inferred.
- **Comparison and selection.** Quotations are compared line by line on price and lead time through the quotation list filtered by RFQ. Selection records the winning quote, the selecting user, a mandatory justification and the comparison basis; it requires `procurement.select_supplier`, and an RFQ can be selected only once.
- **Purchase orders (PRC-05/06).** A PO is generated from a supplier selection, copying the selected line, quantity and price, and carrying the request's project, cost centre, destination and supplier. A PO can also be raised with manual lines for cases the request did not cover, but it must reference an **approved** request. Numbered `PO-YYYY-NNNN`. Lifecycle is draft → submitted → approved → issued → partially received → received → closed, with cancellation available before issue.
- **PO approval.** Requires `procurement.approve_purchaseorder`, refuses self-approval, and stamps the approver. Issued orders are the only ones that can be received against.
- **Delivery scheduling (PRC-07).** Schedules attach to a PO line and a destination, with an expected date and quantity. A line can be scheduled across several destinations and several dates. Total scheduled quantity cannot exceed the ordered quantity; every schedule carries its own destination, so one order can split between warehouse and site.
- **Goods received notes (PRC-08/09).** A GRN records date, supplier delivery reference, receiver, destination and optional document links, with lines recording delivered, accepted, rejected and damaged quantities. Rules enforced server-side:
  - accepted + rejected + damaged must equal delivered;
  - rejected and damaged quantities never count as accepted;
  - a rejection requires a reason;
  - a line cannot exceed its schedule's remaining quantity, and cumulative accepted quantity cannot exceed the ordered quantity — **over-receipt is refused outright** because Q-17b gives no tolerance;
  - receipts are refused against a closed or cancelled order.
- **Status derivation.** A PO becomes `partially_received` when any line has accepted quantity, `received` when every line is fully accepted. Closure requires a received order, records the closing user and time, and blocks all further receipts. Closing an order that is not fully received is refused.
- **Numbering (B-32).** One `DocumentSequence` row per document kind per year, incremented inside a row lock, producing `PR-`, `RFQ-`, `QT-`, `PO-` and `GRN-` numbers. No manual numbering, no gaps by design.
- **Immutability.** Approved requests, issued RFQs, submitted quotations, approved/issued orders and all GRNs reject update and delete at the API layer; corrections happen through the next document (resubmission, new quotation, closure), not by editing history.

### Deliberately not included

- **Screens.** No procurement page exists in the Angular portal; the lifecycle is reachable only through the API and Django admin.
- **Role-based permissions.** Every procurement endpoint currently requires only an authenticated session, except the three approval/selection actions, which require their specific permission. Any signed-in user can raise requests, invite suppliers, register quotations, schedule deliveries and receive goods.
- **Approval limits, routing and delegation.** D-04, D-04a, D-04b and D-18 are unresolved; the engine is deliberately permission-only. No threshold, value band or escalation time appears in code or data.
- **Stock posting and budget checks.** No stock ledger exists until Phase 5; no budget data exists until `PRJ-03` is specified.
- **Attachments on GRNs.** The field accepts document IDs, but no upload UI exists; evidence is not mandatory because Q-16 is unanswered.
- **PO amendment revisions and cancellation after issue.** Cancellation before issue exists; amendments that preserve received quantities are deferred to the amendment work package.

### Files/modules changed

- New app `backend/apps/procurement/`: `models.py` (destination, request and lines, RFQ and invitations, quotation and lines, selection, order and lines, delivery schedules, GRN and lines, document sequence), `services.py` (state machine and receipt arithmetic), `numbering.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, migration `0001_initial.py`.
- `backend/apps/procurement/tests/test_procurement.py`: 22 tests.
- `backend/config/settings/base.py`: `apps.procurement` registered.
- `backend/config/urls.py`: procurement router mounted under `/api/v1/`.
- Documentation: this report, `README.md`, `14-backlog.md`, `13-decision-register.md` (B-28…B-32).

### Database changes

One new app with one initial migration creating twelve tables and their constraints (positive quantities, non-negative prices, unique RFQ supplier, unique quotation per supplier per RFQ, unique sequence per kind and year). No existing table changed. `makemigrations --check` reports no pending changes. Nothing is seeded.

### Tests run

| Command | Result |
| --- | --- |
| `pytest` (backend) | **120 passed**, exit 0 — 98 existing + 22 new procurement tests |
| `ruff check .` | All checks passed, exit 0 |
| `ruff format --check .` | 129 files already formatted, exit 0 |
| `python manage.py check` | No issues, exit 0 (1 silenced: `axes.W002`) |
| `python manage.py makemigrations --check --dry-run` | No changes detected, exit 0 |

What the tests assert, beyond executing: a destination must be exactly one of project, warehouse or other; a warehouse destination must name the warehouse; a request needs a destination and lines, and cannot be approved by its requester; the approval action is refused without the approval permission; rejected requests need a reason and can be resubmitted; an RFQ cannot be raised from an unapproved request, cannot be issued without invited suppliers, and cannot be issued twice; a quotation from an uninvited supplier is refused; a line outside the request is refused; only a permissioned user can select a supplier, and an RFQ can be selected once; a PO cannot be raised against an unapproved request, copies the selected price, and requires the approval permission; partial delivery moves the order to `partially_received` and preserves the remainder; a full receipt moves it to `received`; a rejected quantity with a reason is recorded but does not count as accepted; over-receipt is refused; split schedules cannot exceed the ordered quantity; one order can be scheduled to a warehouse and a second location; and a closed order refuses further receipts.

### Acceptance evidence

- **Automated:** the commands above, against the live PostgreSQL instance.
- **Runtime smoke test:** `/api/v1/purchase-requests/` anonymous → `401`; `/api/v1/purchase-orders/` anonymous → `401`; `/api/v1/goods-receipts/` anonymous → `401`; `/api/v1/schema/` lists `purchase-requests`, `rfqs`, `supplier-quotes`, `supplier-selections`, `purchase-orders`, `delivery-schedules` and `goods-receipts`; `/health/` → `200`.
- **Not evidenced:** browser screens (none exist), role-based restriction (blocked by D-03), approval limits (blocked by D-04) and stock posting (Phase 5).

### Unresolved decisions

| ID | Decision | Owner | Impact if unanswered |
| --- | --- | --- | --- |
| D-04 / D-04a / D-04b | Approval limits, dual vs single approval, approver basis | Management + Finance | Approvals are permission-only; no threshold, routing or escalation exists |
| D-14 / D-15 | Direct-to-project and warehouse workflow steps | Procurement / Warehouse | Workflow follows the documented proposal; sign-off outstanding |
| D-03 | Role and permission matrix | Management | Any authenticated user can operate procurement; only approvals and selection are gated |
| D-17 / D-18 | Record visibility and delegation | Management | All buyers see all requests; no delegation |
| Q-13 | Direct PO without a request | Procurement | Not implemented; every PO needs an approved request |
| Q-15 | One PO to warehouse and project | Procurement | Supported by multiple schedules; the business rule on whether it should be allowed is unconfirmed |
| Q-16 | Receiving evidence and receivers | Warehouse / Projects | Receiver is a user reference; evidence is optional |
| Q-17b | Over-delivery tolerance | Procurement | Over-receipt is refused outright |
| Q-12 | When multiple quotations are mandatory | Procurement | RFQ is available but never compulsory; a PO can be raised from a single quote |
| Q-24 | Tax codes | Accountant | PO lines carry no tax code field beyond free text |

### Risks and limitations

| Risk | Severity | Mitigation / workaround |
| --- | --- | --- |
| Any authenticated user can raise, quote, schedule and receive outside the gated approval actions | High | Permissions are data (`procurement.approve_purchaserequest`, `approve_purchaseorder`, `select_supplier`); W4 can map them to roles without code changes |
| No approval limits means a permissioned approver can approve any value | High | Deliberate: inventing a threshold would be policy. D-04 must close before production use |
| Goods receipt records acceptance but does not post stock | High | Phase 5 inventory ledger; until then accepted quantities exist only on the GRN |
| No budget or project-budget check exists | Medium | `PRJ-03` budgets unspecified; requests carry project and cost centre for later enforcement |
| Over-receipt is refused with no tolerance | Medium | Conservative default; Q-17b can add a tolerance without schema change |
| Receipts can be recorded by any authenticated user, with no receiver signature or mandatory evidence | Medium | Q-16 unanswered; evidence fields exist and are optional |
| PO amendments and post-issue cancellation are not implemented | Medium | Amendment work package; issued orders are immutable by design |
| Direct-PO pathway is absent | Low | Q-13 unanswered; every PO references an approved request, which is the stricter control |
| No screens: procurement is API/admin only | Medium | Portal screens are a separate work package |
| Sequence rows are locked per document kind, so numbering serialises under concurrency | Low | Correctness over throughput; acceptable at TMD volumes |

### Recommendation

Ready for review as a **backend procurement lifecycle**, not as a production-ready module. Every state transition, permission gate and receipt rule is enforced server-side and covered by tests, and no approval limit, tolerance or tax rate has been invented. It should not be used by procurement staff until W4 permissions, D-04 approval policy and portal screens exist, and until Phase 5 gives accepted receipts a stock ledger to post into.

### Next phase proposal

Close Phase 2 W4–W9 once G1 is signed, so procurement actions can be permissioned and audited; then Phase 5 inventory, which consumes the GRN accepted quantities. Phase 6 posting remains blocked by D-05.

---

## Addendum — 11 November 2026 (session 2)

The procurement workflow is now interactive end to end: RFQ creation and issue, invitations, quotations with lines, selection, manual and selection-generated purchase orders, draft amendments with revision numbers, delivery schedules, and receiving with accepted/rejected/damaged quantities. Purchase requests can be edited while draft. The earlier "screens outstanding" gap is closed.

Still outstanding: permission-only approval because D-04 thresholds are unsigned, three-way match (which belongs with Phase 7 accounts payable), supplier returns, and the role matrix that grants approval permissions. The module remains **PARTIAL**.

## Rules applied to this report

- No financial feature is reported as production-ready; none was built.
- "Implemented" means code, tests and documentation together — not a page that renders.
- No real company data, credentials or personal data appear here; all test data is synthetic.
