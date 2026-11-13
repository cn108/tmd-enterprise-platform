# TMD Enterprise System — Production Deployment Runbook

**Version:** 1.0  
**Date:** 13 November 2026  
**Status:** prepared; **not executed**  
**Use only after:** `final-production-readiness-report.md` changes from NO-GO to GO and the Managing Director signs the launch authorisation.

## 1. Stop conditions

Do not start if any of the following is true:

- No approved domain/TLS certificate, production host or secret store.
- No signed chart of accounts, mappings, posting rules or tax opinion.
- No reconciled opening balances or approved migration schedule.
- No verified backup/restore and off-host backup destination.
- No monitoring/alert owner.
- UAT-D-004 or the owner/developer acceptance records remain unsigned.
- No written go-live authorisation.
- The release has failing tests, migration drift, a security warning or an unexplained ledger difference.

If a stop condition appears mid-deployment, stop, preserve logs and restore the previous release. Do not improvise a financial workaround.

## 2. Roles

| Role                            | Responsibility                                             |
| ------------------------------- | ---------------------------------------------------------- |
| Release manager                 | Owns the runbook, timeline and go/no-go call               |
| Software Developer              | Builds, deploys, runs migrations and technical smoke tests |
| Finance Controller / accountant | Verifies opening balances, mappings and financial reports  |
| Managing Director               | Authorises launch and any financial activation             |
| Operations / infrastructure     | DNS, TLS, host, secrets, backups, monitoring               |

No one may approve their own financial transaction merely because they are deploying.

## 3. Pre-deployment checklist

- [ ] Release tag/commit and changelog approved; no uncommitted local edits included.
- [ ] Backend tests, frontend tests, lint, build, Ruff, Django check, migration drift all pass.
- [ ] Production `check --deploy` has no security warning.
- [ ] Compose config validated with the real environment file.
- [ ] Database and media backup taken, checksum verified and restore-tested.
- [ ] Off-host encrypted copy exists; retention and key custody confirmed.
- [ ] TLS certificate chain, private key and renewal owner confirmed.
- [ ] DNS points to the production host; HTTPS redirect and HSTS verified externally.
- [ ] Production secrets populated; no development/default secret reused.
- [ ] Company SMTP mailbox tested; SPF/DKIM/DMARC confirmed.
- [ ] Monitoring, alert routing and on-call owner active.
- [ ] Migration CSVs validated; discrepancies resolved; Finance sign-off recorded.
- [ ] Rollback image and previous database backup identified.
- [ ] Maintenance window and user communication agreed.
- [ ] Written launch authorisation on file.

## 4. Environment

Use a protected environment file outside the repository, for example `/etc/tmd/production.env`, mode 0600, owned by the deployment account. Required values are listed in `infra/prod/.env.example`:

```
COMPOSE_PROJECT_NAME=tmd-production
TMD_DOMAIN=erp.<company-domain>
TLS_CERT_DIR=/etc/tmd/tls
POSTGRES_DB=tmd_production
POSTGRES_USER=tmd_app
POSTGRES_PASSWORD=<secret>
REDIS_PASSWORD=<secret>
DJANGO_SECRET_KEY=<long random secret>
BANK_ACCOUNT_ENCRYPTION_KEYS=<Fernet key>
MFA_ENCRYPTION_KEY=<separate Fernet key>
MFA_REQUIRED_FOR_ALL_USERS=true
MFA_ISSUER=Tico McDon Limited
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<company SMTP host>
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=<company mailbox>
EMAIL_HOST_PASSWORD=<secret>
DEFAULT_FROM_EMAIL=<company sender>
API_USER_RATE=5000/hour
API_ANON_RATE=120/hour
LOGIN_RATE=10/min
MFA_RATE=10/min
```

Validate without printing secrets:

```bash
docker compose --env-file /etc/tmd/production.env \
  -f infra/prod/docker-compose.yml config >/dev/null
```

## 5. Build and release

```bash
cd <release-directory>
docker compose --env-file /etc/tmd/production.env \
  -f infra/prod/docker-compose.yml build --pull
docker compose --env-file /etc/tmd/production.env \
  -f infra/prod/docker-compose.yml up -d
```

The backend entrypoint applies migrations and runs `check --deploy` before Gunicorn. Confirm containers are healthy; do not assume a running container means a working application.

```bash
docker compose --env-file /etc/tmd/production.env \
  -f infra/prod/docker-compose.yml ps
docker compose --env-file /etc/tmd/production.env \
  -f infra/prod/docker-compose.yml logs --tail=200 backend
```

## 6. First-run administration

```bash
docker compose --env-file /etc/tmd/production.env \
  -f infra/prod/docker-compose.yml exec backend \
  python manage.py create_initial_admin
```

- Create named accounts; no shared administrator.
- Enrol MFA immediately and store recovery codes offline.
- Assign roles only from the signed matrix.
- Do not create production users from the synthetic seed command.
- Keep the developer's technical administrator role separate from financial approval roles.

## 7. Data migration

Follow `final-data-migration-report.md`:

1. Freeze legacy writes.
2. Take a verified pre-migration backup.
3. Import master data, then projects/stock, then commitments/invoices, then bank/cash/advances.
4. Post the approved opening trial balance through the controlled document.
5. Reconcile AP, AR, inventory, bank, VAT/WHT and advances.
6. Record row counts and discrepancies.
7. Obtain Finance Controller sign-off before continuing.

## 8. Production verification

### Technical

```bash
curl -fsS https://$TMD_DOMAIN/health/
curl -fsS https://$TMD_DOMAIN/health/ready/
```

- HTTPS redirect works; certificate chain valid; HSTS present.
- Sign-in, MFA enrolment/verification, recovery-code refusal after use.
- CSRF mutation refused without token; foreign origin refused.
- Role restrictions return 403; no object leakage.
- Dashboard and a read-only report load.
- API 429 after the configured threshold in an approved test.
- Audit event written for a test-role change and a document download.
- No secret or full bank number in logs/HTML.

### Financial (while activation remains off)

- Test invoice remains marked test-only; posting refused.
- Trial balance/statements load; no unexpected figure.
- Opening balances reconcile to the signed schedule.
- Customer/supplier balances and stock agree to control records.

## 9. Financial activation (separate authorisation)

Do **not** combine this with deployment. Activate only after:

- approved chart, mappings, posting rules and tax configuration;
- signed opening balances and migration acceptance;
- recorded Finance Controller posting review;
- successful production smoke tests;
- written Managing Director activation authorisation.

Then follow the dated activation checklist. Enable in this order: chart/mappings, posting review, invoice issuance, receipt/payment posting, then any separately authorised NRS/bank integration. Verify one controlled transaction and its journal; do not bulk-enable.

## 10. Backups and monitoring

- Confirm the scheduled backup ran after go-live and an off-host copy exists.
- Verify checksum and manifest; do not rely on exit code alone.
- Confirm alerts for health, 5xx, auth failures, database, backup and certificate expiry.
- Record RPO/RTO assumptions and the first restore-drill date.

## 11. Rollback

### Application rollback

1. Stop new writes or put the system in maintenance mode.
2. Record the failing release, time, request IDs and affected records.
3. Start the previous image with the previous environment.
4. Verify health, sign-in, MFA and a read-only report.
5. Do not reverse a database migration by editing migration history.

### Database rollback

If the schema/data change is unsafe:

1. Stop the application.
2. Preserve the failed database and logs.
3. Restore the verified pre-change backup into a clean database.
4. Validate migration count, ledger balance, media and access.
5. Obtain management approval before reconnecting users.
6. Record data loss between backup and incident.

## 12. Launch record

| Field                     | Entry                            |
| ------------------------- | -------------------------------- |
| Release version/commit    |                                  |
| Deployment date/time      |                                  |
| Deployed by               |                                  |
| Migration numbers         |                                  |
| Backup reference/checksum |                                  |
| Smoke-test result         |                                  |
| Financial activation      | Disabled / separately authorised |
| Incidents                 |                                  |
| Approved by (MD)          |                                  |
| Signature/date            |                                  |

**This runbook has not been executed. No production deployment is claimed.**
