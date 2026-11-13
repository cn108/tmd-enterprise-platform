# Central UAT Defect and Decision Register

**System:** TMD Enterprise System  
**UAT cycle:** 13 November 2026  
**Environment:** Isolated QA database `tmd_qa_adversarial_20261113`  
**Register owner:** UAT lead / Management  
**Last updated:** 13 November 2026

## 1. How to read this register

| Field | Meaning |
|---|---|
| ID | Stable UAT defect identifier |
| Severity | Critical / High / Medium / Low |
| Type | Technical defect / Security gap / Policy decision / Not a defect |
| Status | Fixed / Open / Decision required / Closed |
| Acceptance impact | Whether the item blocks business acceptance |

A defect is closed only after retest evidence is recorded. A policy decision is not closed by a tester; it requires the named business owner’s written decision.

## 2. Open and fixed items

| ID | Severity | Type | Finding | Root cause / impact | Disposition | Evidence |
|---|---|---|---|---|---|---|
| **UAT-D-001** | Medium | Technical defect | Restricted modules (Invoices/Banking) issued list API requests before showing “Access restricted”, producing expected 403 console errors. | `WorkspaceComponent` called `load()` in its constructor before checking module view permissions. The API correctly denied access, but the UI requested data it knew the role could not use. | **FIXED** — added `viewPermissions` to `ModuleConfig`, preflight `moduleViewDenied`, hidden tabs and skipped `load()`. Retested with no data API request and no 403 console error. | `frontend/e2e/formal-uat.spec.ts` UAT-SEC; `frontend/src/app/features/workspace/workspace.component.spec.ts`; 71 frontend tests pass; lint and build pass |
| **UAT-D-002** | High | Security gap / policy decision | MFA was previously a stored flag only. | The flag was not wired to authentication, so a privileged account was protected by password only. | **CLOSED — implemented and regression-tested.** TOTP enrolment, encrypted secrets, one-time login challenges, replay refusal, recovery codes, per-user enforcement, production global enforcement and an administrator reset command are implemented. MFA remains optional in development/UAT so synthetic accounts continue to work; production defaults it on. | `backend/apps/identity/mfa.py`; `backend/apps/identity/tests/test_mfa.py` (5 tests); `frontend/src/app/features/login/login.component.spec.ts`; `evidence/uat-api-probe.json` (`mfa`) |
| **UAT-D-003** | Medium | Security gap / policy decision | No general API throttle and no login throttle beyond Axes. | A compromised authenticated session could make sustained API requests. | **CLOSED — implemented as configurable controls.** Default authenticated/anonymous/login/MFA throttles are configured; production uses tighter defaults and Axes remains active. Production rates require a capacity review but are no longer absent. | `config/settings/base.py`; `config/settings/prod.py`; `evidence/uat-api-probe.json` (`throttling`) |
| **UAT-D-004** | High | Policy decision | The ten-role matrix is provisional. There is no General Requester role. Auditor is read-only and cannot raise a purchase request. | Request creation is distributed across operating roles, with approval bands providing control. This is a design choice, not a technical failure, but it is not yet formally signed. | **DECISION REQUIRED.** Management must ratify, amend or replace the matrix; the absence of a General Requester role must be recorded as an explicit management decision. | `administration-uat.md` §5; `backend/apps/core/role_matrix.py`; `evidence/uat-api-probe.json` |

## 3. Reviewed and closed as not defects

| ID | Item | Review result | Disposition |
|---|---|---|---|
| UAT-D-005 | Management and Auditor can read Users/Roles in Administration. | Intentional. Both have `view_user`, `view_group` and `view_permission`; neither has add/change. Direct writes return 403. | **CLOSED — designed read-only oversight.** |
| UAT-D-006 | `/api/v1/trial-balance/` returned HTTP 400 for every role when called without date parameters. | Missing required input validation, not a permission failure. Authenticated authorised roles receive 200 with a valid period. | **CLOSED — not a defect.** |
| UAT-D-007 | Operations sees “Financial statements” absent from Reports. | Least-privilege reporting is intentional; operational report tabs remain. | **CLOSED — designed access control.** |
| UAT-D-008 | Supplier payments are `recorded`, not executed; invoices are test documents; NRS is disabled. | Production controls are intentionally off. No bank adapter or NRS submission is enabled. | **CLOSED — control boundary, not a defect.** |
| UAT-D-009 | No General Requester role. | This is the same policy item as UAT-D-004, recorded separately here only to prevent it being logged as a functional bug. | **MERGED INTO UAT-D-004.** |

## 4. Retest log

| Defect | Retest performed | Result | Date |
|---|---|---|---|
| UAT-D-001 | Frontend unit suite; lint; production build; Playwright UAT-SEC on Procurement/Store banking and Operations invoicing/banking | No data API request, no 403 console error; Access restricted rendered; all checks passed | 13 Nov 2026 |
| UAT-D-002 | Backend MFA suite and frontend login tests | Enrolment, login challenge, replay refusal, recovery-code single use, global enforcement and invalid-code refusal passed | 13 Nov 2026 |
| UAT-D-003 | Settings and API probe | Global authenticated/anonymous throttles plus scoped login, MFA and password-reset rates configured; Axes enabled | 13 Nov 2026 |
| UAT-D-004 | Role matrix and access probe | Ten roles loaded; counts and read/write boundaries recorded; decision outstanding | 13 Nov 2026 |

## 5. Defect summary

| Severity | Open | Fixed | Closed as not defect |
|---|---:|---:|---:|
| Critical | 0 | 0 | 0 |
| High | 1 (role matrix) | 1 (MFA) | 0 |
| Medium | 0 | 2 (throttling, restricted API preflight) | 0 |
| Low | 0 | 0 | 4 |
| **Total** | **1** | **3** | **4** |

## 6. Acceptance impact

The technical UAT evidence is sufficient to demonstrate that the executed workflows work and that restricted access is denied. It is **not** sufficient for formal acceptance because:

1. UAT-D-004 requires the role matrix and the no-General-Requester decision to be signed.
2. No named business representative has signed the role scripts.
3. Some transaction-creating cases (new stock adjustment, physical count, new budget variation, invoice posting, payment execution) were deliberately not run; they require a business witness and, for financial actions, separate authorisation.

## 7. Register approval

| Field | Entry |
|---|---|
| Prepared by | UAT lead |
| Reviewed by | ______________________________ |
| Accepted by | ______________________________ |
| Date | ______________________________ |
| Signature | ______________________________ |

**Register status: OPEN — 1 open management decision (UAT-D-004), 3 fixed technical items.**
