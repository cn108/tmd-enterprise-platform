# TMD Enterprise System — Operational Handover Report

**Date:** 13 November 2026  
**Handover status:** documentation and procedures prepared; **production operations not started**  
**Recipient:** Owner / Managing Director, Software Developer / Technical Administrator, and future finance/procurement/inventory/project staff  
**Classification:** A. TECHNICALLY COMPLETE — AWAITING EXTERNAL APPROVALS

## 1. Handover statement

The platform, manuals, controls and recovery procedures are ready for controlled UAT and for the next phase of production preparation. No production system has been handed over because no production deployment, approved accounting configuration, real data migration, employee training or go-live authorisation exists.

This report deliberately distinguishes:

- **Prepared:** documentation, scripts, configurations and tests exist.
- **Verified:** the stated check was executed with evidence.
- **Operational:** real users are running real company transactions in production.

Only the first two apply today.

## 2. Manual set

| Audience                  | Document                                         | Purpose                                                          |
| ------------------------- | ------------------------------------------------ | ---------------------------------------------------------------- |
| Owner / Managing Director | `docs/manuals/owner-managing-director-manual.md` | Decisions, monthly rhythm, escalation, sign-off                  |
| All employees             | `docs/manuals/employee-user-manual.md`           | Sign-in, MFA, navigation, records, approvals, errors             |
| System Administrator      | `docs/manuals/administrator-manual.md`           | Users, roles, MFA reset, activation gates, security, incidents   |
| Finance                   | `docs/manuals/finance-manual.md`                 | Invoices, receipts, payments, journals, reconciliation, periods  |
| Procurement               | `docs/manuals/procurement-manual.md`             | Requests, RFQs, quotes, orders, receipts                         |
| Inventory / warehouse     | `docs/manuals/warehouse-manual.md`               | Receipts, issues, transfers, counts, valuation                   |
| Projects and operations   | `docs/manuals/project-management-manual.md`      | Projects, budgets, milestones, costs, service/leasing boundaries |
| Banking                   | `docs/manuals/banking-manual.md`                 | Bank accounts, statements, matching, reconciliation, cash        |
| Reporting                 | `docs/manuals/reporting-manual.md`               | Report sources, completeness warnings, exports                   |
| Deployment                | `docs/manuals/deployment-manual.md`              | Host, TLS, secrets, build, first run, rollback                   |
| Backup and restoration    | `docs/manuals/backup-restoration-manual.md`      | Backup, checksums, isolated restore, DR, RPO/RTO                 |
| Troubleshooting           | `docs/manuals/troubleshooting-guide.md`          | Symptom, cause, safe action, escalation                          |
| Technical architecture    | `docs/manuals/system-architecture.md`            | Modules, flows, integrity, security, constraints                 |
| API                       | `docs/manuals/api-documentation.md`              | Auth, MFA, permissions, errors, endpoints, throttles             |
| Maintenance               | `docs/manuals/maintenance-procedures.md`         | Routine checks, change control, patches, certificates, DB        |
| Post-launch               | `docs/manuals/post-launch-monitoring-plan.md`    | 30-day hypercare, metrics, first close, exit criteria            |

The manuals index is `docs/manuals/README.md`.

## 3. Operational controls handed over

### Access and security

- Ten roles retained; named-user policy; no shared accounts.
- TOTP MFA with recovery codes; production enforcement on by default.
- Administrator reset procedure after identity verification.
- Axes lockout plus configurable API/login/MFA throttles.
- Read-only Management/Auditor administration; financial authority separated from technical administration.
- Audit trail and immutable posted journals/stock movements.

### Financial control

- Invoice, payment and receipt posting is permissioned and idempotent.
- Activation gates keep live issuance/posting/NRS/bank execution off.
- Approval bands, maker-checker and period controls are implemented.
- Reports derive from posted journals and disclose incomplete configuration.
- Notes/WHT/FX remain blocked until policy is approved.

### Data and recovery

- PostgreSQL custom-format dumps, media archive, SHA-256 manifests and retention.
- Restore refuses the source database and non-test targets without explicit confirmation.
- Isolated restore drill passed: 72 migrations, 1 journal, 2 lines, ₦125.50 debit/credit, 476 documents.
- Proposed RPO 24 hours / RTO 8 hours; **not approved** and not operational until off-host encrypted backups and monitoring exist.

## 4. 30-day post-launch plan

The plan in `docs/manuals/post-launch-monitoring-plan.md` covers:

- daily availability, 5xx, authentication/MFA, financial posting, inventory, email and backup checks;
- weekly bank/AR/AP/stock/access review;
- metrics for availability, p95 response, duplicate journals, reconciliation ageing, negative stock and backup success;
- escalation and evidence preservation;
- exit criteria for hypercare.

This plan is prepared but not started. It begins only after authorised go-live.

## 5. First financial month-end close

The project cannot be declared fully operational until the first close is completed and signed. Required acceptance evidence:

1. All bank accounts reconciled; unexplained items listed and owned.
2. AP/AR control accounts agree to supplier/customer balances.
3. Inventory valuation agrees to stock records and count policy.
4. VAT/WHT position reviewed and supported.
5. Trial balance balances; statements have no unexplained completeness warning.
6. Journals posted only in open periods; close performed by an authorised person.
7. Opening balances and first-month activity traceable to source documents.
8. Managing Director signs the close acceptance.

## 6. Training and support

Training material exists in the manuals, but **no production employee training has been delivered** and no training attendance record exists. Before go-live:

- run role-based sessions using synthetic data only;
- test MFA enrolment and recovery with each named user;
- walk through one procurement, one receipt/payment and one report per role;
- record attendance, questions and unresolved difficulties;
- provide a support contact and incident channel.

Do not use real bank instructions, invoices or supplier payments in training.

## 7. Credentials and secret custody

No production credential is included in this report or repository. The Managing Director/IT owner must:

- create the production secret store and restrict access;
- issue named accounts, not shared logins;
- keep MFA recovery codes offline;
- retain the bank and MFA Fernet keys with a documented rotation/custody procedure;
- ensure the Software Developer can administer the system without holding financial approval authority;
- remove access promptly on role change or departure.

## 8. Known operational limitations

| Limitation                              | Effect                                          | Owner                      |
| --------------------------------------- | ----------------------------------------------- | -------------------------- |
| No production host/TLS/domain           | Cannot operate publicly                         | Infrastructure             |
| No approved chart/tax/opening balances  | Live posting must stay off                      | Finance / external adviser |
| No real migration                       | No company data in production                   | Finance / data owner       |
| No off-host encrypted backup/monitoring | RPO/RTO not operational                         | Infrastructure             |
| No load/concurrency/failure test        | Capacity unproven                               | Engineering                |
| No independent penetration test         | Security assurance incomplete                   | Management                 |
| Synchronous reports/email               | Long operations may block a request             | Engineering                |
| No email delivery history/resend UI     | Support must use audit/logs                     | Engineering                |
| Notes/WHT/FX blocked                    | Some documents cannot post                      | Finance / tax adviser      |
| No NRS/bank integration                 | Statutory e-invoicing and bank execution absent | Management                 |

## 9. Handover acceptance

| Item                              | Delivered | Accepted by | Date |
| --------------------------------- | --------- | ----------- | ---- |
| Manuals and procedures            | Yes       |             |      |
| Source code and migration files   | Yes       |             |      |
| Deployment assets and runbook     | Yes       |             |      |
| Backup/restore evidence           | Yes       |             |      |
| Production secrets/host/TLS       | **No**    |             |      |
| Approved accounting configuration | **No**    |             |      |
| Real data migration               | **No**    |             |      |
| Employee training                 | **No**    |             |      |
| First month-end close             | **No**    |             |      |

## 10. Sign-off

| Role                            | Name | Decision                           | Date | Signature |
| ------------------------------- | ---- | ---------------------------------- | ---- | --------- |
| Software Developer              |      | Technical handover complete        |      |           |
| Owner / Managing Director       |      | Operational handover accepted      |      |           |
| Finance Controller / accountant |      | Financial procedures accepted      |      |           |
| Infrastructure owner            |      | Hosting/backup/monitoring accepted |      |           |

## 11. Conclusion

The handover pack gives TMD a coherent, tested platform and the procedures needed to run it safely once the external prerequisites exist. It does **not** claim that TMD is already operating the system. The next gate is a signed business/technical acceptance and the infrastructure/finance approvals listed in the production readiness report.
