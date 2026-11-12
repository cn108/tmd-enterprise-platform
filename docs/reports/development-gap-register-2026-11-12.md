# Development gap register — 12 November 2026

**Basis:** technical review dated 12 November 2026.
**Environment:** synthetic `tmd_staging`.
**Production activation:** disabled. No live issuance, ledger posting, payment execution or
NRS submission was enabled.

Status definitions:

- **Implemented and verified** — code exists and automated tests or browser checks passed.
- **Implemented but not fully verified** — code exists, but the production or external path
  has not been exercised.
- **Partially implemented** — some code exists; a required rule, mapping or workflow is
  missing.
- **Not implemented** — no working code path exists.
- **Blocked** — implementation or activation requires an accounting, tax, management or
  infrastructure decision.

---

## 1. Implemented and verified

| ID | Capability | Evidence | Notes |
|---|---|---|---|
| G-01 | Balanced supplier and customer invoice posting | `apps/invoicing/posting.py`; 316 backend tests | Journals are posted only after activation; test invoices are refused |
| G-02 | Invoice posting idempotency | Invoice replay test; `Idempotency-Replayed` header | Deterministic fallback key prevents a second journal |
| G-03 | Recorded supplier payment posting | Payment posting test | AP or supplier advances debited; bank/cash credited |
| G-04 | Payment posting idempotency | Payment replay test | Same journal returned on replay |
| G-05 | Approved-note integrity guard | New posting test | An invoice with an approved note is refused until note posting exists |
| G-06 | Role-aware module access indicators | Dashboard component test; browser screenshot | Restricted modules remain visible with a badge |
| G-07 | Restricted-page access state | Browser screenshot | Administration exposes no user or role records |
| G-08 | Invoice email permission enforcement | Role-matrix tests | Only permitted finance/management roles can send |
| G-09 | Invoice posting permission enforcement | Role-matrix tests | System Administrator, Accountant, Finance Controller only |
| G-10 | Test-mode financial posting refusal | Browser 409 evidence and automated tests | No journal is created for a test document |

---

## 2. Implemented but not fully verified

| ID | Capability | What is missing | Next verification |
|---|---|---|---|
| G-11 | Supplier payment posting in the browser | Only the refusal path was exercised because the staging payment is a test document | After an authorised test activation in an isolated environment, post a non-test payment and inspect the journal |
| G-12 | Invoice posting idempotency through the UI | Automated API replay is verified; the generic Angular action does not display the replay header | Confirm a repeat click returns the original journal without a duplicate |
| G-13 | Email to external recipients | A real message was delivered to the owner mailbox, not an external customer | Send a controlled external test with approval and check SPF/DKIM/DMARC |
| G-14 | Dashboard module access for custom roles | Tested against role permissions, not every possible custom permission bundle | Review with the access administrator after the real matrix is approved |
| G-15 | Payment posting with a company bank account GL mapping | Code supports it; no staging bank account has an approved GL mapping | Configure one UAT bank account with an approved GL account and post a payment |

---

## 3. Partially implemented

| ID | Capability | Implemented now | Missing | Risk |
|---|---|---|---|---|
| G-16 | Supplier cost classification | Product → inventory; project → project cost; other → cost of sales | Approved line-level policy for direct expense, capital, cost centre and service treatment | Costs may be posted to the wrong account even though the journal balances |
| G-17 | Customer revenue recognition | Receivable/revenue/output VAT entry on invoice date | Delivery/acceptance, deferred revenue, milestone and policy rules | Revenue may be recognised too early |
| G-18 | WHT | Rates, calculation and document balances | WHT payable/receivable roles, posting, remittance, certificates and tax return | WHT invoices cannot be posted; correct but incomplete |
| G-19 | Credit/debit notes | Draft, submit, approve, balances and PDF | Journal link, posting service, reversal/classification rules | Approved notes block invoice and payment posting; no partial ledger is created |
| G-20 | Supplier payment posting allocation | AP for allocated portion, supplier advances for remainder | Customer receipts, bank reconciliation posting and payment execution boundaries | A recorded payment is not proof of bank clearance |
| G-21 | Company email | SMTP, App Password, PDF attachment, audit | Recipient policy, company domain, SPF/DKIM/DMARC, bounce handling, resend history | A permitted user can email a test PDF externally |
| G-22 | Dashboard access model | Module-level read indicator | Module-level write indicator and custom-role review | A module may be openable but partially restricted; the page itself still shows Limited actions |
| G-23 | Temporary sharing | Public quick tunnel, login gate, synthetic data | Stable hosting, TLS-only cookie policy, IP/SSO restriction, tunnel-origin CSRF support | Ephemeral; not suitable for real data or remote administration |

---

## 4. Not implemented

| ID | Capability | Required next action | Priority |
|---|---|---|---|
| G-24 | Credit/debit note ledger posting | Design note posting against the original invoice classification; add a journal link and migration | P1 after accounting policy |
| G-25 | Customer receipts and allocation | Add receipt model, allocation, statement and ageing workflow | P1 |
| G-26 | Customer statements and dunning | Statement format, ageing buckets, delivery and audit | P2 |
| G-27 | Email history and resend | Persist attempts, recipients, outcome and allow controlled resend | P2 |
| G-28 | Invoice ageing and collection workspace | Approved ageing buckets and collection ownership | P2 |
| G-29 | Background jobs | Queue for email, exports and long reports | P2 |
| G-30 | Payment execution | Bank integration or explicit execution boundary | Blocked by management policy |
| G-31 | NRS network submission | Credentials, endpoint, sandbox and authorisation | Blocked |
| G-32 | Foreign-currency posting and revaluation | FX policy, rates and gain/loss treatment | Blocked |
| G-33 | MFA | Enforcement plan and enrolment | P1 production control |

---

## 5. Blocked by accounting or management approval

| ID | Blocker | Owner | Consequence |
|---|---|---|---|
| B-01 | Real chart of accounts and all 19 account-role mappings | Accountant / Finance Controller | Posting cannot run against real accounts |
| B-02 | Approved posting rules for invoices, notes and payments | Finance Controller | Current rules are code assumptions, not an approved policy |
| B-03 | WHT base, withholding point, payable/receivable accounts and remittance owner | Tax adviser / Finance Controller | WHT invoices and payments remain unpostable |
| B-04 | Revenue-recognition policy | Management / Finance Controller | Invoice-date revenue is provisional |
| B-05 | Supplier cost-classification policy | Accountant / Finance Controller | Cost may be misclassified |
| B-06 | Opening balances, bank and inventory reconciliation | Finance Controller | No credible live trial balance |
| B-07 | Company legal details, Tax ID, numbering and rounding | Management / Accountant | Activation is blocked |
| B-08 | Production email identity and recipient policy | Management / IT | Email remains a personal-mailbox arrangement |
| B-09 | Written Stage 7B activation authorisation | Managing Director | `test_mode` must remain true |
| B-10 | Production hosting, backups, monitoring and MFA | IT / Management | Not production-ready |

---

## 6. Recommended order of work

1. **Accounting policy pack** — chart, mappings, cost classification, revenue recognition,
   WHT and note treatment. This unblocks the largest number of items.
2. **Note posting** — implement only after the note classification and tax treatment are
   approved; remove the current hard refusal once it is safe.
3. **Customer receipts and statements** — complete the receivables loop.
4. **Payment posting browser verification** — with an approved non-test UAT payment and a
   mapped bank account, in an isolated environment.
5. **Email governance** — company identity, recipient policy, delivery history and bounce
   handling.
6. **Production controls** — MFA, TLS-only cookies, stable hosting, backups, monitoring and
   restore drill.
7. **UI/UX polish** — add module-level write indicators and use the same role-aware language
   on remaining action surfaces.

**Do not activate Stage 7B merely because the gap count has fallen. Activation remains a
separate management decision backed by the P0 evidence in the activation checklist.**
