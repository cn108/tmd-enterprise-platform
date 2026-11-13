# TMD Enterprise System — Final Security Assessment

**Date:** 13 November 2026  
**Scope:** application-level authentication, authorization, MFA, API abuse controls, data integrity, file handling, audit and production configuration  
**Environment:** isolated QA/UAT database with synthetic accounts; production was not deployed  
**Overall:** no known unresolved Critical/High **application-level** security defect; production infrastructure and independent penetration testing remain outstanding

## 1. Controls verified

| Control               | Implementation                                                                                                                                                                | Evidence                                                |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Authentication        | Session cookie, CSRF on mutations, Axes lockout (5 failures / 1 hour), Argon2 passwords                                                                                       | 7/7 session/CSRF checks; backend tests                  |
| MFA                   | TOTP, encrypted device secret, signed one-time challenge, six-digit verification, replay prevention, hashed one-time recovery codes, per-user and production-wide enforcement | 5 backend MFA tests; 2 frontend login tests             |
| MFA browser flow      | Playwright MFA test: enrolment, TOTP login, recovery code and replay refusal                                                                                                  | 1 Playwright test                                       |
| Authorization         | Authenticated-by-default; model/action permissions; object-level checks; approval permissions                                                                                 | 45/45 direct API checks; 120 role-page visits           |
| Administration        | Management/Auditor read-only; writes 403                                                                                                                                      | UAT probe                                               |
| Segregation of duties | Creator ≠ approver; two approvers at high bands; no repeat decisions                                                                                                          | Role/workflow tests                                     |
| API throttling        | Global authenticated/anonymous + scoped login, MFA and password-reset limits; configurable through environment                                                                | Settings and UAT probe                                  |
| File upload           | Extension/size validation, private storage, authenticated audited download                                                                                                    | Real `.exe` rejected; no public media URL               |
| Injection/XSS         | ORM-bound queries; hostile text rendered literally                                                                                                                            | XSS/SQL-like probe                                      |
| Error handling        | Structured error envelope with request ID; no stack traces or SQL to browser                                                                                                  | API probes/log review                                   |
| Audit                 | Hash-chained append-only events; posted journals and stock movements protected by database triggers                                                                           | Audit tests and schema                                  |
| Secrets               | No committed production credentials; production fails closed; bank/MFA keys encrypted                                                                                         | `prod.py`; `.env.example`; secret scan reviewed         |
| Production config     | HTTPS redirect, secure cookies, HSTS, CSP, frame denial, trusted CSRF origins                                                                                                 | `check --deploy`: 0 security warnings with test secrets |

## 2. MFA implementation detail

- `MfaDevice` stores a Fernet-encrypted TOTP secret, confirmation time, last-used counter and hashed recovery codes.
- Login issues a short-lived signed challenge instead of a session when MFA is required.
- Enrolment requires a valid challenge and confirms a code before creating the session.
- A TOTP counter cannot be replayed; a used challenge cannot be reused. Challenge and device rows are locked in a database transaction while the code is consumed, so concurrent submissions cannot both succeed.
- Recovery codes are single-use and removed after use; they are shown only at enrolment. Each code carries 64 bits of random entropy and only its password-hash is stored.
- `MFA_REQUIRED_FOR_ALL_USERS` is false in development/UAT and **true in production**.
- `MFA_ENCRYPTION_KEY` is mandatory in production; losing it without retaining the old key makes existing devices unusable.
- `python manage.py reset_mfa <email>` removes the device and pending challenges after identity verification; `--disable-requirement` exists only for controlled recovery.

Regression evidence: `backend/apps/identity/tests/test_mfa.py` covers enrolment, session start, login verification, challenge replay, recovery-code single use, global enforcement and invalid-code refusal.

## 3. Throttling

Configured classes: `UserRateThrottle` and `AnonRateThrottle` by default, plus `ScopedRateThrottle` on login, MFA and password-reset views.

| Scope              | Development default | Production default |
| ------------------ | ------------------- | ------------------ |
| Authenticated user | 20,000/hour         | 5,000/hour         |
| Anonymous          | 5,000/hour          | 120/hour           |
| Login              | 120/min             | 10/min             |
| MFA                | 60/min              | 10/min             |
| Password reset     | 20/hour             | 20/hour            |

These are engineering defaults, not an approved capacity policy. Production-tuning requires a load/capacity review. Axes remains an independent lockout layer.

## 4. Findings closed or dispositioned

| ID                      | Finding                                                        | Disposition                                                                                |
| ----------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| SEC-01 / UAT-D-002      | MFA was a stored flag with no enforcement                      | **Closed** — full TOTP flow implemented and tested                                         |
| SEC-06 / UAT-D-003      | No general API throttle                                        | **Closed** — configurable global and scoped throttles                                      |
| UAT-D-001               | Restricted modules requested data before showing access denied | **Closed** — permission preflight; browser retest showed no request/403 console error      |
| Email default           | Personal Gmail address used as a default                       | **Closed** — default removed, production rejects Gmail, forward migration clears old value |
| Party option permission | Endpoint denied legitimate lookups                             | **Fixed** — queryset added, permission still enforced                                      |
| RFQ invitation detail   | Missing retrieval route                                        | **Fixed**                                                                                  |
| Computed report row     | Called nonexistent detail route                                | **Fixed**                                                                                  |

## 5. Residual risks and gaps

| Risk                                                                                      | Severity            | Status                                                            |
| ----------------------------------------------------------------------------------------- | ------------------- | ----------------------------------------------------------------- |
| No production TLS/host independent test; no external penetration test                     | High for production | Open — infrastructure                                             |
| No off-host encrypted backup or key-custody evidence                                      | High for production | Open                                                              |
| No monitoring/alerting or on-call owner                                                   | High for operations | Open                                                              |
| No production-scale load/concurrency/failure test                                         | High for capacity   | Open                                                              |
| Python dependency CVE scan not installed (`pip-audit` absent)                             | Medium              | Open — CI/infrastructure                                          |
| 37 OpenAPI schema warnings; some plain views omitted                                      | Medium              | Open — documentation debt                                         |
| File upload edge cases (oversized, corrupted, MIME mismatch, filename) not browser-tested | Medium              | Open — coverage gap                                               |
| Session idle/absolute expiry not waited out in browser                                    | Low/Medium          | Partial — configured, not elapsed                                 |
| No independent host/network penetration test                                              | High for production | Open — external assurance                                         |
| MFA recovery is administrator-assisted; no self-service                                   | Low                 | Accepted for small team; identity verification procedure required |
| Document access is authenticated-user based; entity-level sharing policy not final        | Medium              | Policy open                                                       |
| No background worker; long reports synchronous                                            | Medium              | Architecture limitation                                           |

## 6. Production security prerequisites

1. Company-controlled domain, valid TLS chain, HSTS verified from an external client.
2. Private PostgreSQL/Redis with no public ports and least-privilege database users.
3. Secret manager; rotated Django, bank and MFA keys; no secrets in images, logs or tickets.
4. Company SMTP identity with SPF/DKIM/DMARC; no personal mailbox.
5. Off-host encrypted backups with retention, immutability and restore monitoring.
6. Error tracking, metrics, alert routing and a named on-call owner.
7. MFA enforced for all production users; recovery process tested.
8. Dependency scanning in CI and a tested patch cadence.
9. Independent penetration test and remediation before go-live.
10. Written security acceptance by the Managing Director.

## 7. Limitations of this assessment

This was an application-level security review, not a penetration test of the host, TLS terminator, reverse proxy, database, cloud account or email infrastructure. No production deployment exists to test. No external identity provider, WAF, SIEM or managed detection service was in scope. No real customer, supplier or financial data was used.

## 8. Conclusion

The application has a defensible security baseline for controlled UAT: MFA is now real, API abuse controls exist, authorization is enforced server-side, sensitive financial operations are fail-closed, and audit/immutability controls are present. It is **not** production-security-approved until the infrastructure, independent testing, monitoring and backup controls are supplied and verified.

**Application-level security status: PASS for controlled UAT, with the residual items recorded above.**  
**Production security status: NOT APPROVED.**
