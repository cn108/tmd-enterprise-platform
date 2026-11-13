# Final UAT Summary

**System:** TMD Enterprise System  
**UAT cycle:** 13 November 2026  
**Environment:** Isolated QA database `tmd_qa_adversarial_20261113`; frontend `http://127.0.0.1:49630`; API `http://127.0.0.1:8000`  
**Data:** Synthetic QA records only  
**Production integrations:** Invoice issuance, financial posting, bank execution and NRS submission remain disabled  
**Technical execution:** Complete for the executed scripts  
**Formal UAT result:** **CONDITIONAL — TECHNICAL EXECUTION COMPLETE; BUSINESS ACCEPTANCE PENDING**

> **This document does not declare UAT successful.** No named business representative has signed acceptance. Three management/security decisions remain open. The system is not authorised for production release by this report.

## 1. Deliverables

| Deliverable | Status |
|---|---|
| `management-uat.md` | Complete; Management sign-off outstanding |
| `procurement-uat.md` | Complete; Procurement/Management sign-off outstanding |
| `warehouse-uat.md` | Complete; Warehouse sign-off outstanding |
| `finance-uat.md` | Complete; Finance Controller/Management sign-off outstanding |
| `project-operations-uat.md` | Complete; Project and Operations/HSE sign-off outstanding |
| `administration-uat.md` | Complete; Administration/Management/Audit sign-off outstanding; includes Audit script and role-permission matrix |
| `uat-defect-register.md` | Complete; 1 open management decision, 3 fixed technical items |
| `final-uat-summary.md` | This document |

Supporting evidence:

- `evidence/uat-api-probe.json` — role, workflow, access and production-control results.
- `evidence/screenshots/` — 24 full-page role and restricted-access screenshots.
- `frontend/e2e/formal-uat.spec.ts` — repeatable keyboard/mouse UAT evidence run.
- `backend/apps/core/management/commands/qa_uat_probe.py` — controlled QA workflow and security probe.

## 2. Technical execution result

| Check | Result |
|---|---|
| Formal UAT browser journey | **9/9 passed** |
| Frontend unit suite | **71/71 passed** |
| Frontend lint | Passed |
| Frontend production build | Passed |
| Backend regression (last recorded) | **343 passed**; Ruff clean; no missing migrations |
| Formal UAT API probe | **5/5 checks passed** |
| Role-access matrix (prior adversarial cycle) | **130/130 checks passed**, 10 roles |
| API security probe (prior adversarial cycle) | **45/45** |
| Playwright adversarial journey (prior cycle) | **18/18** |

The browser journey used real sign-in for all ten roles, not mocked sessions. The API probe used the real permission classes but authenticated the synthetic role users directly for repeatable permission checks.

## 3. Role-group outcome

| Business area | Technical result | Business acceptance |
|---|---|---|
| Management | PASS — dashboard, procurement oversight, financial statements, read-only administration, approval separation, production gates | **PENDING** |
| Procurement | PASS — draft creation, submission, independent approval, PO/GRN visibility, auditor read-only, banking restriction | **PENDING** |
| Warehouse | PASS — valuation, movements, stock receipt, project issue, reconciliation; stock adjustment and physical count not executed | **PENDING** |
| Finance | PASS — invoices, AP/AR, reconciliation, journals, statements, payment status, production gates; no new posting or bank execution | **PENDING** |
| Project Management | PASS — project dashboard, project stock cost, service/rental evidence; new budget variation not executed | **PENDING** |
| Operations/HSE | PASS — work orders, operational reports, invoices/banking/administration restrictions | **PENDING** |
| Administration | PASS — ten roles, user/role administration, read-only Management/Auditor access, operating-role denial; user/role changes not executed | **PENDING** |
| Audit | PASS — read-only procurement and administration, financial reporting access, no write path | **PENDING** |

## 4. Investigation outcomes

### 4.1 MFA enforcement — **closed, implemented**

TOTP MFA is now implemented: encrypted device secrets, one-time enrolment/login challenges, replay refusal, one-time recovery codes, per-user enforcement and production-wide enforcement. Five backend tests and two frontend login tests pass. Development/UAT leaves MFA optional for synthetic accounts; production defaults it on. See UAT-D-002.

### 4.2 API throttling — **closed, configurable controls implemented**

General authenticated and anonymous throttles plus scoped login, MFA and password-reset rates are configured. Production uses tighter defaults. Axes remains enabled at 5 failed attempts with a 1-hour cool-off. The production rates still require a capacity review, but the technical control is no longer absent. See UAT-D-003.

### 4.3 Management/Auditor administrative permissions — **intentional, read-only**

Management and Auditor can read users, roles and permissions; they cannot create or change them. API evidence: `GET /access/users/` 200, `GET /access/roles/` 200, `POST /access/users/` 403 for both. This supports oversight and audit independence without granting administrative write access. It is not a defect.

### 4.4 Unnecessary requests from restricted modules — **fixed**

Previously, an authorised module route loaded its first list endpoint before the UI knew the role could not view the module. The API correctly returned 403, but the browser logged avoidable console errors and made unnecessary requests.

The workspace now carries `viewPermissions` on the module configuration and checks them before `load()` is called. Invoicing requires `invoicing.view_supplierinvoice` or `invoicing.view_customerinvoice`; Banking requires `banking.view_bankaccount` or `banking.view_reconciliation`. The restricted page shows “Access restricted”, hides its tabs and makes no data request.

**Retest:** Procurement and Storekeeper Banking, and Operations Invoicing and Banking all made **zero** matching data API requests and produced **zero** 403 console errors. See UAT-D-001.

### 4.5 Final role and permission matrix — **provisional, decision required**

Ten roles are configured. Permission counts observed:

| Role | Permissions |
|---|---:|
| System Administrator | 623 |
| Management | 142 |
| Accountant | 194 |
| Finance Controller | 148 |
| Finance Officer | 154 |
| Procurement Officer | 158 |
| Project Manager | 172 |
| Storekeeper | 118 |
| Operations / HSE | 138 |
| Auditor | 132 |

There is **no General Requester role**. Operating roles can raise purchase requests within their existing role; Auditor is read-only and cannot raise one. Management must ratify this design or approve a replacement matrix. The full module-access and per-role sign-off matrix is in `administration-uat.md` §5.

## 5. Defect and decision status

| ID | Severity | Status | Item |
|---|---|---|---|
| UAT-D-001 | Medium | **Fixed** | Restricted modules made unnecessary API requests and logged 403 console errors |
| UAT-D-002 | High | **Fixed** | MFA enrolment, challenge, recovery and production enforcement implemented |
| UAT-D-003 | Medium | **Fixed** | Configurable API, login and MFA throttles implemented |
| UAT-D-004 | High | **Open — decision** | Provisional ten-role matrix and no General Requester role |

No Critical defect was found. Four candidate items were closed as intentional design or input validation: Management/Auditor read-only admin access, trial-balance parameter validation, least-privilege reporting, and disabled production execution.

## 6. Production safety state

| Control | State |
|---|---|
| Invoice test mode | **ON** |
| Invoice issuance activated | **NO** (`activated_at = null`) |
| NRS submission | **DISABLED** (`nrs_enabled = false`, no environment) |
| Supplier payment execution | **NOT EXECUTED**; payments recorded only |
| Bank execution adapter | **NOT ENABLED** |
| New financial postings during UAT | **0** |
| New invoices issued during UAT | **0** |
| New purchase orders/receipts during UAT | **0** |
| Controlled procurement approval during UAT | `PR-2026-0002` approved; no downstream commitment |

## 7. What was actually tested, and what was not

**Executed with new evidence in this cycle:**

- Real sign-in and role-specific browser journeys for Management, Procurement, Warehouse, Finance, Project, Operations, Administration and Audit.
- A new procurement request (`PR-2026-0002`) created by Procurement, submitted, and independently approved by Management.
- Financial statements computed and rendered; supplier invoices, reconciliation, journals, stock valuation, movements, receipt, project dashboard, work orders and operational reports inspected.
- API permission probes for all ten roles, Management/Auditor read-only administration, Operations restrictions and production gates.
- Restricted-module network and console checks.

**Not executed — requires business witness, authorisation or is outside the control boundary:**

- Physical stock count, new stock adjustment or write-off.
- New project budget/variation approval.
- RFQ issue, quote evaluation and supplier selection.
- New supplier invoice posting or payment execution through a bank.
- New user creation, role change or permission change.
- NRS submission or production invoice issuance.
- Import of any real company data.

These are documented as `NOT RUN` in the relevant role scripts; absence of evidence is not treated as a pass.

## 8. Controlled data migration

The controlled migration plan is in `administration-uat.md` §6. It covers extract, clean, stage, validate, opening balances, user/role mapping, parallel run, cutover, rollback and hypercare, with mandatory reconciliation gates. **Migration status: NOT STARTED. No real records imported.**

## 9. Recommendation

**Do not treat this UAT as accepted or complete.** Proceed to formal business acceptance only after:

1. Management signs UAT-D-004 (role matrix and no-General-Requester decision).
2. Management ratifies or replaces the ten-role matrix and records the no-General-Requester decision (UAT-D-004).
3. The named Management, Procurement, Warehouse, Finance, Project, Operations/HSE, Administration and Audit representatives sign their scripts.
4. The `NOT RUN` transaction cases are scheduled with the relevant business witnesses, without activating production invoice issuance, financial posting, bank execution or NRS.

The executed evidence supports a **conditional technical pass**. It does not support a declaration of production readiness or business acceptance.

## 10. Master acceptance sign-off

| Business area | Representative | Decision | Signature | Date |
|---|---|---|---|---|
| Management | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |
| Procurement | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |
| Warehouse | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |
| Finance | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |
| Project Management | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |
| Operations / HSE | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |
| Administration | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |
| Audit | ________________ | ☐ Accept ☐ Condition ☐ Reject | ____________ | ________ |

**Overall formal status: CONDITIONAL TECHNICAL PASS — BUSINESS ACCEPTANCE PENDING.**
