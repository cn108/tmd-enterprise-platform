# Customer Receipts Completion Report — 12 November 2026

**Status:** Implemented and tested in staging, test-mode only. Ledger posting is policy-blocked.

## What was added

### Backend

- `CustomerReceipt`: unique reference, customer, receipt date, currency, amount, method, external
  bank/cheque reference, allocated and unallocated amounts, status, test flag, notes, cancellation
  fields.
- `CustomerReceiptAllocation`: one receipt allocated across approved customer invoices, with unique
  receipt/invoice and positive-amount constraints.
- `CustomerInvoice.amount_paid` and `payment_status` (`unpaid`, `part_paid`, `paid`).
- Receipt API: list/create, `allocate`, `cancel`, and `statement` PDF.
- New permissions: view, add, allocate and cancel customer receipts.

### Controls

- A receipt cannot exceed its own amount when allocating.
- An allocation cannot exceed an approved invoice balance.
- Customer and currency must match; draft, cancelled and unapproved invoices are refused.
- Cancellation requires a reason and reverses every allocation; invoice balances are recalculated.
- Cancelled receipts cannot be allocated.
- Receipts are never deleted; the reference is preserved.
- No bank transfer, card collection or payment execution exists.
- Receipts are test documents while Stage 7B is closed.
- Ledger posting is not implemented; no journal is created.

### Frontend

New **Customer receipts** tab with:

- Receipt list, status filter, search and test flag.
- Create form with customer, date, amount, method, bank reference, notes and one or more invoice
  allocations.
- Allocated and unapplied amounts.
- Detail view with allocation summary.
- **Allocate unapplied funds** and **Cancel receipt** actions.
- **Preview PDF** opening the customer account statement.
- Permission-aware actions and table action tray.

### Customer statement

The PDF includes:

- Receipt reference and period.
- Customer code and name.
- Opening balance, closing balance, outstanding invoice total and unapplied receipts.
- Movements for approved invoices, approved credit/debit notes and recorded receipts.
- Debit, credit and running balance.
- A test-document banner while production issuance is disabled.

The statement is generated from database records, not a client-side calculation.

## Tests added

| Case | Result |
| --- | --- |
| Partial allocation across two invoices | Pass |
| Multiple allocations on one receipt | Pass |
| Unapplied funds retained | Pass |
| Later allocation of unapplied funds | Pass |
| Allocation above receipt amount | Refused |
| Allocation above invoice balance | Refused |
| Allocation to another customer's invoice | Refused |
| Allocation to a draft invoice | Refused |
| Cancellation restores invoice balances | Pass |
| Cancellation without reason | Refused |
| Allocation after cancellation | Refused |
| Statement PDF generated | Pass |

**Backend suite:** 331 passed. **Frontend:** 54 passed. Lint and production build passed.

## Browser evidence

- [Receipt list at 1366](evidence/final/customer-receipts-list-1366.png)
- [Receipt screen at 360](evidence/final/customer-receipts-360.png)

A live receipt was created for NGN 100,000, allocated NGN 40,000 to `CI-2026-0001`, leaving NGN
60,000 unapplied. Cancellation restored the invoice from NGN 2,460,000 to NGN 2,500,000. The
reference and cancellation audit record were preserved.

## Remaining work

- Approved customer-receipt ledger posting and cash/AR account mappings.
- Approval or review step for large receipts.
- Individual allocation reversal (current cancellation reverses the whole receipt).
- Receipt email delivery, bank statement auto-match and receipt-to-bank reconciliation.
- WHT deduction handling and net receipt presentation.
- Receipt numbering approval for production.
