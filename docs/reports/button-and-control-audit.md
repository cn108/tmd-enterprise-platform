# Button and Control Audit

**Evidence:** [browser-role-matrix.json](evidence/adversarial/browser-role-matrix.json), [browser-tab-inventory.json](evidence/adversarial/browser-tab-inventory.json), [browser-control-interactions.json](evidence/adversarial/browser-control-interactions.json)  
**Roles:** 10  
**Role-page visits:** 120  
**Administrator tab states:** 104  
**Controls discovered:** 4,718  
**Controls exercised in the safe sweep:** 466  
**Page-level JavaScript errors:** 0

---

## 1. Inventory

Across the 120 role-page visits the browser found:

| Control type | Count |
|---|---:|
| Buttons | 2,727 |
| Links | 1,792 |
| Inputs | 199 |
| Native selects | 0 |
| Disabled controls | 37 |
| **Total visible controls** | **4,718** |

Angular Material renders its selects as `mat-select` comboboxes rather than native `<select>` elements, so the native-select count is zero. They are included in the control totals through their button/combobox roles.

The administrator-only tab inventory covers **104 tab states** and **4,615 controls**:

| Module | Tab states | Controls | Rows |
|---|---:|---:|---:|
| Master data | 31 | 1,934 | 49 |
| Procurement | 8 | 277 | 10 |
| Inventory | 12 | 400 | 11 |
| Accounting | 6 | 262 | 30 |
| Invoices | 7 | 252 | 5 |
| Banking | 13 | 489 | 9 |
| Projects | 9 | 321 | 9 |
| Services | 7 | 234 | 5 |
| Leasing | 11 | 446 | 15 |
| **Total** | **104** | **4,615** | **143** |

All 104 tabs rendered a heading. Sixty-nine tab states had at least one row; the rest were legitimately empty QA datasets or report states with no qualifying records.

## 2. What was actually exercised

The safe interaction sweep re-visited all 104 tabs as System Administrator and performed only non-mutating interactions:

| Interaction | Count |
|---|---:|
| Tab switches | 104 |
| "New …" dialogs opened and cancelled | 82 |
| Tabs with no create control | 22 |
| Row "View" dialogs opened and closed | 69 |
| Sortable column headers clicked | 60 |
| **Controls exercised (including tab/cancel/close clicks)** | **466** |

Every create dialog was closed with Cancel or its Close action; no submit/save request was made. Every detail dialog was closed; no edit, deactivate, approve, reject, post, cancel or download action was clicked during this sweep. Those state-changing paths were covered by the API probes and integration tests instead, so they were not fired blindly at seeded rows.

## 3. Controls that did nothing or failed

Two groups of visible buttons were confirmed broken and fixed.

### 3.1 RFQ invitation View — fixed

On Procurement → RFQ invitations, every row offered **View**. Clicking it called `/api/v1/rfq-suppliers/{id}/`, which returned **404** because the endpoint implemented only list and create. The page showed "Something went wrong" and no detail dialog.

- Root cause: missing `RetrieveModelMixin`.
- Fix: add safe read-only retrieve with the same `procurement.view_rfqsupplier` permission.
- Regression: backend test `test_rfq_invitation_detail_is_readable`.
- Re-test: the full 104-tab sweep now opens the dialog successfully.

### 3.2 Computed report View — fixed

Six tab states exposed View but their endpoints are computed list APIs with no per-row detail route:

- Banking → Banking dashboard (`banking-summary`)
- Banking → Reconciliation report (`banking-reconciliation-report`)
- Projects → Project dashboard (`project-dashboard`)
- Projects → Profitability (`project-profitability`)
- Leasing → Utilisation (`equipment-utilisation`)
- Leasing → Availability (`equipment-availability`)

Clicking View produced 404s and error banners. The Balances tab (`stock-balances`) already returned no row id, so the generic `view()` opened its detail locally; it was still marked `detailFromRow` for consistency. Four more computed states (`banking-match-suggestions`, `banking-unmatched-transactions`, `reorder-alerts`, `equipment-warnings`) had no retrievable row id or empty data and were hardened at the same time.

- Root cause: the generic workspace always called the detail endpoint for numeric row ids, even when the list was a projection.
- Fix: `detailFromRow` resource flag opens the configured detail from the row already in memory.
- Regression: frontend unit test asserts View opens the dialog and makes **no** `/banking-summary/7/` request.
- Re-test: the sweep passes all 104 tabs with no page errors.

## 4. Create, view, sort and refresh controls

- **Create:** 82 dialogs opened across 104 tabs. The 22 remaining tabs have no create action by design (dashboards, reports, history, derived balances). In the administrator run no create button was disabled because the administrator holds all create permissions.
- **View:** 69 dialogs opened. The remaining tabs either had no rows or their row action is not a detail (for example write-off/reject actions).
- **Sort:** 60 sort clicks. Where the resource has `serverSort: false`, the UI does not render sortable headers; that is deliberate.
- **Refresh:** the Refresh button is present on every tab and was exercised through the repeated tab/page reload cycle; no stale-data or console error was observed.
- **Pagination:** Material paginator controls are present; page-size and page changes are covered by the frontend unit tests. They were not clicked on every tab during the sweep.
- **Deactivate:** confirmation logic was tested once through the browser (open, Cancel, reopen, confirm) on a QA supplier. It is not executed against seeded company records.
- **Approve/reject/post/cancel:** not clicked in bulk. The API probe verifies repeat and invalid transitions return 409/400 without changing state. Dedicated integration tests cover each lifecycle.

## 5. Disabled controls

The role matrix found **37 disabled controls**. Examples:

- Auditor procurement create button: disabled with text explaining the user lacks permission to create.
- Restricted-module create controls: rendered as a locked action with a permission tooltip.
- Paginator first/previous/next/last controls when the result set is a single page.
- "Remove" on the only line in a multi-line form.

No disabled control was expected to perform an action. The disabled state was visually distinct and did not submit a request when clicked. The tooltip/explanation was sampled on the auditor and restricted-module controls; all 37 were not individually tooltip-audited.

## 6. Controls tested by category

| Category | Coverage |
|---|---|
| Navigation links | All 12 workspaces per role (120 visits) |
| Module tabs | All 104 administrator tab states |
| Create buttons | 82 dialogs opened/cancelled |
| View buttons | 69 detail dialogs opened/closed |
| Sort headers | 60 clicks |
| Search fields | SQL-like input and no-match state tested on suppliers |
| Filters | Present on list tabs; not exhaustively changed per tab |
| Row actions | View and one deactivation confirmation path tested in browser; lifecycle actions through API/integration tests |
| Modal cancel/discard | Create dialogs and unsaved-change discard tested |
| File upload | `.exe` rejection tested with a real file chooser |
| Pagination | Unit-tested; not clicked on every tab |
| Downloads/PDF | PDF permission tested at API level; report CSV download covered by UAT test |

## 7. Conclusion

The UI does not contain a known decorative or misleading control in the paths exercised after the fixes. The two families of dead View buttons were real defects and are corrected. The remaining controls either have no create action by design, are disabled with an explanation, or are destructive lifecycle actions that were verified safely through API-level state-transition tests rather than mass clicking.

The honest limitation is coverage: **466 deliberate interactions** across 104 tabs is not the same as clicking all 4,718 discovered controls, because the discovered count repeats navigation and row controls across ten roles and many rows. No claim of 100% click coverage is made.
