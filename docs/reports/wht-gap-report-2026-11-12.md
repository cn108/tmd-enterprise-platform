# WHT Technical and Accounting Gap Report — 12 November 2026

**Status: policy-blocked.** No rate, tax classification, payable/receivable account or remittance
treatment has been invented.

## Implemented

- Supplier and customer invoice lines can carry a configured WHT tax code.
- Invoice totals expose `wht_total`; customer invoices expose `net_receivable` after WHT.
- Posting refuses any WHT invoice before journal creation.
- Tax codes are date-effective through the existing tax configuration.
- Dashboard and invoice screens display WHT figures without presenting them as posted tax.

## Missing design decisions

### Supplier-side withholding

- Which supplier payments are subject to WHT, by service and supplier category.
- Approved WHT payable account and vendor/authority subledger.
- Whether WHT is withheld at invoice approval, payment, or remittance.
- Partial-payment and credit-note interaction.
- Remittance document, period, return reference and evidence of payment.

### Customer-side withholding

- Whether customer deductions create a receivable from the tax authority or reduce revenue.
- Approved WHT receivable account and customer deduction evidence.
- Allocation of a net receipt to a gross invoice and the resulting WHT balance.
- Statement presentation of withheld amounts.

### Remittance

- Authority, period, rates, thresholds and filing format.
- Remittance journal, payment record, receipt attachment and reconciliation.
- Late-payment interest and penalty treatment.

## Required controls before implementation

1. Written tax policy approved by TMD management and its tax adviser.
2. Approved account roles for WHT payable and WHT receivable.
3. Mapping of every WHT code to its legal rate and effective dates.
4. Separation between invoice approval, withholding and remittance.
5. Remittance evidence and audit trail.
6. Period-close and reconciliation report.

## Tests

Existing tests confirm WHT invoices are refused at posting and that WHT totals do not create a
journal. No live WHT posting test exists because the feature is deliberately disabled.

## Decision

WHT remains disabled. Customer receipts currently record the actual amount received; they do not
calculate or post withholding.
