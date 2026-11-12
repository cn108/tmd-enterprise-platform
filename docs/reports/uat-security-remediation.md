# Security and deployment hardening report

**Scope:** staging and production configuration review, OpenAPI warnings, MFA readiness, secrets, TLS/headers, backup/restore, dependency checks and privilege tests.

## 1. OpenAPI warnings — investigated and reduced

| Measure | Before | After |
| --- | ---: | ---: |
| “Could not resolve authenticator” warnings | 130 | 0 |
| Report APIViews without a response schema | 2 | 0 |
| Total schema-generation findings | 647 warnings / 129 errors | 13 warnings / 121 errors |
| Unique remaining findings | 138 warnings / 27 errors | 8 warnings / 25 errors |

Corrections:
- Registered an OpenAPI security scheme for `SessionAuthentication401` (session cookie), removing all 130 authenticator warnings.
- Added explicit response and parameter schemas to `ReportView` and `ReportExportView`.

Remaining findings are **not dismissed**:
- 25 custom `APIView` classes still lack a response serializer/annotation (identity CSRF/logout, inventory reports, leasing availability/utilisation/warnings, project dashboard/profitability/documents and similar). Runtime responses are correct; the generated schema omits their response bodies.
- 6 enum-name collisions for repeated `status`/`direction` choice sets. The schema is technically valid but component names are non-optimal.
- These are **Medium** documentation defects, not runtime authorization failures. They should be annotated before external API consumers depend on the schema.

## 2. Authentication, MFA and sessions

| Control | Finding | Severity |
| --- | --- | --- |
| Session authentication | HttpOnly, SameSite=Lax, one-hour default; production sets Secure cookies and CSRF Secure | OK |
| CSRF | Middleware enabled; SPA obtains a token from `/api/v1/auth/csrf/` | OK |
| Login throttling | django-axes installed; failed-attempt reset observed during login | OK |
| MFA | `mfa_required` exists on the user model and is exposed to the client, but no TOTP/WebAuthn enrolment, challenge, recovery codes or login enforcement exists | **Critical (production)** |
| MFA policy | No role requires MFA; no enforcement test exists | **Critical (production)** |

**Conclusion:** MFA is **not implemented**. A boolean flag is not MFA. Production must not be authorized for finance, procurement approval or administration until an MFA provider is integrated, enrolment is enforced for privileged roles, recovery is designed and login is tested end to end.

## 3. Authorization and privilege escalation

- 130 direct-API checks across 10 roles passed (allowed actions do not return 403; denied actions return 403).
- Deep links were exercised in Angular. Operations could not see formal financial statements; Auditor could not create a purchase request.
- The role matrix had been silently broken: its CRUD helper granted no `view_*`, `add_*` or `change_*` permissions. This is fixed and covered by a regression test.
- Procurement and inventory reads no longer rely on authentication alone (SEC-04 closed for those modules).
- No tested role could reach bank execution, NRS submission or production payment execution; those paths remain disabled.

## 4. Secrets and deployment settings

- No real secret was found in the staged changes. Staging passwords are synthetic and confined to the UAT seed and reports.
- `.env`, database dumps and media are ignored by version control.
- Production settings fail closed when `DJANGO_ALLOWED_HOSTS`, the secret key or `BANK_ACCOUNT_ENCRYPTION_KEYS` are missing.
- `manage.py check --deploy` under production settings with a synthetic long key and a generated Fernet key exited 0. With production configuration, no Django `security.W*` warnings were reported; the 33 remaining check entries are schema (W002) findings.
- No TLS certificate, private key or production hostname was supplied. `SECURE_SSL_REDIRECT`, HSTS (one year, subdomains, preload), secure cookies, `X-Content-Type-Options` and a same-origin referrer policy are configured in `prod.py`, but actual TLS termination is unverified.

## 5. Dependencies

- `npm audit --omit=dev`: **0** production vulnerabilities across 15 production dependencies.
- `pip check`: no broken requirements.
- `pip-audit` is not installed, so Python CVE scanning was **not performed**. Outdated packages include Django 5.2.19 (6.1.3 available), DRF 3.16.1, cryptography 46.0.7 and drf-spectacular 0.28.0. Upgrades require a separate compatibility and regression pass; they were not applied during UAT.
- Playwright 1.65.0 was added as a development dependency for acceptance testing.

## 6. Encrypted backup and isolated restore

Procedure tested locally:
1. `pg_dump -Fc tmd_staging`.
2. AES-256 symmetric encryption with `gpg` and a one-time random passphrase.
3. Decryption into a separate dump.
4. Restore into a new isolated database `tmd_restore_uat`.
5. Row-count verification.

Result: 63 migrations, 11 journals, 23 journal lines, 5 parties and 6 stock movements restored. The encrypted archive was 139,793 bytes versus the 926,846-byte plain dump.

**Still missing for production:** an off-host encrypted destination, retention/rotation policy, key custody separate from the backup, scheduled verification, restore-time objective and a documented disaster-recovery owner. The local test proves the procedure, not the production control.

## 7. Monitoring and alerting requirements

Not configured in this environment. Minimum production requirements:
- availability and latency for `/health/` and `/health/ready/`;
- 5xx rate, authentication failures and lockouts;
- database connections, slow queries and replication/backup failures;
- pending/failed financial-event outbox and reconciliation mismatches;
- disk, memory, worker queue depth and certificate expiry;
- alert ownership, escalation path and on-call rota.

## 8. Findings summary

| ID | Severity | Finding | Status |
| --- | --- | --- | --- |
| SEC-01 | **Critical** | MFA is not implemented or enforced | Open; production blocker |
| SEC-02 | **High** | No production TLS certificate/termination evidence | Open; production blocker |
| SEC-03 | **High** | No off-host encrypted backup destination, retention or key custody | Open; production blocker |
| SEC-04 | **High** | Procurement/inventory read access was authentication-only | Fixed and retested |
| SEC-05 | **High** | Role-matrix CRUD grants were silently empty | Fixed and regression-tested |
| SEC-06 | **Medium** | 25 APIViews lack OpenAPI response schemas; 6 enum collisions remain | Open |
| SEC-07 | **Medium** | No Python dependency CVE scan (`pip-audit` absent) | Open |
| SEC-08 | **Medium** | Monitoring/alerting not implemented | Open; production blocker |
| SEC-09 | **Low** | Production check still emits schema warnings; no runtime security warnings | Documented |

**Conclusion:** staging authorization is materially stronger and the critical role defects are fixed. Production security is **not approved** while MFA, TLS evidence, off-host backups and monitoring remain outstanding.
