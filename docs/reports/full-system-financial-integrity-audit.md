# Full-system financial integrity audit

**Date:** 12 November 2026
**Scope:** Double-entry accounting, invoicing, payments, banking, inventory
valuation, project costing, tax presentation and financial reporting.
**Basis:** Code inspection, automated tests, live development data inspection
and isolated restore evidence. No production ledger, bank statement or tax
filing was available.

## 1. Conclusion

The accounting design is sound and conservative: formal statements use posted
double-entry journals, not invoice totals; posting is balanced and immutable;
unapproved mappings block or warn; transaction writes are atomic. The audit
found and corrected several reporting-integrity defects during Phase 10 and the
authorization of the ledger during the full audit.

However, the live database has **no chart of accounts, no approved account-role
mappings, no posting rules, no opening balances and no posted journals**. It is
therefore impossible to verify TMD's actual financial statements. Zero figures
shown by the application are correct outputs for empty posted data, not
evidence of financial correctness.

**Financial integrity readiness: B — the engine is suitable for staged
accounting validation; production financial activation is blocked.**

## 2. Verified controls

### 2.1 Double entry and posting

- Journals are created with at least two lines and must balance; unbalanced
  journals are refused by service and database constraints.
- Posting is a controlled transition; posted journals cannot be edited.
- Reversal creates a linked reversing journal rather than mutating history.
- Periods must be open for posting; closing and reopening are permissioned
  workflows.
- Opening balances are posted through a dedicated path and require the posting
  permission.
- The isolated restore test restored 1 journal / 2 lines with debit = credit =
  ₦125.50 and confirmed the ledger remained balanced.
- Live audit: 0 posted journals, 0 unbalanced posted journals, 0 negative stock
  layers.

### 2.2 Transaction atomicity

Atomic transactions were added to invoice, credit/debit note, payment, purchase
request, quotation, purchase order, opening balance and posting-rule
create/update paths. A rollback regression test proves a failed invoice write
does not leave a partial header or lines. The absence of partial records after
validation errors was rechecked.

### 2.3 Reporting integrity

| Risk | Control |
| --- | --- |
| P&L built from invoice totals | Statements derive from posted journal lines via accounting services |
| Purchase orders counted as expense | PO values are labelled commitments |
| Gross profit replaced by net result | Gross profit only when an approved `COST_OF_SALES` mapping exists; otherwise unavailable |
| Cash flow guessed from account type | Approved account-role classification; unmapped counterparts become **Unclassified**, report marked incomplete |
| Mixed currencies added | Per-currency totals; mixed totals withheld |
| Receivables/payables presented as ledger balances | Labelled approved-document balances |
| Inventory valuation invented | Unavailable when no valuation policy exists |
| Draft journals included | Only posted journals in formal statements; journal register labels status |
| CSV formula injection | Formula-leading values neutralised |
| PDF silent truncation | Explicit truncation notice; CSV remains complete |

Regression tests cover posted-only statements, trial balance, cash-flow role
mapping and incompleteness, gross-profit requirement, ageing boundaries,
inventory availability, overview separation and CSV injection.

### 2.4 Invoice and payment controls

- Supplier/customer invoice and note totals use `Decimal` fields.
- Payments and allocations are permissioned and atomic.
- Approval is separate from creation; self-approval restrictions are enforced
  where the workflow requires them.
- Duplicate approvals and invalid state transitions return conflicts rather
  than creating duplicate postings.
- No live invoice issuance, payment execution or NRS submission is authorised.

### 2.5 Inventory and project costing

- Stock layers use four-decimal quantities and database checks preventing
  negative remaining quantity.
- Valuation requires an approved method/policy.
- Issues, transfers, returns, adjustments and damage are separate documents;
  reporting does not count receipts and issues as independent expenses.
- Project costs require approval and are aggregated from approved cost records;
  commitments are reported separately from actual cost.
- Project margin is labelled an estimate; revenue recognition is not calculated.

### 2.6 Banking

Bank statements and reconciliation records exist; matching does not create
ledger entries without the accounting posting path. Bank account numbers are
encrypted. No live bank transfer or bank execution is enabled.

## 3. Findings

| ID | Severity | Finding | State |
| --- | --- | --- | --- |
| FI-01 | Critical | Any authenticated employee could read the general ledger and financial statements | Fixed; permission regression test added |
| FI-02 | High | Gross profit was copied from net result when no cost-of-sales mapping existed | Fixed; gross profit now unavailable without an approved mapping |
| FI-03 | High | Cash flow classified every asset counterpart as investing, including receivables | Fixed; approved role mapping + Unclassified warning + incomplete flag |
| FI-04 | High | Receivable/payable and tax totals silently added different currencies | Fixed; per-currency presentation and totals withheld |
| FI-05 | High | Live ledger has no approved accounting configuration, so no statement can be certified | Open; Finance Controller/management blocker |
| FI-06 | Medium | No foreign-currency conversion or revaluation | Open; out of scope until policy supplied |
| FI-07 | Medium | Tax reporting presents approved-document VAT/WHT totals, not a tax return | Accepted boundary; labelled in UI and manuals |
| FI-08 | Medium | No live interest, lease accounting or revenue-recognition calculations | Deliberately excluded; requires accounting policy |
| FI-09 | Medium | No production-scale reconciliation of opening balances | Open; migration blocker |
| FI-10 | Low | Ageing labels were inconsistent | Fixed |

## 4. Live data audit

Executed against the development database on 12 November 2026:

| Query | Result |
| --- | ---: |
| Journal entries | 0 |
| Posted journals | 0 |
| Journal lines | 0 |
| Unbalanced posted journals | 0 |
| Negative stock layers | 0 |
| Accounts | 0 |
| Supplier invoices | 4 |
| Customer invoices | 3 |

Interpretation: document records exist, but there are no ledger entries. Any
formal financial statement therefore correctly shows ₦0.00 with warnings. This
must not be presented to management as TMD's actual financial position.

## 5. Opening balances and migration

The migration templates include an `opening_trial_balance.csv` and bank/cash
balances. Structural validation passed 11 templates / 12 rows with 0 errors, but:

- no source-document reconciliation was performed;
- no trial balance was approved by a Finance Controller;
- no opening balances were imported or posted;
- no financial migration is authorised.

Financial migration remains blocked until a qualified accountant reviews the
opening trial balance, mappings, tax treatment and cut-off transactions.

## 6. Segregation of duties and approvals

- Account/mapping/posting-rule approvals are separate permissions.
- Journal approval and posting are separate permissions.
- Bank account change approval is separate and self-approval is refused.
- Invoice/payment approvals are separate permissions.
- Role matrix grants are provisional and require management approval.

Residual: MFA is not enforced, so a single stolen password could satisfy an
approval step. This is a security control weakness affecting financial approval
integrity and is recorded in the security audit.

## 7. Verification performed

| Check | Result |
| --- | --- |
| Backend suite | 295 passed, including financial/reporting/rollback tests |
| Migration drift | None |
| Restore ledger balance | PASS (₦125.50 debit/credit) |
| Live unbalanced journals | 0 |
| Live negative stock layers | 0 |
| Reporting permissions | Enforced; 403 regression test |
| Invoice rollback | No partial records |
| Production financial activation | Not performed |

## 8. Required approvals before financial use

1. Appoint a Finance Controller and record delegated authority.
2. Approve the chart of accounts and account-role mappings.
3. Approve posting rules and tax policy, including VAT/WHT treatment.
4. Approve opening balances and the cut-off date.
5. Reconcile migrated supplier/customer invoices to source documents.
6. Approve the inventory valuation method.
7. Authorise any live bank/NRS integration separately.
8. Record UAT sign-off for financial reports.

## 9. Final financial-integrity statement

The code is designed not to invent financial results and correctly refuses to
present incomplete statements as complete. The corrected defects were real
reporting risks. The absence of approved accounting data is the dominant
financial blocker.

**No assurance is given that TMD's actual financial statements are complete or
accurate until the accounting configuration, opening balances and reconciliation
above are completed and approved.**
