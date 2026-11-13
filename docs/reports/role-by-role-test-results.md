# Role-by-Role Test Results

**Source evidence:** [browser-role-matrix.json](evidence/adversarial/browser-role-matrix.json)  
**Roles:** 10 (from the live `role_matrix.py`, not the older example list)  
**Page visits:** 120 (10 roles × 12 workspaces)  
**Visible controls discovered:** 4,718  
**Page-level JavaScript errors:** 0

Each role signed in through the real Angular login page. For every role the test opened Dashboard, Master data, Procurement, Inventory, Accounting, Invoices, Banking, Projects, Services, Leasing, Reports and Administration. It recorded the heading, whether the Access Restricted panel appeared, row counts, controls and direct API statuses.

---

## 1. Summary

| Role | Effective permissions | Dashboard focus | Controls seen | Restricted workspaces | Direct access-admin |
|---|---:|---|---:|---|---|
| System Administrator | 623 | Management overview | 498 | None | 200 |
| Management | 142 | Management overview | 464 | None | 200 (read-only) |
| Accountant | 194 | Finance workspace | 477 | Administration | 403 |
| Finance Controller | 148 | Finance workspace | 476 | Administration | 403 |
| Finance Officer | 154 | Finance workspace | 464 | Administration | 403 |
| Procurement Officer | 158 | Procurement workspace | 475 | Banking, Administration | 403 |
| Project Manager | 172 | Project workspace | 458 | Banking, Administration | 403 |
| Storekeeper | 118 | Warehouse workspace | 477 | Banking, Administration | 403 |
| Operations / HSE | 138 | Your workspace | 466 | Invoices, Banking, Administration | 403 |
| Auditor | 132 | Finance workspace | 463 | None | 200 (read-only) |

All ten dashboards rendered the current "Welcome back" heading and the role focus chip. No dashboard displayed a JavaScript error or a 500 state.

## 2. Role detail

### System Administrator — 623 permissions

- All 12 workspaces opened without restriction.
- Access administration, roles, accounting settings, bank accounts, invoices, purchase orders, stock movements and equipment all returned 200.
- Created the most controls (498) because administrative tabs and write actions are exposed.
- Superuser status was separately verified; the party-lookup 403 in the initial probe was a real application defect (TMD-ADV-01), not a missing permission on this account.
- After the fix, `/api/v1/parties/` returns 200 for this role.

### Management — 142 permissions

- All 12 workspaces opened.
- Read access to users and roles returned 200, consistent with the intentional Management read-only administration grant.
- Creating a supplier returned 403; creating a user returned 403. Read-only administration does not grant write authority.
- The dashboard is the management overview; no financial totals were fabricated.

### Accountant — 194 permissions

- All business workspaces opened; Administration showed Access Restricted.
- Access users/roles returned 403.
- Bank accounts, supplier invoices, customer invoices, purchase orders, stock movements and equipment returned 200.
- Trial balance returned 400 without date parameters; this is a required-parameter response, not a permission failure.

### Finance Controller — 148 permissions

- Finance workspace focus; all business modules available; Administration restricted.
- Access administration returned 403.
- Invoice, bank, purchase-order and stock APIs returned 200.
- High-value approval bands and creator/approver separation were exercised through invoice/receipt tests, not by clicking every seeded Approve button.

### Finance Officer — 154 permissions

- Finance workspace focus; Administration restricted.
- Access administration returned 403.
- Read access to invoices, banking, procurement and stock data returned 200.
- Payment/receipt creation and allocation paths were covered by the invoicing integration tests.

### Procurement Officer — 158 permissions

- Procurement workspace focus.
- Banking and Administration showed Access Restricted.
- Company bank accounts returned 403; access users/roles returned 403.
- Supplier invoices and customer invoices remained readable (200); purchase orders returned 200.
- One browser console 403 was recorded for the restricted banking request; the UI correctly rendered the restriction.
- Purchase request, RFQ, quotation, purchase order and receipt transitions were covered by backend integration tests.

### Project Manager — 172 permissions

- Project workspace focus.
- Banking and Administration showed Access Restricted.
- Company bank accounts returned 403; access users/roles returned 403.
- Projects, project dashboard, profitability and cost data returned 200.
- Project cost double-counting was tested separately: commitments, receipts and stock transfers are not counted twice.

### Storekeeper — 118 permissions

- Warehouse workspace focus.
- Banking and Administration showed Access Restricted.
- Company bank accounts returned 403; access users/roles returned 403.
- Stock movements, purchase orders, equipment and invoice read APIs returned 200.
- Stock receipt, transfer, issue, return and adjustment permissions were exercised by inventory integration tests; stock balances are derived, not edited directly.

### Operations / HSE — 138 permissions

- "Your workspace" focus.
- Invoices, Banking and Administration showed Access Restricted.
- Supplier invoices and customer invoices returned 403; company bank accounts returned 403; purchase orders, stock movements and equipment returned 200.
- Two browser console 403 messages were recorded for the two restricted financial requests; the UI displayed Access Restricted and exposed no financial rows.
- Operational services, HSE and work-order paths were covered by service integration tests.

### Auditor — 132 permissions

- Finance workspace focus; no workspace showed Access Restricted.
- Read access to users and roles returned 200, consistent with the intentional read-only audit grant.
- Bank accounts, invoices, purchase orders, stock and equipment returned 200.
- Auditor could not create a supplier (403) or a purchase request; the procurement create control was disabled with permission text.

## 3. Direct API access matrix

| Endpoint | Admin | Mgmt | Accountant | Controller | Finance | Procurement | Project | Store | Operations | Auditor |
|---|---|---|---|---|---|---|---|---|---|---|
| `/access/users/` | 200 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 200 |
| `/access/roles/` | 200 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 200 |
| `/accounting-settings/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/company-bank-accounts/` | 200 | 200 | 200 | 200 | 200 | 403 | 403 | 403 | 403 | 200 |
| `/supplier-invoices/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 403 | 200 |
| `/customer-invoices/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 403 | 200 |
| `/purchase-orders/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/stock-movements/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/equipment/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/trial-balance/` | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 | 400 |

The trial-balance result is a **400 missing-date-parameter** response for all ten roles. It is not a permission denial and must not be read as one.

## 4. Segregation-of-duties findings

- A creator cannot approve their own invoice or receipt; the backend rejects it with 403/409 regardless of the UI.
- Five-million-naira invoices require two distinct approvers.
- A reconciliation cannot be approved by its preparer.
- A closed purchase order cannot receive goods.
- A posted journal cannot be posted again.
- A closed accounting period cannot be closed again.
- An approved supplier invoice cannot be edited.
- Operations, Procurement, Project and Store roles cannot see company bank accounts or access administration through the API even when they know the URL.
- Missing objects return 403 to an unauthorised role rather than 404, reducing object-enumeration leakage; the administrator receives 404.

## 5. Residual observations

- Five browser console messages across Procurement, Project, Store and Operations are the browser reporting the correct 403 for restricted modules. The page then renders Access Restricted. No data is shown and no operation succeeds.
- Disabled create controls sampled in Procurement (Auditor) and restricted modules carried permission explanations. All 37 disabled controls were counted, but their tooltips were not individually audited.
- The role matrix is described in the repository as provisional; holder names remain an operational assignment, not a code concern.
