# UI/UX Acceptance Report — 12 November 2026

**Scope:** Dashboard completion, shared interaction polish and responsive review across the major
business modules.  
**Environment:** Staging, synthetic data, Finance Controller account (`controller@staging.tmd.local`).  
**Decision:** Accepted for staging demonstration and internal review. Not accepted for production
until the financial and security blockers in the financial workflow register are closed.

## 1. Dashboard completion

The dashboard now presents the management view from authorised backend data. No figure is
hard-coded, calculated in the browser or substituted when a source is missing.

| Requirement | Implementation |
| --- | --- |
| Financial overview cards | Six cards from approved invoice, supplier-payment and customer-receipt sources. Cards expose basis text, record count, test/recorded state and an empty state instead of a false zero. |
| Outstanding invoices and overdue balances | Outstanding customer/supplier balances and overdue/due supplier balances are separated. Figures are document balances, not posted ledger totals, and say so. |
| Pending approvals | Permission-filtered approval queue covering invoices, payments, procurement, journals, bank reconciliation and project budgets. Zero-count items are omitted. |
| Procurement activity | Open purchase orders, open order value, overdue deliveries, requests awaiting approval and receipts in the selected period. The five latest orders are listed with status and value. |
| Recent company activity | Authorised audit events. Finance/management views are no longer restricted to finance events; specialist focuses retain their scoped activity. |
| Project performance | Active/on-hold project position with approved budget, actual cost, open commitments, available budget and utilisation. Project access follows the existing assigned-project rule. |
| Role-specific quick actions | Actions are returned only when the signed-in role holds the relevant create/import permission. |
| Access indicators | Every module is shown. The dashboard marks **Restricted**, **View only**, **Limited actions** or no badge for open/full access. The workspace and administration pages retain their detailed access panels. |

New backend fields: `procurement_activity`, `project_performance`, and `module_access[].access`.

## 2. Shared UI changes

### Brand and controls

- Material's default azure primary has been replaced with the TMD navy for buttons, focus states and
  selection controls. Gold remains the accent for active tabs and attention states.
- The missing `--tmd-surface`, `--tmd-border`, `--tmd-text`, `--tmd-accent` and
  `--tmd-accent-dark` tokens are now defined. This repairs Administration panels that previously
  referenced undefined colours.
- Dialog titles, content, spacing and action bars are standardised globally. Dialog actions are
  separated from the content and remain visible while long forms scroll.

### Tables and row actions

- Row actions now use one compact outlined style with consistent height and no mid-label wrapping.
- View and preview actions sit above workflow actions; **Post to ledger** is the only filled primary
  row action.
- The action column is sticky on narrow screens, so actions remain available while the data columns
  scroll.
- Table scrollbars are explicitly visible and styled. Page-level horizontal scrolling is suppressed
  so only the table or tab row scrolls.

### Tabs and responsive layout

- Module and report tabs wrap below 960 px rather than hiding their final tabs.
- Panels, metric grids, project cards, procurement lists and dialog forms reflow to one or two
  columns on narrow viewports.
- Long project and procurement labels truncate only where the full value remains available in the
  record; headings and metric labels wrap instead of overflowing.

### Style budget

The dashboard stylesheet was divided into three scoped files by responsibility:

- `dashboard.component.scss` — page layout, header, period controls and shared section headings.
- `dashboard-cards.scss` — financial, status, procurement and project-performance cards.
- `dashboard-activity.scss` — approval queues, activity, quick actions and module cards.

The 6 kB component-style warning is resolved by this refactor. The production budget was not
increased.

## 3. Module review

| Module | Result | Notes |
| --- | --- | --- |
| Dashboard | Updated and verified | Complete management sections, role-aware access states, no invented values. |
| Accounting | Pass with minor limitation | Shared table actions and brand controls applied. Wide tables scroll with sticky actions. No accounting-policy changes. |
| Invoicing | Updated and verified | Action tray is compact and stays visible; posting remains disabled in staging. |
| Procurement | Updated and verified | Brand primary, wrapped tabs, sticky actions. Procurement activity is also summarised on the dashboard. |
| Inventory | Updated and verified | Wrapped tabs expose all sections; balances remain readable and actions stay visible. |
| Banking | Pass with minor limitation | Tabs wrap and table scrolling is explicit. Wide statement columns still require horizontal scroll. |
| Projects | Pass with minor limitation | Project dashboard, budgets and costing remain intact. Wide tables require horizontal scroll on narrow screens. |
| Reports | Updated and verified | Report tabs wrap; export controls and print layout preserved. |
| Administration | Restricted state verified | The Finance Controller sees the proper restricted page. Missing surface/border tokens were repaired for administrators. |
| Master data | Pass | Shared workspace table and action changes apply; page renders with no document overflow. |
| Services | Pass | Workspace shell, tabs and table actions render correctly. |
| Leasing | Pass | Equipment register and tabs render correctly. |

Dolibarr and Odoo were used only as usability references for dense ERP tables, compact status chips,
role-aware landing pages and consistent action placement. No branding, layout or copy was copied.

## 4. Evidence

Screenshots are viewport captures from the live local staging portal at approximately 877 CSS pixels.
The browser tool could not complete full-page captures, so wide pages are represented by their
first screen and section-specific captures.

| Area | Before | After |
| --- | --- | --- |
| Dashboard overview | [`before`](evidence/uiux/before-dashboard-2026-11-12.png) | [`after`](evidence/uiux/after-dashboard-overview-2026-11-12.png) |
| Dashboard procurement and projects | — | [`after`](evidence/uiux/after-dashboard-procurement-final-2026-11-12.png) |
| Dashboard access indicators | — | [`after`](evidence/uiux/after-dashboard-access-2026-11-12.png) |
| Accounting | [`before`](evidence/uiux/before-accounting-2026-11-12.png) | [`after`](evidence/uiux/after-accounting-final-2026-11-12.png) |
| Invoicing | [`before`](evidence/uiux/before-invoicing-2026-11-12.png) | [`after`](evidence/uiux/after-invoicing-sticky-actions-2026-11-12.png) |
| Procurement | [`before`](evidence/uiux/before-procurement-2026-11-12.png) | [`after`](evidence/uiux/after-procurement-2026-11-12.png) |
| Inventory | [`before`](evidence/uiux/before-inventory-2026-11-12.png) | [`after`](evidence/uiux/after-inventory-final-2026-11-12.png) |
| Banking | [`before`](evidence/uiux/before-banking-2026-11-12.png) | [`after`](evidence/uiux/after-banking-scrollbar-2026-11-12.png) |
| Projects | [`before`](evidence/uiux/before-projects-2026-11-12.png) | [`after`](evidence/uiux/after-projects-2026-11-12.png) |
| Restricted access | [`before`](evidence/uiux/before-restricted-access-2026-11-12.png) | [`after`](evidence/uiux/after-restricted-access-2026-11-12.png) |
| Reports | — | [`after`](evidence/uiux/after-reports-final-2026-11-12.png) |

## 5. Verification

| Check | Result |
| --- | --- |
| Backend suite | **325 passed** |
| Frontend suite | **54 passed** |
| Frontend lint | Passed |
| Production build | Passed |
| Component-style budget | **No warning** |
| Django system check | Passed |
| Migration drift | None |
| Ruff | Passed |
| Staging `test_mode` | `True` |
| `can_issue` | `False` |
| `activated_at` | `None` |

## 6. Remaining limitations

- The browser proof was captured at one narrow desktop viewport. Tablet touch, phone browser,
  screen-reader and keyboard-only acceptance were not exercised.
- The unrestricted Administration users/roles forms were not opened because the test account is
  not an administrator; their missing-token repair was verified by code review and the build, not
  by an administrator screenshot.
- Wide tables still scroll horizontally; the action column stays fixed, but some intermediate
  columns are off-screen at the narrow viewport.
- Dashboard project performance is limited to six active/on-hold projects.
- Access states are capability-derived labels, not a substitute for opening the module and checking
  its own finer-grained controls.
- No production data, production account, NRS submission or live payment execution was used.
