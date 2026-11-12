# Stage 7B activation checklist

**Date prepared:** 12 November 2026
**Status:** NOT READY FOR ACTIVATION
**Current control state:** `InvoiceSettings.test_mode = True`; `activated_at = None`; no Finance Controller is assigned.
**Purpose:** provide the ordered, evidence-based route from Stage 7A test invoicing to authorised live invoice issuance and ledger posting.

Passing tests is **not** evidence that Stage 7B may be activated. Every P0 item below needs an owner, an evidence artefact, and a named approval before the activation endpoint is called.

---

## 1. Activation rule

Do not activate until:

1. All ten `ACTIVATION_GATES` in `backend/apps/invoicing/services.py` are true.
2. `AccountingSettings.posting_reviewed_at` is recorded.
3. Company legal name and Tax Identification Number are populated.
4. The active customer-invoice numbering scheme has `review_status = reviewed`.
5. The tax profile has `review_status = reviewed`.
6. An NRS environment is recorded if NRS is enabled.
7. Written activation notes and management authorisation are attached.
8. All P1 go-live controls are complete or separately accepted in writing by management.

Activation is performed only through:

```text
POST /api/v1/invoice-settings/{id}/activate/
```

with the checked gates and activation notes. Do not edit `test_mode` through SQL, fixtures or the ordinary settings endpoint.

---

## 2. Priority definitions

| Priority | Meaning | Consequence if incomplete |
|---|---|---|
| **P0** | Hard activation blocker | Live issuance must not be enabled |
| **P1** | Production go-live control | Activation is technically possible, but live use is not safe or authorised |
| **P2** | Post-activation improvement | Can follow controlled live use |

---

## 3. P0 — hard blockers

Work in the order shown. Items 3–7 can run partly in parallel once the Finance Controller and chart are agreed.

| # | Priority | Work item | Owner | Required evidence | Depends on / gate |
|---|---|---|---|---|---|
| P0-01 | Critical | Appoint a qualified Finance Controller and confirm the nine-role authority matrix, named role holders and the ₦5,000,000 approval band | Managing Director / Management | Signed role-matrix decision; named holders for every operational role and Finance Controller; user-role assignment export; approved approval-band wording; evidence that the dual-approval path was exercised | Gate: `management_roles_approved` |
| P0-02 | Critical | Approve company legal details and the production invoice template | Management with Accountant | Signed company-details sheet covering legal name, registered address, Tax Identification Number, invoice footer and authorised signatory; approved sample PDF; matching values recorded in `InvoiceSettings` | Gate: `company_legal_details_recorded` |
| P0-03 | Critical | Approve the chart of accounts and all account-role mappings | Accountant, independently approved by Finance Controller | Full chart of accounts; one approved account for every account role (19 roles); second-person approval record; mapping export; zero unmapped roles | Gate: `chart_and_mappings_approved` |
| P0-04 | Critical | Approve the posting rules for invoices, notes and payments | Accountant / Finance Controller | Signed rule table for AP, AR, input VAT, output VAT, WHT and invoice journals; balanced sample journal per rule; rule IDs and effective dates; evidence from a staging posting and reversal | P0-03; gate: `posting_rules_approved` |
| P0-05 | Critical | Approve VAT/WHT rates, Tax ID, tax treatment and the WHT basis | Tax adviser / Accountant | Reviewed rate schedule with effective dates; Tax ID; treatment of zero-rated, exempt and out-of-scope lines; WHT base and remittance owner; `TaxProfile.review_status = reviewed`; evidence that every active tax code is reviewed or explicitly retired | P0-02; gate: `vat_and_wht_reviewed` |
| P0-06 | Critical | Approve invoice numbering and rounding policies (D-08 and D-23) | Accountant | Signed numbering decision; active `customer_invoice` scheme with `review_status = reviewed`; cancellation/no-reuse rule; rounding decision per document type; samples showing no duplicate or reused numbers | Gate: `numbering_and_rounding_approved` |
| P0-07 | Critical | Load and approve opening balances, supplier/customer open items, bank balances and inventory values | Finance Controller with Finance Officer, Stores and Accountant | Signed opening trial balance; AP/AR open-item listing; reconciled bank statements; inventory valuation by warehouse/item; import and reconciliation report with no unexplained differences; evidence that debits equal credits | P0-03; gates: `opening_balances_loaded`, `bank_and_inventory_opening_loaded` |
| P0-08 | Critical | Record the Finance Controller's posting review | Finance Controller | Completed review memo; `AccountingSettings.posting_reviewed_at`; reviewer identity and notes recorded; review covers chart, mappings, posting rules, tax treatment, opening balances and report output | P0-03 to P0-07; gate: `finance_review_recorded` |
| P0-09 | Critical | Obtain written management authorisation for activation | Managing Director / Management | Signed authorisation naming the activation date, scope, excluded functions, rollback owner and support contact; explicit statement that NRS, bank execution and real payments remain disabled unless separately authorised | P0-01 to P0-08; gate: `management_go_live_authorised` |
| P0-10 | Critical | Run the activation in staging and record the result | Finance Controller with System Administrator / technical owner | Screenshot or API receipt of the activation response; `invoice_settings.activated` audit event; all blockers cleared; post-activation smoke test; test documents cleared from the intended production environment | P0-01 to P0-09 |

### P0 exit criteria

- [ ] All ten activation gates are true.
- [ ] The activation endpoint returns success.
- [ ] The audit event names the activating user and timestamp.
- [ ] A test invoice can be issued and posted into a balanced journal.
- [ ] Reversal of that test journal is balanced and traceable.
- [ ] No test document remains in the environment intended for live customers.
- [ ] Management has signed the activation record.

---

## 4. P1 — production go-live controls

These do not prevent the activation API from returning success, but live financial use must not begin until they are complete or formally accepted.

| # | Priority | Work item | Owner | Required evidence |
|---|---|---|---|---|
| P1-01 | High | Complete departmental UAT and obtain written sign-off | Department leads / Management | UAT scripts, defect log, sign-off from procurement, warehouse, finance, projects, banking and reporting leads |
| P1-02 | High | Establish production host, domain, DNS and TLS | IT / Infrastructure | Host and DNS records; valid TLS certificate; HTTPS smoke test; certificate renewal owner |
| P1-03 | High | Provision production secrets and private services | IT / Infrastructure | Secret-manager inventory; no secrets in Git or images; private PostgreSQL and Redis; backup credentials secured |
| P1-04 | High | Configure encrypted off-host backups and prove restoration | IT / Infrastructure + Finance Controller | Backup schedule; off-host encrypted destination; retention and key custody; successful restore into an isolated database; RPO/RTO approval |
| P1-05 | High | Configure monitoring, error tracking and alert routing | IT / Infrastructure | Dashboards for availability, errors, database, disk and backup age; alert recipients; test alert delivered |
| P1-06 | High | Close access-control gaps | Management / Security owner | MFA decision and enforcement plan; inventory/procurement read-access policy; access review evidence; privileged-account list |
| P1-07 | High | Complete load, concurrency and failure testing | Technical owner | Measured results for expected user count, peak invoice volume and database/Redis failure; accepted thresholds; remediation log |
| P1-08 | High | Trial-import and reconcile migration data | Finance / Procurement / Technical owner | Validated import files; line-by-line reconciliation to source documents; rejected-row log; signed migration reconciliation |
| P1-09 | High | Approve payment execution and bank reconciliation boundaries | Finance Controller / Management | Signed decision on who may record versus execute payments; bank integration scope; reconciliation owner; no implied bank execution in Stage 7B |
| P1-10 | High | Complete NRS onboarding only if NRS is in scope | Management / Tax adviser / Technical owner | NRS credentials, endpoint, API version, environment and submission authorisation; adapter tested against the approved sandbox |
| P1-11 | High | Approve production invoice email identity | Management / IT | Company-domain sender or approved mailbox; SPF/DKIM/DMARC or provider verification; bounce and reply-to owner; email retention decision |
| P1-12 | High | Rehearse rollback and incident response | Technical owner / Finance Controller | Rollback procedure; incident contacts; restore drill; evidence that a failed activation or posting leaves no partial journal |
| P1-13 | High | Obtain final go-live authorisation | Managing Director / Management | Signed go-live decision referencing this checklist, UAT result and all accepted residual risks |

---

## 5. P2 — after controlled activation

| # | Work item | Owner | Evidence / note |
|---|---|---|---|
| P2-01 | Add invoice email history and resend to the invoice detail view | Technical owner | Email attempt, recipient, sender, timestamp and outcome visible to authorised users |
| P2-02 | Add invoice ageing, customer statements and receipt allocation | Finance Controller / Technical owner | Approved ageing buckets and statement format |
| P2-03 | Add idempotency to invoice posting | Technical owner | Duplicate posting attempts return the original result; regression test |
| P2-04 | Add asynchronous jobs for exports and notifications | Technical owner | Worker, queue, retry and dead-letter procedure |
| P2-05 | Complete OpenAPI schemas and throttling | Technical owner | Schema warnings closed; report/export/auth rate limits tested |
| P2-06 | Review the first live month's journals and reports | Finance Controller | Signed month-end reconciliation and defect log |

---

## 6. Day-of-activation sequence

1. Confirm the production environment contains no Stage 7A test invoices or test customers.
2. Export and archive the current settings and audit state.
3. Verify all P0 evidence is attached to the activation pack.
4. Confirm P1 acceptance or written management risk acceptance.
5. Call the activation endpoint with all ten gates checked and activation notes.
6. Verify the activation audit event and permission behaviour.
7. Issue one controlled live-representative invoice to an internal test customer, post it, reverse it and reconcile the journal.
8. Hand the system to the Finance Controller for live use.
9. Record the activation time, operator, result and any deviations.

---

## 7. Sign-off record

Complete one row per gate. Do not write “approved” without a named person and date.

| Gate | Owner | Evidence reference | Approved by | Date |
|---|---|---|---|---|
| P0-01 Management roles and authority | Management |  |  |  |
| P0-02 Company legal details and invoice template | Management / Accountant |  |  |  |
| P0-03 Chart and account-role mappings | Accountant / Finance Controller |  |  |  |
| P0-04 Posting rules | Accountant / Finance Controller |  |  |  |
| P0-05 VAT/WHT and tax profile | Tax adviser / Accountant |  |  |  |
| P0-06 Numbering and rounding | Accountant |  |  |  |
| P0-07 Opening balances, bank and inventory | Finance Controller / Finance Officer / Stores |  |  |  |
| P0-08 Finance Controller posting review | Finance Controller |  |  |  |
| P0-09 Management activation authorisation | Managing Director / Management |  |  |  |
| P0-10 Activation executed and verified | Finance Controller / System Administrator |  |  |  |

**Final decision:** ☐ Approved for Stage 7B activation  ☐ Not approved

**Decision owner:** ____________________  **Date:** ____________________

**Scope excluded from this authorisation:** NRS submission ☐  Bank payment execution ☐  Real customer receipts ☐  Other: ____________________

---

## 8. Stop conditions

Stop and do not activate if any of the following is true:

- A gate is marked true without evidence.
- The Finance Controller has not personally reviewed the mappings, rules and opening balances.
- Opening debits and credits do not reconcile.
- Unmapped account roles remain.
- The tax profile or numbering scheme is still provisional.
- Test documents remain in the intended production environment.
- Management authorisation is verbal only.
- The rollback or restore procedure has not been rehearsed.
- NRS is enabled without credentials, endpoint and separate authorisation.

---

## 9. Related records

- [`phase-7b-activation-blockers.md`](phase-7b-activation-blockers.md) — original blocker list and control rationale
- [`phase-7a-completion-report.md`](phase-7a-completion-report.md) — Stage 7A scope and evidence
- [`../13-decision-register.md`](../13-decision-register.md) — D-07, D-08, D-19, D-21 and D-23
- [`../reviews/04-review-tracker.md`](../reviews/04-review-tracker.md) — decision routing and gate status
- [`phase-11-production-readiness-report.md`](phase-11-production-readiness-report.md) — infrastructure and production blockers
- [`final-uat-report.md`](final-uat-report.md) — UAT readiness decision and residual findings
