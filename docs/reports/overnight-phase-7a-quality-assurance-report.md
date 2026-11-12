# Overnight Phase 7A quality-assurance report

**Date:** 12 November 2026  
**Scope:** Accounts payable, customer invoicing, credit/debit notes, payments and NRS boundary  
**Mode:** Stage 7A test mode only — production issuance, ledger posting, bank execution and NRS submission remain disabled  
**Classification:** **PASS for Stage 7A test-mode UAT.** **NOT ACCEPTED for Stage 7B activation or production use.** No known CRITICAL or HIGH code defect remains after the fixes recorded below; policy, tax, accounting and governance blockers remain open.

## 1. Executive summary

The Phase 7A invoicing module was reviewed end to end: tax calculation and configuration, supplier and customer document lifecycles, matching, notes, payments, approvals, PDFs, supporting documents, Angular screens, permissions and failure paths.

The review found two blocking frontend defects that prevented any invoice with lines from being submitted through the portal, plus a server-side calculated-field failure and several tax, permission and presentation defects. All known CRITICAL/HIGH defects were fixed. The final state passes:

- **237 backend tests**
- **40 Angular unit tests**
- **31 live API end-to-end checks** against Django/PostgreSQL
- backend Ruff, frontend lint, production build and migration-drift checks

The browser review found no remaining console errors in the invoice workspace after the fixes, and a draft supplier invoice, its detail view, a linked private supporting document, a customer invoice detail, payments, settings and the disabled NRS view all rendered and behaved as expected.

Acceptance is deliberately limited. The Finance Controller is still unassigned; no tax rates, legal details, posting rules or opening balances have been approved; NRS has no credentials or endpoint; and posting/payment execution/activation remain blocked by design. Those are business and governance blockers, not evidence that Stage 7B is ready.

## 2. Constraints observed

- No tax rate, tax treatment, account mapping, company legal information or approval authority was invented.
- No production invoice was issued. Every document created by the application in this environment is a test document.
- No journal was posted. The posting endpoint returns a controlled conflict.
- No bank payment was executed. Recording is an explicit external-event record.
- No NRS request was sent.
- No database reset, commit, push or deployment was performed.
- Existing uncommitted work from earlier phases was preserved.
- The E2E approver account was temporarily enabled only for the live two-person approval run, then disabled again.

## 3. Work completed

### 3.1 Tax model and calculations

- Added explicit line treatments: **taxable, zero-rated, exempt and out of scope** for supplier, customer and note lines.
- Added effective-date validation for VAT and WHT codes. The code must be effective on the invoice date or the explicit tax-point date.
- Added tax-type validation: a VAT field rejects a WHT code and a WHT field rejects a VAT code.
- Added `TaxConfiguration.is_effective(on_date)`.
- Added supplier **recoverable input VAT**:
  - line `vat_recoverable`
  - line `vat_recoverable_amount`
  - invoice `vat_recoverable_total`
- Added customer **withholding tax**:
  - line `wht_tax`
  - line `wht_amount`
  - invoice `wht_total`
  - invoice `net_receivable` (balance after WHT)
- Added tax-rate range validation: rates must be between 0 and 100 percent; effective end date cannot precede the start date.
- Kept per-line and per-document money in `Decimal`, rounded half-up to two decimal places.
- Added tests for expired codes, tax-point date use, zero-rated/exempt treatment, recoverable VAT, customer WHT, rate boundaries, invalid rates and reversed effective dates.

### 3.2 Workflow and integrity

- Added model-view permission enforcement to supplier invoices, customer invoices, notes, payments, settings and NRS read/PDF views. Authentication alone is no longer sufficient to read an invoice or download its PDF.
- Added supplier-invoice supporting-document attachment through `DocumentLink` with a new `supplier_invoice` entity type, an audited `attach-document` action and a portal action.
- Added audit events for create and update actions, in addition to the existing lifecycle actions.
- Reworked payment-record idempotency so the idempotency record is checked while the payment row is locked; a replay returns the original result instead of conflicting after a concurrent request.
- Added tests for:
  - split receipts/partial deliveries
  - debit-note increase and credit-note over-credit refusal
  - one payment allocated across multiple invoices
  - approved-invoice edit refusal
  - supporting-document attachment and replay
  - PDF markup escaping
  - rate/date validation
- Confirmed cancelled numbers remain preserved and no delete route exists.

### 3.3 PDFs

- Escaped free text (company details, party names, notes and line descriptions) before insertion into PDF paragraphs, preventing markup from breaking the PDF parser or being rendered as markup.
- Added recoverable input VAT and customer WHT/net receivable to the appropriate PDF summaries.
- Changed PDF status labels to their human-readable display values.
- Validated a generated PDF directly: HTTP 200, `application/pdf`, `%PDF-1.4`, 5,271 bytes, with the expected test banner and invoice totals. The file is retained at `docs/reports/evidence/phase7a-supplier-invoice.pdf`.

### 3.4 Angular portal

- Fixed a blocking `FormArray` registration defect: line forms previously rendered `formArrayName="lines"` without adding the array to the parent form. Any invoice with lines produced Angular control errors and could not be created.
- Fixed line checkboxes being wrapped in a `mat-form-field`, which has no form-field control and raised Angular errors. The recoverable-input-VAT checkbox now renders as its own control.
- Fixed the line grid: four columns for fields, with the remove action on its own row, so quantity, unit price, tax code/treatment and WHT are not squeezed into a hidden auto column.
- Added a default `NGN` currency and made currency visibly required. Before this, a blank currency produced a server-side null-field error.
- Hid Edit for non-draft records.
- Humanised status, match status, duplicate status and payment status in both tables and detail/PDF views.
- Fixed singular/plural record counts.
- Made dialog hints use dynamic sizing so they no longer overlap the next row.
- Added a readable private-document selector label (document title rather than `#1`).
- Changed action-form submit labels to the action name instead of the generic `Create`.
- Added a frontend regression test that proves `lines` is registered on the parent form and is included in the POST body.

## 4. Defects found and disposition

| # | Severity | Defect | Evidence | Disposition |
|---|---|---|---|---|
| 1 | CRITICAL | Invoice line `FormArray` was never added to the parent form. Every line-bearing invoice threw `Cannot find control with name: 'lines'` and could not be submitted. | Browser console; `record-form.component.ts` | **Fixed.** Form array registered; regression test added. |
| 2 | CRITICAL | Line checkbox was placed inside `mat-form-field`, causing `mat-form-field must contain a MatFormFieldControl` on invoice/note forms. | Frontend test; Angular console | **Fixed.** Checkbox moved outside the form field. |
| 3 | HIGH | Supplier invoice create returned 500 when a calculated tax field arrived as NULL; the database rejected `vat_recoverable_total`. | Browser save; Django traceback | **Fixed.** Calculated fields are stripped from incoming create data, so model defaults and recalculated values apply. |
| 4 | HIGH | Read and PDF endpoints required only authentication, not the model view permission. | Security test before fix | **Fixed.** Explicit view-permission mixin across all invoice resources. |
| 5 | HIGH | Tax codes were not checked for tax type or effective date; expired codes could be used. | Tax tests before fix | **Fixed.** Type and effective-date validation at line serialization and submission. |
| 6 | HIGH | Supplier input VAT had no recoverable/non-recoverable distinction. | Tax model review | **Fixed.** Line flag, amount and invoice total added. |
| 7 | HIGH | Customer invoices had no customer WHT or net-receivable representation. | Tax model review | **Fixed.** WHT code/amount and net receivable added and tested. |
| 8 | HIGH | Tax rates could be negative or above 100%; effective end date could precede start. | Tax configuration review | **Fixed.** Serializer validation and tests added. |
| 9 | MEDIUM | Edit was offered for approved invoices even though the API rejects edits. | Browser screenshot | **Fixed.** Edit is now draft-only. |
| 10 | MEDIUM | Status labels displayed raw values (`draft`, `unmatched`, `unpaid`, `clear`) in tables/detail. | Browser screenshots | **Fixed.** Human-readable display labels in portal and PDFs. |
| 11 | MEDIUM | Record count said “1 records”. | Browser screenshot | **Fixed.** Singular/plural logic corrected. |
| 12 | MEDIUM | Dialog hints overlapped the next field on the invoice form. | `phase7a-new-supplier-invoice-form.png` | **Fixed.** Dynamic field subscript sizing. |
| 13 | MEDIUM | Line fields were squeezed into a four-column-plus-auto grid, hiding quantity in a tiny column. | Browser screenshot | **Fixed.** Four-column field grid, separate remove row. |
| 14 | MEDIUM | Free text was interpolated into PDF paragraphs without escaping. | PDF source review | **Fixed.** Escaped output and a markup-in-free-text regression test. |
| 15 | MEDIUM | Currency had no default and no visible required marker; blank currency returned a server error. | Browser save | **Fixed.** NGN default and required validation. |
| 16 | LOW | Supporting-document selector showed `#1` rather than the document title. | Browser attachment dialog | **Fixed.** Title is used as the option label. |
| 17 | LOW | Action dialogs used the generic `Create` button. | Browser attachment dialog | **Fixed.** Action label used for submit. |
| 18 | LOW | The invoice list offered “Allocate to invoice” on a payment with nothing unallocated; the server correctly rejected it. | Browser payment list | **Open UX gap.** Server guard is correct; no client-side disable. |

No known CRITICAL or HIGH defect remains open.

## 5. VAT and WHT findings

### 5.1 Implemented behaviour

- The tax-point date, when supplied, controls effective-date validation; otherwise the invoice/note date is used.
- A tax code must match the expected type (`vat` or `wht`) and be effective on that date.
- A zero-rated, exempt or out-of-scope line cannot use a non-zero VAT rate.
- Supplier VAT is calculated per line on the line subtotal. Only the recoverable portion is added to the recoverable VAT total; the full VAT remains part of the invoice total.
- Supplier WHT is summed into `wht_total` and reduces `payment_due`.
- Customer WHT is summed into `wht_total`; it does not reduce the invoice total but reduces `net_receivable` after WHT.
- Per-line rounding is half-up to two decimal places. A boundary test confirms `0.10` at `7.5%` produces `0.01` VAT and `0.11` total.
- Tax rates are not seeded by the application.

### 5.2 Tax positions that remain unapproved

These are recorded as decisions, not silently assumed:

1. **WHT base:** the application calculates WHT on the line subtotal, excluding VAT. No reviewed Nigerian tax advice in the repository confirms this for every transaction type.
2. **WHT remittance:** the application records withholding but does not model remittance, filing or a WHT payable account. Posting is disabled.
3. **Recoverable VAT default:** supplier lines default `vat_recoverable=True`. This is a workflow convenience, not a tax determination; users must clear it when input VAT is not recoverable.
4. **Tax-code review status:** Stage 7A accepts provisional tax codes on test documents. Activation checks the reviewed `TaxProfile` but does not require every `TaxConfiguration` row to be individually reviewed.
5. **Zero-rated evidence:** a zero-rated line can have a 0% VAT code or no code. The evidence required to support zero-rating is not modelled.
6. **Exempt/out-of-scope classification:** the application records the user’s treatment; it does not determine the legal classification.
7. **Rounding policy:** half-up per line is an assumption pending decision D-23.
8. **No VAT/WHT ledger:** because posting is blocked, there are no input-VAT, output-VAT or WHT journal entries to reconcile.

A tax adviser and the Finance Controller must resolve these before Stage 7B.

## 6. Workflow test results

### 6.1 Backend

Command:

```bash
cd backend
./.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider
```

Result: **237 passed**. The invoicing suite contains **28 tests**.

Coverage added or exercised includes:

- normal VAT/WHT calculations and PDF generation
- zero-rated/exempt/out-of-scope treatment
- expired and wrong-type tax codes
- tax-point date effective dating
- recoverable versus non-recoverable input VAT
- customer WHT and net receivable
- tax-rate/date boundary validation
- exact and near duplicate detection
- creator cannot approve their own document
- independent approval and dual approval at the ₦5m band
- PO/receipt matching, over-invoicing and split receipts
- approved-document edit refusal
- credit/debit notes and over-credit refusal
- payment recording idempotency and multi-invoice allocation
- over-allocation refusal
- supporting-document attachment and replay
- PDF markup escaping
- read/PDF permission denial
- cancelled number preservation
- NRS disabled
- Stage 7B posting/activation refusal
- Finance Controller remains unassigned

Ruff: clean. `makemigrations --check --dry-run`: no changes detected.

### 6.2 Frontend

Commands:

```bash
cd frontend
npm run build
npm run lint
npm test -- --watch=false
```

Results: production build succeeds, lint is clean, **40 tests passed** across 7 files. The new regression test checks that the invoice line array is registered and posted with the parent document.

### 6.3 Live API E2E

Command shape:

```bash
TMD_BASE_URL=http://127.0.0.1:8000 \
TMD_VERIFY_EMAIL=admin@tmd.local TMD_VERIFY_PASSWORD=... \
TMD_APPROVER_EMAIL=e2e.approver@tmd.local TMD_APPROVER_PASSWORD=... \
node scripts/verify-phase7a-invoicing.mjs
```

Result: **31 checks passed**. It created and approved a test supplier invoice, recorded and allocated a payment, generated a PDF, created/approved a customer invoice, and confirmed posting, activation and NRS remain blocked.

## 7. Browser review and evidence

Browser: Chromium at desktop width against `http://127.0.0.1:4200`, backed by Django at `http://127.0.0.1:8000`.

Reviewed screens:

| Screen | Result |
|---|---|
| Supplier invoices list | Renders; status/match labels humanised; draft actions differ from approved actions; `1 record`/`2 records` correct. |
| New supplier invoice | Dialog fits; currency defaults to NGN; notes and matching hints no longer overlap; line fields readable in a four-column grid; recoverable checkbox renders. |
| Supplier invoice detail | Status labels humanised; totals, recoverable VAT, WHT and payment due render; linked supporting document title appears. |
| Customer invoices list/detail | Renders; customer WHT and net receivable columns/values present; no console errors. |
| Credit/debit note form | Renders; note lines, VAT treatment and tax selector present. |
| Supplier payments | Recorded versus executed distinction visible; allocation action present. |
| Invoice settings | Test mode and NRS-disabled state visible; activation not offered in the ordinary edit path. |
| NRS submissions | Read-only; rows show `Disabled` and the explicit disabled message. |

No console errors remained in the final pass. A draft invoice created through the UI (`SI-2026-0003`, supplier number `UI-QA-2026-0001`, total `NGN 1,000.00`) was used for the final detail, attachment and PDF checks.

Evidence files:

- `docs/reports/evidence/phase7a-supplier-invoices.png` — supplier invoice list
- `docs/reports/evidence/phase7a-new-supplier-invoice-form.png` — pre-fix dialog with overlapping hints
- `docs/reports/evidence/phase7a-new-supplier-invoice-form-final.png` — corrected form
- `docs/reports/evidence/phase7a-line-fields-final.png` — final line layout and checkbox
- `docs/reports/evidence/phase7a-supplier-invoice-detail.png` — supplier detail
- `docs/reports/evidence/phase7a-supporting-document.png` — linked private document visible
- `docs/reports/evidence/phase7a-customer-invoice-detail.png` — customer WHT/net receivable presentation
- `docs/reports/evidence/phase7a-attach-document-dialog.png` — attachment dialog during opening animation (kept as a review artefact, not a final layout claim)
- `docs/reports/evidence/phase7a-supplier-invoice-pdf.png` — embedded Chromium PDF surface, which rendered blank in the capture
- `docs/reports/evidence/phase7a-supplier-invoice.pdf` — valid generated PDF used for content verification

The embedded Chromium PDF viewer returned a blank screenshot. This is a viewer/capture limitation, not a malformed response: the same URL returned `200`, `application/pdf`, `%PDF-1.4`, 5,271 bytes, and text extraction showed the test banner, supplier details, lines and totals. No claim is made that the PDF was visually reviewed inside the embedded viewer.

## 8. Security and integrity review

### 8.1 Confirmed controls

- All invoice, note, payment, settings and NRS read/PDF endpoints enforce model view permissions.
- Invoice create/edit/action permissions remain separate from read access.
- PDFs escape free text, preventing markup injection or parser failure.
- Documents are private; the attachment action stores a `DocumentLink` and does not expose a public file URL.
- Audited actions include creation, update, attachment and the full workflow lifecycle.
- Payment recording is idempotent under the payment row lock; replay returns the original result.
- No invoice or payment delete route exists.
- There is no endpoint that edits a posted journal; posted-journal immutability is enforced in the accounting module.
- Cancellation preserves the document number.
- Posting, activation, NRS and bank execution remain disabled.

### 8.2 Residual security/integrity risks

| Risk | Severity | Notes |
|---|---|---|
| Supporting-document ACL is coarse | Medium | An invoice viewer sees linked document titles; attachment checks that the document exists but not a per-document access policy. Files remain private. |
| Audit table is not database-trigger immutable | Medium | API has no update/delete route and events are hash-chained, but a database superuser could still alter rows. No append-only trigger was added. |
| Tax-code review is not enforced per row | Medium | A provisional tax code can be used on a test document; activation checks the tax profile, not every code. |
| No automated browser security regression | Low | Permission checks are covered by API tests; the browser was reviewed manually with an administrator account. |
| No rate limiting on invoice actions | Low | Existing global platform controls apply; no invoice-specific throttling was introduced. |

## 9. Remaining defects and limitations

1. No production ledger posting exists; `post` is intentionally blocked. Therefore “balanced journal” was not exercised in this stage.
2. No live invoice issuance; customer invoices remain test drafts/approved documents.
3. No bank execution or reconciliation.
4. NRS is a disabled adapter skeleton with no endpoint or credentials.
5. WHT remittance/filing is not modelled.
6. Input VAT recoverability defaults to true and needs a reviewed operating rule.
7. Tax rates, legal details, chart of accounts and posting rules remain unapproved.
8. Customer receipts, ageing and statements remain Phase 8.
9. Supporting-document attachment is implemented for supplier invoices only; customer invoices and notes do not yet have the same action.
10. The payment list can show an allocation action when nothing remains unallocated; the API rejects it, but the UI does not hide it.
11. Browser review covered desktop width only; no mobile/tablet review was performed.
12. No Playwright or equivalent browser E2E project exists; browser checks were manual.
13. The embedded Chromium PDF viewer did not render in the capture; PDF validity was checked by response headers, signature/text extraction and saved artefact.
14. Supplier-invoice totals do not use FX conversion; multi-currency payment allocation remains restricted by matching currency.

## 10. Decisions requiring the client

These were not invented:

- exact VAT/WHT rates, effective dates and tax registrations
- whether WHT is deducted from the supplier payment, who remits it and on what base
- whether input VAT is recoverable by default and who may change that flag
- whether zero-rated/exempt/out-of-scope lines require evidence or a mandatory zero-rate code
- approved customer-invoice numbering scheme and rounding policy
- approved company legal details, invoice footer and signatory
- posting rules and account-role mappings
- the named Finance Controller and independent approvers
- NRS environment, credentials, endpoint and API version

## 11. Blockers to Stage 7B

Stage 7B remains blocked independently of the passing tests:

- Finance Controller unassigned
- no approved chart of accounts or account-role mappings
- no opening trial balance, bank or inventory balances
- no reviewed VAT/WHT rates or Tax ID
- no approved numbering/rounding decision
- no company legal details
- no approved posting rules
- no recorded Finance Controller posting review
- no management go-live authorisation
- no NRS onboarding or credentials

The detailed gate list is maintained in `docs/reports/phase-7b-activation-blockers.md`.

## 12. Files changed in this QA pass

Backend:

- `backend/apps/invoicing/models.py`
- `backend/apps/invoicing/migrations/0002_tax_treatment_and_wht.py`
- `backend/apps/invoicing/serializers.py`
- `backend/apps/invoicing/services.py`
- `backend/apps/invoicing/views.py`
- `backend/apps/invoicing/pdf.py`
- `backend/apps/invoicing/tests/test_invoicing.py`
- `backend/apps/core/models.py`
- `backend/apps/core/serializers.py`
- `backend/apps/documents/models.py`
- `backend/apps/documents/migrations/0002_supplier_invoice_links.py`

Frontend:

- `frontend/src/app/features/workspace/invoicing-config.ts`
- `frontend/src/app/features/workspace/record-form.component.ts`
- `frontend/src/app/features/workspace/record-form.component.html`
- `frontend/src/app/features/workspace/record-form.component.scss`
- `frontend/src/app/features/workspace/record-form.component.spec.ts`
- `frontend/src/app/features/workspace/record-detail.component.ts`
- `frontend/src/app/features/workspace/resource-api.service.ts`
- `frontend/src/app/features/workspace/workspace.component.ts`
- `frontend/src/app/features/workspace/workspace.component.html`
- `frontend/src/app/features/workspace/workspace-config.ts`

Documentation and evidence:

- `docs/reports/phase-7a-completion-report.md`
- `docs/reports/phase-7b-activation-blockers.md`
- `docs/reports/evidence/` (screenshots and generated PDF)

## 13. Reproduce the checks

Backend:

```bash
cd backend
./.venv/Scripts/python.exe manage.py migrate
./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider
```

Frontend:

```bash
cd frontend
npm ci
npm run build
npm run lint
npm test -- --watch=false
```

Live E2E (requires the backend, an approver account and the passwords):

```bash
TMD_BASE_URL=http://127.0.0.1:8000 \
TMD_VERIFY_EMAIL=admin@tmd.local TMD_VERIFY_PASSWORD='...' \
TMD_APPROVER_EMAIL=e2e.approver@tmd.local TMD_APPROVER_PASSWORD='...' \
node scripts/verify-phase7a-invoicing.mjs
```

## 14. Acceptance decision

**Stage 7A test-mode UAT: PASS.**

- All known CRITICAL/HIGH defects were fixed and re-tested.
- The full backend, frontend, live E2E, build, lint, Ruff and migration checks pass.
- The Angular invoice screens were reviewed in a browser, with final evidence retained.
- Tax treatment, recoverable VAT and customer WHT are represented and tested, with unapproved policy explicitly documented.
- Security controls for read/PDF/PDF output and document attachment were tightened.

**Production / Stage 7B: NOT ACCEPTED.**

- Issuance, posting, bank execution and NRS are disabled.
- Tax, accounting, governance and legal inputs remain unapproved.
- The Finance Controller is unassigned.
- The documented tax and WHT assumptions require professional review.

This QA pass therefore supports continued Stage 7A UAT and training only. It does not authorise live invoicing, ledger posting, payment execution, NRS submission or Stage 7B activation.
