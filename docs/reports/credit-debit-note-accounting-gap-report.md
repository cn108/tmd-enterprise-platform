# Credit and Debit Note Accounting Gap Report

**Date:** 12 November 2026  
**Status:** document workflow works; ledger posting is intentionally not implemented

## What is implemented and tested

- Supplier and customer credit/debit notes can be drafted, submitted, approved, rejected and cancelled.
- Creator approval is refused; configured note approval bands are honoured.
- Approval recalculates the linked invoice's credited/debited totals and remaining balance.
- A credit note cannot exceed the invoice's remaining value.
- An invoice with an approved note cannot be posted gross; the posting gate returns a conflict because note posting is not configured. This prevents ledger/document disagreement.
- A payment or receipt allocated to an invoice with an approved note cannot be posted.

Evidence: `test_posting_refuses_a_gross_invoice_when_an_approved_credit_note_exists`, `test_posting_refuses_a_gross_invoice_when_an_approved_debit_note_exists`, note approval and excess-credit tests, plus the full 336-test suite.

## Accounting event matrix

The debits and credits below are the **candidate treatment requiring TMD approval**. They are not active posting rules and no journal is created by note approval today.

| # | Event | Trigger | Debit role | Credit role | Tax role | Current ledger state | Policy dependencies |
|---|---|---|---|---|---|---|---|
| 1 | Supplier credit note — price correction | Approved note linked to approved supplier invoice | `AP_CONTROL` | `COST_OF_SALES` / `INVENTORY` / `PROJECT_COST` as appropriate | `INPUT_TAX` | No journal; invoice balance reduced | Confirm cost/expense reversal classification per line; approve note posting rule; define treatment when invoice unposted |
| 2 | Supplier debit note — additional charge | Approved note | `COST_OF_SALES` / `INVENTORY` / `PROJECT_COST` | `AP_CONTROL` | `INPUT_TAX` | No journal; invoice balance increased | Same classification decision; additional-charge tax point; approve posting rule |
| 3 | Customer credit note — sales reduction | Approved note linked to approved customer invoice | `REVENUE` | `AR_CONTROL` | `OUTPUT_TAX` | No journal; invoice balance reduced | Confirm revenue reversal and output-tax reversal; approve note posting rule |
| 4 | Customer debit note — additional sale | Approved note | `AR_CONTROL` | `REVENUE` | `OUTPUT_TAX` | No journal; invoice balance increased | Confirm revenue recognition and tax point; approve posting rule |

## Why posting remains disabled

1. There is no `journal_entry` link or posting service for `InvoiceNote`.
2. No approved note posting rules or note-specific account mappings exist.
3. TMD has not approved revenue/cost reversal classification, tax-point treatment, or the interaction with already-posted invoices.
4. Notes against a posted invoice require a reversal/adjustment policy; posting a credit note against a posted gross invoice without that policy would misstate AR/AP.

## Safe interim behaviour

- Note approval changes document balances only.
- Invoice, payment and receipt posting refuses to proceed when an approved note exists.
- Once TMD approves the event matrix and posting rules, note posting must reuse `post_system_journal`, open periods, idempotency and reversal controls used by receipts and invoices.

## Required decisions

- Per-line mapping to cost, inventory, project cost or revenue reversal.
- Whether notes may post to a different period from the original invoice and how tax points follow.
- Treatment of notes on already-posted invoices (adjustment vs reversal plus re-post).
- Approval bands and segregation for note posting.
- Whether supplier/customer debit notes require a separate numbering and tax sequence.