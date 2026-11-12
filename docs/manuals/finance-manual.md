# Finance manual

## 1. Current control state

The system is safe for test documents, UAT and training. Live invoice issuance, live posting, bank execution and NRS submission are blocked. See `docs/reports/phase-7b-activation-blockers.md`.

## 2. Chart of accounts

Create accounts only from the accountant-approved chart. Each account needs a type and normal balance. Approval is a separate step. Do not invent account codes or mappings.

## 3. Account roles and posting rules

Account-role mappings connect business events to ledger accounts. A mapping must be approved and effective. If a required mapping is missing:

- posting that event is refused;
- the cash-flow statement may show **Unclassified** and is marked incomplete;
- gross profit is unavailable until a `COST_OF_SALES` mapping exists.

Never add a mapping simply to remove a warning. Obtain the approved mapping.

## 4. Journals

1. Create a balanced journal with at least two lines.
2. Submit it.
3. An independent approver approves it.
4. An authorised user posts it.

Posted journals are immutable. Correct an error with a reversal and a new journal, recording the reason. The system enforces debit = credit and period controls.

## 5. Periods

Create fiscal years and monthly periods from the approved calendar. Close a period only after reconciliations. Reopening requires permission and a recorded reason. Posting into a closed period is refused.

## 6. Invoices and payments

- Supplier invoices are checked for duplicates, matched to purchase order/receipt and approved.
- Customer invoices follow draft → review → approval. In test mode they carry a test banner and are not tax invoices.
- Payments are recorded as external events; the platform does not execute a bank transfer.
- Allocate payments to invoices. An unallocated amount remains visible.
- Credit/debit notes correct an approved invoice; do not edit the original.

## 7. Banking

Import statements, match lines to book transactions, investigate exceptions and approve reconciliations. A recorded book balance is not a confirmed bank balance. See the [Banking manual](banking-manual.md).

## 8. Financial statements

Formal statement figures come from posted journal lines. Receivables and payables in operational reports are approved document balances unless explicitly labelled ledger. Commitments are not expenses. Read every completeness warning.

## 9. Tax

Tax configurations are not a tax remittance report. Confirm rates, effective dates, WHT basis, VAT recoverability and NRS scope with the tax adviser. The current WHT calculation and recoverability default are provisional and must not be treated as an approved tax position.

## 10. Month-end checklist

1. All bank accounts reconciled or exceptions documented.
2. Supplier and customer statements reconciled.
3. Inventory physical count and valuation reconciled.
4. Accruals, prepayments and corrections posted through approved journals.
5. Trial balance balanced; no unposted approved documents left unexplained.
6. Financial statements reviewed with warnings resolved or documented.
7. Period closed by an authorised user.

## 11. Prohibited actions

- No direct database edits to financial records.
- No deleting posted journals, invoices or audit events.
- No sharing of approver accounts.
- No live processing before written activation.
