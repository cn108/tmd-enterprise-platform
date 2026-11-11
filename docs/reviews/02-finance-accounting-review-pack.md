# Finance and Accounting Review Pack

**Purpose:** obtain the accountant's (and tax adviser's) decisions that every posting depends on.
**Owner of the meeting:** TMD's accountant / finance lead, with tax adviser input
**Pack version:** 1.0 — 11 November 2026
**Pre-read:** `07-accounting-events.md` §2–§6, `06-data-model.md` §4, `03-srs.md` §2.7

**How to use:** this pack presents **options and their consequences**, not recommendations. Standard accounting mechanics are described; which one TMD adopts is the accountant's decision and is recorded with a name and date. Blank cells mean "not decided".

**Why this meeting matters most:** without it, no journal can be posted. Every other module can be built and left disabled; the ledger cannot be built at all without the choices below.

---

## Agenda (proposed 2–3 hours)

| Time | Item | Output |
| --- | --- | --- |
| 0:00 | Chart of accounts mapping | Worksheet 1 completed |
| 0:40 | Financial year, periods, closing routine | P-04, Q-22b |
| 0:55 | Inventory valuation and GRNI | P-05, P-06, Q-18, Q-18b |
| 1:25 | Revenue recognition and project cost/WIP | P-07, P-08, Q-23 |
| 1:50 | Landed costs, FX, rounding | P-16, P-10, P-15, Q-20c |
| 2:10 | Tax, numbering, reporting | Worksheet 3, Worksheet 4, P-09, P-12, P-14 |
| 2:30 | Fixed assets, write-offs, opening balances | P-11, P-17, P-03 |
| 2:45 | Sign-off | Signature page |

---

## Worksheet 1 — Chart of accounts mapping (P-01)

Every posting in `07-accounting-events.md` refers to an **account role**, not an account code. Map each role to the account code and name from TMD's approved chart of accounts. Leave blank if TMD has no account for the role yet — a blank is a real outcome and blocks only the events that need it.

| Role | Account code | Account name | Notes |
| --- | --- | --- | --- |
| AR_CONTROL |  |  |  |
| AP_CONTROL |  |  |  |
| INVENTORY |  |  |  |
| GRNI (if used) |  |  |  |
| PROJECT_COST / WIP |  |  |  |
| COST_OF_SALES |  |  |  |
| REVENUE |  |  |  |
| OUTPUT_TAX |  |  |  |
| INPUT_TAX |  |  |  |
| BANK |  |  |  |
| CASH |  |  |  |
| CUSTOMER_ADVANCES |  |  |  |
| SUPPLIER_ADVANCES |  |  |  |
| BANK_FEES |  |  |  |
| FX_GAIN_LOSS |  |  |  |
| STOCK_ADJUSTMENT |  |  |  |
| SUSPENSE (temporary only) |  |  |  |
| RETAINED_EARNINGS |  |  |  |
| OPENING_BALANCE_EQUITY |  |  |  |

Attach the chart of accounts itself (a spreadsheet or list of all accounts with codes, names and types). The system imports it as configuration; I do not create accounts.

## Worksheet 2 — Financial year, periods and close (P-04)

| Question | Answer |
| --- | --- |
| Financial year end date |  |
| Number of posting periods per year (monthly / 4-4-5 / other) |  |
| Who may post into a period after it is closed (name/role)? |  |
| Who may reopen a closed period, and what evidence is required? (Q-22b) |  |
| Is a soft-close stage wanted (no new postings, corrections allowed)? | ☐ Yes ☐ No |
| Cut-off rule for a transaction dated in a closed period |  |

## Worksheet 3 — Inventory valuation (P-05, Q-18)

Three common methods. The choice changes both the balance sheet and every project's cost.

| Method | How it works | Effect when prices rise | Effect on records | Choose |
| --- | --- | --- | --- | --- |
| Specific identification | Cost tracked per unit/lot | Exact project cost | Requires lot tracking on every receipt and issue — heavier for staff | ☐ |
| FIFO | Oldest cost issued first | Lower cost of sales, higher closing stock value | Needs receipt layers per item; moderate discipline | ☐ |
| Weighted average | Running average cost per item | Smooths price swings across projects | Simplest to operate; project cost is averaged, not actual | ☐ |

Decision on method: `[ ]` plus any per-category exceptions (e.g. one method for materials, another for equipment spares): `[ ]`

Also confirm:

| Question | Answer |
| --- | --- |
| Does valuation include freight, clearing and handling? (P-16, Q-20c) | ☐ Include ☐ Exclude ☐ Include only when charged on the same invoice |
| If included, how is a landed cost allocated across lines (by value, quantity, weight)? |  |
| Revaluation/obsolescence: who writes down stock, and with what approval? |  |

## Worksheet 4 — Goods received not invoiced (P-06, Q-18b)

| Option | Posting at receipt | Posting at invoice | Consequence |
| --- | --- | --- | --- |
| A. Invoice-first (no GRNI) | No journal at receipt; stock quantity recorded only | Debit inventory, credit AP | Simplest, but the ledger lags reality while goods sit unreceived in the books |
| B. GRNI accrual | Debit inventory, credit GRNI | Debit GRNI, credit AP | Ledger reflects goods on hand; needs a GRNI account and a reconciliation report |
| C. GRNI with period-end accrual only | No journal at receipt; accrual at close | Debit inventory/accrual, credit AP | Less transactional load, more manual at close |

Choose: ☐ A ☐ B ☐ C. If B or C, confirm the GRNI/accrual account above.

## Worksheet 5 — Revenue recognition (P-07, Q-23)

| Option | Recognition point | Effect on reported revenue | Choose |
| --- | --- | --- | --- |
| A. On invoice issuance | When the customer invoice is posted | Simple; revenue can lead or lag delivery | ☐ |
| B. On milestone acceptance | When the client accepts the milestone/service | Matches delivery; requires acceptance evidence before invoicing | ☐ |
| C. On project completion | When the project closes | Conservative; delays revenue on long projects | ☐ |
| D. Stage of completion (percentage) | Measured progress | Matches long contracts; requires a measurement rule agreed upfront | ☐ |

If D, state the measurement basis: `[ ]`

Also confirm whether a separate "invoiced but not recognised" view is required for management reporting: ☐ Yes ☐ No

## Worksheet 6 — Project cost and WIP (P-08)

| Question | Answer |
| --- | --- |
| Are project costs held in WIP until invoiced, or expensed as incurred? |  |
| Are stock issues to a project expense or WIP? |  |
| Is labour costed to projects (timesheets), and at what rate? (Q-27) |  |
| Is overhead allocated to projects? If so, on what basis? |  |
| Should the project profitability report show committed cost alongside actual? | ☐ Yes ☐ No |
| Which cost categories must appear separately (materials, labour, logistics, subcontract, equipment)? |  |

## Worksheet 7 — Rounding, currency and numbering

**Rounding (P-15):** line level vs invoice level, and the rounding increment.

| Question | Answer |
| --- | --- |
| Round tax per line or per invoice? |  |
| Round line totals before summing, or sum then round? |  |
| Rounding increment (e.g. nearest kobo, nearest naira) |  |

**Currency (P-10, Q-25):**

| Question | Answer |
| --- | --- |
| Any foreign-currency purchases or sales expected in year 1? | ☐ No ☐ Yes (currencies: ) |
| If yes, which rate source and rate date? |  |
| Revaluation at period end required? | ☐ Yes ☐ No |

FX features stay **disabled** until this is answered; enabling them later is configuration, not code.

**Numbering (P-12, D-08):** the system will never let a user type a document number. Confirm the format per document type.

| Document | Format (e.g. PO/2026/0001) | Reset rule (yearly / never) |
| --- | --- | --- |
| Purchase request |  |  |
| RFQ |  |  |
| Purchase order |  |  |
| Goods received note |  |  |
| Supplier invoice (internal ref) |  |  |
| Customer invoice |  |  |
| Credit note |  |  |
| Payment |  |  |
| Receipt |  |  |
| Journal |  |  |

## Worksheet 8 — Tax configuration intake (P-09, Q-24, Q-26)

Per the brief, every setting records its **source, version, effective date, approval owner and implementation date**. The system stores these as configuration; no rate is written into code.

| Item | Value | Source document / reference | Effective from | Approved by |
| --- | --- | --- | --- | --- |
| Tax registrations held (types and numbers, or "none") |  |  |  |  |
| Tax codes to configure (code, rate, treatment) |  |  |  |  |
| Tax on sales (rate(s), exemptions) |  |  |  |  |
| Tax on purchases (recoverable? how recorded?) |  |  |  |  |
| Withholding tax on supplier payments? (Q-24c) | ☐ No ☐ Yes:  |  |  |  |
| Fields required on a valid invoice |  |  |  |  |
| E-invoicing (NRS) status: not in scope / registered / onboarding / live |  |  |  |  |
| If registered/onboarding: identifiers, channel, contact |  |  |  |  |
| Submission timing: at invoice time or batched |  |  |  |  |
| Official API documentation version held |  |  |  |  |

Until this worksheet is signed, invoice issuance is built but **fiscal submission stays switched off** with a recorded manual step (invoice marked "submitted manually, reference/date"), so nothing is silently skipped.

## Worksheet 9 — Report definitions (P-14, D-26)

| Report | Definition needed | Answer |
| --- | --- | --- |
| AP ageing | Bucket boundaries |  |
| AP ageing | Basis (due date / invoice date) |  |
| AR ageing | Bucket boundaries |  |
| AR ageing | Basis |  |
| Income statement | Groupings and subtotals (e.g. revenue, direct cost, gross margin, overheads) |  |
| Balance sheet | Groupings; current/non-current split |  |
| Project profitability | Columns and cost inclusions |  |
| Stock valuation report | Basis shown; exceptions |  |
| Tax report | Format required |  |

Attach any existing management report the accountant wants reproduced; I will match its layout where the data supports it.

## Worksheet 10 — Assets, write-offs, opening balances

| Item | Answer |
| --- | --- |
| Equipment capitalisation threshold and depreciation basis (P-11, Q-27b) |  |
| Who may approve a bad debt write-off, and up to what value? (P-17, D-25) |  |
| Opening balances: full trial balance or balances plus open items? (P-03, D-11b) |  |
| Prior-period comparatives to be loaded? (D-11a) |  |
| Named signatories for migration reconciliation? (D-11c) |  |

## Worksheet 11 — Sign-off

| ID | Policy | Decided value / choice | Approved by | Date |
| --- | --- | --- | --- | --- |
| P-01 | Chart of accounts |  |  |  |
| P-03 | Opening balances approach |  |  |  |
| P-04 | Financial year and periods |  |  |  |
| P-05 | Inventory valuation |  |  |  |
| P-06 | GRNI policy |  |  |  |
| P-07 | Revenue recognition |  |  |  |
| P-08 | Project cost / WIP |  |  |  |
| P-09 | Tax configuration |  |  |  |
| P-10 | FX policy |  |  |  |
| P-11 | Fixed assets |  |  |  |
| P-12 | Invoice numbering |  |  |  |
| P-14 | Report definitions |  |  |  |
| P-15 | Rounding |  |  |  |
| P-16 | Landed costs |  |  |  |
| P-17 | Write-off authority |  |  |  |

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Accountant / finance lead |  |  |  |
| Tax adviser (tax items only) |  |  |  |
| Managing Director (approving policy) |  |  |  |

---

## After this meeting

1. Return the filled worksheets with the chart of accounts attached.
2. I convert each choice into configuration requirements and add the posting rules to the build plan; no account code will be hard-coded.
3. Features whose policy is still blank stay disabled rather than defaulting to something plausible — for example, if revenue recognition is undecided, invoices can be issued but revenue postings wait.
4. Phase 6 (ledger) starts only when P-01, P-04 and at least P-05/P-06 are signed.
