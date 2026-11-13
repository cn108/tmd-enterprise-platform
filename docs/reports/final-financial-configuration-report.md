# TMD Enterprise System — Final Financial Configuration Report

**Date:** 13 November 2026  
**Prepared for:** TICO MCDON LIMITED Managing Director and an external Nigerian qualified accountant/tax adviser  
**Status:** **configuration structure implemented; company policy NOT approved; production posting disabled**  
**Accounting authority:** no approval is claimed by this report

## 1. Purpose and boundary

This pack describes the accounting mechanisms implemented in the application and the decisions that must be made before real TMD transactions are posted. It does **not** invent a chart of accounts, account balances, tax rates, opening balances, revenue policy or professional approval.

The application currently contains synthetic QA accounts and tax data for testing only. They must never be imported into, or represented as, TMD's real ledger.

Production remains fail-closed:

- `InvoiceSettings.test_mode = True`
- `can_issue = False`
- `activated_at = None`
- NRS disabled
- automatic posting requires approved mappings and a recorded Finance Controller review
- WHT, notes and foreign-currency posting are refused

## 2. Chart of accounts and account roles

The chart is configurable. Accounts have a code, name, type, normal balance, approval timestamp and active flag. No real account has been supplied.

Nineteen account roles are defined:

`AR_CONTROL`, `AP_CONTROL`, `INVENTORY`, `GRNI`, `PROJECT_COST`, `COST_OF_SALES`, `REVENUE`, `OUTPUT_TAX`, `INPUT_TAX`, `BANK`, `CASH`, `CUSTOMER_ADVANCES`, `SUPPLIER_ADVANCES`, `BANK_FEES`, `FX_GAIN_LOSS`, `STOCK_ADJUSTMENT`, `SUSPENSE`, `RETAINED_EARNINGS`, `OPENING_BALANCE_EQUITY`.

A mapping must point to an approved, active account. The mapping must be approved by a different user. A role-based posting rule cannot be approved until every role it uses is mapped. This prevents a posting rule from silently inventing a ledger account.

**Required from TMD:** the real chart with codes and types, then one approved mapping per role actually used. Unused roles must still be documented as intentionally unused.

## 3. Implemented posting events

| Event                                  | Debit                                                                | Credit                           | Current state                                               |
| -------------------------------------- | -------------------------------------------------------------------- | -------------------------------- | ----------------------------------------------------------- |
| Supplier invoice (approved, activated) | Inventory / project cost / cost of sales, plus recoverable input VAT | AP control                       | Implemented; production activation off                      |
| Customer invoice (approved, activated) | AR control                                                           | Revenue and output VAT           | Implemented; production activation off                      |
| Supplier payment                       | AP control or supplier advances                                      | Bank or cash                     | Implemented; recording/posting tested, no bank execution    |
| Customer receipt                       | Bank or cash                                                         | AR control and customer advances | Implemented; ledger posting, allocation and reversal tested |
| GRNI receipt (E-02)                    | Inventory                                                            | GRNI                             | Outbox; rule/mapping/review required                        |
| Project stock issue (E-04)             | Project cost                                                         | Inventory                        | Outbox; rule/mapping/review required                        |
| Stock adjustment/count variance (E-16) | Stock adjustment or inventory                                        | Inventory or stock adjustment    | Outbox; rules/mapping/review required                       |
| Opening balance (E-21)                 | Accountant-supplied lines                                            | Accountant-supplied lines        | Controlled document; no real balances supplied              |
| Period reopen/adjustment (E-22)        | Adjustment lines                                                     | Adjustment lines                 | Controlled reopen and journal lifecycle                     |

Every posted journal must balance, belongs to an open period, and is immutable. Invoice, payment and receipt posting use transactional locks and idempotency so a retry returns the original journal rather than creating a second one.

## 4. Approval and segregation

Provisional policy record:

- below ₦5,000,000: one approval;
- at or above ₦5,000,000: two independent approvals;
- creator/requester cannot approve;
- the same person cannot record two decisions on the same document;
- rejection ends the approval;
- approval records are append-only and audited.

The ₦5,000,000 band and the document value it applies to (request estimate, order value or budget) are **provisional** and require written confirmation. The ten-role matrix, including the absence of a separate General Requester role, also requires signature.

## 5. Tax configuration — verified references, not an opinion

Nigerian tax law changed with the Nigeria Tax Act 2025 and Nigeria Tax Administration Act 2025, effective 1 January 2026. The application does not encode a legal opinion. The following are reference points for the external adviser:

- The Nigeria Revenue Service states the standard VAT rate is **7.5%**, with zero-rated and exempt supplies; VAT returns are due by the 21st day of the following month for taxable persons above the exemption threshold. [NRS VAT guidance](https://www.nrs.gov.ng/tax-information/value-added-tax)
- The Nigeria Revenue Service issued Information Circular No. 2026/05 on 29 June 2026 covering VAT administration, time/place of supply, input/output VAT, VAT withholding agents and the Electronic Fiscal System. [KPMG summary](https://kpmg.com/ng/en/insights/2026/10/nigerias-vat-reset.html)
- WHT is transaction-specific. Current professional summaries show 10% for specified resident corporate payments and 10% for non-resident corporate payments in the referenced categories, subject to exemptions, thresholds, treaty relief and the Deduction of Tax at Source (Withholding) Regulations 2024. There is no single WHT rate for all supplier payments. [PwC Nigeria WHT summary](https://taxsummaries.pwc.com/nigeria/corporate/withholding-taxes)
- NRS e-invoicing/EFS (Merchant Buyer Solution) is being phased by turnover. Large taxpayers (above ₦5 billion) were in post-go-live/enforcement during 2026; medium taxpayers (₦1–5 billion) had a 1 July 2026 go-live with enforcement from January–March 2027; emerging taxpayers (below ₦1 billion) are scheduled from 1 July 2027. TMD's turnover category is not established in this repository. [NRS public notice summary](https://kpmg.com/kpmg-us/content/dam/kpmg/taxnewsflash/pdf/2026/02/nigeria-feb18-2026.pdf)

**No VAT rate, WHT code, tax ID, NRS credential or tax treatment is seeded as approved company policy.** The external adviser must confirm TMD's registration status, turnover band, VAT treatment by supply, WHT treatment by payment type, treaty position, filing obligations and e-invoicing go-live date.

## 6. Revenue, inventory, GRNI and project costing

| Area                | Implemented mechanism                                                                                                      | Decision required                                                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Revenue recognition | Invoice-date receivable/revenue/output VAT when an approved invoice is posted                                              | Confirm whether delivery/acceptance, milestones, deferred revenue or retention applies                  |
| Inventory valuation | Weighted average for ordinary stock; specific identification where batch/serial tracking applies                           | Confirm method and any write-down policy                                                                |
| GRNI                | Receipt creates an inventory/GRNI event, held in outbox until rules/mapping/review exist                                   | Confirm GRNI account and reversal at invoice matching                                                   |
| Project cost        | Approved supplier invoices, project stock issues and approved direct costs become actual cost; open POs remain commitments | Confirm cost classification and whether project issues create a separate committed/consumed distinction |
| Cost of sales       | Supplier invoice lines classified to inventory, project cost or cost of sales                                              | Approve line-level direct/indirect/capital/service treatment                                            |

No revenue is recognised merely because a quotation, order or estimate exists.

## 7. Periods, numbering, rounding and opening balances

- Fiscal years and calendar-month periods are configurable. Closing and reopening are permissioned actions with reasons and audit.
- A posted journal cannot enter a closed period; a receipt reversal uses the current open period and is blocked if that period is closed.
- Customer invoice numbering is a configurable scheme; the provisional format is `INV-YYYY-NNNNNN`. It requires approval before live issuance.
- Money uses `Decimal` and is quantised at posting/document boundaries; the rounding policy and treatment of line-level discounts require written approval.
- Opening balances use a controlled document, not a direct database edit. They must reconcile to signed bank, supplier, customer, inventory and tax records.

## 8. Credit/debit notes, WHT and FX — deliberately blocked

### Credit/debit notes

Document workflow, approval, balances and PDFs are implemented. No note journal exists because the following are unapproved:

- cost/revenue reversal classification by line;
- output/input VAT reversal and tax point;
- treatment when the original invoice is already posted (adjustment or reversal plus re-post);
- whether a note may post in a different period;
- numbering and tax sequence for debit notes.

The system refuses gross invoice/payment posting when an approved note exists. This is safer than creating a ledger that disagrees with the document.

### WHT

WHT totals and tax codes exist on invoice lines. Posting is refused. Required decisions:

- supplier/customer WHT categories and rates;
- withholding point (invoice approval, payment or remittance);
- WHT payable/receivable account roles and subledger;
- partial payment, credit note and FX interaction;
- remittance return, certificate and evidence;
- customer deduction treatment and statement presentation.

### Foreign currency

Document currency is captured, but there is no approved FX rate source, realised/unrealised gain/loss policy or revaluation process. Posting is refused.

## 9. Financial reporting rules

- Formal statements are computed from **posted journal lines**, not invoice totals.
- The income statement excludes period-close journals; the balance sheet includes posted closing entries and the unclosed current result.
- Reports warn when the chart, mappings, bank links or tax configuration are incomplete.
- Trial balance, general ledger, cash flow, receivables/payables ageing, journal register and tax reports are available.
- Customer statements are generated from approved invoices, approved notes and receipt allocations.
- A report is not final merely because it renders; completeness warnings must be resolved or accepted by the Finance Controller.

## 10. Decision and sign-off register

| #    | Decision                       | Responsible                              | Options / required evidence                                                 | State    |
| ---- | ------------------------------ | ---------------------------------------- | --------------------------------------------------------------------------- | -------- |
| F-01 | Real chart of accounts         | External accountant / Finance Controller | Signed codes, names, types, normal balances                                 | **OPEN** |
| F-02 | Nineteen account-role mappings | Finance Controller                       | Approved, effective mapping per used role; second-person approval           | **OPEN** |
| F-03 | Posting rules                  | Finance Controller                       | Approve invoice, payment, receipt, note, GRNI, project and adjustment rules | **OPEN** |
| F-04 | VAT treatment                  | Tax adviser                              | Registration status, rate by supply, zero/exempt, input recovery, filing    | **OPEN** |
| F-05 | WHT treatment                  | Tax adviser / Finance Controller         | Category rates, withholding point, accounts, remittance, certificates       | **OPEN** |
| F-06 | NRS/e-invoicing                | Managing Director / Tax adviser          | Turnover band, onboarding, access point, credentials, go-live               | **OPEN** |
| F-07 | Revenue recognition            | MD / Finance Controller                  | Invoice date vs delivery/milestone/deferred/retention                       | **OPEN** |
| F-08 | Inventory valuation            | Finance Controller                       | Weighted average/specific identification; write-down policy                 | **OPEN** |
| F-09 | GRNI                           | Finance Controller                       | Account, matching/reversal and ageing                                       | **OPEN** |
| F-10 | Project costing                | Finance Controller / Project Manager     | Cost classification, commitments, capitalization                            | **OPEN** |
| F-11 | Approval bands and delegates   | Managing Director                        | Confirm ₦5,000,000 band, document basis, named delegates                    | **OPEN** |
| F-12 | Invoice numbering and rounding | Finance Controller                       | Format, sequence, rounding, discounts                                       | **OPEN** |
| F-13 | Opening balances               | Finance Controller / MD                  | Signed trial balance reconciled to bank/AP/AR/stock                         | **OPEN** |
| F-14 | Note posting policy            | Finance Controller / Tax adviser         | Classification, tax point, reversal, period                                 | **OPEN** |
| F-15 | Foreign-currency policy        | Finance Controller                       | Rate source, gain/loss, revaluation                                         | **OPEN** |

## 11. Review checklist for the external accountant/tax adviser

- [ ] Read this report and the provisional configuration report.
- [ ] Confirm TMD's legal name, RC number, TIN, VAT registration and reporting currency.
- [ ] Approve or replace the chart of accounts and all role mappings.
- [ ] Confirm the VAT and WHT positions against the Nigeria Tax Act 2025 and current NRS guidance.
- [ ] Confirm the e-invoicing turnover category and required go-live date.
- [ ] Approve revenue, inventory, GRNI and project-cost policies.
- [ ] Approve approval bands, invoice numbering and rounding.
- [ ] Review the opening trial balance and reconciliation evidence.
- [ ] Record the review in the application and sign this report.
- [ ] State any matter that must remain disabled.

## 12. Sign-off

| Role                                | Name | Decision                          | Date | Signature |
| ----------------------------------- | ---- | --------------------------------- | ---- | --------- |
| External qualified accountant       |      | Chart/mappings/reporting approved |      |           |
| External tax adviser                |      | VAT/WHT/NRS position approved     |      |           |
| Finance Controller (or MD delegate) |      | Posting review recorded           |      |           |
| Managing Director                   |      | Financial policy approved         |      |           |

**No row may be completed by the software developer on another person's behalf.**
