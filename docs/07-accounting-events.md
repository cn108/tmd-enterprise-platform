# Accounting Event Matrix and Policy Approvals

**Version:** 0.1 — 11 November 2026
**Guide references:** §6 (accounting architecture and financial controls), §15.6
**Status:** **No chart-of-accounts code, account name, tax rate or accounting policy is selected in this document.** Account *roles* are described; actual accounts must be supplied and approved by TMD's accountant (D-05). The brief forbids choosing debit/credit accounts without approval.

---

## 1. Non-negotiable accounting controls

| # | Control |
| --- | --- |
| C-01 | Every posted journal has ≥2 lines and total debits = total credits in journal and base currency rules |
| C-02 | One central posting service creates journals; no module writes journal rows directly |
| C-03 | Posting is atomic — source status, journal, lines and audit event commit together |
| C-04 | Posted journals are immutable; corrections use reversal + replacement or approved adjustment |
| C-05 | Posting validates period status, posting date, source reference, currency, exchange rate and approval status |
| C-06 | Every journal line links to its originating document/event; drill-through must work |
| C-07 | Posting is idempotent per source event (no duplicate journals on retry) |
| C-08 | A warehouse purchase is never expensed twice (at invoice **and** at issue) |
| C-09 | Commitment (open PO) is not expense |
| C-10 | Budget, committed, received-not-invoiced, actual, reserved and issued are distinct figures |

## 2. Account roles used below

Roles, not accounts. The accountant maps each role to an approved account code:

`AR_CONTROL`, `AP_CONTROL`, `INVENTORY`, `GRNI` (if used), `PROJECT_COST` / `WIP`, `COST_OF_SALES`, `REVENUE`, `OUTPUT_TAX`, `INPUT_TAX`, `BANK`, `CASH`, `CUSTOMER_ADVANCES`, `SUPPLIER_ADVANCES`, `BANK_FEES`, `FX_GAIN_LOSS`, `STOCK_ADJUSTMENT`, `SUSPENSE` (not for permanent balances), `RETAINED_EARNINGS`, `OPENING_BALANCE_EQUITY`.

Mapping table shape: `PostingRule(event_type, debit_role, credit_role, amount_basis, project_dimension_required, tax_role, approval_required, effective_from)`.

## 3. Event matrix (illustrative effects only — **not final policy**)

The brief's §6 table is reproduced faithfully; each row requires accountant approval before enablement.

| # | Business event | Trigger / source | Illustrative effect | Dimensions | Approval before posting | Status |
| --- | --- | --- | --- | --- | --- | --- |
| E-01 | Supplier invoice for accepted **warehouse** goods | Supplier invoice matched to PO + accepted GRN | Debit INVENTORY (or landed-cost account); credit AP_CONTROL. GRNI may be used between receipt and invoice | Supplier, warehouse, project if pre-allocated | Invoice approval + match | UNRESOLVED |
| E-02 | Goods received **before** supplier invoice | GRN posted | Debit INVENTORY; credit GRNI/accrual | Supplier, warehouse | Receipt acceptance | UNRESOLVED (policy) |
| E-03 | GRNI cleared when invoice arrives | Supplier invoice posted against GRN | Debit GRNI; credit AP_CONTROL (per approved policy) | Supplier | Invoice approval | UNRESOLVED |
| E-04 | Stock issued to a project | Stock issue movement | Credit INVENTORY; debit PROJECT_COST/WIP/COST_OF_SALES as approved | Project, cost centre, warehouse | Issue authorisation | UNRESOLVED |
| E-05 | **Direct-to-project** purchase invoiced | Supplier invoice matched to PO + site acceptance | Debit PROJECT_COST/expense/WIP; credit AP_CONTROL. Classification depends on contract and policy | Project, cost centre | Invoice approval | UNRESOLVED |
| E-06 | Customer invoice posted | Approved customer invoice | Debit AR_CONTROL; credit REVENUE and OUTPUT_TAX only when recognition criteria and invoice rules are met | Customer, project, cost centre | Invoice approval | UNRESOLVED |
| E-07 | Customer receipt allocated to invoice | Receipt + allocation | Debit BANK/CASH; credit AR_CONTROL | Customer, bank | Receipt acceptance | UNRESOLVED |
| E-08 | Customer advance (unallocated receipt) | Receipt without allocation | Debit BANK/CASH; credit CUSTOMER_ADVANCES | Customer, bank | Receipt acceptance | UNRESOLVED |
| E-09 | Customer advance later applied to invoice | Allocation event | Debit CUSTOMER_ADVANCES; credit AR_CONTROL | Customer | Allocation approval | UNRESOLVED |
| E-10 | Supplier payment | Approved payment execution | Debit AP_CONTROL; credit BANK/CASH | Supplier, bank | Payment approval | UNRESOLVED |
| E-11 | Supplier advance / deposit | Payment not allocated to invoice | Debit SUPPLIER_ADVANCES; credit BANK/CASH | Supplier, bank | Payment approval | UNRESOLVED |
| E-12 | Supplier advance applied to invoice | Allocation event | Debit AP_CONTROL; credit SUPPLIER_ADVANCES | Supplier | Allocation approval | UNRESOLVED |
| E-13 | Bounced / failed payment | Status change or bank statement | Reverse original payment effect (linked reversal) | Supplier, bank | Finance approval | UNRESOLVED |
| E-14 | Payment reversal | Controlled reversal | Linked reversal journal; original untouched | Supplier, bank | Accountant approval | UNRESOLVED |
| E-15 | Bank charges / interest | Statement line with adjustment workflow | Debit BANK_FEES; credit BANK | Bank | Finance approval | UNRESOLVED |
| E-16 | Stock adjustment (count variance, damage, write-off) | Approved count/adjustment | Debit STOCK_ADJUSTMENT/expense; credit INVENTORY (direction depends on sign) | Warehouse, project where allocable | Adjustment approval | UNRESOLVED |
| E-17 | Supplier return (stock) | Supplier return document | Reverse receipt: credit INVENTORY; debit AP_CONTROL or GRNI per policy | Supplier, warehouse | Return approval | UNRESOLVED |
| E-18 | Supplier credit note | Credit note matched | Debit AP_CONTROL; credit INVENTORY/PROJECT_COST/INPUT_TAX per reason | Supplier, project | Credit note approval | UNRESOLVED |
| E-19 | Customer credit note | Credit note approved | Debit REVENUE; debit OUTPUT_TAX; credit AR_CONTROL | Customer, project | Credit note approval | UNRESOLVED |
| E-20 | Unrealised/realised FX difference | Payment/receipt in foreign currency | Debit/credit FX_GAIN_LOSS | Currency | Finance approval | **Disabled** until FX policy approved (Q-25) |
| E-21 | Opening balances loaded | Migration event | Per signed opening trial balance | All | Accountant + management sign-off | UNRESOLVED (migration only) |
| E-22 | Period reopen adjustment | Controlled adjustment journal | Per adjustment reason | All | Accountant + management | UNRESOLVED |
| E-23 | Equipment rental income (if TMD leases out) | Rental invoice | Debit AR_CONTROL; credit revenue role (service) | Asset, customer | Invoice approval | UNRESOLVED (scope Q-27b) |

## 4. Posting engine requirements

1. `PostingService.post(event)` receives a typed domain event: `event_type`, `source_type`, `source_id`, `date`, `currency`, `amounts`, `dimensions`, `actor`, `idempotency_key`.
2. Resolve `PostingRule` for the event type and effective date; refuse if none is active (**no default posting**).
3. Validate: period open, source approved, dimensions present, currency/rate present, amounts non-zero.
4. Build journal + lines; validate balance with exact decimal arithmetic.
5. Persist journal, lines, source status change and audit event in **one transaction**; write `IdempotencyRecord`.
6. Return the journal reference to the caller; the caller never constructs journal rows.
7. Reversal creates a new journal with negated lines and `reversal_of_id`; the original remains untouched and both link to the reason.

Failure behaviour: any exception rolls back the whole unit; the source document stays unposted and the error is surfaced with correlation ID. No partial postings, no silent suppression.

## 5. Reports requiring approved definitions

| Report | Definition needs | Owner |
| --- | --- | --- |
| Trial balance | Account ranges, level of detail, period selection, zero-balance handling | Accountant |
| General ledger detail | Ordering, drill-through, source columns | Accountant |
| Income statement | Account groupings, cost-of-sales treatment, project dimension columns | Accountant |
| Balance sheet | Groupings, current/non-current split, retained earnings handling | Accountant |
| Project profitability | Recognised vs invoiced revenue, cost inclusions (committed? reserved?), overhead allocation (if any) | Accountant + Management |
| AP/AR ageing | Buckets (e.g. current, 30/60/90+), basis (due date vs invoice date), disputed handling | Accountant |
| Stock valuation | Costing method, landed-cost inclusion, negative-stock policy | Accountant |
| VAT/tax reports | Return format required by TMD's adviser | Tax adviser |
| Budget vs actual vs committed | Budget version, commitment definition | Management + Accountant |

Bucket boundaries and groupings are **not proposed here** because they are company policy.

## 6. Approvals required before production posting is enabled (Guide §6)

Signed approval must be obtained for **each** of the following. Until signed, the affected feature remains **not production-enabled**:

| # | Item | Owner | Status |
| --- | --- | --- | --- |
| P-01 | Chart of accounts | Accountant | UNRESOLVED |
| P-02 | Accounting framework / reporting standard basis | Accountant | UNRESOLVED |
| P-03 | Opening balances | Accountant + Management | UNRESOLVED |
| P-04 | Fiscal year and accounting period rules | Accountant | UNRESOLVED |
| P-05 | Inventory costing method | Accountant | UNRESOLVED |
| P-06 | Goods-received-not-invoiced policy | Accountant | UNRESOLVED |
| P-07 | Revenue recognition policy | Accountant | UNRESOLVED |
| P-08 | Project cost / WIP treatment | Accountant | UNRESOLVED |
| P-09 | Tax configuration (rates, codes, treatment) | Accountant + tax adviser | UNRESOLVED |
| P-10 | Foreign exchange policy | Accountant | UNRESOLVED |
| P-11 | Fixed asset capitalisation and depreciation policy | Accountant | UNRESOLVED |
| P-12 | Invoice numbering scheme (all document types) | Accountant | UNRESOLVED |
| P-13 | Approval limits | Management | UNRESOLVED |
| P-14 | Report definitions | Accountant | UNRESOLVED |
| P-15 | Rounding policy per document type | Accountant | UNRESOLVED |
| P-16 | Landed-cost allocation method (freight, duty, clearing) | Accountant | UNRESOLVED |
| P-17 | Write-off / bad debt authority and thresholds | Management + Accountant | UNRESOLVED |

## 7. Testing obligations (Phase 6 acceptance)

Every posting path must be covered by automated tests proving:

1. Debits equal credits for each event type.
2. Duplicate source events cannot post twice (idempotency).
3. Posted journals cannot be edited or deleted through any API path.
4. Reversals link to originals and preserve history.
5. Posting into a locked period is refused; reopen is permissioned and audited.
6. Subledgers (AP, AR, stock) reconcile to their GL control accounts.
7. Report totals equal journal totals for the same period.
8. A simulated failure mid-posting leaves no partial state.
9. No warehouse purchase appears twice in project cost.
10. Currency precision and rounding behave as documented at boundaries.
