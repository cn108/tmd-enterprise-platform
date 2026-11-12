# Phase 7B activation blockers

**Date:** 12 November 2026
**Purpose:** keep production invoice issuance, NRS submission and ledger posting disabled until the controls below are formally approved.
**Current setting:** `InvoiceSettings.test_mode = True`; `activated_at = None`; no Finance Controller is assigned.

**Execution checklist:** use [`phase-7b-activation-checklist.md`](phase-7b-activation-checklist.md) for the prioritized order, owners, evidence and sign-off record.

Passing Stage 7A tests is **not** an activation criterion. A test run must never set these gates.

## 1. Blocking checklist

| # | Gate | Required evidence | Current status | Owner |
|---|---|---|---|---|
| 1 | Management roles and approval authority | Signed matrix covering the nine operational roles and Finance Controller; named holders | **BLOCKED** — roles exist, no holders; Finance Controller unassigned | Management |
| 2 | Chart of accounts and account-role mappings | Approved accounts; every one of the 19 roles mapped; mappings approved by a second person | **BLOCKED** — no account exists | Accountant |
| 3 | Opening trial balance and subledger balances | Signed opening trial balance, AP/AR open items, inventory value | **BLOCKED** — no opening balances | Accountant / Finance |
| 4 | Bank and inventory opening balances | Reconciled bank and inventory opening positions | **BLOCKED** — none loaded | Finance / Stores |
| 5 | VAT and WHT configuration | Reviewed rates, effective dates, Tax ID, tax treatment and WHT basis | **BLOCKED** — tax treatment and effective-date fields exist, but no reviewed rate, Tax ID or WHT basis supplied | Tax adviser / Accountant |
| 6 | Invoice numbering and rounding | Approved customer-invoice scheme and per-document rounding policy (D-08, D-23) | **BLOCKED** — scheme is provisional; rounding is half-up assumption | Accountant |
| 7 | Company legal details | Legal name, address, Tax ID, invoice footer and authorised signatory | **BLOCKED** — settings are blank | Management |
| 8 | Accounting posting rules | Approved rules for AP, AR, input VAT, output VAT, WHT and invoice journals | **BLOCKED** — no posted invoice rule exists | Accountant / Finance Controller |
| 9 | Qualified finance review | Recorded `AccountingSettings.posting_reviewed_at`, reviewer and notes | **BLOCKED** — no Finance Controller appointed, no review recorded | Finance Controller |
| 10 | Management go-live authorisation | Written authorisation naming the activation date and scope | **BLOCKED** — not requested | Management |

## 2. Technical activation gates in the code

`POST /api/v1/invoice-settings/{id}/activate/` requires all of:

- every key in `ACTIVATION_GATES` set true;
- `AccountingSettings.posting_reviewed_at` recorded;
- non-blank company legal name and Tax Identification Number;
- a `customer_invoice` numbering scheme with `review_status = reviewed`;
- a `TaxProfile` with `review_status = reviewed`;
- an NRS environment if `nrs_enabled` is true;
- written activation notes.

The endpoint also requires `invoicing.manage_invoicesettings`, and it writes an audit event. There is no automatic activation, fixture or test that flips `test_mode`.

## 3. Additional controls that must be completed before live use

- Assign the Finance Controller and at least one independent approver; test the two-person ₦5m path with real accounts.
- Confirm D-07 (tax registrations, rates and NRS scope), D-08 (numbering), D-21 (landed cost) and D-23 (rounding).
- Decide whether a service invoice without a goods receipt needs an approved service-acceptance record instead of a free-text exemption.
- Agree the duplicate-detection window and whether a suspected duplicate can ever be overridden in production.
- Agree WHT treatment: whether it is withheld from the payment, who remits it, and which account/role is used.
- Confirm the WHT base. The application currently calculates WHT on the line subtotal, excluding VAT, for both supplier and customer lines; this is not an approved tax position.
- Confirm whether supplier input VAT is recoverable by default and who may clear the recoverable flag. The application defaults the flag to true.
- Confirm that each provisional `TaxConfiguration` is reviewed before live use. Stage 7A accepts provisional codes on test documents; the activation gate checks the reviewed tax profile, not every individual tax code.
- Confirm the treatment of zero-rated, exempt and out-of-scope lines, including whether a zero-rate code is mandatory instead of leaving the code blank.
- Approve the PDF layout and legal wording; the current PDF is explicitly a test document.
- Design and approve payment execution and bank reconciliation before recording real payments; Stage 7A only records an external event.
- Add invoice ageing, statements and receipt allocation in Phase 8.
- Obtain NRS onboarding, credentials, endpoint and API version before enabling the flag. The adapter boundary exists, but no NRS network client is implemented.
- Invoice and supplier-payment posting are idempotent as of 12 November 2026; replay returns the original journal. Successful payment posting remains a test-only path until activation.

## 4. What remains safe while blocked

Stage 7A is safe for development, UAT and training because:

- every created document has `is_test=True`;
- PDFs carry a “TEST DOCUMENT — NOT A TAX INVOICE” banner;
- no journal is created and `post` returns `409`;
- no NRS request is sent;
- no bank payment is executed;
- cancelled invoice numbers are retained;
- approvals and audit records are real and attributable to test users.

## 5. Activation decision

**Do not activate.** The missing items are accounting and governance inputs, not code defects. Activation should be a separate, dated management decision after items 1–10 are evidenced and the Phase 7A test documents have been cleared from any production environment.
