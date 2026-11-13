# Financial Workflow Final Gap Report — 12 November 2026

> **Historical snapshot.** Customer receipt ledger posting, allocation reversal, bank matching and idempotency were subsequently completed and tested. See `customer-receipt-posting-completion-report.md` and `final-project-completion-report.md`. Notes, WHT and FX remain policy-blocked.

**Activation state:** `test_mode=True`, `can_issue=False`, `activated_at=None`. No live payment,
NRS submission or production invoice issuance is enabled.

## Status summary

| Workflow | Status |
| --- | --- |
| Supplier invoice posting | Implemented, tested, disabled by gate |
| Customer invoice posting | Implemented, tested, disabled by gate |
| Supplier payment recording and posting | Implemented and tested in test mode |
| Partial payments and multi-invoice allocation | Implemented and tested |
| Supplier advances | Implemented and tested |
| Customer receipts | Implemented and tested in test mode |
| Customer receipt allocation | Implemented and tested |
| Customer receipts ledger posting | **Incomplete — no approved accounting policy** |
| Customer statements | Implemented as a generated PDF |
| Credit/debit note adjustments | Implemented at document level and tested |
| Credit/debit note ledger posting | **Policy-blocked** |
| WHT posting | **Policy-blocked** |
| Foreign-currency posting | **Policy-blocked** |
| NRS production submission | Disabled |
| Production bank execution | Not implemented by design |

## Duplicate and concurrency controls

- Invoice and supplier-payment posting use idempotency keys and a stored receipt.
- Concurrent posting locks the document row; only one journal is linked.
- Replays return the original journal with `Idempotency-Replayed`.
- Receipt allocation locks the receipt and invoice; over-allocation is refused.
- Receipt cancellation is transactional and recalculates every affected invoice.
- Approved notes cannot be cancelled; corrections require another note.
- A credit note that would make the invoice negative is refused.

## Credit and debit notes

Document-level effects are tested:

- Partial credit reduces the payable/receivable.
- Debit notes increase the amount due.
- A credit beyond the remaining value is refused.
- Approved notes block gross invoice and payment posting.
- Draft notes can be cancelled; approved notes require a correcting note.

**No note journal is created.** There is no approved note-to-account mapping, no approved tax
treatment and no note posting endpoint. Concurrent note *posting* therefore cannot be tested; adding
it without policy would create an unaudited accounting path.

## Customer receipts

Receipt records, partial and multiple allocations, unapplied funds, cancellation/reversal, statement
PDF, outstanding balances and receipt history are implemented. See the
[customer receipts report](customer-receipts-completion-report.md).

Not implemented:

- Ledger journal for receipting or unapplied cash.
- Approval threshold for receipts.
- Individual allocation reversal.
- Bank statement matching and receipt-to-bank reconciliation.
- Customer WHT deduction.

## WHT

See the [WHT technical and accounting gap report](wht-gap-report-2026-11-12.md). All WHT posting is
refused; no rate or remittance treatment was invented.

## Foreign currency

Posting remains refused. Invoice and payment document currency is captured, but no approved FX,
realised/unrealised gain-loss or revaluation policy exists.

## Tests

- Backend: **331 passed**.
- Frontend: **54 passed**.
- Ruff, Django check and migration drift: passed.
- Frontend lint and production build: passed.
- Relevant new tests: receipt partial/multiple allocation, unapplied funds, cross-customer refusal,
  over-allocation refusal, cancellation restoration, statement PDF and privileged role grant.

## Production blockers

1. Signed role matrix and chart of accounts.
2. Approved account-role mappings for receipts, notes and WHT.
3. Opening balances and bank/inventory opening entries.
4. Approved tax, FX, WHT and note policies.
5. Production numbering and company legal details.
6. Finance Controller posting review and management go-live authorisation.
7. Production email identity, MFA, backups, monitoring and stable hosting.
8. Customer-receipt and statement acceptance by Finance.

## Decision

The implemented workflows are suitable for controlled UAT with synthetic data. Production financial
activation remains refused.
