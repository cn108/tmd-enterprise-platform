## Phase: 3 — Master data (backend APIs)

**Date:** 11 November 2026
**Prepared by:** Build agent, for review by TMD management and the technical owner
**Status:** ready for review — **partial phase report.** Master-data APIs are delivered; no screens, no per-role permissions and no append-only audit trail exist yet, so the Phase 3 exit gate is **not** met.

### Requirements addressed

`MAS-01` (customers), `MAS-02` (suppliers, bank details, compliance documents), `MAS-03` (catalogue, price history), `MAS-06` (warehouses and locations), `MAS-08` (no deletion of master data), `PRJ-01` (projects), `PRJ-02` (contracts and revisions), `PRJ-04` (cost centres) and `DOC-01`/`DOC-02` (private storage, authenticated download, attachments).

**Partially addressed:** `MAS-04` models units of measure and optional conversion, but no conversion data is seeded and Q-14 is unanswered. `MAS-07` models categories and retention metadata, but category-level access rules need roles (W4). `PRJ-04` provides cost centres; using them on PO lines, issues and invoices is Phase 4 onward.

**Not addressed:** `MAS-05` tax codes (Q-24 unresolved; catalogue items carry a free-text classification only), `PRJ-03` budgets and budget lines, `PRJ-05` milestones, `PRJ-06` closure enforcement, `PRJ-07` project cost views, `DOC-03` generated PDFs.

### Implemented

- **Parties (B-19):** one `Party` record with supplier/customer flags, so a company can be both; contacts, addresses and tax registrations attach to the party. `Supplier` and `Customer` endpoints are separate views over the same table, so a code cannot exist twice. Supplier categories are records, not a hard-coded list; payment terms, credit limit and due-diligence status are client-supplied and nullable — no default is invented.
- **Bank details (MAS-02, B-26, B-27):** account numbers are encrypted at rest with Fernet envelope encryption; only ciphertext and the last four digits are stored, and the API never returns either the plaintext or the ciphertext. Bank accounts are **read-only** through the API and the Django admin: creating or changing one requires a `BankAccountChangeRequest` that names a reason, records the requester, and must be approved by a **different** user holding `parties.approve_bankaccountchange`. Self-approval and unpermissioned approval are refused, and decisions are written to the application log without any account number. Bank accounts are refused for parties that are not suppliers.
- **Compliance documents:** type, issuer reference, issue/expiry dates, optional document link and a verification record; expiry before issue is refused.
- **Catalogue (B-20):** one `CatalogueItem` table with `kind` (`product`/`service`), so a SKU is unique across both and price history and specifications have a single owner. Products report `is_stock_tracked`; services cannot enable batch, serial or expiry tracking.
- **Price history:** effective-dated rows, append-only (no update or delete endpoint), with overlap rejection and a non-negative amount check.
- **Technical specifications:** per-item name/value/unit rows, unique per item.
- **Traceability (B-21):** per-item `tracks_batches`/`tracks_serials`/`tracks_expiry` flags default to **off**, because Q-17 (which items need traceability) is unanswered. Batches carry manufacture/expiry dates; serial numbers can reference a batch of the same item; certificates can reference an item, batch or serial and an uploaded document.
- **Warehouses and locations (MAS-06):** warehouse records with a free-text site label because D-02 is unresolved; storage-location codes are unique per warehouse, not globally.
- **Projects and contracts (PRJ-01, PRJ-02):** projects start as draft and follow an explicit transition table (draft → active → on hold/closed, on hold → active/closed, closed terminal). Contract values, dates and terms are client data; revisions are append-only and auto-numbered.
- **Departments and cost centres (PRJ-04):** cost centres are coded records with an optional parent and optional department. No codes are seeded; the hierarchy is optional because Q-14b is unanswered. Cycles are refused.
- **Documents (B-23, DOC-01/02):** private storage with UUID filenames; checksum, size and MIME type are derived from the bytes stored, not from client claims. Uploads are refused for disallowed extensions or above the configured size. There is **no media URL route**; downloads go through an authenticated endpoint that is logged. Document bytes are immutable — updating metadata cannot replace the file.
- **Deletion policy (B-24, M-05, MAS-08):** every master-data endpoint refuses `DELETE` with `409 delete_not_permitted` and directs the caller to deactivate instead.
- **Audit columns:** every master record carries `created_by`, `updated_by`, `created_at` and `updated_at`.

### Deliberately not included

- **Screens.** The Angular portal still has only sign-in, the dashboard and sign-out. Master data is reachable through the API and Django admin only.
- **Per-role permissions and record-level visibility.** W4/W5 are blocked by D-03 and D-17, so every master-data endpoint currently requires only an authenticated session. Any signed-in user can create or edit any master record.
- **Append-only audit trail.** W7 is blocked; bank-detail decisions and document downloads are written to the application log, and each bank change request permanently records its requester, reviewer and timestamps, but none of this is tamper-evident yet.

### Files/modules changed

- `backend/shared/`: new `models.py` (audited/coded bases), `serializers.py` (code normalisation before uniqueness checks), `viewsets.py` (deactivation, audit stamping, filtering).
- New apps: `apps/parties`, `apps/catalogue`, `apps/warehousing`, `apps/projects`, `apps/documents`, each with models, serializers, views, URLs, admin and tests.
- `apps/organisation`: `CostCentre` added; departments gain audit columns; serializers, views and URLs added.
- `backend/config/`: settings register the new apps and document limits; root URLs mount the routers.
- `backend/conftest.py`: shared API fixtures.
- Documentation: this report, `README.md`, `14-backlog.md` status, `13-decision-register.md` (B-19…B-25).

### Database changes

Six new apps, one initial migration each, plus `organisation.0002` adding cost centres and department audit columns. No financial table, no stock ledger, no journal. `makemigrations --check` reports no pending changes. Nothing is seeded: no categories, units, cost codes, suppliers, warehouses or projects.

### Tests run

| Command | Result |
| --- | --- |
| `pytest` (backend) | **98 passed**, exit 0 — 42 existing + 56 new master-data tests |
| `ruff check .` | All checks passed, exit 0 |
| `ruff format --check .` | 114 files already formatted, exit 0 |
| `python manage.py check` | No issues, exit 0 (1 silenced: `axes.W002`) |
| `python manage.py makemigrations --check --dry-run` | No changes detected, exit 0 |

New tests by module: parties 19, catalogue 12, warehousing 4, projects 8, documents 8, organisation 5.

What they assert, beyond executing: duplicate codes are a 400 even when submitted in a different case; supplier and customer codes share one namespace; bank numbers never appear in responses; tax registrations are unique per party/scheme/number; expiry before issue/manufacture is refused; SKUs cannot collide across products and services; service items cannot track stock; price periods cannot overlap while consecutive periods are accepted; price rows cannot be updated or deleted; serial/batch uniqueness is per item; a batch from another item is refused; certificates need a target; location codes repeat across warehouses but not within one; project lifecycle transitions are enforced and illegal ones refused; contract revisions number 1, 2 and are immutable; uploads are checksummed, size/type limited, non-replaceable and downloadable only when authenticated; no media URL is routed; document links are unique; every delete is refused with 409. For bank details: direct writes are 405; a change request stores ciphertext rather than plaintext; approval by a second permissioned user creates or updates the account while preserving the masked value; self-approval and approval without the permission are refused; rejection leaves the data untouched; decisions are logged without account numbers; and requesters see only their own requests.

### Acceptance evidence

- **Automated:** the commands above, against the live PostgreSQL instance.
- **Runtime smoke test:** `/health/` → `200`; anonymous `GET /api/v1/suppliers/` → `401` with `error.code = not_authenticated`; anonymous `POST /api/v1/suppliers/` → `401`; `/api/v1/schema/` lists `/suppliers/`, `/customers/`, `/catalogue-items/`, `/warehouses/`, `/projects/`, `/customer-contracts/`, `/documents/`, `/cost-centres/` and `/departments/`; `/api/v1/docs/` → `200`.
- **Not evidenced:** browser screens (none exist), role-based restriction (blocked), and audit persistence (blocked).
- **Reconciliation evidence:** not applicable — no financial records exist.

### Unresolved decisions

| ID | Decision | Owner | Impact if unanswered |
| --- | --- | --- | --- |
| D-02 | Entity/office/warehouse/site structure | Management | Warehouse site is free text; no site hierarchy |
| Q-14b | Cost-code structure and hierarchy | Management / Finance | Cost centres are flat unless a parent is supplied; no rollups |
| Q-14 | Whether unit conversions are needed | Management | Conversion is modelled but unused; no factors seeded |
| Q-17 | Which items need batch/serial/expiry tracking | Management | All traceability flags default to off |
| Q-28 | Document retention periods and access rules | Management / adviser | Retention is optional per category; access rules deferred to W4 |
| Q-24 | Tax codes and treatments | Accountant | Items carry free-text classification only |
| D-03, D-04, D-17, D-18 | Roles, limits, visibility, delegation | Management | Every authenticated user can maintain all master data |
| D-10 | Hosting/storage | Management / IT | Documents use local filesystem storage |

### Risks and limitations

| Risk | Severity | Mitigation / workaround |
| --- | --- | --- |
| Any authenticated user can create or edit any master record outside bank details | High | Roles arrive in W4 (blocked by D-03); bank account changes already require the approval permission, but the rest of master data remains authenticated-only |
| Encryption key custody and rotation are untested operationally | Medium | Keys come from `BANK_ACCOUNT_ENCRYPTION_KEYS`; losing every key makes stored numbers unrecoverable, so custody needs a named owner (D-10/D-12) |
| The approval permission has to be granted by hand until W4 exists | Medium | A Django permission (`parties.approve_bankaccountchange`) is data, so W4 can map it to roles without code changes; until then an administrator assigns it |
| Uploaded files are not virus-scanned | Medium | Extension and size limits only; scanning belongs to the production hardening phase |
| Document category access rules and retention enforcement are not implemented | Medium | Categories and retention metadata exist; enforcement needs W4 and Q-28 |
| Contract revisions are recorded but never applied to the live contract | Medium | Applying a revision is an approval action in a later phase; the history is preserved now |
| Auto-numbered contract revisions can collide under concurrent writes | Low | Unique constraint rejects the second write; retry is required |
| Every delete is refused, even for unreferenced records | Low | Deliberately conservative; reference-aware deletion can be added when transactions exist |
| No screens: master data is API/admin only | Medium | A portal work package is required before business users can maintain data |
| No browser end-to-end test of document upload/download | Low | API tests cover upload, validation and download; the UI does not exist yet |

### Recommendation

Ready for review as a **backend master-data foundation**, not as a production-ready module. The schema and rules are enforced server-side, nothing is seeded or guessed, and every open decision produces a safe default rather than an assumption. It should not be handed to business users until W4 permissions and portal screens exist.

### Next phase proposal

Either close Phase 2 (W4–W9) once G1 is signed, so master data can be permissioned and audited, or begin Phase 4 procurement against these records. Phase 4 remains blocked by D-04, D-14, D-15 and Q-15…Q-20b.

---

## Addendum — 11 November 2026 (session 2)

The portal now covers the master-data surface described above: supplier categories, contacts, addresses, tax registrations, masked bank accounts and two-person changes, compliance documents, catalogue support records, storage locations, departments, cost centres, destinations, project locations, contracts and revisions, project budgets with lines and separate approval, milestones, and private document upload/download. The earlier gap "No screens: master data is API/admin only" and the missing budgets/milestones are closed.

Still outstanding: append-only audit history (W7), approved retention rules (Q-28), and the management-approved role matrix that decides who may change restricted records. The module remains **PARTIAL** under the specification's definition.

## Rules applied to this report

- No financial feature is reported as production-ready; none was built.
- "Implemented" means code, tests and documentation together — not a page that renders.
- No real company data, credentials or personal data appear here; all test data is synthetic.
