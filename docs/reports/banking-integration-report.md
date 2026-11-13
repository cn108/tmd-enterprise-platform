# Banking Integration Report

**Date:** 12 November 2026  
**Scope:** customer receipts and supplier payments joined to company bank accounts and bank reconciliation

## Implemented linkage

Both document types can now carry a **company bank account**. A recorded supplier payment or receipt creates a `BankTransaction` row as a company-side expectation:

| Document | Source type | Amount sign | Initial status |
|---|---|---|---|
| Supplier payment | `supplier_payment` | negative (money out) | `recorded` |
| Customer receipt | `customer_receipt` | positive (money in) | `recorded` |

The transaction references the company bank account, document number, external bank reference, date and currency. It is **not** marked reconciled. `ReconciliationMatch` remains the only route to a confirmed match, and matching remains a deliberate user action in the Banking workspace.

The unique constraint on `(source_type, source_id)` prevents duplicate bank expectations. Receipt cancellation or rejection sets the expectation to `void`; cancellation is refused when the transaction is already reconciled.

## Traceability path

`CustomerReceipt` / `SupplierPayment` → `BankTransaction(source_type, source_id)` → imported `StatementLine` → `ReconciliationMatch` → `Reconciliation`.

The Banking UI already exposes unreconciled transactions, statement import, proposed matches and reconciliation approval. No live bank transfer, payment execution or automatic reconciliation was added.

## Defect found and fixed

Supplier payment bank expectations previously required both the supplier's bank account and the company bank account. A payment with only the company account silently produced no bank transaction. The condition now requires the company account only, which is the account being reconciled.

## Automated evidence

- `test_customer_receipt_posts_allocated_and_unapplied_funds_once`: identifies the customer receipt's `BankTransaction`, amount NGN 120, status `recorded`, zero matches; cancellation changes it to `void`.
- `test_supplier_payment_creates_an_unreconciled_bank_expectation`: identifies the supplier payment's transaction, amount −NGN 250, status `recorded`, zero matches.
- Full backend suite: **336 tests passed**.

## Not performed

- A full browser statement import and manual match against a posted receipt was not executed on staging because staging receipt posting is disabled and the available data does not include a matching statement line.
- No bank API or transfer execution exists; this is deliberate.

## Policy / operational dependencies

1. Company bank accounts must have approved, active ledger accounts before receipts or payments can post.
2. A user with `banking.match_banktransaction` must explicitly confirm statement matches.
3. Reconciled receipt cancellation requires reversal of the match first.
4. Bank statement data must be supplied by TMD for formal UAT.