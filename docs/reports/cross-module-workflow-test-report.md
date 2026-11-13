# Cross-Module Workflow Test Report

**Environment:** Django API integration tests against the isolated test database derived from the QA configuration  
**Targeted tests:** 33 passed  
**Concurrency tests:** 2 passed  
**Full backend suite:** 343 passed  
**Purpose:** prove that connected modules preserve balances, statuses and audit relationships when operated in sequence or concurrently.

---

## 1. Workflows executed

### 1.1 Procurement → inventory

Tests:

- `test_full_receipt_marks_the_order_received_then_closure_blocks_receipts`
- `test_over_receipt_is_refused`
- `test_receipt_posts_a_signed_movement_and_a_derived_balance`
- `test_transfer_cannot_dispatch_more_than_is_available`
- `test_return_brings_stock_back_at_its_cost`

Verified:

- an approved purchase order can be received;
- a full receipt moves the order to received and a later closure blocks further receipts;
- over-receipt is refused;
- the stock movement is signed and the balance is derived from movements, never typed over;
- a transfer cannot dispatch more than is available;
- a return restores stock at its original cost.

No duplicate balance row or unsupported stock movement was produced.

### 1.2 Procurement → accounts payable / three-way matching

Tests:

- `test_matching_blocks_over_invoicing_and_accepts_matched_line`
- `test_partial_deliveries_can_be_invoiced_across_split_receipts`
- `test_customer_invoice_draft_approval_and_test_pdf`
- `test_approved_supplier_invoice_cannot_be_edited`
- `test_one_payment_can_be_allocated_across_multiple_invoices`
- `test_supplier_payment_creates_an_unreconciled_bank_expectation`

Verified:

- over-invoicing against received quantities is refused;
- a correctly matched line is accepted;
- split receipts can be invoiced across multiple deliveries without exceeding the order;
- tested customer invoices can be approved and produce a test PDF;
- an approved supplier invoice is immutable;
- one payment can be allocated across multiple invoices;
- a supplier payment creates an unreconciled bank expectation rather than silently marking cash reconciled.

### 1.3 Customer invoicing and receipts

Tests:

- `test_customer_receipt_allocates_partial_and_multiple_invoices`
- `test_customer_receipt_rejects_over_allocation_and_wrong_customer`
- `test_customer_receipt_allocates_unapplied_funds_later`
- `test_customer_receipt_cancellation_restores_invoice_balance`
- `test_customer_receipt_approval_separation_and_threshold`
- `test_customer_receipt_posts_allocated_and_unapplied_funds_once`
- `test_receipt_allocation_reversal_duplicate_and_invoice_cancellation`
- `test_concurrent_receipt_allocations_create_one_allocation`

Verified:

- partial and multiple allocations update outstanding balances correctly;
- over-allocation and an invoice belonging to another customer are refused;
- unapplied funds can be allocated later;
- cancelling a receipt restores the invoice balance;
- creator/approver separation and approval thresholds hold;
- allocated and unapplied funds post once, not twice;
- reversal, duplicate allocation and invoice cancellation remain consistent;
- two concurrent allocation attempts produce exactly one allocation.

### 1.4 Banking and reconciliation

Tests:

- `test_csv_statement_import_creates_lines_and_draft_reconciliation`
- `test_match_rejects_wrong_account_and_supports_partial_split`
- `test_reconciliation_requires_all_lines_resolved_and_independent_approval`
- `test_reconciliation_cannot_be_approved_by_its_preparer`
- `test_summary_and_unmatched_reports`

Verified:

- CSV import creates statement lines and a draft reconciliation;
- a line cannot be matched to the wrong account;
- partial split matching is supported;
- reconciliation approval requires every line resolved and an independent approver;
- the preparer cannot approve their own reconciliation;
- summary and unmatched reports reflect live statement records;
- no unexplained difference can be silently marked reconciled.

### 1.5 Projects and cost integrity

Test:

- `test_cost_summary_does_not_double_count_commitments_receipts_or_project_stock_transfers`

Verified:

- approved invoices, project stock issues and approved direct costs are consumed cost;
- an open purchase order is a commitment, not an expense;
- goods receipts and project-site transfers are not counted a second time;
- budget, commitment, actual and available figures reconcile without double counting.

### 1.6 Services and HSE

Test:

- `test_work_order_full_workflow`

Verified:

- work order creation, assignment, progress, completion report and acceptance remain linked;
- a work order cannot be accepted twice;
- completion reporting uses the configured status path.

### 1.7 Equipment and leasing

Test:

- `test_dispatch_return_inspection_and_maintenance`

Verified:

- equipment registration, reservation/agreement, dispatch, return, inspection and maintenance remain linked;
- a closed agreement cannot be dispatched again (probe returns 409);
- overlapping reservations and invalid return dates are rejected by the leasing rules covered in the module suite.

### 1.8 Reporting

Tests:

- `test_payables_ageing_uses_approved_invoice_balances`
- `test_dashboard_does_not_invent_payment_receipts`
- `test_dashboard_history_uses_recorded_receipts_and_permissions`

Verified:

- ageing uses approved invoice balances, not drafts;
- dashboard payment/receipt history is based on recorded transactions, not invented placeholders;
- dashboard history respects the signed-in user's permissions.

## 2. Concurrency

The two explicit concurrency tests passed:

| Test | Race | Result |
|---|---|---|
| `test_concurrent_posting_requests_create_exactly_one_journal` | Two posting requests for the same invoice | Exactly one journal |
| `test_concurrent_receipt_allocations_create_one_allocation` | Two receipt allocations for the same invoice | Exactly one allocation |

These complement the idempotency checks: repeat submit/approve/post returns 409, and concurrent posting does not create a duplicate ledger entry.

## 3. Integrity assertions

Across the 33 tests:

- posted journals balance;
- posted transactions cannot be silently modified;
- stock balances remain derived from signed movements;
- invoice outstanding balances remain consistent after partial allocation, cancellation and reversal;
- project cost does not double count commitments, receipts or stock transfers;
- closed orders and periods reject further work;
- reconciliation approval cannot bypass unresolved lines or independent approval;
- no duplicate receipt allocation or journal posting appears under a race.

## 4. What was not executed

- No real bank transfer, NRS submission, external email or production posting was performed.
- Financial activation remains blocked pending approved accounting policy; the tests assert the block, not a production posting.
- End-to-end browser clicking of every lifecycle action was not performed; the workflows above are API/integration tests against the real serializers, views, services and database constraints. The browser side verified access, forms, dialogs and navigation.
- Partial delivery with damaged/rejected quantities was covered by the invoicing/procurement suites, but not every combination of accepted/damaged/rejected split was enumerated in this pass.

## 5. Conclusion

The connected workflows preserve balances and relationships in the tested paths. The two race conditions each produced exactly one financial record. No duplicate records, stale status, missing relationship or double-counted cost was found after the fixes.
