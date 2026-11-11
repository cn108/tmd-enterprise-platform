# Security and Compliance Register

**Version:** 0.1 — 11 November 2026
**Guide references:** §8 (security, privacy, operational controls), Appendix B (governance note)
**Status:** Draft. No compliance obligation is asserted as settled law; all Nigerian tax, data-protection and record-keeping items require confirmation by TMD's advisers against current official requirements.

---

## 1. Security controls (with verification method)

| ID | Control | Verification |
| --- | --- | --- |
| S-01 | Role-based access control at module, action and record level | Permission matrix test suite hitting every sensitive endpoint |
| S-02 | Backend authorisation on every sensitive endpoint and object (no reliance on hidden UI) | Direct API calls by unauthorised users must return 403/404 |
| S-03 | Least privilege; segregation of duties (storekeeper cannot approve payments; creator cannot approve own invoice) | Automated negative tests, see `05-…` §7 |
| S-04 | Strong password hashing, secure session/token handling, optional MFA, lockout/rate limiting, immediate disablement | Auth test suite; configuration review |
| S-05 | Restricted access to supplier bank details, employee personal data, financial reports and document downloads | Record-level test per role |
| S-06 | HTTPS in all deployed environments; secure cookies; CSRF protection for cookie-authenticated endpoints | Deployment checklist + automated header test |
| S-07 | Server-side validation of all input; protection against SQL injection, XSS, CSRF, IDOR, insecure uploads, mass assignment | Security test suite + code review against OWASP ASVS baseline |
| S-08 | Upload validation: MIME, size, extension; private storage; authorised streaming; no execution of uploads | Upload attack tests (double extension, SVG/HTML with script, oversized, traversal) |
| S-09 | Encryption of backups and sensitive data at rest where appropriate; restricted production DB access | Infrastructure review |
| S-10 | Audit events for authentication, master-data change, approvals, posting, reversal, export, permission change, document access | Audit coverage test per module |
| S-11 | Append-only audit for ordinary users; actor, timestamp, action, record, before/after, reason, correlation ID | Tamper attempt test |
| S-12 | No secrets in Git, logs, browser storage or assets | Secret scan in CI; log review checklist |
| S-13 | Independent security review before go-live (Guide §8) | Review report; critical/high findings resolved or formally accepted |
| S-14 | Dependency patching and vulnerability response process | CI dependency audit + documented cadence |
| S-15 | External integration payloads validated and authenticated; retries idempotent | Adapter tests with replayed callbacks |

## 2. Data classification (proposed)

| Class | Examples | Handling |
| --- | --- | --- |
| Restricted | Supplier bank details, employee personal data, payroll-adjacent data, tax identifiers, credentials | Encrypted at rest where feasible, masked in UI to unauthorised roles, audited access, never exported casually |
| Confidential | Financial statements, project costs, contracts, price lists, approval limits | Role-restricted, audited exports |
| Internal | Operational documents (POs, GRNs, stock reports) | Authenticated users per role |
| Public | None in release 1 | n/a |

## 3. Threat scenarios worth explicit testing

1. IDOR on document download (guessing another supplier's invoice PDF).
2. Privilege escalation by editing a role payload or by calling an admin endpoint directly.
3. Self-approval via API despite a UI restriction.
4. Mass assignment of `status`, `approved_by`, `posted_at`, amounts or balances.
5. Stored XSS through a supplier name, item description or attachment filename.
6. CSRF against cookie-authenticated mutation endpoints.
7. Replay of a payment execution request creating a second payment.
8. Upload of a disguised executable or an HTML file served inline.
9. Cross-project/cross-department access after a permission change.
10. Access with a disabled account holding a still-valid session.

## 4. Compliance register (confirm with advisers — do not treat as settled)

| ID | Area | What must be confirmed | Owner | Status |
| --- | --- | --- | --- | --- |
| CMP-01 | Tax registration and taxpayer category | TMD's registrations, taxpayer category, applicable obligations | Accountant / tax adviser | UNRESOLVED (Q-24) |
| CMP-02 | E-invoicing / fiscalisation (NRS) | Whether TMD is in scope now, onboarding/API access status, required invoice fields, submission channel, test evidence | Tax adviser | UNRESOLVED (Q-26) |
| CMP-03 | Value added tax treatment | Applicable rates, exemptions, invoice requirements, reporting | Accountant / adviser | UNRESOLVED (Q-24b) |
| CMP-04 | Withholding tax (if applicable to TMD's payments) | Scope, rates, remittance and evidence | Accountant / adviser | UNRESOLVED (Q-24c) |
| CMP-05 | Companies income tax / statutory filings | Periods and reporting needs from the system | Accountant | UNRESOLVED |
| CMP-06 | Company and tax record retention | Mandatory retention periods, format, legal hold | Legal / adviser | UNRESOLVED (Q-28) |
| CMP-07 | Data protection (NDPA 2023 and NDPC guidance) | Lawful basis, notices, data subject handling, breach process, cross-border storage | Legal / adviser | UNRESOLVED (Q-29) |
| CMP-08 | Employment data handling | What employee data is stored and who may see it | Management / adviser | UNRESOLVED |
| CMP-09 | Document retention and destruction | Per category; audit trail retention | Management / adviser | UNRESOLVED (Q-28) |
| CMP-10 | Statutory financial reporting | Basis of preparation the accountant will use | Accountant | UNRESOLVED (P-02) |
| CMP-11 | Retention of system audit logs | Duration and access | Management | UNRESOLVED |
| CMP-12 | Cross-border hosting | Whether data may be stored outside Nigeria | Management / adviser | UNRESOLVED (Q-34) |

Each setting, once confirmed, is recorded with **source, version, effective date, approval owner and implementation date** in the `SystemSetting`/`TaxCode` records (Guide Appendix B).

## 5. Privacy handling rules (implementation commitments)

- Store only data the business needs; no speculative personal fields.
- Restrict reports that expose personal data to named roles.
- Do not log full request bodies for endpoints carrying personal or bank data.
- Support data correction through audited master-data changes; deletion only where retention rules permit, via deactivation.
- Export functions audited with actor, filter and row count.
- Access review at defined intervals (frequency unresolved — Q-29b).

## 6. Operational security controls

| Area | Requirement |
| --- | --- |
| Production access | Least-privilege service accounts; no direct public DB; admin access logged |
| Backups | Automatic, encrypted, stored separately; restore tests recorded (a backup never restored is not a recovery plan) |
| Monitoring | Logs, error alerts, queue and storage monitoring, DB capacity |
| Patching | Documented dependency and OS patch cadence; vulnerability response process |
| Onboarding/offboarding | Checklist with access review and delegation revocation |
| Incident response | Contact tree, severity definitions, containment, breach assessment and notification per adviser guidance |
| Change management | Release approval, rollback plan, post-deployment checks |

## 7. Verification evidence required before go-live

1. Security test suite output covering §1 and §3.
2. Independent review report with findings and resolutions.
3. Restore test evidence for database and documents.
4. Access review signed by management.
5. Adviser sign-off on CMP-01 to CMP-12 items that affect the release.
6. Audit log integrity check (append-only behaviour demonstrated).

## 8. Hard limits recorded for the build

- No online banking credentials are stored (Guide §9, AR/AP phase).
- No real customer/supplier/bank data in development, prompts, logs or public repositories (Guide §14.8).
- No production posting enabled before accountant sign-off (`07-accounting-events.md` §6).
- No external portal exposure in release 1 without separate approval.
