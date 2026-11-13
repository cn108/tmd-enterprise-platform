# Developer / technical acceptance script

**Participant:** Software Developer / Technical Administrator  
**System:** TMD Enterprise System, isolated QA/UAT environment  
**Purpose:** confirm functionality, security, data integrity, backup/restore, deployment preparation and monitoring readiness.  
**Status:** **script prepared — technical acceptance record pending**

> This is a technical acceptance, not a production go-live authorisation. No live invoice, payment, bank transfer, NRS submission or production database operation is permitted.

## 1. Build and regression

| # | Check | Command / evidence | Expected | Result |
| --- | --- | --- | --- | --- |
| DEV-01 | Backend suite | `POSTGRES_DB=tmd_qa_adversarial_20261113 .venv/Scripts/python.exe -m pytest -q` | All tests pass | ☐ Pass ☐ Fail |
| DEV-02 | Backend lint | `ruff check .` | No errors | ☐ Pass ☐ Fail |
| DEV-03 | Django system check | `manage.py check` | No issues (silenced warning permitted) | ☐ Pass ☐ Fail |
| DEV-04 | Migration drift | `manage.py makemigrations --check --dry-run` | No changes | ☐ Pass ☐ Fail |
| DEV-05 | Frontend unit tests | `npm test -- --watch=false` | All tests pass | ☐ Pass ☐ Fail |
| DEV-06 | Frontend lint/build | `npm run lint && npm run build` | Both pass | ☐ Pass ☐ Fail |
| DEV-07 | Browser UAT | `npx playwright test e2e/formal-uat.spec.ts --reporter=line` | All role workflows pass | ☐ Pass ☐ Fail |

## 2. Authentication, MFA and permissions

| # | Check | Expected | Result |
| --- | --- | --- | --- |
| DEV-08 | Sign in without MFA where the account is not enrolled, then enrol a test account. | Enrolment returns a secret and recovery codes once; confirmation starts a session. | ☐ Pass ☐ Fail |
| DEV-09 | Sign in again with a TOTP code. | A challenge is issued before the session; a valid code starts the session. | ☐ Pass ☐ Fail |
| DEV-10 | Reuse the same challenge or code. | Replay is refused; a challenge is single-use. | ☐ Pass ☐ Fail |
| DEV-11 | Use a recovery code twice. | First use succeeds; second use is refused. | ☐ Pass ☐ Fail |
| DEV-12 | Sign in with a wrong/expired code. | No session is created; the error does not reveal whether the account exists. | ☐ Pass ☐ Fail |
| DEV-13 | Check an operating role against restricted APIs. | Correct 403, no object data or PDF is returned. | ☐ Pass ☐ Fail |
| DEV-14 | Check Management/Auditor administration access. | Read 200; create/change 403. | ☐ Pass ☐ Fail |
| DEV-15 | Check CSRF and foreign-origin mutation. | Missing token and foreign origin are refused. | ☐ Pass ☐ Fail |
| DEV-16 | Check API throttle behaviour. | Configured limits apply; a throttled request returns 429 without data. | ☐ Pass ☐ Fail |

## 3. Financial integrity

| # | Check | Expected | Result |
| --- | --- | --- | --- |
| DEV-17 | Post an approved customer receipt. | Bank debit, AR credit and advances credit balance; one journal only. | ☐ Pass ☐ Fail |
| DEV-18 | Replay a posted invoice/payment/receipt. | Original journal is returned; no duplicate. | ☐ Pass ☐ Fail |
| DEV-19 | Post a supplier payment. | AP/advance debit and bank credit balance; test-mode refusal remains. | ☐ Pass ☐ Fail |
| DEV-20 | Reverse a posted receipt. | Reversal journal is created; original remains immutable. | ☐ Pass ☐ Fail |
| DEV-21 | Attempt a gross posting with an approved note or WHT. | Refused with a controlled conflict; no partial ledger. | ☐ Pass ☐ Fail |
| DEV-22 | Attempt a duplicate/concurrent allocation. | Exactly one succeeds; the other returns conflict. | ☐ Pass ☐ Fail |
| DEV-23 | Verify trial balance and control accounts on synthetic data. | Debits equal credits; AR/AP/inventory/bank reconcile to source records. | ☐ Pass ☐ Fail |
| DEV-24 | Verify negative stock and posted-journal database guards. | Database refuses the operation. | ☐ Pass ☐ Fail |

## 4. Data, backup and recovery

| # | Check | Expected | Result |
| --- | --- | --- | --- |
| DEV-25 | Run the migration template validator. | 15 templates/17 rows, 0 errors, 0 warnings. | ☐ Pass ☐ Fail |
| DEV-26 | Run `scripts/test-restore.sh`. | Backup and isolated restore pass; migration, row, ledger and media checks match. | ☐ Pass ☐ Fail |
| DEV-27 | Inspect the backup manifest. | SHA-256, timestamp, database, migration count and retention are present. | ☐ Pass ☐ Fail |
| DEV-28 | Confirm the restore target is isolated and removed. | No live database was overwritten. | ☐ Pass ☐ Fail |

## 5. Production configuration and monitoring

| # | Check | Expected | Result |
| --- | --- | --- | --- |
| DEV-29 | Run `manage.py check --deploy` with production settings and test secrets. | Exit 0; no `security.W*` warnings; only documented schema warnings. | ☐ Pass ☐ Fail |
| DEV-30 | Validate `docker compose config`. | Configuration resolves without exposing secrets. | ☐ Pass ☐ Fail |
| DEV-31 | Verify production MFA/email/rate variables. | All required values present; no personal Gmail; production MFA on. | ☐ Pass ☐ Fail |
| DEV-32 | Check health endpoints and structured logs. | Liveness/readiness answer; errors carry request IDs; no secrets in logs. | ☐ Pass ☐ Fail |
| DEV-33 | Check dependency audit. | `npm audit --omit=dev` reports 0; Python audit tool available or gap recorded. | ☐ Pass ☐ Fail |
| DEV-34 | Review monitoring/alerting. | Health, 5xx, auth, backup, certificate and database alerts have an owner. | ☐ Pass ☐ Fail |

## 6. Deployment and rollback

| # | Check | Expected | Result |
| --- | --- | --- | --- |
| DEV-35 | Build images in a non-production environment. | Images build and start; non-root backend. | ☐ Pass ☐ Fail |
| DEV-36 | Deploy to a staging host with TLS. | HTTPS redirect, HSTS, CSP and private DB/Redis verified. | ☐ Pass ☐ Fail |
| DEV-37 | Exercise rollback. | Previous image restored; database restore procedure validated; smoke tests pass. | ☐ Pass ☐ Fail |
| DEV-38 | Record release and migration numbers. | Evidence retained; no secret in the artifact. | ☐ Pass ☐ Fail |

## 7. Acceptance decision

**Technical acceptance:** ☐ Accepted ☐ Accepted with conditions ☐ Not accepted

**Open technical blockers (must be named, not hidden):**

1. Production host, domain and TLS certificate not supplied.
2. Off-host encrypted backup destination and monitoring not configured.
3. Production-scale load/concurrency/failure testing not performed.
4. Python dependency audit tool not installed in this environment.
5. OpenAPI schema warnings for some plain API views remain.
6. Real migration import and reconciliation not performed.

| Field | Entry |
| --- | --- |
| Name | ________________________________ |
| Role | Software Developer / Technical Administrator |
| Date | ________________________________ |
| Signature | ________________________________ |
