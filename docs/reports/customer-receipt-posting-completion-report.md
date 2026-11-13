# Customer Receipt Posting Completion Report

**Date:** 12 November 2026  
**Environment:** local staging (`tmd_staging`), test finance activation remains disabled  
**Scope:** approved customer receipt accounting, idempotency, open periods, audit, reversal and banking traceability

## Outcome

The controlled receipt-to-ledger path is implemented and covered by automated tests. It is **not active in staging**: `InvoiceSettings.test_mode=True`, `activated_at=None`, `can_issue=False`, and the accounting posting review is not recorded.

Posting therefore fails closed until the Finance Controller approves receipt account mappings, posting rules and the activation checklist. No accounting policy, approval limit or account mapping was invented.

## Implemented controls

- Receipt lifecycle: `recorded → submitted → approved → posted`; rejection and cancellation are separate outcomes.
- Only an approved, non-test receipt may post.
- `post_system_journal` supplies the balanced double-entry journal and existing open-period enforcement.
- A database transaction and `select_for_update` lock the receipt before posting.
- An `IdempotencyRecord` scoped to the receipt prevents duplicate journals; a replay returns the original journal.
- Journal lines:
  - **Debit** the approved company bank account ledger account, or the `CASH` role for cash.
  - **Credit** `AR_CONTROL` for the sum of active invoice allocations.
  - **Credit** `CUSTOMER_ADVANCES` for the unapplied balance.
- Every allocation must belong to an approved, already-posted invoice with the same currency; approved notes and WHT block posting until their accounting treatment exists.
- Audit events are written for submission, approval, posting, reversal and cancellation.
- Cancellation of a posted receipt creates a controlled reversal journal. The reversal date uses the current open period, so a closed period blocks cancellation rather than silently posting into a closed period.
- A receipt linked to a reconciled bank transaction cannot be cancelled until the reconciliation match is reversed.

## API and interface

- `POST /api/v1/customer-receipts/{id}/submit/`
- `POST /api/v1/customer-receipts/{id}/approve/`
- `POST /api/v1/customer-receipts/{id}/reject/`
- `POST /api/v1/customer-receipts/{id}/post/`
- `POST /api/v1/customer-receipts/{id}/cancel/`
- Permissions: `invoicing.approve_customerreceipt` and `invoicing.post_customerreceipt` in addition to recording, allocation and cancellation permissions.

The customer receipt screen exposes the lifecycle actions only in the applicable status. The posting action is visible to authorised users but the API remains fail-closed when activation or mappings are incomplete.

## Automated evidence

- `test_customer_receipt_posts_allocated_and_unapplied_funds_once` posts NGN 120 (NGN 100 allocated, NGN 20 unapplied) and asserts: bank debit NGN 120, AR credit NGN 100, customer advances credit NGN 20, balanced journal, one journal on replay, and one unreconciled bank expectation.
- `test_customer_receipt_approval_separation_and_threshold` proves creator approval refusal and two configured approvals for a `customer_receipt` policy band.
- `test_activated_*` posting tests continue to prove the activation gate.
- Full backend suite: **336 tests passed**; Ruff, Django check and migration drift were run separately.

## Outstanding policy dependencies

1. Approve `AR_CONTROL`, `CUSTOMER_ADVANCES`, `BANK`, `CASH` and all other posting mappings for the live chart of accounts.
2. Approve the customer receipt posting rule and accounting policy.
3. Record the Finance Controller posting review and management activation.
4. Configure receipt approval bands. No TMD limit has been seeded; without a band the safe fallback is one independent approval.
5. Approve FX and WHT treatment before receipts in those cases can post.

## Limitations

No posting was executed against the staging ledger because staging is deliberately not activated. Browser evidence therefore covers the receipt screen, form validation and policy messaging, not a live staging journal. Posting evidence is from the automated UAT database.