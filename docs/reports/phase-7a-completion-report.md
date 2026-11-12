# Phase 7A completion report — Accounts payable and invoice issuance

**Date:** 12 November 2026
**Stage:** 7A — development and testing only
**Status:** Implemented, browser-reviewed and tested; **not authorised to issue live invoices or post financial transactions**

## 1. Audit finding

There was no Phase 7 invoice, payment, matching, note or NRS implementation in the workspace at the start of this assignment. Phase 6 exposed provisional tax, numbering, approval and role configuration only. `invoicing` is therefore a new module; existing procurement, inventory and accounting code was reused rather than rebuilt.

## 2. Stage 7A completion matrix

| Requirement | Backend | Angular portal | Integration / controls | Tests | Status |
|---|---|---|---|---|---|
| Supplier invoice capture and management | Models, nested lines, draft edit, submit, approve, reject, cancel, PDF, supporting-document links | Supplier invoices tab with filters, detail, lines, approval actions, attachment action and PDF preview | Duplicate check, matching, approvals, audit, test-mode flag | 28 invoicing tests | Complete for Stage 7A |
| Customer invoice drafting | Models, lines, VAT calculation, submit, approve, reject, cancel, PDF | Customer invoices tab with detail, lines, approval actions and PDF preview | Sequential numbering from `NumberingScheme`; no issuance endpoint | Included | Complete for drafting only |
| Duplicate invoice detection | Normalised supplier-number uniqueness; exact and near-match candidates; override reason; check endpoint | Duplicate status and warnings in detail; number field help text | Database constraint plus service re-check at submission | Included | Complete |
| PO / receipt / invoice matching | PO-line and receipt-line links; accepted-quantity and price checks; per-line exceptions; exemption reason | Order-line and accepted-receipt-line selectors; match status and exceptions shown | Tolerance settings; no over-invoicing across submitted/approved invoices | Included | Complete for stock and exempt service invoices |
| Configurable VAT and WHT | Per-line tax treatment (taxable, zero-rated, exempt, out of scope), effective-dated tax codes, recoverable input VAT split, customer WHT and net receivable; Decimal amounts recalculated from `TaxConfiguration` | Tax treatment, recoverable-input-VAT checkbox, VAT code and WHT code on invoice lines | No rate seeded; tax codes are effective-dated and type-checked; rates still require reviewed tax configuration before activation | Included | Complete as configuration, not a tax opinion |
| Maker-checker and approvals | Shared `ApprovalRecord` engine; creator exclusion; duplicate decision refusal; ₦5m bands for invoices, notes and payments | Approve/reject actions permission-gated; approval counts displayed | Finance Controller and Management approval permissions; no controller assigned | Included | Complete for Stage 7A |
| Credit and debit notes | Supplier and customer notes, lines, submit/approve/reject/cancel, invoice balance update, PDF | Notes tab with lines and approval actions | Credit-note cap; approved notes cannot be cancelled | Included | Complete |
| Invoice PDF generation and previews | ReportLab PDFs generated on demand; test banner; legal-detail placeholders | Preview PDF button on supplier invoices, customer invoices and notes | `inline` response for preview, `download=1` for attachment | Included | Complete |
| Partial payments and allocation | Supplier payments, independent approval, recording, allocation, over-allocation guards, invoice balances | Payments tab with approval, record and allocate actions | Explicitly recording only; no bank execution; idempotency key on recording | Included | Complete for recording/allocation |
| NRS adapter behind feature flag | Submission state model, payload builder, disabled-by-default adapter, feature flag | Read-only NRS submissions tab | No network submission, credentials or endpoint; disabled response is explicit | Included | Skeleton only; Stage 7B |
| Finance Controller role | Created as a permission bundle and left unassigned | Not assignable in this work because no controller exists | No approval invented or recorded | Included | Created and unassigned |

## 3. APIs added

```
/api/v1/supplier-invoices/                  list, create, retrieve, update
/api/v1/supplier-invoices/{id}/submit/      POST
/api/v1/supplier-invoices/{id}/approve/     POST
/api/v1/supplier-invoices/{id}/reject/      POST
/api/v1/supplier-invoices/{id}/cancel/      POST
/api/v1/supplier-invoices/{id}/post/        POST — blocked by Stage 7B
/api/v1/supplier-invoices/{id}/pdf/         GET — inline; ?download=1
/api/v1/supplier-invoices/{id}/attach-document/ POST — link a private Document
/api/v1/supplier-invoices/check-duplicate/  GET
/api/v1/customer-invoices/                  list, create, retrieve, update
/api/v1/customer-invoices/{id}/submit/      POST
/api/v1/customer-invoices/{id}/approve/     POST
/api/v1/customer-invoices/{id}/reject/      POST
/api/v1/customer-invoices/{id}/cancel/      POST
/api/v1/customer-invoices/{id}/submit-nrs/  POST — disabled by flag
/api/v1/customer-invoices/{id}/pdf/         GET
/api/v1/invoice-notes/                      list, create, retrieve, update
/api/v1/invoice-notes/{id}/submit/          POST
/api/v1/invoice-notes/{id}/approve/         POST
/api/v1/invoice-notes/{id}/reject/          POST
/api/v1/invoice-notes/{id}/cancel/          POST
/api/v1/invoice-notes/{id}/pdf/             GET
/api/v1/supplier-payments/                  list, create, retrieve, update
/api/v1/supplier-payments/{id}/submit/      POST
/api/v1/supplier-payments/{id}/approve/     POST
/api/v1/supplier-payments/{id}/reject/      POST
/api/v1/supplier-payments/{id}/record/      POST — Idempotency-Key supported
/api/v1/supplier-payments/{id}/allocate/    POST
/api/v1/supplier-payments/{id}/cancel/      POST
/api/v1/invoice-settings/                   list, retrieve, partial update
/api/v1/invoice-settings/{id}/activate/     POST — Stage 7B gate
/api/v1/nrs-submissions/                    read-only list/retrieve
/api/v1/goods-receipt-lines/                read-only matching lookup
```

## 4. Controls implemented

- **Test documents:** every invoice, note and payment created while activation is absent is stamped `is_test=True`. PDFs carry “TEST DOCUMENT — NOT A TAX INVOICE” and state that no receivable or payable exists.
- **Matching:** a supplier invoice linked to a PO cannot be submitted if its line has no accepted receipt, exceeds accepted quantity, belongs to another order, or exceeds the configured price tolerance. A non-PO invoice needs a written exemption reason.
- **Duplicates:** supplier invoice numbers are normalised (punctuation and spaces removed) and unique per supplier. Near matches are flagged as suspected and need an override reason before submission; cancelled numbers remain reserved.
- **Approvals:** the shared independent-approval engine is used with ₦5,000,000 bands. The creator cannot approve; one person cannot decide twice; rejected documents stop.
- **Money:** all amounts are `Decimal`/PostgreSQL `NUMERIC`; line and document totals are rounded half-up to two decimal places. WHT is computed on the line subtotal, not on VAT — a documented assumption requiring review.
- **Tax treatment:** a line records taxable, zero-rated, exempt or out-of-scope treatment. Zero-rated, exempt and out-of-scope lines cannot carry a non-zero VAT rate. VAT and WHT codes must match their expected tax type and be effective on the invoice or tax-point date. Supplier input VAT is split into charged VAT and recoverable VAT; customer WHT is subtracted to produce net receivable.
- **Payment limits:** a payment must be recorded before allocation; allocations cannot exceed the payment or invoice balance; supplier and currency must match; allocation records are linked to both documents.
- **Idempotency:** payment recording accepts `Idempotency-Key` (or an `idempotency_key` body field), scoped to that payment, and replay returns the original result without a second state change.
- **Audit:** creation, update, document attachment, submission, approval, rejection, cancellation, recording, allocation and NRS attempts write hash-chained audit events. No API update or delete route exists for audit events; database-level append-only enforcement is not yet present.
- **Immutability:** invoices and payments have no delete route; cancellation preserves numbers. There is no endpoint that updates a posted journal.
- **Activation gate:** `test_mode` is read-only through the ordinary settings endpoint. Activation requires all ten Stage 7B checklist items, a recorded Finance Controller posting review, company legal details, a reviewed tax profile, a reviewed customer-invoice numbering scheme and an NRS environment when NRS is enabled.

## 5. Explicit limitations

1. **No ledger posting.** The `post` endpoint deliberately returns `409` before Stage 7B authorisation; no invoice journal is created.
2. **No live invoice issuance.** Customer invoices can be drafted and approved but not issued. PDFs are test documents.
3. **No payment execution.** Recording marks an externally executed payment; no bank API, transfer, file upload or execution retry exists.
4. **NRS is a skeleton.** The feature flag is off, no endpoint is configured, and no network request is made. A “queued” state would mean “awaiting adapter implementation”, not submitted to NRS.
5. **Matching covers PO/receipt stock and exempt services.** It does not implement a full three-way tolerance matrix for every procurement type, landed costs or FX.
6. **VAT/WHT rates are not seeded.** Lines calculate correctly only against a `TaxConfiguration` record supplied and reviewed by the client.
7. **Company legal details are blank.** Test PDFs show “TMD LIMITED” and do not claim to be valid tax invoices.
8. **Customer receipts, statements and ageing are Phase 8.** Customer invoices have a balance but no receipt allocation in this stage.
9. **No saved report or export layer for invoices.** The portal lists, filters and previews; it does not produce an ageing report.
10. **Browser review is manual.** The Angular invoice workspace was reviewed in Chromium at desktop width; no Playwright/browser E2E suite is committed. Mobile and tablet layouts were not reviewed.
11. **Supporting-document access is coarse.** A user who can view an invoice sees linked document titles; the attachment action validates the document exists but does not apply a per-document ACL. Document files remain private and downloads require authentication.

## 6. Verification

```
backend:   237 tests pass
frontend:  build succeeds; lint clean; 40 tests pass
live E2E:  scripts/verify-phase7a-invoicing.mjs -> 31 checks pass against Django/PostgreSQL
ruff:      clean
migrations: core.0004, invoicing.0002 and documents.0002 applied; makemigrations --check clean
seed:      apply_provisional_governance -> 10 roles; 13 approval bands; no accounts, rates or balances
```

New tests cover tax calculation and rounding, invalid/expired tax codes, zero-rated/exempt/recoverable VAT, customer WHT, read/PDF permission denial, exact and near duplicate detection, creator exclusion, dual approval at ₦5m, PO/receipt matching and over-invoicing, split receipts, approved-document edit refusal, customer invoice approval and PDF, credit/debit notes and over-credit refusal, supporting-document attachment, payment recording/idempotency/allocation across invoices, over-allocation refusal, NRS disabled, activation and posting refusal, cancellation number preservation, and the seeded Finance Controller role being unassigned.

## 7. Assumptions requiring review

- WHT is withheld on the line subtotal; VAT is calculated on the line subtotal. A tax adviser must confirm treatment, base, remittance and rounding.
- Supplier input VAT is recoverable by default; users must clear the flag for non-recoverable VAT. The default is a workflow convenience, not a tax determination.
- Per-line half-up rounding is used until D-23 is confirmed.
- `INV-YYYY-NNNNNN` remains the provisional customer-invoice numbering scheme; D-08 is not confirmed.
- Supplier-invoice internal numbers (`SI-YYYY-NNNN`) and payment/note numbers are internal traceability references, not statutory document numbers.
- Exact duplicate detection ignores punctuation and spacing; near-match detection uses supplier, total and a seven-day window.
- Service invoices without a goods receipt require a free-text exemption reason rather than an approved service acceptance record.
- Payment recording is not payment execution; bank reconciliation is out of scope.

## 8. Stage 7B

Stage 7B is **not started**. Activation is blocked independently of test results; see [`phase-7b-activation-blockers.md`](phase-7b-activation-blockers.md).
