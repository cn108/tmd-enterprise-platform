# Configuration report — provisional accounting and governance decisions

**Version:** 1.0-provisional
**Effective date:** 12 November 2026
**Status:** Applied as configuration; **not** a verified historical accounting record and **not** approved for production posting.
**Generated from:** `manage.py apply_provisional_governance`
**Machine-readable copy:** `GET /api/v1/governance/configuration-report/`

## 1. Scope and disclaimer

This report records the provisional decisions supplied on 12 November 2026. They are implemented as versioned configuration, not as a claim that TMD's historical books, account codes, tax positions or opening balances have been verified.

- No account code, account balance, bank balance, tax liability, tax rate, opening balance or historical transaction has been seeded.
- No tax return has been filed and no statutory accounting approval is claimed.
- Production financial posting remains disabled pending review by a qualified Finance Controller.
- The nine-role reduction and the ₦5,000,000 band interpretation are explicitly recorded as assumptions requiring confirmation.

## 2. Decisions implemented

| # | Decision | Implementation | State |
|---|---|---|---|
| 1 | Nine-role permission model plus Finance Controller | Ten Django groups: the nine operational roles plus an unassigned Finance Controller; no user assigned | Provisional |
| 2 | ₦5,000,000 approval threshold | Purchase order and budget bands: one approval below, two at or above; purchase requests one approval | Provisional |
| 3 | Independent approval / maker-checker | Creator or requester barred; same person cannot decide twice; permission still required; approval records persisted | Implemented for requests, orders, budgets, journals, accounts, rules and mapping approval |
| 4 | Proposed chart-of-accounts structure | 19 configurable account roles, effective-dated account-role mappings, role-based posting-rule lines | Structure implemented; **no accounts or mappings supplied** |
| 5 | Monthly accounting periods and controlled closure | `POST /api/v1/fiscal-years/{id}/create-periods/` creates calendar-month periods; close and reopen are separate permissioned actions with reasons | Implemented; no fiscal year or period seeded |
| 6 | Weighted average ordinary stock; specific identification for traceable items | Policy method `weighted_average`; items with batch or serial tracking are costed by specific identification; method locked after movements | Implemented; provisional |
| 7 | GRNI accrual | Event E-02 posts debit `INVENTORY` / credit `GRNI` through a role-based rule | Rule seeded unapproved; mapping outstanding |
| 8 | Events E-02, E-04, E-16, E-21, E-22 | Inventory outbox; opening-balance document; controlled reopen plus adjustment journal | E-02/E-04/E-16 queue; E-21/E-22 use controlled documents; posting blocked pending review |
| 9 | VAT, Tax IDs, sequential invoice numbers, WHT, NRS | Versioned tax configuration, tax profile, numbering scheme/allocator, Stage 7A invoice and payment approvals | Stage 7A implemented as test-only; no rate, Tax ID or NRS credential supplied |
| 10 | Immutable journals, audit, payment approvals, stock history | PostgreSQL triggers on journals, stock movements and audit events; hash-chained audit; Stage 7A payment approvals | Ledger posting and bank execution remain disabled |

## 3. The nine operational roles and the Finance Controller

| Role | Intended authority |
|---|---|
| System Administrator | Users, roles, master data and accounting configuration; **no transaction approval by default** |
| Management | Read oversight; approve requests, orders, budgets and journals; close or reopen periods |
| Accountant | Chart, role mappings, posting rules, journals, periods, opening balances, tax configuration and reports |
| Finance Officer | Read access to financial, procurement, inventory and project records; no posting or approval |
| Procurement Officer | Requests, RFQs, quotations, orders and supplier records; no approval |
| Project Manager | Projects, budgets, milestones, project requests and contracts; no approval of own budget |
| Storekeeper | Receipts, transfers, issues, returns, adjustments, damages, counts and reservations |
| Operations / HSE | Documents, compliance and read access to operational records |
| Auditor | Read-only across modules plus the audit trail |

The Phase 7 instruction creates a separate **Finance Controller** role for the review and approval duties that cannot be assigned while TMD has no appointed accountant. It is created as a permission bundle but **no user is assigned to it**. The nine operational roles above remain otherwise unchanged.

**Assumption requiring confirmation:** the earlier draft contained eleven roles. The nine-role instruction was interpreted by folding HSE into **Operations / HSE** and treating **Requester** as a capability of every authenticated employee rather than a role. The Finance Controller is an additional unassigned control role, not a tenth operational role. No user has been assigned any role.

## 4. Approval bands

| Document | Band (NGN) | Approvals |
|---|---|---|
| Purchase order | 0 – below 5,000,000 | 1 |
| Purchase order | 5,000,000 and above | 2 |
| Project budget | 0 – below 5,000,000 | 1 |
| Project budget | 5,000,000 and above | 2 |
| Purchase request | All amounts (no value on request lines) | 1 |
| Supplier invoice | 0 – below 5,000,000 | 1 |
| Supplier invoice | 5,000,000 and above | 2 |
| Customer invoice | 0 – below 5,000,000 | 1 |
| Customer invoice | 5,000,000 and above | 2 |
| Supplier payment | 0 – below 5,000,000 | 1 |
| Supplier payment | 5,000,000 and above | 2 |
| Credit or debit note | 0 – below 5,000,000 | 1 |
| Credit or debit note | 5,000,000 and above | 2 |

The approval service enforces:

- the actor must hold the document permission;
- the creator or requester cannot approve;
- the same person cannot record two decisions on one document;
- a rejected decision ends the approval;
- each decision is written to `ApprovalRecord` and the audit trail.

**Outstanding:** the Stage 7A invoice, note and payment workflows exercise these bands, but all documents remain test-only. Stock adjustments and write-offs still use permission plus audit, not a two-person draft/approve workflow.

## 5. Account roles and posting

The 19 roles are:

`AR_CONTROL`, `AP_CONTROL`, `INVENTORY`, `GRNI`, `PROJECT_COST`, `COST_OF_SALES`, `REVENUE`, `OUTPUT_TAX`, `INPUT_TAX`, `BANK`, `CASH`, `CUSTOMER_ADVANCES`, `SUPPLIER_ADVANCES`, `BANK_FEES`, `FX_GAIN_LOSS`, `STOCK_ADJUSTMENT`, `SUSPENSE`, `RETAINED_EARNINGS`, `OPENING_BALANCE_EQUITY`.

A mapping must point to an approved, active account and must itself be approved by a different person. A posting rule may reference an account directly (legacy behaviour) or an account role. A role-based rule cannot be approved until every role has an approved mapping.

**No account exists.** Consequently no mapping can be approved and no role-based rule can be approved or posted.

## 6. Financial events

| Event | Trigger | Debit → credit | Current state |
|---|---|---|---|
| E-02 | Accepted warehouse GRN | `INVENTORY` → `GRNI` | Outbox entry created; rule awaiting mappings/review |
| E-04 | Stock issue to a project | `PROJECT_COST` → `INVENTORY` | Outbox entry created; rule awaiting mappings/review |
| E-16 | Adjustment, damage or count variance | Loss: `STOCK_ADJUSTMENT` → `INVENTORY`; gain: `INVENTORY` → `STOCK_ADJUSTMENT` | Outbox entry created; rules awaiting mappings/review |
| E-21 | Opening balance document posted | Accountant-supplied lines | Journal created; event recorded as posted |
| E-22 | Closed period reopened, then reasoned adjustment journal posted | Accountant-supplied adjustment | Reopen audited; adjustment uses the normal journal lifecycle |

Warehouse-to-project **transfers** and **reservations** do not create a consumption event. Only a project issue creates E-04. This preserves the instruction that transfers and reservations are not consumed expenditure.

Automatic posting is doubly gated:

1. every posting rule must be approved and every role mapped;
2. `AccountingSettings.posting_reviewed_at` must record the Finance Controller review.

Until both are true, events remain in the outbox with an explicit error; they are not silently dropped.

## 7. Tax and numbering

- `TaxConfiguration` stores versioned VAT/WHT/other rates, jurisdiction, registration number, effective dates and review status. No rate is seeded.
- `TaxProfile` stores the legal tax identity, Tax Identification Number, VAT registration flag and NRS status/environment. No value is seeded.
- A reviewed tax configuration cannot be edited; a new rate is a new record.
- The reviewer cannot be the creator.
- `NumberingScheme` and `allocate_document_number()` provide sequential, configurable numbering. The provisional customer-invoice scheme uses `INV-YYYY-NNNNNN`; Stage 7A drafts use it, but the format still needs D-08 approval.
- NRS e-invoicing is **not integrated**. No credentials, onboarding status or API version was supplied, and no submission is attempted.

## 8. Immutability and audit

| Control | Implementation |
|---|---|
| Posted journals | No update/delete API; PostgreSQL trigger refuses `UPDATE`/`DELETE` on posted journals and their lines |
| Stock movements | PostgreSQL trigger refuses `UPDATE`/`DELETE` |
| Audit events | Hash-chained append-only table; PostgreSQL trigger refuses `UPDATE`/`DELETE` |
| Approval decisions | Append-only records; duplicate person refused |
| Role/user changes | Written to the audit trail |
| Document downloads | Written to the audit trail |
| Tax review | Written to the audit trail |

Payment approvals and recording exist in Stage 7A, but recording an external payment is not execution and no bank integration exists.

## 9. Outstanding controls

1. No account has been created, so no account-role mapping is approved.
2. No opening balances, bank balances or tax liabilities have been entered.
3. No user has been assigned to the nine operational roles or the Finance Controller role.
4. No qualified Finance Controller has recorded the posting review.
5. No VAT or WHT rate, Tax Identification Number or NRS credential has been supplied.
6. No tax configuration has been reviewed by a second person.
7. Stage 7A invoice, note and payment modules exist as test-only workflows; ledger posting, live issuance and bank execution are blocked.
8. Stock adjustments, damages and counts are permission-gated and audited, but do not yet require a second approver.
9. The nine-role reduction and threshold interpretation need written confirmation.
10. The provisional policies have a review date of **28 February 2027** recorded in the seed command; that date is a review prompt, not an approval.

## 10. Blocked features

| Feature | Why blocked |
|---|---|
| Automatic posting of E-02/E-04/E-16 | No approved account mappings and no Finance Controller review |
| Production general ledger | Chart, opening balances and posting review absent |
| Supplier invoice and payment posting | Stage 7A capture, matching, approval and allocation exist; ledger posting and payment execution remain Stage 7B |
| Customer invoice issuance | Stage 7A drafting, approval and test PDFs exist; issuing a live invoice remains Stage 7B |
| NRS e-invoicing | Adapter state and feature flag exist; no onboarding, credentials, endpoint or API version |
| VAT/WHT returns | No reviewed rates or statutory filing authority |
| Statutory accounting approval | No signed accounts or professional opinion |
| Multi-currency and period reopening policy | FX policy and reopen controls remain provisional |

## 11. Assumptions requiring professional review

1. **Threshold interpretation:** one approval below ₦5,000,000 and two independent approvals at or above it. Management must confirm whether the trigger is the order value, the request estimate, or the budget total; only order and budget totals exist today.
2. **Nine-role reduction:** HSE is folded into Operations / HSE; Requester is not a separate role.
3. **Traceability:** an item is treated as traceable when `tracks_batches` or `tracks_serials` is true.
4. **Invoice numbering:** `INV-YYYY-NNNNNN` is provisional and is not attached to an invoice record.
5. **Monthly periods:** calendar months are clipped to the fiscal year; no 4-4-5 calendar is implied.
6. **Tax review:** the tax configuration is provisional until a second reviewer with tax competence approves it.
7. **Opening balance format:** the portal accepts account-level debit/credit lines; no open-item or comparative load has been defined.

## 12. Review checklist for the Finance Controller

- [ ] Confirm the nine operational roles and the unassigned Finance Controller role, and name at least one holder for each.
- [ ] Confirm the ₦5,000,000 band and which document value it applies to.
- [ ] Supply the chart of accounts (codes, names, types) and approve it.
- [ ] Map every account role to an approved account and approve each mapping by a second person.
- [ ] Supply opening balances and bank balances; do not invent them.
- [ ] Confirm the inventory method and the traceable-item rule.
- [ ] Confirm the GRNI policy and account.
- [ ] Review and approve the four posting rules.
- [ ] Enter and review VAT/WHT rates, Tax ID and NRS onboarding details.
- [ ] Record `POST /api/v1/accounting-settings/` with review notes to unlock automatic posting.
- [ ] Sign this report and update the decision register from **PROVISIONAL** to **CONFIRMED**.

## 13. Verification

```
backend:  224 tests pass; ruff clean
frontend: build succeeds; lint clean; 39 tests pass
migrations: accounting.0003, accounting.0004, core.0001–0003, inventory.0002–0003
seed:      manage.py apply_provisional_governance
```

The seed command is idempotent and seeds only policy, roles, account-role names, approval bands, posting-rule definitions and a provisional numbering scheme. It seeds **no account, balance, rate, Tax ID, NRS credential or historical transaction**.

## 14. Final statement

The provisional decisions are implemented as configuration and controls. They are **not** verified historical TMD accounting records, **not** a statutory filing, and **not** authority to activate live posting. A qualified Finance Controller must review the mappings, opening balances and tax settings before production use.
