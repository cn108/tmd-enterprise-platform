# Master Data Workspace (MASTER_DATA_V2)

**Date:** 13 November 2026

**Routes:** `/master-data` → `/master-data/suppliers`, plus 31 further entity routes

**Status:** implemented behind a default-off feature flag; staging data only

## What changed

The master-data route is now a dedicated record workspace rather than a dashboard-style page. It contains:

- page header with `Master Data › {Entity}`, record count chip and last-updated timestamp;
- sticky toolbar with debounced server search, entity tabs, removable filter chips, export, selection control and `+ New {Entity}`;
- 48 px table rows with sticky header, sticky checkbox/ID/name columns and pinned actions column;
- CDK virtual scrolling above 500 rows, with normal semantic rows for paginated pages;
- 400 px slide-in record panel with read-only detail, activity timestamps, inline create/edit form, validation and soft-deactivation;
- fixed bulk-actions bar for export, duplicate-merge placeholder, deactivation and clear;
- skeleton, empty and retryable error states;
- pagination with current range, page buttons, jump input and 25/50/100 page size.

All **32 registers** in the master-data module are available in V2: the four primary registers plus warehouses, projects, supplier categories, contacts, addresses, tax registrations, supplier bank accounts, bank changes, compliance documents, document categories, documents, product categories, units of measure, manufacturers, item prices, specifications, batches, serial numbers, certificates, storage locations, departments, cost centres, destinations, project locations, customer contracts, contract revisions, project budgets and milestones.

No KPI, chart, pending-action, quick-action or promo widget renders under the new master-data workspace. The flag-off fallback remains the existing generic workspace so UAT can compare the old page.

## Feature flag and routing

`MASTER_DATA_V2` is `false` by default. The explicit preview URL is `?layout=v2`; it is remembered for the browser session so sidebar/tab navigation stays in the new workspace. `?layout=legacy` clears the preview and pins the old workspace. Direct `/master-data` loads the legacy page until the flag is enabled.

Routes are split so each entity has its own title, breadcrumb and back/forward history. The route table is generated from one entity list, so adding a register cannot silently create a tab without a URL:

| Route | Entity | Endpoint |
|---|---|---|
| `/master-data/suppliers` | Supplier Registry | `/api/v1/suppliers/` |
| `/master-data/customers` | Customer Directory | `/api/v1/customers/` |
| `/master-data/products` | Product Catalogue | `/api/v1/catalogue-items/` |
| `/master-data/tax-rates` | Tax Rate Register | `/api/v1/governance/tax-configuration/` |
| `/master-data/warehouses` | Warehouses | `/api/v1/warehouses/` |
| `/master-data/projects` | Projects | `/api/v1/projects/` |
| `/master-data/supplier-categories` | Supplier Categories | `/api/v1/supplier-categories/` |
| `/master-data/contacts` | Contacts | `/api/v1/contacts/` |
| `/master-data/addresses` | Addresses | `/api/v1/addresses/` |
| `/master-data/tax-registrations` | Tax Registrations | `/api/v1/tax-registrations/` |
| `/master-data/supplier-bank` | Supplier Bank Accounts | `/api/v1/bank-accounts/` |
| `/master-data/bank-changes` | Bank Changes | `/api/v1/bank-account-change-requests/` |
| `/master-data/compliance` | Compliance Documents | `/api/v1/compliance-documents/` |
| `/master-data/document-categories` | Document Categories | `/api/v1/document-categories/` |
| `/master-data/documents` | Documents | `/api/v1/documents/` |
| `/master-data/product-categories` | Product Categories | `/api/v1/product-categories/` |
| `/master-data/units` | Units of Measure | `/api/v1/units-of-measure/` |
| `/master-data/manufacturers` | Manufacturers | `/api/v1/manufacturers/` |
| `/master-data/prices` | Item Prices | `/api/v1/item-prices/` |
| `/master-data/specifications` | Specifications | `/api/v1/technical-specifications/` |
| `/master-data/batches` | Batches | `/api/v1/item-batches/` |
| `/master-data/serials` | Serial Numbers | `/api/v1/serial-numbers/` |
| `/master-data/certificates` | Certificates | `/api/v1/certificates/` |
| `/master-data/storage-locations` | Storage Locations | `/api/v1/storage-locations/` |
| `/master-data/departments` | Departments | `/api/v1/departments/` |
| `/master-data/cost-centres` | Cost Centres | `/api/v1/cost-centres/` |
| `/master-data/destinations` | Destinations | `/api/v1/destinations/` |
| `/master-data/project-locations` | Project Locations | `/api/v1/project-locations/` |
| `/master-data/contracts` | Customer Contracts | `/api/v1/customer-contracts/` |
| `/master-data/contract-revisions` | Contract Revisions | `/api/v1/contract-revisions/` |
| `/master-data/budgets` | Project Budgets | `/api/v1/project-budgets/` |
| `/master-data/milestones` | Milestones | `/api/v1/project-milestones/` |

## API contract

The workspace sends `page`, `pageSize`, `search`, `sort`, `order` and flat filter query parameters. The API now accepts the camel-case `pageSize` alias with the same 100-row cap, and the new safe `SortOrderFilter` accepts `sort`/`order` only for concrete model fields. Existing `page_size` and `ordering` clients are unchanged.

Server filters verified:

- suppliers: `is_active`;
- customers: `is_active`, `credit_hold`;
- products: `is_active`, `kind`;
- tax rates: `review_status`;
- projects: `status`;
- bank changes: `status`;
- project budgets: `status`;
- every deactivatable register: `is_active`.

Search was enabled for the registers whose legacy tab previously disabled it: contacts, addresses, tax registrations, supplier bank accounts, bank changes, compliance documents, item prices, specifications, batches, serial numbers, certificates, destinations, project locations and contract revisions. A search that does not match now returns a server-filtered empty page instead of silently showing every record.

Supplier rows now expose read-only `tin` and `region` fields from the active TIN registration and primary address. Their querysets prefetch those relations to avoid per-row queries. No supplier or customer data was seeded or invented; empty TIN/region values remain visible as `—`.

Network evidence from the live portal:

```
GET /api/v1/suppliers/?page=1&pageSize=25&sort=updated_at&order=desc
GET /api/v1/suppliers/?page=1&pageSize=25&sort=updated_at&order=desc&is_active=true
GET /api/v1/customers/?page=1&pageSize=25&sort=updated_at&order=desc
GET /api/v1/catalogue-items/?page=1&pageSize=25&sort=updated_at&order=desc
GET /api/v1/governance/tax-configuration/?page=1&pageSize=25&sort=updated_at&order=desc
```

## Verification

| Check | Result |
|---|---|
| Backend tests | **340 passed** |
| Backend lint | `ruff check .` passed |
| Django check / migration drift | No issues; no changes detected |
| Frontend tests | **67 passed** |
| Frontend lint | Passed |
| Production build | Passed, no component-style budget warnings |
| axe-core 4.10.2 | **0 violations** at 1366 and 390, including the open detail panel |
| Register coverage | Configuration test asserts 32 unique routes, 32 unique endpoints and a pinned identity column for every register |
| Keyboard | Arrow Up/Down moves row focus; Enter opens the panel; Escape closes; focus returns to the row |
| Focus trap | Panel traps focus while open |
| Virtualisation | 2,000 in-memory rows rendered 14 DOM rows initially and 12 at the end; jump reached mock rows 1988–1999 |
| CLS | **0.0000** on a 390 px load after the 32-register nav change (buffered layout-shift observer) |

axe leaves only `incomplete` checks for symbolic glyphs (`▼`, `⋯`) and the floating Freebuff badge; there are no failing nodes.

### Responsive measurements

| Viewport | Document scroll width | Sidebar | Table behaviour |
|---|---:|---:|---|
| 1920×1080 | 1920 | 260 px | fits, pinned actions |
| 1366×768 | 1366 | 260 px | fits, pinned actions |
| 1024×768 | 1024 | 76 px | horizontal scroll inside card, pinned actions |
| 768×1024 | 768 | 76 px | horizontal scroll inside card, pinned actions |
| 390×844 | 373 | drawer | horizontal scroll inside card, pinned actions; panel is full width |

No page-level horizontal overflow was found. On mobile the table header was moved to `top: 0` inside its own scroll container so it no longer overlaps the first row.

With 32 registers the tabs wrap in two rows at 1920 and four at 1366. Below 640 px the tab strip becomes a horizontally scrollable, keyboard-focusable row and scrolls the active tab into view; this avoids a 300 px navigation block pushing the table below the fold.

## States and actions

- Search is debounced by 300 ms and always hits the server.
- Filter chips are removable and re-query the server.
- Sorting is server-side with visible direction arrows and an aria-live announcement.
- Bulk selection shows the fixed bar; deactivation opens a confirmation modal stating the count; `Merge duplicates` is disabled because no server-side merge operation exists yet.
- Create/edit uses the panel form; required-field validation blocks the request; server field errors map beside controls.
- Bank-change approve/reject and project-budget approve actions use the register's configured permission, status and reason rules through the same panel.
- Document creation uses multipart form data and its file control; the browser never sends a fake file path.
- Deactivation is a soft `is_active=false` patch; no delete endpoint is used.
- Empty state renders at mobile width, and the footer reads `No records` rather than `Showing 0–0 of 0`.
- Loading uses skeleton rows rather than a spinner.

## Evidence

After (five required breakpoints):

- `docs/reports/evidence/master-data-v2/master-data-v2-1920x1080-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/master-data-v2-1366x768-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/master-data-v2-1024x768-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/master-data-v2-768x1024-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/master-data-v2-390x844-2026-11-13.png`

Before (legacy workspace):

- `docs/reports/evidence/master-data-v2/before-master-data-1920x1080-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/before-master-data-1366x768-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/before-master-data-1024x768-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/before-master-data-768x1024-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/before-master-data-390x844-2026-11-13.png`

Additional states:

- `docs/reports/evidence/master-data-v2/master-data-v2-panel-390-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/master-data-v2-empty-390-2026-11-13.png`
- `docs/reports/evidence/master-data-v2/master-data-v2-nav-390-2026-11-13.png`

The screenshot tool sometimes crops/scales wide captures; the DOM measurements above are authoritative for overflow and pinned-column checks.

## Limitations / not claimed

- **TTI and 60 fps were not measured.** The current dev page reached `loadEnd` in 119 ms, but TTI needs a production Lighthouse trace at 1,000 records. The browser tab throttles background `requestAnimationFrame`, so an honest frame-timing result was not available. Virtualisation was verified by DOM count and a bottom jump.
- **Merge duplicates** has no reviewed backend operation and stays visibly disabled rather than faking a merge.
- **Linked documents** are not aggregated on these list records; the panel says so instead of inventing links.
- **Budget lines** are not edited in the V2 panel yet. A budget header can be created and metadata edited, but line-level budget authoring remains in the legacy register until the line editor is migrated.
- **TIN/Region** are blank for staging suppliers that have no tax registration or address; the fields are real read-only API projections.
- Manual screen-reader sign-off and memory profiling on teardown remain for TMD UAT.
- The repo-wide `ruff format --check` baseline still reports 39 pre-existing unformatted files; no unrelated file was reformatted.