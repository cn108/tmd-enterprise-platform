# Final TMD UAT report

> **Current-status note (13 November 2026).** MFA and general API throttling were implemented after this report. See `final-security-assessment.md` and `final-business-acceptance-report.md`.

**Date:** 12 November 2026
**Scope:** the existing TMD Enterprise System — procurement, inventory, accounting, invoicing, banking, projects, services, leasing and reporting.
**Environment:** isolated `tmd_staging`; synthetic company and employees only.
**Production activation:** none. No deployment, push, live payment, production invoice or NRS submission was performed.

## 1. Readiness decision

# A. Ready for controlled employee UAT

This decision applies to **controlled, supervised employee acceptance testing on synthetic staging data**. It does **not** mean the system is ready for production.

The system now:
- starts cleanly on an isolated staging database;
- contains realistic, internally reconciled synthetic data;
- completes all eight required end-to-end workflows;
- enforces least-privilege access across 10 roles through both the API and the Angular portal;
- exports management reports from posted journals;
- passes 295 backend tests, 50 frontend tests, frontend build and lint;
- passes five browser acceptance workflows with screenshots;
- survives a measured concurrent read load with zero unexpected errors;
- restores an encrypted database dump into an isolated database.

## 2. Evidence summary

| Area | Result |
| --- | --- |
| Staging setup | PASS — 63 migrations, isolated DB, guarded seed |
| Synthetic reconciliation | PASS — trial balance, balance sheet, AP, AR, inventory and bank all reconcile |
| Role acceptance | PASS — 130/130 API checks across 10 roles |
| End-to-end workflows | PASS — 8/8, plus partial delivery, damage, duplicate, cancellation and concurrency tests |
| Browser acceptance | PASS — 5/5 Playwright workflows, 9 screenshots |
| Performance | PASS for controlled UAT — 400 requests, 61.5 req/s, 0 unexpected errors |
| Security remediation | Partially complete — critical staging defects fixed; MFA/TLS/off-host backup remain production blockers |
| Backend regression | PASS — 295 tests |
| Frontend regression | PASS — 50 tests, build and lint |
| Production readiness | **NOT READY** — see blockers register |

## 3. Defects corrected during this assignment

| ID | Severity | Correction |
| --- | --- | --- |
| RBAC-01 | High | Fixed the role-matrix CRUD grant bug that silently granted no view/add/change permissions |
| RBAC-02 | High | Opened the banking import/match/submit/approve lifecycle to the correct finance roles |
| RBAC-03 | High | Closed authentication-only read access on procurement and inventory |
| RBAC-04 | High | Added explicit guards to procurement submit/issue/close/receive actions |
| RBAC-05 | High | Granted operational service and leasing actions to Operations and Project Management |
| RBAC-06 | Medium | Separated create and edit permissions in the portal; Auditor cannot create a request |
| RBAC-07 | Medium | Let operational employees raise purchase requests without granting approval |
| SEC-01 | High | Removed all 130 OpenAPI authenticator warnings; added report response schemas |

All corrected items were retested. No corrected defect regressed in the final suites.

## 4. Residual UAT findings

| ID | Severity | Finding | Effect on UAT |
| --- | --- | --- | --- |
| UAT-01 | Medium | 25 custom APIViews still lack OpenAPI response schemas; 6 enum-name collisions remain | API documentation incomplete; runtime works |
| UAT-02 | Medium | Purchase-order list p95 is 681 ms under 16-worker local load | Usable for a small UAT group; re-measure on target infrastructure |
| UAT-03 | Medium | No sustained write-concurrency load, database-failure or worker-failure test | Integrity is covered by targeted tests, not by infrastructure failure testing |
| UAT-04 | Medium | No Python CVE scan; several dependencies are behind current releases | Security debt; requires separate upgrade pass |
| UAT-05 | Medium | Work-order browser coverage is list-level; file upload and every PDF were not driven in the browser | Manual UAT should exercise uploads and PDFs |
| UAT-06 | Low | Project issues appear in project reporting but do not create a `ProjectCost` row | Explain to project users during UAT |
| UAT-07 | Low | Maintenance was created as planned, not completed, in the seed | Manual completion remains a UAT script item |
| UAT-08 | Low | Some UI create/edit controls outside procurement still rely on API rejection rather than hiding/disabling | Train testers that the API is the authority |

None of these prevents controlled UAT. They are recorded for the UAT defect log.

## 5. Conditions for the UAT

1. Use only `tmd_staging` and the `@staging.tmd.local` identities.
2. Do not connect a real bank feed, execute a transfer, issue a customer invoice for collection or submit to NRS.
3. Treat tax rates, chart of accounts, mappings and opening balances as provisional test data.
4. Record policy decisions separately; do not change production policy from UAT feedback without approval.
5. Capture defects with role, document number, expected result, actual result and screenshot.
6. Re-run `verify_staging_uat`, `verify_workflows` and `check_role_access` after any staging reset.

## 6. Production assessment

**Production is not ready.** The system has strong functional depth and now has materially better access control, but production finance cannot be authorized while:
- the chart of accounts, account-role mappings, opening balances, tax policy and inventory method are unapproved;
- MFA is not implemented or enforced;
- TLS termination and certificate evidence are absent;
- an off-host encrypted backup destination, retention and key custody are not configured;
- monitoring, alerting and an operational owner are absent;
- production-scale performance and disaster recovery are unproven;
- management has not signed the UAT result and go-live authorization.

## 7. Final statement

The TMD Enterprise System is suitable for **controlled employee UAT on synthetic data**. It is **not suitable for production financial operations** on the evidence available. No production readiness is claimed.

## 8. UI/UX addendum — dashboard and access presentation

**Date:** 12 November 2026

A follow-up review replaced the dashboard's API status and permission dump with role-aware financial, invoice, pending-action, activity and quick-action sections. It also replaced raw permission warnings with **View only**, **Limited actions** and **Access restricted** states, retaining backend enforcement.

The review covered Management, Finance, Procurement, Warehouse, Project Manager, Auditor and System Administrator accounts on staging. Five focused browser tests passed, alongside 26 backend reporting tests, 52 frontend unit tests, frontend lint and the production build.

Evidence and before/after screenshots: [`uiux-dashboard-and-access-report.md`](uiux-dashboard-and-access-report.md).

Residual finding UAT-08 is partially addressed for the dashboard and the modules reviewed here; other create/edit controls should continue to be checked during UAT. Production activation remains disabled.
