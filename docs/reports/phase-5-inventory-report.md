## Phase: 5 — Inventory management (backend APIs)

**Date:** 11 November 2026
**Prepared by:** Build agent, for review by TMD management and the technical owner
**Status:** ready for review — **partial phase report.** The stock ledger, documents and both valuation methods are implemented and tested through the API; no screens, role-based permissions, damaged/quarantine states or accounting postings exist, so the Phase 5 exit gate is **not** met.

### Requirements addressed

`INV-01` immutable stock movements with balances derived from the ledger, `INV-03` reservations preventing overselling and issues exceeding availability, `INV-05` configurable FIFO or weighted-average valuation with a cost snapshot per movement, `INV-07` project issues recording project, cost centre and recipient, `INV-08` reorder levels and low-stock alerts, and `INV-10` negative stock refused.

**Partially addressed:** `INV-02` records item, warehouse, optional location, batch and serial, and separates on-hand, reserved and available; it does **not** maintain separate damaged, quarantined or in-transit balances — damage is a valued write-off and transferred stock is simply absent from both ends until receipt. `INV-04` records source and destination transfers and excludes dispatched stock from both warehouses, but there is no in-transit report. `INV-06` captures counted, system and variance quantities and posts an auditable movement, but posting needs the `inventory.count_stock` permission and no second approval, because D-04 is unresolved. `INV-09` supports returns from a project into a warehouse; supplier returns are not implemented.

**Not addressed:** stock valuation snapshots as a downloadable report (the API returns current valuation rows), lot-level balance tracking, batch expiry enforcement, damaged/quarantine buckets, supplier returns, and any accounting entry (D-05 blocks Phase 6).

### Implemented

- **One signed ledger (B-33).** `StockMovement` rows are append-only. Inbound movements are positive and outbound negative, and each carries a unit cost and value change. There is no balance table and no balance endpoint that accepts a write: on-hand is `SUM(quantity)` over the ledger, so a balance cannot disagree with its movements.
- **Multi-warehouse stock.** Movements, balances and valuation are grouped by warehouse, with an optional storage location. Two warehouses holding the same item keep separate quantities and values.
- **Direct receipts (RCP).** Stock received outside a purchase order records item, quantity, unit cost, optional batch/serial, supplier and date. This covers opening balances and direct purchases.
- **GRN integration.** When a Phase 4 goods receipt is posted, every accepted quantity whose delivery destination is a **warehouse** creates an inventory receipt at the PO line price. Rejected and damaged quantities never enter stock, and direct project or other-location deliveries do not affect warehouse stock. One receipt line can post at most once.
- **Reservations (B-36).** A reservation names item, warehouse, quantity and optionally a project. Available quantity is on-hand minus the remaining quantity of open reservations. Reservations can be released, and an issue can consume one; the reservation becomes `fulfilled` when fully used.
- **Project issues (ISS).** An issue records project, cost centre, recipient and notes, with per-line item, warehouse, location, quantity, batch/serial and optional reservation. Stock is costed by the configured valuation method and leaves the ledger at that cost, so project cost is recognised once at issue.
- **Transfers (TRF, B-37).** Draft transfers move between warehouses or storage locations. Dispatch costs the stock out of the source using the same valuation method and stores that cost on the line; receipt posts the same value into the destination, so value is preserved. Dispatched stock is unavailable at both ends until receipt, and a dispatched transfer cannot be cancelled.
- **Returns (RET).** Stock returns into a warehouse at a supplied unit cost, optionally linked to a project. The cost is client data; nothing is inferred.
- **Adjustments (ADJ).** An adjustment requires a reason and per-line direction. An increase requires the unit cost at which stock is added; a decrease is costed by the valuation method and cannot take available stock below zero.
- **Damaged stock (DMG, B-38).** A damage record requires a reason and writes the quantity out of available stock at its valuation cost. Damaged goods on a supplier delivery never entered stock in the first place.
- **Stock counts (CNT).** A count is created as a draft with counted quantities (optionally a unit cost for gains). Posting snapshots the system quantity, computes the variance and posts `count_gain` or `count_loss` movements. A gain with no existing stock needs a unit cost; a loss is valued by the configured method. Posted counts are immutable and cannot be posted twice.
- **Reorder alerts.** Reorder levels are per item and warehouse with a minimum and suggested reorder quantity. The alert endpoint lists levels where on-hand is at or below the minimum, with reserved, available and shortfall quantities.
- **Valuation (B-34, B-35).** `InventoryPolicy` records FIFO or weighted average, who recorded it and when. **No method is seeded:** until one is recorded, issues and the valuation report are refused, because D-06/Q-18 is unsigned. FIFO consumes dated cost layers oldest-first and records which layers each issue consumed; weighted average costs out at the running value divided by the running quantity. The method cannot change once any movement exists, because that would restate costs already reported.
- **Numbering.** `RCP-`, `TRF-`, `ISS-`, `RET-`, `ADJ-`, `DMG-`, `CNT-` documents and `SM-` movements use the shared locked sequence.
- **Permissions (B-39).** Writes are gated on Django permissions: `inventory.receive_stock`, `transfer_stock`, `issue_stock`, `return_stock`, `adjust_stock`, `write_off_stock`, `count_stock`, `reserve_stock` and `set_valuation_method`. They are data, so W4 can map them to roles without code changes.

### Deliberately not included

- **Screens.** No inventory page exists in the Angular portal; the API and Django admin are the only surfaces.
- **Roles and record visibility.** W4/W5 remain blocked by D-03/D-17. The action permissions above must be granted by hand.
- **Damaged, quarantined and in-transit buckets.** Damage is a write-off, and transfers do not expose an in-transit balance. Adding buckets changes the balance model and needs a business decision on what each state means.
- **Stock-count approval workflow.** Posting is permissioned but not maker-checked; D-04 must decide whether a count needs a second approver.
- **Supplier returns and purchase-return documents.** Project returns exist; supplier returns need a procurement decision (Q-20c/Q-21).
- **Batch/serial capture on GRNs.** The ledger and issue/transfer/count documents accept batches and serials, but Phase 4 GRN lines do not capture them; Q-17 is unanswered and traceability flags default to off.
- **Accounting postings.** Issues and receipts carry cost and value, but nothing posts to a ledger; Phase 6 is blocked by D-05.
- **Concurrent-issue test.** Posting locks the item row, which serialises movements per item, but no simultaneous-thread test was run.

### Files/modules changed

- New app `backend/apps/inventory/`: `models.py` (policy, signed movements, FIFO layers and consumptions, reservations, receipts, transfers, issues, returns, adjustments, damage, counts, reorder levels), `services.py`, `serializers.py`, `views.py`, `urls.py`, `apps.py`, migration `0001_initial.py`.
- `backend/apps/inventory/tests/test_inventory.py`: 31 tests.
- `backend/apps/procurement/services.py`: accepted warehouse GRN quantities now post into the inventory ledger.
- `backend/config/settings/base.py`: `apps.inventory` registered.
- `backend/config/urls.py`: inventory router mounted under `/api/v1/`.
- Documentation: this report, `README.md`, `14-backlog.md`, `13-decision-register.md` (B-33…B-39).

### Database changes

One new app with one initial migration creating twenty tables and their constraints (signed movement non-zero, layer bounds, reservation bounds, positive line quantities, unique reorder level per item/warehouse, unique item per count, one movement per GRN line). No existing table changed. `makemigrations --check` reports no pending changes. Nothing is seeded: no valuation method, reorder level, cost, quantity or warehouse.

### Tests run

| Command | Result |
| --- | --- |
| `pytest` (backend) | **151 passed**, exit 0 — 120 existing + 31 new inventory tests |
| `ruff check .` | All checks passed, exit 0 |
| `ruff format --check .` | 140 files already formatted, exit 0 |
| `python manage.py check` | No issues, exit 0 (1 silenced: `axes.W002`) |
| `python manage.py makemigrations --check --dry-run` | No changes detected, exit 0 |

What the tests assert, beyond executing: a receipt posts a signed movement and a derived balance; movements are read-only and balances have no write route; warehouses keep separate balances; a reservation reduces availability without moving stock and can be released; over-reserving is refused; a project issue records the project and costs the stock out; an issue consumes a reservation; issue beyond availability is refused and needs the permission; a transfer moves stock and preserves value, cannot dispatch more than available and cannot be received twice; returns add stock at the supplied cost; an adjustment increase needs a cost and a decrease cannot take stock negative; damage needs a reason and writes stock off at cost; a count posts its variance and cannot be posted twice or edited; a count gain with no stock needs a cost; reorder alerts fire at or below the level and levels are not deleted; FIFO consumes oldest layers and leaves the expected value; weighted average costs out at the running average; accepted warehouse GRN quantities enter the ledger at the PO price, while a direct project delivery creates no warehouse movement.

### Acceptance evidence

- **Automated:** the commands above, against the live PostgreSQL instance.
- **Runtime smoke test:** anonymous `/api/v1/stock-movements/`, `/api/v1/stock-balances/` and `/api/v1/inventory-valuation/` → `401`; `/api/v1/schema/` lists the inventory routes; `/health/` → `200`.
- **Not evidenced:** browser screens (none exist), role-based access (blocked by D-03), a real concurrent issue, and any accounting entry (Phase 6).

### Unresolved decisions

| ID | Decision | Owner | Impact if unanswered |
| --- | --- | --- | --- |
| D-06 / Q-18 | Inventory costing method and GRNI policy | Accountant | Valuation refuses to answer until a method is recorded; the recorded choice is a build setting, not an accountant sign-off |
| Q-19 | Whether negative stock can ever be allowed | Management / Warehouse | Negative stock is always refused |
| D-04 | Approval limits and maker-checker | Management + Finance | Counts and write-offs need a permission but no second approver |
| D-03 / D-17 | Roles and record visibility | Management | Action permissions must be granted by hand; every signed-in user can read all stock |
| Q-17 | Which items need batch/serial/expiry tracking | Management | Fields exist; GRN capture and enforcement are absent |
| Q-16 | Receiving evidence and receivers | Warehouse / Projects | Receipts record the acting user only |
| D-05 | Chart of accounts and posting matrix | Accountant | Inventory value never reaches a general ledger |
| Q-20c / Q-21 | Supplier returns and return authorisation | Procurement | Only project-to-warehouse returns exist |

### Risks and limitations

| Risk | Severity | Mitigation / workaround |
| --- | --- | --- |
| Valuation method is recorded by a permissioned user, not necessarily the accountant | High | The policy stores who recorded it and when; production use should wait for D-06/Q-18 and a named approver |
| No role matrix: action permissions must be assigned by hand | High | Permissions are data; W4 can map them without code changes. Until then a superuser grants them |
| Accepted stock has no accounting value until Phase 6 | High | Movements carry unit cost and value; Phase 6 will post from them |
| Damaged and quarantined stock are not separate balances | Medium | Damage writes stock off; a quarantine model needs a business definition |
| Transfers have no in-transit balance | Medium | Dispatched stock is excluded from both warehouses and visible on the transfer document |
| Counts are posted by one permissioned user, with no second approval | Medium | D-04 must decide; counts and their movements are immutable and auditable |
| GRN lines cannot capture batch/serial, so tracked items lose lot traceability on receipt | Medium | Q-17 is unanswered and tracking defaults off; issue/transfer/count documents accept lots |
| Weighted-average value is rounded to two decimal places per movement | Low | D-23 rounding policy is unresolved; the final issue consumes the remaining value exactly |
| Concurrent issues are serialised by locking the item row, not proven by a concurrent test | Medium | Add a two-thread test when the ledger is load-tested |
| No screens: inventory is API/admin only | Medium | Portal work package required before warehouse staff can use it |

### Recommendation

Ready for review as a **backend inventory ledger**, not as a production-ready warehouse module. No balance can be typed over, no valuation method is assumed, no negative stock is possible, and every quantity and value change is traceable to a document and a movement. It should not be used operationally until W4 permissions, D-06/Q-18 valuation sign-off, damaged/in-transit definitions and portal screens exist, and until Phase 6 can post the resulting value.

### Next phase proposal

Phase 6 general ledger is the natural consumer of these movements but is hard-blocked by D-05. Before then, close Phase 2 W4–W9 so inventory actions become role-scoped and auditable, and decide D-06/Q-18 so the valuation method is accountant-approved rather than merely configured.

---

## Rules applied to this report

- No financial feature is reported as production-ready; none was built.
- "Implemented" means code, tests and documentation together — not a page that renders.
- No real company data, credentials or personal data appear here; all test data is synthetic.
