# Full-system security audit

**Date:** 12 November 2026
**Scope:** Django API, Angular SPA, authentication, authorization, data protection, uploads, dependency and deployment configuration.
**Reference:** OWASP ASVS 4.0 themes, adapted to a session-authenticated single-tenant enterprise application.
**Limitation:** This is a code/configuration review plus automated tests, not a penetration test. No production host, real customer data or external identity provider was accessed.

## 1. Executive summary

The application has a sound authentication baseline, encrypted bank account
data, permission-aware reporting/documents and production settings that fail
closed. Two significant authorization defects were found during the audit and
fixed:

1. **Critical — master-data write exposure:** any authenticated employee could
   create or modify suppliers, customers, catalogue items, warehouses,
   departments and cost centres.
2. **High — ledger read exposure:** any authenticated employee could read
   accounts, journals, trial balance, financial statements and the general
   ledger.

Both now enforce Django model/accounting permissions and have regression tests.
Residual high-risk items are absence of MFA enforcement, unresolved
inventory/procurement read policy, no general API rate limiting, and no
production monitoring. The system is not approved for production on security
grounds yet.

## 2. Authentication and session management

| Control | State |
| --- | --- |
| Password storage | Argon2 primary hasher |
| Password policy | Django validators configured; minimum length/commonalities/numeric checks |
| Login failure messages | Generic for unknown user, wrong password and disabled account |
| Lockout | django-axes, 5 failures, one-hour cool-off, by IP and username |
| Session lifetime | 1 hour, HttpOnly, SameSite=Lax; Secure in production |
| Session invalidation | Password change rotates session auth hash and deletes reset tokens |
| Password reset | Administrator-issued single-use token, hashed at rest, scoped throttle 20/hour |
| CSRF | Django CSRF middleware, SPA obtains token from `/api/v1/auth/csrf/`; session auth enforces CSRF |
| MFA | **Not enforced.** `mfa_required` exists as a field but no TOTP/WebAuthn flow exists |
| Logout | Session logout endpoint |

**Finding SEC-01 (High, open):** MFA is an attribute only. Administrative and
finance roles can sign in with a password alone. MFA enrolment/enforcement must
be implemented or formally risk-accepted before production.

## 3. Authorization

### 3.1 Corrected findings

**SEC-02 (Critical, fixed) — master-data endpoints were authentication-only.**
`MasterDataViewSet`/`NoDeleteViewSet` supplied list/create/update but no model
permission checks. Any signed-in employee could alter commercial master data.
Fix: `shared/permissions.py` maps safe methods to `view_*`, POST to `add_*`,
PUT/PATCH to `change_*`; DELETE remains a controlled 409/deactivation. Applied
to parties, catalogue, organisation and warehousing viewsets, including the
bank-account change request. Regression:
`test_master_data_requires_model_permissions` proves 403 without permission,
200 for read with `view_party`, and 403 for write with read-only permission.

**SEC-03 (High, fixed) — accounting reads were open to any authenticated user.**
`AccountingReadMixin` now requires the model's `view_*` permission on accounts,
roles, mappings, fiscal years, periods, journals, opening balances, posting
rules and financial events. Trial balance, financial statements and general
ledger call `_require("accounting.view_account")`. Regression:
`test_financial_views_require_accounting_permission`.

### 3.2 Verified controls

- Reporting enforces `view_reporting`, `view_financialreporting` and
  `export_reporting`; hiding a tab is not the control.
- Documents enforce model permissions and private-file access; a 403 regression
  test exists.
- Bank account changes are visible only to their creator unless the reviewer has
  `approve_bankaccountchange`; self-approval is refused.
- Approval workflows separate create/approve and check the specific approve
  permission rather than a role name.
- The role matrix is data-driven and a drift test compares grants to the
  intended provisional matrix.

### 3.3 Residual

**SEC-04 (High, open) — inventory and procurement reads.** These list/read
endpoints still rely on authentication plus action-specific checks. Stock
levels, supplier quotations and purchase history are commercially sensitive.
A management decision is needed on which roles may read them; then the same
model-permission pattern should be applied.

**SEC-05 (Medium, open) — default permission is `IsAuthenticated`.** Any new
model endpoint that forgets a permission class is exposed to every signed-in
employee. The master-data gap is an example. Prefer a permission-required
default for new viewsets, with explicit `AllowAny` only for login/health.

## 4. Object-level and cross-user access

- Bank-account change requests are filtered to the creator unless the approver
  permission is held.
- Documents are private and served through authenticated endpoints, not a
  public media URL.
- Invoice/payment viewsets check module permissions rather than relying on the
  Angular menu.
- Tests cover unprivileged 403s for supplier invoices, customer invoices,
  invoice notes, payments, invoice settings, NRS submissions, equipment and
  reports.

No cross-tenant model exists; this is a single-company deployment. Object-level
checks therefore focus on per-record creator/approver rules and module
permissions.

## 5. Data protection

- Bank account numbers are encrypted with Fernet; only last four digits are
  stored/displayed in clear; audit logs deliberately omit the number and
  ciphertext.
- Production refuses to start without at least one valid Fernet key.
- Documents are hashed (SHA-256), size-limited (10 MiB default), extension
  allow-listed and stored under private media.
- No real credentials were found in source. A scan found only synthetic test
  passwords.
- Logs include request IDs and structured events; bank/account secrets are not
  logged.
- Backups contain the database and private documents and are not encrypted by
  the script; storage-layer encryption is mandatory (open operational risk).

## 6. Input, output and application security

| Area | Finding |
| --- | --- |
| SQL injection | ORM and parameterised queries; no raw SQL building from request input found |
| XSS | Angular escaping; nginx CSP `default-src 'self'`, `script-src 'self'`, no inline scripts; `style-src` permits inline styles |
| CSRF | Session auth + CSRF middleware; unsafe methods require token |
| CSV injection | Report exports neutralise formula-leading values |
| File uploads | Extension, size and checksum validation; MIME is recorded, not trusted as the only control |
| PDF generation | Server-side; no user-supplied template execution found |
| Error disclosure | Envelope returns code/message/request ID; production `DEBUG=False` |
| Security headers | HSTS, nosniff, DENY framing, referrer policy, permissions policy, CSP via nginx |
| Rate limiting | Only password reset is throttled; login is protected by lockout, but general API abuse is not throttled |
| Outbound requests | No unrestricted user-controlled URL fetch identified |
| NRS/bank integrations | Disabled/not authorised; no live credentials present |

**SEC-06 (Medium, open):** no general per-user/IP API throttle. Add throttling
for expensive report/export endpoints and authentication-adjacent APIs before
production.

## 7. Dependency and configuration security

| Check | Result |
| --- | --- |
| `pip check` | No broken requirements |
| `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
| Production `check --deploy` with required env | Exit 0; 165 OpenAPI schema warnings; one weak-key warning caused by the throwaway verification key, not repository configuration |
| Production secrets | Fail closed; no committed production values |
| TLS | nginx TLS 1.2/1.3 configuration present; certificates not supplied |
| Database/Redis | Private network; Redis requires password; no public ports for DB/Redis |
| Container user | Backend runs as non-root `tmd` user |
| Debug | `DEBUG=False` in production |

The 165 warnings are documentation/schema-generation warnings for plain
`APIView` classes, not security-control failures. They mean some endpoints are
less completely described in the generated OpenAPI document.

## 8. Audit logging

Append-only `AuditEvent` records exist with hash chaining, actor, action, entity
and before/after data. They are used by approvals, documents, reporting exports
and selected governance actions. Not every CRUD operation writes an audit event;
financial and approval-critical transitions are the priority. Broader coverage
should be assessed against TMD's retention policy.

## 9. OWASP ASVS gap summary

| ASVS area | Status |
| --- | --- |
| V1 Architecture | Adequate for a monolith; threat model not formally documented |
| V2 Authentication | Password/lockout/session good; MFA absent |
| V3 Session | Secure cookies, rotation, timeout; production TLS pending |
| V4 Access control | Major gaps fixed; residual inventory/procurement read policy and default-auth risk |
| V5 Validation | Serializers, constraints, upload validation present |
| V6 Cryptography | Argon2, Fernet, TLS config; backup encryption pending |
| V7 Error/logging | Structured logs, request IDs; monitoring/alerting absent |
| V8 Data protection | Private documents, masked bank data; backup encryption pending |
| V9 Communications | nginx TLS/HSTS configured; certificates pending |
| V10 Malicious code | Dependencies audited; no secrets found |
| V11 Business logic | Approval separation and state machines tested; no full abuse-case testing |
| V12 Files | Extension/size/private storage controls present |
| V13 API | Permissions on sensitive modules; general throttling absent |
| V14 Configuration | Production fail-closed; auth/inventory/procurement gaps above |

## 10. Conclusion

The most dangerous authorization defects are fixed and regression-tested. The
application is materially safer than at the start of the audit. It is still
**not production-approved** because MFA, general API throttling, the
inventory/procurement access decision, monitoring and encrypted off-host backups
remain open.

**Security readiness: B — acceptable for controlled staging/UAT with synthetic
data; production approval withheld pending SEC-01, SEC-04, SEC-05, SEC-06 and
the operational controls in the Phase 11 report.**
