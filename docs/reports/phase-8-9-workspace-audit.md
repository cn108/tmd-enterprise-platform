# Phase 8 and 9 workspace audit

Date: 12 November 2026

## Scope inspected

- Django settings and root URL configuration
- `apps/projects`, `apps/procurement`, `apps/inventory`, `apps/accounting`, `apps/invoicing`,
  `apps/documents`, `apps/organisation` and `apps/identity`
- Angular workspace, route and navigation configuration
- Existing backend and frontend test conventions
- Existing Stage 7A reports and activation blockers

## Existing functionality

| Area | Existing capability | Reusable integration point |
| --- | --- | --- |
| Projects | Project registration, locations, customer contracts, append-only contract revisions, versioned budgets and approval, milestones | `Project`, `CustomerContract`, `ProjectBudget`, `BudgetLine`, `ProjectMilestone` |
| Procurement | Requests, RFQs, purchase orders, receipt notes and project destinations | `Destination.project`, `PurchaseOrder`, `PurchaseOrderLine`, `GoodsReceiptLine` |
| Inventory | Append-only stock ledger, stock issues, project and cost-centre links | `StockIssue`, `StockMovement.project`, `project_issue` movement type |
| Accounting | Chart of accounts, roles, mapping, journals, posting rules, financial event outbox | `Account`, `AccountRoleMapping`, `FinancialEvent`, `PostingRule` |
| Invoicing | Supplier/customer invoices, notes, payments, allocations, NRS test state, Stage 7B gate | `SupplierInvoice`, `SupplierPayment`, `InvoiceSettings.can_issue` |
| Documents | Private uploads, checksums and links to business records | `Document`, `DocumentLink` |
| Organisation | Departments and cost centres | `Department`, `CostCentre` |
| Identity | Users, groups, permission catalogue | `User`, `access/users/` |
| Frontend | Generic API-backed workspace with pagination, filters, forms, action dialogs, permissions and tests | `workspace-config.ts`, `WorkspaceComponent`, `ResourceApi` |

## Missing Phase 8 components

- No `apps.banking` application, models, migrations, API, permissions or tests.
- No company bank account register, statement import, statement lines, matching, reconciliation,
  cash account, petty cash voucher, replenishment or transfer records.
- No statement CSV/XLSX parser, duplicate detector or matching suggestion service.
- No bank reconciliation approval workflow or reconciliation report.
- No Angular banking route, navigation entry or workspace configuration.
- No link from recorded supplier payments to a company bank account for expected bank transactions.

## Missing Phase 9 components

- Projects lack department/cost-centre defaults, project-manager assignment details, budget categories,
  revision reasons, direct cost capture, commitments, material issue reporting, profitability and
  document views.
- No services/work-order module: no service contracts, work orders, assignments, progress, checklists,
  HSE records, completion reports or customer acceptance.
- No equipment leasing module: no equipment register, rates, agreements, reservations, dispatch,
  returns, inspections, maintenance, utilisation or warning reports.
- No Angular projects, services or leasing routes, navigation entries or workspace configurations.

## Accounting decisions that remain unresolved

- Stage 7B production posting, reconciliation posting and bank execution remain blocked.
- Bank account to ledger mappings are not configured and will not be invented.
- Matching tolerances are configurable; zero is the initial exact-match baseline.
- Equipment asset classification and accounting treatment are configurable text fields with no default
  classification.
- No purchase order, receipt or project-site transfer is treated as an actual cost. Actual cost comes
  from approved supplier invoices, project stock issues and approved direct project costs.
- Revenue recognition remains unconfigured and is not calculated by the profitability report.

## Implementation sequence

1. Phase 8 banking backend, migrations, API permissions and tests.
2. Phase 8 Angular banking workspace and browser verification.
3. Phase 9 project costing, services and leasing backend, migrations, API permissions and tests.
4. Phase 9 Angular workspaces and browser verification.
5. Full backend/frontend checks, live API E2E, reports and screenshots.
