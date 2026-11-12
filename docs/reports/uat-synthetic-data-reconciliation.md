# Synthetic data and reconciliation report

**Database:** `tmd_staging`
**Evidence:** `docs/reports/evidence/staging-reconciliation.json`, `staging-reconciliation.md`, `workflow-checks.json`

## 1. Records created through real workflows

| Area | Synthetic records |
| --- | --- |
| People and organisation | 10 UAT users, 6 departments, cost centres, two warehouses and storage locations |
| Parties | 3 suppliers, 2 customers, contacts, addresses, encrypted supplier bank account |
| Catalogue | 4 engineering items, prices and units of measure |
| Procurement | 1 request, approval, RFQ, quote, supplier selection, 1 purchase order, 1 partial goods receipt with 1 damaged pump |
| Inventory | Opening stock, 6 stock movements, 1 project issue, valuation at weighted average |
| Project | 1 active project, 1 customer contract, approved budget of ₦12,000,000, milestones, direct cost, material issue |
| Invoicing | 1 approved matched supplier invoice (₦680,000), 1 approved customer invoice (₦2,500,000), 1 recorded payment (₦500,000) |
| Banking | CSV statement, 2 statement lines, 2 exact matches, 1 approved reconciliation |
| Accounting | 18 accounts, mappings, 11 posted journals, 1 reversal, October close, November open period |
| Services | Active service contract, work order from request to completion and customer acceptance |
| Leasing | Equipment, reservation, approved rental agreement, dispatch, return, inspection, planned maintenance |

All records were produced by the application’s service functions. The seed does not insert disconnected ledger rows or hand-write financial statement totals.

## 2. Controlled reconciliation result

| Check | Result | Ledger | Source document / stock / bank |
| --- | --- | ---: | ---: |
| Accounts payable | PASS | ₦180,000.00 | ₦180,000.00 |
| Accounts receivable | PASS | ₦2,500,000.00 | ₦2,500,000.00 |
| Inventory | PASS | ₦1,315,000.00 | ₦1,315,000.00 |
| Bank | PASS | ₦4,160,000.00 | ₦4,160,000.00 |
| Trial balance | PASS | debit ₦10,250,000.00 | credit ₦10,250,000.00 |
| Balance sheet | PASS | assets | liabilities + equity + unclosed result |

- Supplier invoice total: ₦680,000; payment: ₦500,000; remaining payable: ₦180,000.
- Customer invoice balance: ₦2,500,000; receivables control: ₦2,500,000.
- Stock: 7 pumps, 20 valves and 5 helmets, value ₦1,315,000.
- November posted result: revenue ₦2,500,000, expenses ₦15,000, net ₦2,485,000.
- October 2026 closed; its result is carried to retained earnings.
- The one damaged pump was excluded from accepted stock and carries a rejection reason.
- Bank statement opens at ₦4,675,000, has a ₦500,000 payment and ₦15,000 charge, and closes at ₦4,160,000, matching the bank ledger.

## 3. Financial statement derivation

The trial balance, income statement and balance sheet are calculated by `apps.accounting.services` from **posted journal lines**. The reporting API does not recompute profit from invoice totals. The income statement excludes period-close journals, while the balance sheet includes posted closing entries and the unclosed current result.

## 4. Limitations

- The chart of accounts, tax rates, opening balances and mappings are synthetic and provisional. They are not an approved production ledger.
- The bank statement is a generated CSV for reconciliation testing, not a real bank feed.
- Revenue recognition remains disabled pending an approved accounting policy.
- The inventory value is a UAT valuation under a provisional method, not a signed-off stock count.

**Conclusion:** the synthetic data is internally consistent across journals, control accounts, stock, documents and the bank statement, and is suitable for controlled employee acceptance testing only.
