# Payment Allocation and Reversal Report

**Date:** 12 November 2026  
**Scope:** customer receipt allocations; supplier payment allocation regression

## Controls

- Receipt and invoice rows are locked with `select_for_update` during allocation.
- A receipt may allocate no more than its unapplied amount.
- An invoice may not receive more than its current balance.
- Only an approved invoice belonging to the receipt customer can receive funds.
- Duplicate active allocations for the same receipt and invoice are rejected by both service check and a conditional database uniqueness constraint.
- Allocations are immutable history. Reversal sets `is_reversed`, reviewer, timestamp and reason, then recalculates the receipt and invoice balances. A reversed row can be followed by a new allocation.
- An allocation can be reversed only while the receipt is `recorded`; after submission the receipt must be rejected or cancelled so the approved amount cannot silently change.
- Invoice cancellation is blocked while an active receipt allocation exists. The allocator must reverse the allocation first.
- Receipt cancellation restores every active invoice balance.

## Tested scenarios

| Scenario | Result | Evidence |
|---|---|---|
| Partial allocation | Passed | `test_customer_receipt_allocates_partial_and_multiple_invoices` |
| Multiple invoices on one receipt | Passed | same test |
| Unapplied balance retained | Passed | same test |
| Later allocation of unapplied funds | Passed | `test_customer_receipt_allocates_unapplied_funds_later` and posting integration test |
| Individual allocation reversal | Passed | `test_receipt_allocation_reversal_duplicate_and_invoice_cancellation` |
| Re-allocation after reversal | Passed | same test |
| Duplicate allocation request | Rejected with 409 | same test |
| Over-allocation | Rejected with 409 / 400 | same test and existing over-allocation test |
| Concurrent allocation requests | Exactly one allocation, one 409 | `test_concurrent_receipt_allocations_create_one_allocation` |
| Receipt cancellation | Restores invoice balance | `test_customer_receipt_cancellation_restores_invoice_balance` |
| Invoice cancellation with active allocation | Blocked | `test_receipt_allocation_reversal_duplicate_and_invoice_cancellation` |
| Invoice cancellation after reversal | Allowed | same test |
| Posted receipt cancellation | Reversal journal created | `test_customer_receipt_posts_allocated_and_unapplied_funds_once` |

## Consistency result

Invoice `amount_paid`, `balance` and `payment_status` are recalculated from active allocations whose receipt is in `recorded`, `submitted`, `approved` or `posted`. Reversed allocations and cancelled/rejected receipts do not contribute. The posting test confirms the ledger AR credit equals active allocations, not the gross receipt.

## Residual controls

- Cancellation of a posted receipt requires an open current period for the reversal.
- A reconciled bank transaction blocks receipt cancellation until the reconciliation match is reversed.
- There is no bulk allocation-reversal endpoint; reversals are individual and auditable.
- Supplier payment allocation uses the existing independent controls and was regression-tested by the full suite.

## Automated result

The full backend suite passed **336 tests**. No frontend-only allocation logic was changed; the generic workspace action sends the service payload and displays the API result.