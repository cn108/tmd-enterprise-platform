# Phase 11 — Production readiness and deployment preparation

**Date:** 12 November 2026
**Status:** deployment assets and operational procedures prepared; **not production-ready**
**Decision supported:** B — ready for staging/UAT after the blockers below are closed, not for production go-live.

## 1. Outcome

Phase 11 produced a reproducible container topology, fail-closed production
settings, backup/restoration procedures, migration templates and the operational
documentation set. The restoration procedure was executed successfully against
isolated databases with non-zero ledger data.

Production go-live is **not authorised** by this assignment and several controls
are not yet supplied: TLS certificates, production secrets, monitoring and
alerting, off-host encrypted backup storage, an approved chart of accounts and
posting rules, and management approval of the migration. Those are recorded as
blockers, not silently assumed.

## 2. Infrastructure and environments

| Asset | Location | State |
| --- | --- | --- |
| Backend image | `backend/Dockerfile` | Multi-stage-free Python 3.13 slim runtime, non-root user, Gunicorn, health check, migrations on start |
| Backend entrypoint | `backend/entrypoint.sh` | `migrate --noinput`, `check --deploy`, Gunicorn |
| Frontend image | `frontend/Dockerfile` | Node 24 build, nginx 1.27 runtime |
| Reverse proxy / TLS | `frontend/nginx/default.conf.template` | HTTP→HTTPS redirect, TLS 1.2/1.3, HSTS, CSP, Permissions-Policy, request size limit, SPA fallback |
| Production topology | `infra/prod/docker-compose.yml` | Private Postgres 16, Redis 7 with password, backend, web; only 80/443 exposed |
| Environment template | `infra/prod/.env.example` | Every secret required; no value committed |
| Production settings | `backend/config/settings/prod.py` | Fails closed when secret key, hosts, CSRF origins or bank encryption keys are absent; secure cookies, HSTS, no debug |
| Staging | Same compose file with a separate `COMPOSE_PROJECT_NAME`, volumes, database and secrets | Configuration pattern documented; no staging host was provisioned in this assignment |

Redis is configured but no background worker/task queue exists in the
repository. Current work is processed synchronously in request transactions.
If TMD requires asynchronous jobs, a worker design and deployment must be added
before production (see blocker B-11-06).

There is no production deployment in this assignment, so no image build or
container smoke test has been represented as evidence. The deployment manual
describes the build and health checks.

## 3. Database readiness

Inspected locally on 12 November 2026:

| Check | Result |
| --- | --- |
| Migration drift (`makemigrations --check --dry-run`) | No changes detected |
| Applied migrations in development | 63 |
| Journal entries / posted journals | 0 / 0 |
| Journal lines | 0 |
| Unbalanced posted journals | 0 |
| Negative stock layers | 0 |
| Accounts | 0 |
| Supplier invoices / customer invoices | 4 / 3 |
| Database constraints | Unique constraints and check constraints present on journals, journal lines, periods, stock layers, movements and document lines; negative stock blocked at database level |
| Deletion behaviour | Master data uses protected deletes/deactivation; transaction headers use PROTECT where history must survive; line records cascade only with their owning document |

The live development database contains no chart of accounts and no posted
journals. Formal financial reports correctly show zero posted figures with
completeness warnings. This is a configuration blocker, not a database defect.

Referential-integrity and duplicate checks were exercised through the test
suite. No destructive repair, reset or production data operation was performed.

## 4. Backup and disaster recovery

Assets:

- `scripts/backup.sh` — custom-format `pg_dump`, private media archive, SHA-256
  manifests, migration count and local retention.
- `scripts/restore.sh` — restores into an explicitly named target database;
  refuses to overwrite the source without an explicit flag.
- `scripts/test-restore.sh` — isolated restore rehearsal.
- `docs/manuals/backup-restoration-manual.md` — procedures and ownership.

Executed restoration evidence (`docs/reports/evidence/phase-11-restore-test.txt`):

| Measure | Source | Restored |
| --- | ---: | ---: |
| Migrations | 63 | 63 |
| Journals | 1 | 1 |
| Journal lines | 2 | 2 |
| Debits | ₦125.50 | ₦125.50 |
| Credits | ₦125.50 | ₦125.50 |
| Private documents | 101 | 101 |
| Ledger balanced | yes | yes |

The restore used an isolated synthetic verification database, not the live
records, and the isolated databases were removed afterwards. Result: **PASS**.

Provisional objectives (management approval required):

- **RPO:** 24 hours.
- **RTO:** 8 hours.

Limitations:

1. The backup archive is not encrypted by the script. Storage-layer encryption
   or an encrypted object store is mandatory; the manifest records this.
2. Backups are local by default. No off-host bucket, retention lifecycle,
   immutability or restore alerting is configured.
3. No scheduled backup job, monitoring check or periodic restore drill is
   configured on a host.
4. The restore test proves the procedure, not that a future production backup
   will run or be monitored.

## 5. Application security summary

Full detail is in `full-system-security-audit.md`.

Verified controls include session authentication with CSRF protection, Axes
lockout (5 failures, one-hour cool-off), Argon2 password hashing, password
validation, scoped password-reset throttling, encrypted bank account numbers,
permission-controlled documents and reporting, private media paths, CSP and
security headers, production secret fail-closed behaviour and no committed
production credentials.

Two authorization defects were found and corrected during this audit:

- Master-data endpoints accepted any authenticated user for reads and writes.
  They now enforce model permissions; a regression test proves an employee
  without permission receives 403 while a view permission permits reads only.
- Trial balance, financial statements, general ledger, accounts, journals and
  other accounting reads accepted any authenticated user. They now require
  accounting/reporting permissions.

Residual security gaps are stated in the security audit; the most important is
that inventory and procurement read endpoints still rely on authentication plus
their action-specific checks. A business policy decision is required before
tightening them, because every employee may raise a purchase request.

## 6. Performance and reliability

Not performed: a production-scale load test, sustained concurrency test,
database failover test or Redis-outage test. No staging load environment was
available. The following were verified instead:

- Server-side pagination and search across list APIs.
- Selected-relation/prefetch use in reporting and list views.
- Transactional writes for invoices, notes, payments, requests, quotes,
  purchase orders, opening balances and posting rules.
- Rollback regression test proving a failed invoice write leaves no partial
  header or lines.
- Idempotent/conflict handling for duplicate approvals and invalid state
  transitions.
- Zero negative stock layers and zero unbalanced posted journals in the live
  development data.

Performance acceptance remains **open** (blocker B-11-07). Do not describe the
system as load-tested.

## 7. Data migration and go-live preparation

Templates (`docs/templates/migration`):

`suppliers.csv`, `customers.csv`, `projects.csv`, `products.csv`,
`warehouses.csv`, `inventory_balances.csv`, `supplier_invoices.csv`,
`customer_invoices.csv`, `bank_balances.csv`, `opening_trial_balance.csv`,
`commitments.csv`.

Validation: `scripts/validate_migration.py` passed 11 templates / 12 rows with
0 errors and 0 warnings
(`docs/reports/evidence/phase-11-migration-template-validation.md`).

The PASS is structural only: types, references, duplicates and invoice/trial
balance arithmetic. No records were imported, no source documents were
reconciled and no opening balances were approved. Financial migration remains
blocked until the Finance Controller review and management approval are
recorded.

## 8. Operational documentation

`docs/manuals/` contains:

- Employee user manual
- Administrator manual
- Procurement manual
- Warehouse manual
- Finance manual
- Project management manual
- Banking manual
- Reporting manual
- Deployment manual
- Backup and restoration manual
- Troubleshooting guide
- System architecture
- API documentation

These describe implemented workflows and explicit boundaries. They do not
replace user acceptance training on the deployed staging system.

## 9. Phase 11 acceptance matrix

| # | Requirement | State |
| --- | --- | --- |
| 1 | Reproducible deployment instructions | Provided; not executed on a production host |
| 2 | Separate staging and production configuration | Supported by project name, secrets and volumes; staging not provisioned |
| 3 | Secure secrets handling | Fail-closed production settings and external env template; actual secret manager not configured |
| 4 | Automated backup procedures | Scripts and retention exist; scheduling, encryption and off-host storage not configured |
| 5 | Tested restoration procedures | PASS on isolated synthetic source |
| 6 | Security assessment | Completed; two authorization defects corrected; residual gaps recorded |
| 7 | Performance test results | **Not performed** — open blocker |
| 8 | Migration and reconciliation plan | Templates validated; no trial import or reconciliation performed |
| 9 | Monitoring and logging | Structured logs and health endpoints exist; no metrics, error tracker or alert routing |
| 10 | Complete operational documentation | Provided |
| 11 | Identified production blockers | Listed below |
| 12 | Management go-live checklist | Provided below |

## 10. Production blockers

| ID | Blocker | Owner |
| --- | --- | --- |
| B-11-01 | No server/domain/TLS certificate and no production secret store | TMD management / infrastructure |
| B-11-02 | No Finance Controller, approved chart of accounts, account-role mappings, posting rules or tax policy | TMD finance |
| B-11-03 | No approved opening balances or reconciled opening trial balance | TMD finance |
| B-11-04 | No off-host encrypted backup destination, schedule or monitoring | TMD infrastructure |
| B-11-05 | No production monitoring, error tracking or alert routing | TMD infrastructure |
| B-11-06 | No background worker/task-queue design; all work is synchronous | TMD technical owner |
| B-11-07 | No staging load/concurrency/failure test | TMD technical owner |
| B-11-08 | Migration not trial-imported or reconciled to source documents | TMD finance/procurement |
| B-11-09 | No written UAT sign-off by department leads | TMD management |
| B-11-10 | Inventory/procurement read-access policy unresolved | TMD management |
| B-11-11 | NRS credentials and submission authorisation absent | TMD management |
| B-11-12 | Production go-live, financial activation, bank execution and NRS submission not authorised | TMD management |

## 11. Go-live checklist

- [ ] Production host, domain, TLS certificate and DNS ready
- [ ] Secret manager populated; no secret in git or images
- [ ] Postgres/Redis private, password-protected and backed up
- [ ] Off-host encrypted backup verified and restore drill scheduled
- [ ] Monitoring, alerting and log retention active
- [ ] Finance Controller appointed; chart, mappings, rules and tax policy approved
- [ ] Opening balances approved and posted through the controlled procedure
- [ ] Migration trial-imported into staging and reconciled line by line
- [ ] UAT completed by procurement, warehouse, finance, projects, banking and reporting
- [ ] Security findings accepted or closed
- [ ] Load/concurrency/failure tests passed
- [ ] Rollback and incident procedures rehearsed
- [ ] Written management authorisation for go-live and financial activation
- [ ] NRS/bank integrations remain disabled unless separately authorised

## 12. Conclusion

The repository now contains the infrastructure, procedures, manuals and
restoration evidence needed to enter a controlled staging/UAT programme. It does
not yet meet the production acceptance requirements because performance testing,
off-host encrypted backups, monitoring, migration reconciliation, production
secrets/TLS and the accounting approvals are outstanding.

**Phase 11: PREPARED, NOT PRODUCTION-READY.**
