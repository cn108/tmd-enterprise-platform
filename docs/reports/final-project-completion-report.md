# TICO MCDON LIMITED — Final Project Completion Report

**Date:** 13 November 2026  
**System:** TMD Enterprise System (Angular 22 + Django 5/DRF + PostgreSQL)  
**Repository state:** working tree with pre-existing uncommitted work preserved; no commit, push or deployment performed  
**Final classification:** **A. TECHNICALLY COMPLETE — AWAITING EXTERNAL APPROVALS**

## 1. Executive statement

The approved enterprise application is implemented as a modular monolith covering master data, procurement, inventory, accounting, invoicing, supplier payments, customer receipts, banking, projects, services/HSE, equipment/leasing, reporting and administration. Every planned module, all ten roles, permissions and scalable structures remain in place.

The system is **not** production-live. It has not been deployed to a company-controlled host, has no production domain/TLS certificate, has no approved chart of accounts, tax opinion or opening balances, and has no Managing Director authorisation for go-live. Those are external business and infrastructure dependencies, not code-completion gaps.

This report therefore claims **technical completion and verified UAT readiness**, not operational completion, not production deployment and not a completed first month-end close.

## 2. What is complete

| Capability                                                                               | State                                                                                                                         | Evidence                                                        |
| ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Master data (organisation, parties, catalogue, warehouses)                               | Implemented and tested                                                                                                        | Backend suite; master-data browser tests                        |
| Procurement (request, approval, RFQ, quote, order, receipt)                              | Implemented, tested and browser-verified                                                                                      | UAT-PRC; `PR-2026-0002`; 9/9 Playwright                         |
| Inventory (receipts, issues, transfers, returns, adjustments, counts, valuation)         | Implemented and tested                                                                                                        | Backend inventory tests; reconciliation evidence                |
| Accounting engine (chart, roles, mappings, periods, journals, posting rules, statements) | Implemented and tested; production configuration blocked                                                                      | Accounting/reporting tests; migration and production gate       |
| Supplier invoices and payments                                                           | Implemented; recording/posting tested; live execution not implemented by design                                               | Invoice/payment tests; activation gates                         |
| Customer invoices and receipts                                                           | Implemented; receipt ledger posting, allocation, reversal and statement PDF tested                                            | `customer-receipt-posting-completion-report.md`; 348-test suite |
| Banking and reconciliation                                                               | Implemented; statement import, matching, approval and reconciliation tested                                                   | Banking tests; reconciliation evidence                          |
| Projects, services/HSE and equipment/leasing                                             | Implemented and tested                                                                                                        | Project/service/leasing tests; phase reports                    |
| Reporting                                                                                | Implemented; formal statements derive from posted journals only                                                               | Phase 10 report; report tests                                   |
| Administration and access control                                                        | Implemented; ten roles, object permissions, read-only oversight, audit                                                        | Role matrix; 45/45 API security probe                           |
| MFA                                                                                      | **Newly implemented** — TOTP, recovery codes, one-time challenges, replay refusal, per-user/global enforcement, reset command | `apps/identity/mfa.py`; 5 MFA tests; 2 frontend login tests     |
| API abuse controls                                                                       | **Newly implemented** — global authenticated/anonymous plus login, MFA and reset scoped limits                                | `config/settings/base.py`; `config/settings/prod.py`; UAT probe |
| Production email identity                                                                | Personal Gmail default removed; production requires a company-controlled mailbox                                              | `.env.example`; `prod.py`; migration `0011`                     |
| Deployment assets                                                                        | Dockerfiles, nginx TLS template, private Postgres/Redis topology, health checks, backup/restore scripts                       | `infra/prod/`; `scripts/`                                       |
| Backup and restore                                                                       | Real isolated backup/restore drill passed                                                                                     | `docs/reports/evidence/phase-11-restore-test.txt`               |

## 3. Verification evidence (13 November 2026)

| Check                              | Result                                                                                                               |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Backend tests                      | **348 passed**                                                                                                       |
| Frontend unit tests                | **73 passed** (11 files)                                                                                             |
| Frontend lint                      | Passed                                                                                                               |
| Frontend production build          | Passed                                                                                                               |
| Ruff                               | Passed                                                                                                               |
| Django `check`                     | Passed (1 silenced issue)                                                                                            |
| Migration drift                    | No changes detected                                                                                                  |
| Browser UAT (`formal-uat.spec.ts`) | **9/9 passed**                                                                                                       |
| MFA browser flow (`mfa.spec.ts`)   | **1/1 passed** — enrolment, TOTP login, recovery code and replay refusal                                             |
| UAT API probe                      | **5/5 checks passed** (ten roles, read-only admin, procurement approval, restricted access, production controls off) |
| Production `check --deploy`        | Exit 0; **0 security warnings**; 37 documented drf-spectacular schema warnings                                       |
| Production Compose validation      | `docker compose config` passed                                                                                       |
| `npm audit --omit=dev`             | 0 vulnerabilities                                                                                                    |
| Backup/restore                     | 72 migrations, 1 journal, 2 lines, debit/credit ₦125.50, **476 private documents**, ledger balanced — PASS           |
| Migration template validation      | **15 templates, 17 rows, 0 errors, 0 warnings**                                                                      |

The UAT API probe still correctly reports `enforcement_in_uat=false`: development/UAT deliberately leaves MFA optional so synthetic accounts remain usable. Production sets `MFA_REQUIRED_FOR_ALL_USERS=true` and fails closed without `MFA_ENCRYPTION_KEY` and company email credentials.

## 4. Defects closed in this phase

| Item                                           | Resolution                                                                                                                                                                                                                |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MFA was a stored flag with no enforcement      | Added TOTP enrolment, encrypted secret storage, signed single-use challenges, replay prevention, hashed one-time recovery codes, per-user enforcement, production-wide enforcement and `reset_mfa` administration command |
| No general API throttling                      | Added configurable DRF authenticated/anonymous throttles and scoped login/MFA/reset rates; production defaults are tighter                                                                                                |
| Personal Gmail used as a configuration default | Removed from `.env.example`, seed data and tests; added a forward migration that clears the old value; production rejects `gmail.com` sender credentials                                                                  |
| UAT-D-001 restricted-module API noise          | Fixed earlier with `viewPermissions`; no restricted data request or 403 console error in browser retest                                                                                                                   |
| Migration coverage gaps                        | Added company profile, employees, equipment and advances templates; validator now covers 15 templates                                                                                                                     |

## 5. Intentionally not enabled

These are controls, not missing code:

- Live customer invoice issuance (`test_mode=True`, `can_issue=False`, `activated_at=None`).
- Production ledger posting of live invoices.
- Bank transfer/payment execution (the platform records payments; it does not instruct a bank).
- NRS/e-invoicing network submission.
- WHT and foreign-currency posting.
- Credit/debit note ledger posting.
- Production financial activation and go-live.

## 6. Remaining policy and product limitations

1. **Credit/debit notes:** document workflow, approval, balances and PDFs work; no journal posting exists because note classification, tax point and reversal policy are unapproved. Approved notes correctly block gross invoice/payment posting.
2. **WHT:** calculation and document totals exist; payable/receivable accounts, withholding point, remittance and tax treatment are unapproved, so WHT invoices cannot post.
3. **Foreign currency:** document currency is captured; revaluation, realised/unrealised gain/loss and FX policy are absent, so posting is refused.
4. **Email history/resend:** sending and audit exist; a persistent delivery-history/resend screen is P2.
5. **Background jobs:** current work is synchronous; Redis is provisioned but no worker topology is deployed.
6. **OpenAPI:** some plain `APIView` endpoints are not fully described; 37 schema warnings remain.
7. **Dependency audit:** npm audit is clean; `pip-audit` is not installed in the environment, so a Python CVE scan remains an infrastructure/CI task.
8. **Performance and failure testing:** production-scale load, sustained concurrency, database failover and Redis-outage tests have not been performed.

## 7. External dependencies that prevent a higher classification

| Dependency                                                          | Responsible person                       | Blocking effect                                       |
| ------------------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------- |
| Company domain, DNS, TLS certificate and production host            | Managing Director / infrastructure owner | Cannot deploy securely                                |
| Production secret store, SMTP mailbox and email authentication      | Managing Director / IT                   | Cannot run production authentication or invoice email |
| Off-host encrypted backup destination, schedule and monitoring      | Infrastructure owner                     | Recovery objective not operational                    |
| Monitoring, alerting and on-call ownership                          | Infrastructure owner                     | No production incident response                       |
| Signed role matrix and delegation/approval authority                | Managing Director                        | UAT-D-004 remains open                                |
| Approved chart of accounts, account-role mappings and posting rules | External accountant / Finance Controller | Ledger posting cannot be activated                    |
| VAT/WHT/tax-ID/NRS review                                           | External tax adviser                     | Tax posting and e-invoicing cannot be activated       |
| Signed opening trial balance and reconciled source records          | Finance Controller / Managing Director   | No credible go-live ledger                            |
| Actual company/source data for migration                            | Managing Director / Finance              | Only template validation is possible                  |
| Explicit written go-live and financial activation authorisation     | Managing Director                        | Production must remain read-only/test-only            |
| First month-end close and operational acceptance                    | Management / Finance                     | Project cannot be declared fully operational          |

## 8. Final classification

### A. TECHNICALLY COMPLETE — AWAITING EXTERNAL APPROVALS

Rationale:

- All approved modules and ten roles are implemented, with backend, frontend and browser evidence.
- Critical/high application defects found in the final cycle are fixed; no known unresolved critical/high application defect remains.
- Production controls (MFA, throttling, email identity, secure settings, backup/restore) are implemented or prepared.
- Deployment and financial activation are blocked by missing external approvals, credentials, data and infrastructure — not by missing application code.

This is **not** B because the production host, secrets and approvals are absent. It is **not** C or D because nothing has been deployed, no real data has been migrated, no live transaction has been authorised, no employees have been trained on production and no month-end close has occurred.

## 9. Sign-off record

| Role                                         | Name | Decision                         | Date | Signature |
| -------------------------------------------- | ---- | -------------------------------- | ---- | --------- |
| Software Developer / Technical Administrator |      | Technical completion accepted    |      |           |
| Owner / Managing Director                    |      | Business workflows accepted      |      |           |
| External accountant / tax adviser            |      | Financial configuration reviewed |      |           |
| Owner / Managing Director                    |      | Production go-live authorised    |      |           |

Unsigned rows are external dependencies. They are not represented as approvals.
