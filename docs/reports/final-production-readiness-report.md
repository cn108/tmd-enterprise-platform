# TMD Enterprise System — Final Production Readiness Report

**Date:** 13 November 2026  
**Decision:** **NO-GO for production go-live**  
**System status:** technically complete for controlled UAT; production environment not supplied; financial configuration not approved  
**Classification:** A. TECHNICALLY COMPLETE — AWAITING EXTERNAL APPROVALS

## 1. Why the answer is no-go

Production go-live requires a company-controlled domain and TLS certificate, a protected secret store, an off-host encrypted backup destination, monitoring and alerting, an approved chart of accounts and posting rules, a verified tax position, reconciled opening balances, a real migration, signed management acceptance and explicit launch authorisation.

None of those external items is present in this repository or supplied in this assignment. The application therefore remains in its safe test-only state:

- `InvoiceSettings.test_mode = True`
- `can_issue = False`
- `activated_at = None`
- NRS disabled
- supplier payments recorded, not executed
- no production deployment performed

## 2. Technical readiness verified

| Area                      | Evidence                                                  | Status                                              |
| ------------------------- | --------------------------------------------------------- | --------------------------------------------------- |
| Backend regression        | 348 tests passed                                          | Pass                                                |
| Frontend regression       | 73 tests, 11 files passed                                 | Pass                                                |
| Browser UAT               | 9/9 role workflows passed                                 | Pass                                                |
| UAT API probe             | 5/5 checks passed                                         | Pass                                                |
| Lint/format               | Ruff and Angular lint passed                              | Pass                                                |
| Build                     | Angular production build passed                           | Pass                                                |
| Migrations                | `makemigrations --check --dry-run` clean                  | Pass                                                |
| Django check              | `manage.py check` clean                                   | Pass                                                |
| Production settings check | Exit 0; 0 `security.W*` warnings; 37 schema-only warnings | Pass with documented schema debt                    |
| Compose topology          | `docker compose config` passed with test secrets          | Pass                                                |
| Backup/restore            | Isolated drill passed                                     | Pass                                                |
| MFA                       | Backend and frontend tests passed                         | Pass — production enforcement by configuration      |
| MFA browser flow          | 1/1 Playwright test passed                                | Pass — enrolment, TOTP, recovery and replay refusal |
| Throttling                | Global and scoped rates configured                        | Pass — capacity review pending                      |
| npm dependency audit      | 0 vulnerabilities (production dependencies)               | Pass                                                |
| Python dependency audit   | `pip-audit` not installed                                 | **Gap**                                             |

### 2.1 Production configuration checks

`manage.py check --deploy` was run with `config.settings.prod`, generated Fernet keys, a test company mailbox and allowed hosts. It exited 0 and reported **zero security warnings**. The remaining 37 warnings are drf-spectacular schema-generation warnings for plain API views and enum-name collisions; they do not weaken runtime access control but must be cleaned up before an API consumer relies on the schema.

`docker compose --env-file ... -f infra/prod/docker-compose.yml config` resolved successfully. This validates interpolation and topology only; it is not a container build, deployment or HTTPS test.

### 2.2 Restore drill

`scripts/test-restore.sh` took a real backup of the local database, restored it into an isolated source, inserted synthetic balanced journals, backed up that source, restored into a second isolated database and compared:

| Measure           | Result            |
| ----------------- | ----------------- |
| Migrations        | 72 = 72           |
| Journals          | 1 = 1             |
| Journal lines     | 2 = 2             |
| Debits            | ₦125.50 = ₦125.50 |
| Credits           | ₦125.50 = ₦125.50 |
| Private documents | 476 = 476         |
| Ledger balanced   | Yes               |

The live database was read-only for the drill; isolated databases were removed. Evidence: `docs/reports/evidence/phase-11-restore-test.txt`.

## 3. Production architecture as prepared

- `infra/prod/docker-compose.yml`: PostgreSQL 16, Redis 7 with password, Django/Gunicorn backend, nginx TLS frontend.
- Only 80/443 published; database and Redis remain on a private network.
- Backend runs as non-root, applies migrations at start, then Gunicorn.
- nginx provides HTTP→HTTPS redirect, TLS 1.2/1.3, HSTS, CSP, frame denial, referrer policy and request-size limits.
- Django production settings fail closed without secret key, allowed hosts, CSRF origins, bank encryption keys, MFA encryption key and company email credentials.
- Media is private and served through authenticated downloads.
- Health endpoints exist (`/health/`, `/health/ready/`).
- Structured logs include request identifiers; no secret is written by the application.

## 4. Production controls matrix

| Control                       | Status               | Evidence / gap                                                    |
| ----------------------------- | -------------------- | ----------------------------------------------------------------- |
| Domain and DNS                | **Not supplied**     | No company-controlled hostname                                    |
| HTTPS/TLS                     | **Not evidenced**    | Template exists; no certificate or external HTTPS test            |
| Private PostgreSQL/Redis      | Prepared             | Compose private network and passwords                             |
| Secret management             | Prepared             | Fail-closed settings and env template; no production secret store |
| MFA                           | Implemented          | TOTP/recovery/enforcement; production default on                  |
| API rate limiting             | Implemented          | Configurable global and scoped limits                             |
| Monitoring and alerts         | **Not implemented**  | No metrics/error tracker/alert route                              |
| Secure document storage       | Implemented          | Private media, authenticated downloads, audit                     |
| Off-host encrypted backups    | **Not implemented**  | Local script only; storage encryption required                    |
| Automated backup verification | Partial              | Manifest checksums and restore drill; no scheduled verifier       |
| Disaster recovery             | Procedure documented | No failover test or measured production RTO                       |
| Rollback                      | Documented           | Not rehearsed on a production-like host                           |
| Production email              | Configuration ready  | No company mailbox credentials or SPF/DKIM/DMARC evidence         |
| NRS integration               | Disabled             | No credentials, onboarding, endpoint or authorisation             |

## 5. Go-live gate

| Requirement                                    | State                                                                    |
| ---------------------------------------------- | ------------------------------------------------------------------------ |
| No unresolved critical/high application defect | Met for application-level findings; external infrastructure not assessed |
| Complete regression testing                    | Met at application level                                                 |
| Browser UAT                                    | Met on synthetic data                                                    |
| Approved accounting configuration              | **Not met**                                                              |
| Reconciled opening balances                    | **Not met**                                                              |
| Verified tax configuration                     | **Not met**                                                              |
| Secure production infrastructure               | **Not met**                                                              |
| Encrypted backups and restore                  | Restore met; encryption/off-host not met                                 |
| MFA and permissions verified                   | Met in tests; production enforcement not deployed                        |
| Data migration approved                        | **Not met**                                                              |
| Management acceptance documented               | **Pending**                                                              |
| Deployment and rollback tested                 | **Not met on production**                                                |

## 6. Blocking register

| ID    | Severity | Blocker                                                   | Owner                                    | Closure evidence                                        |
| ----- | -------- | --------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------- |
| PB-01 | Critical | MFA absent                                                | Closed technically                       | TOTP/recovery/enforcement tests; production default on  |
| PB-02 | Critical | Chart of accounts and mappings unapproved                 | External accountant / Finance Controller | Signed chart and every role mapped                      |
| PB-03 | Critical | Opening balances unapproved                               | Finance Controller / MD                  | Signed opening trial balance reconciled to source       |
| PB-04 | Critical | VAT/WHT/tax IDs/NRS unverified                            | Tax adviser                              | Written opinion, approved rates, NRS evidence           |
| PB-05 | High     | TLS/domain not supplied                                   | Infrastructure                           | Certificate chain and external HTTPS test               |
| PB-06 | High     | No off-host encrypted backup                              | Infrastructure                           | Encrypted bucket, retention, key custody, restore proof |
| PB-07 | High     | No monitoring/alerting                                    | Operations                               | Health/5xx/auth/backup/certificate alerts with owner    |
| PB-08 | High     | No production load test                                   | Engineering                              | Target-host p95 and capacity evidence                   |
| PB-09 | High     | No DR/failover test                                       | Infrastructure                           | Measured RPO/RTO and integrity check                    |
| PB-10 | High     | No production migration                                   | Finance / data owner                     | Trial import, exception log, reconciliation             |
| PB-11 | High     | Role matrix/approval authority unsigned                   | Managing Director                        | Signed matrix and delegation record                     |
| PB-12 | Medium   | 25 APIViews lack schemas; 6 enum collisions               | Engineering                              | Annotated views and clean schema review                 |
| PB-13 | Medium   | Python CVE scan absent                                    | Engineering                              | `pip-audit`/CI and accepted-risk register               |
| PB-14 | Medium   | Dependencies behind current releases                      | Engineering                              | Tested upgrade plan                                     |
| PB-15 | Medium   | Upload/PDF browser coverage incomplete                    | QA                                       | Permitted/rejected upload and PDF tests                 |
| PB-16 | Medium   | Sustained write concurrency unproven                      | Engineering                              | Production-like write load and lock/deadlock results    |
| PB-17 | Medium   | Formal UAT signatures absent                              | Management                               | Signed owner/developer acceptance                       |
| PB-18 | Low      | Project issues do not create `ProjectCost`                | Product/Finance                          | Confirm intended cost model                             |
| PB-19 | Low      | Some UI controls rely on API rejection                    | Frontend                                 | Permission-aware controls across modules                |
| PB-20 | Critical | Live financial activation/NRS/bank execution unauthorised | Managing Director                        | Written go-live authorisation                           |

## 7. Required sequence before a future go-live

1. Supply and verify the production host, domain, DNS and TLS certificate.
2. Provision a secret store; populate `DJANGO_SECRET_KEY`, bank and MFA Fernet keys, database/Redis passwords and company SMTP credentials.
3. Provision private PostgreSQL/Redis, off-host encrypted backups, monitoring and alert routing.
4. Build and deploy to staging; run HTTPS, MFA, permission, email, backup and restore smoke tests.
5. Obtain the approved chart of accounts, mappings, posting rules and tax opinion.
6. Reconcile and approve opening balances and the source migration schedules.
7. Perform a real staging migration rehearsal and reconcile every control account.
8. Complete the owner and developer acceptance records; close UAT-D-004.
9. Re-run regression, production check, load/concurrency/failure tests and a rollback rehearsal.
10. Obtain written Managing Director authorisation for go-live and, separately, financial activation.
11. Activate invoices/posting only after the dated activation checklist is complete.
12. Complete the first month-end close and record operational acceptance.

## 8. Deployment decision

**Not authorised.** A deployment performed solely because automated tests pass would violate the stated control boundary. No production deployment, live transaction, bank execution or NRS submission was performed in this assignment.

## 9. Sign-off

| Role                | Name | Decision                         | Date |
| ------------------- | ---- | -------------------------------- | ---- |
| Software Developer  |      | Production readiness assessed    |      |
| Managing Director   |      | Infrastructure/business approval |      |
| External accountant |      | Financial configuration approval |      |
| Managing Director   |      | Go-live authorisation            |      |
