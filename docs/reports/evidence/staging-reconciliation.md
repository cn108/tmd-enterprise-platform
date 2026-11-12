# Synthetic staging reconciliation

Database: `tmd_staging`
All checks passed: **True**

| Check | Result |
| --- | --- |
| trial_balance_balanced | PASS |
| balance_sheet_balanced | PASS |
| ap_ledger_matches_invoice | PASS |
| ar_ledger_matches_invoice | PASS |
| inventory_ledger_matches_valuation | PASS |
| bank_ledger_matches_statement | PASS |
| bank_reconciliation_approved | PASS |
| po_partially_received | PASS |
| payment_recorded_not_executed | PASS |
| posted_journals_immutable_source | PASS |
| october_period_closed | PASS |

| Control | Ledger | Document / stock / bank |
| --- | ---: | ---: |
| Accounts payable | 180000.00 | 180000.00 |
| Accounts receivable | 2500000.00 | 2500000.00 |
| Inventory | 1315000.00 | 1315000.00 |
| Bank | 4160000.00 | 4160000.00 |

Trial balance: debit 10130000.00 = credit 10130000.00

November net result: 2485000.00

PO status: `partially_received`; supplier invoice balance: `180000.00`; bank reconciliation: `approved`.
