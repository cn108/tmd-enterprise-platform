# TMD Enterprise System — Full Adversarial Testing Report

**Testing window:** 12–13 November 2026  
**Environment:** isolated QA clone `tmd_qa_adversarial_20261113`, cloned from `tmd_staging`  
**Application under test:** Angular frontend on `127.0.0.1:49630`, Django API on `127.0.0.1:8000`  
**Safety state:** `test_mode=True`, `can_issue=False`, NRS submission and production financial activation disabled; email backend set to console output  
**Verdict:** **A — passed adversarial acceptance and ready for formal management UAT**, with the limitations recorded in section 10.

---

## 1. Executive summary

The exercise covered all ten roles defined by the live `role_matrix.py`, all twelve top-level workspaces, all 104 administrator tab states, 45 API abuse probes, seven session/CSRF checks, five real-browser form attacks, and a safe 104-tab interaction sweep.

| Measure                                                       |                                                            Result |
| ------------------------------------------------------------- | ----------------------------------------------------------------: |
| Roles exercised through the real login page                   |                                                       **10 / 10** |
| Role × workspace page visits                                  |                                                           **120** |
| Visible controls discovered across those visits               |                                                         **4,718** |
| Administrator tab states inventoried                          |                                                           **104** |
| Tab states with at least one row                              |                                                      **69 / 104** |
| Controls deliberately exercised in the safe sweep             |                                                           **466** |
| Create dialogs opened and cancelled without writing           |                                                            **82** |
| Row detail dialogs opened and closed                          |                                                            **69** |
| Column sorts exercised                                        |                                                            **60** |
| Page-level JavaScript errors                                  |                                                             **0** |
| API probe checks                                              |                                                **45 / 45 passed** |
| Session/CSRF checks                                           |                                                  **7 / 7 passed** |
| Cross-module and concurrency tests                            |                                                     **33 passed** |
| Backend suite after fixes                                     |                                                    **343 passed** |
| Frontend unit suite after fixes                               |                                                     **70 passed** |
| Playwright suite after fixes                                  |                                                     **18 passed** |
| Application defects fixed                                     |                                                             **6** |
| Critical / high / medium defects remaining from this exercise |                                                       **0 known** |
| Low residual issues                                           | **1 accepted** (expected 403 console noise on restricted modules) |

Six application defects were found and corrected. Two of them broke ordinary master-data work outright (party selection and supplier/customer currency defaulting). Two produced misleading or missing feedback (negative credit limits and invisible file-upload errors). Two produced visible buttons that could never succeed (RFQ invitation View and computed-report View). All six have regression coverage and were re-tested.

No production data, staging data, bank transfer, NRS submission, customer email or financial posting was created or changed by this exercise.

---

## 2. Environment and guard rails

- A dedicated database named `tmd_qa_adversarial_20261113` was cloned from `tmd_staging`. Counts matched before testing: 12 users, 5 parties, 1 purchase order and 11 journals.
- The QA API was started with `POSTGRES_DB=tmd_qa_adversarial_20261113`; staging was never used as the running API database.
- The existing Angular frontend was pointed at the QA API through its development proxy.
- Email was redirected to Django's console backend. No outbound mail was sent.
- NRS issuance, production posting and bank-transfer execution remained disabled.
- New records were prefixed `QA-`; existing company records were never deleted.
- No push, deployment, staging reset or production migration was performed.
- The test role password is intentionally omitted from every report and evidence file.

## 3. Method

1. Read the live role matrix, permission groups and seeded users; did not rely on older role lists.
2. Signed in through the actual Angular login page for every role, inspected every workspace, and recorded restricted states and direct API outcomes.
3. Inventoried every visible interactive element on every role/page and every administrator tab.
4. Ran a safe browser interaction sweep: every tab, every available create dialog, every sortable table header, and the first row detail dialog — closing without saving.
5. Submitted hostile and invalid values through the real forms: empty required fields, stored `<script>`/`onerror` markup, SQL-like search text, negative money, impossible dates, and an executable upload.
6. Probed the API independently with 45 guard-railed checks covering permissions, invalid input, duplicate records, invalid state transitions, over-allocation and CSRF/session behaviour.
7. Ran the existing cross-module/concurrency integration tests for procurement, inventory, invoicing, banking, projects, services, leasing and reporting.
8. Fixed every confirmed critical, high and medium defect, added regression coverage, and reran affected and full suites.

## 4. What was discovered

### 4.1 Role and access discovery

The live matrix contains **10 roles**, not the older example list. There is no separate "General Requester" role: every authenticated employee may raise a purchase request subject to backend permissions. Management and Auditor intentionally hold read-only access-administration grants.

| Role                 | Effective permissions | Dashboard focus       | Pages visited | Controls seen |
| -------------------- | --------------------: | --------------------- | ------------: | ------------: |
| System Administrator |                   623 | Management overview   |            12 |           498 |
| Management           |                   142 | Management overview   |            12 |           464 |
| Accountant           |                   194 | Finance workspace     |            12 |           477 |
| Finance Controller   |                   148 | Finance workspace     |            12 |           476 |
| Finance Officer      |                   154 | Finance workspace     |            12 |           464 |
| Procurement Officer  |                   158 | Procurement workspace |            12 |           475 |
| Project Manager      |                   172 | Project workspace     |            12 |           458 |
| Storekeeper          |                   118 | Warehouse workspace   |            12 |           477 |
| Operations / HSE     |                   138 | Your workspace        |            12 |           466 |
| Auditor              |                   132 | Finance workspace     |            12 |           463 |

Full role detail is in [role-by-role-test-results.md](role-by-role-test-results.md).

### 4.2 Control discovery

The 4,718 visible controls comprise 2,727 buttons, 1,792 links, 199 inputs and 37 disabled controls. All 104 administrator tab states were inventoried; 4,615 controls were observed in the administrator tab pass alone. Counts include repeated navigation/table controls across roles, so they are discovery counts, not unique-widget counts.

The safe interaction sweep exercised **466 controls** and wrote [browser-control-interactions.json](evidence/adversarial/browser-control-interactions.json). It opened and cancelled 82 create dialogs, opened and closed 69 row-detail dialogs, and exercised 60 column sorts. It made no create, edit, approve, post, cancel or delete request.

### 4.3 Form and input attacks

Five real-browser tests covered:

- empty required fields in supplier, customer, project and purchase-request forms;
- `<script>window.__qaXss=1</script>` stored in a supplier name, plus an `onerror`-bearing note;
- an SQL-like supplier search string;
- a negative customer credit limit;
- a project whose end date precedes its start date;
- an `.exe` upload.

All malicious-looking text rendered literally, no dialog executed, no script flag was set, and no unintended record was written. See [invalid-input-and-validation-report.md](invalid-input-and-validation-report.md).

### 4.4 API abuse probes

The probe command `qa_adversarial_probe` passed **45/45 checks** and **7/7 session checks** against the QA API. Status distribution: 2×200, 22×400, 1×401, 9×403, 1×404 and 10×409. Evidence: [api-probe.json](evidence/adversarial/api-probe.json).

It confirmed:

- unauthorised roles cannot read bank accounts, supplier invoices, customer invoices or access-administration records;
- the creator/approver separation is enforced by the backend;
- missing CSRF token and foreign-origin mutations return 403;
- logout invalidates the session (`204`, then `/me` returns `401`);
- the session cookie is `HttpOnly`;
- invalid records are not created when validation fails (supplier count unchanged at 8 before/after create probes).

### 4.5 Cross-module verification

Thirty-three targeted integration/concurrency tests passed across the real API layer:

- procurement receipt and over-receipt refusal;
- signed stock movements and derived balances;
- partial deliveries invoiced across split receipts;
- three-way matching and over-invoicing refusal;
- customer receipt partial/multiple allocation and over-allocation refusal;
- invoice approval, tested PDF, approved-invoice immutability;
- supplier payment creating an unreconciled bank expectation;
- concurrent posting creating exactly one journal;
- concurrent receipt allocation creating exactly one allocation;
- bank CSV import, matching and independent reconciliation approval;
- project cost summary without double counting commitments/receipts/stock transfers;
- full work-order workflow;
- rental dispatch, return, inspection and maintenance;
- payables ageing and dashboard payment-history integrity.

Details are in [cross-module-workflow-test-report.md](cross-module-workflow-test-report.md).

## 5. Defects found and fixed

| ID         | Severity | Defect                                                                                                                                                                                                                                                                                                                 | Fix                                                                                                                                | Regression                                                                                             |
| ---------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| TMD-ADV-01 | High     | `/api/v1/parties/` returned 403 for every user, including the superuser, because `PartyViewSet` had no `queryset` for the shared model-permission class. Party dropdowns in contacts, addresses, tax registrations and other forms could not load choices.                                                             | Added the model queryset and used `super().get_queryset()`.                                                                        | Permission assertions added to the existing master-data test; 24 party tests pass.                     |
| TMD-ADV-02 | Medium   | Negative customer credit limits (`-1.00`) were accepted by the API; only the browser's `min=0` stopped them.                                                                                                                                                                                                           | Server-side `validate_credit_limit` rejects values below zero.                                                                     | New backend test asserts 400 and a `credit_limit` field error.                                         |
| TMD-ADV-03 | High     | Supplier and customer forms started with `Currency = null`; submitting without manually selecting NGN produced "This field may not be null." The model default was not reflected in the UI.                                                                                                                            | All configured currency selects now default to NGN, the only configured reporting currency.                                        | New frontend unit test asserts the supplier form default is NGN.                                       |
| TMD-ADV-04 | Medium   | A rejected `.exe` upload showed only "One or more fields are invalid."; the backend's specific file message was present in state but hidden because the file input was not bound to the Material form field that controls `mat-error` visibility.                                                                      | File-field errors are rendered in an explicit alert block beside the control.                                                      | Browser test asserts the exact "Files of type .exe are not accepted" message and one failed POST only. |
| TMD-ADV-05 | Medium   | RFQ invitations showed a View button, but the endpoint implemented only list/create, so every View returned 404 and left an error banner.                                                                                                                                                                              | Added `RetrieveModelMixin` to `RfqSupplierViewSet`.                                                                                | New backend test reads an invitation detail and checks the supplier name.                              |
| TMD-ADV-06 | High     | Computed dashboard/report tabs (banking dashboard, reconciliation report, project dashboard, profitability, equipment utilisation/availability, stock balances, reorder alerts, matching suggestions, unmatched transactions) showed View but had no per-row retrieve endpoint. View produced 404 and an error banner. | Added `detailFromRow` to those resources; View opens the detail already present in the row without calling a nonexistent endpoint. | New frontend unit test asserts no detail request and a dialog opening; the 104-tab sweep passes.       |

No critical defect was found. No financial corruption, unbalanced journal, unauthorised financial operation, data loss or permission bypass remained after fixes.

## 6. Verification after fixes

| Check                     | Result                                                 |
| ------------------------- | ------------------------------------------------------ |
| Backend tests             | **343 passed**                                         |
| Backend Ruff              | **All checks passed**                                  |
| Django migrations         | **No changes detected**                                |
| Django system check       | **No issues** (one silenced check)                     |
| Frontend unit tests       | **70 passed**                                          |
| Frontend lint             | **All files pass**                                     |
| Production build          | **Success**, 359.95 kB initial raw / 95.40 kB transfer |
| Playwright                | **18 passed** in 4.8 minutes                           |
| API probe                 | **45/45**                                              |
| Session/CSRF checks       | **7/7**                                                |
| 10-role browser matrix    | **120 visits**, zero page errors                       |
| 104-tab interaction sweep | **466 controls**, zero page errors                     |

Before/after: backend 341 → 343 tests; frontend 68 → 70 tests; Playwright 10 → 18 tests; targeted cross-module runs 21 → 33. The added coverage is the negative-credit backend test, RFQ-detail backend test, currency-default frontend test, computed-row frontend test, five browser form attacks and the 104-tab sweep. The API probe count stayed at 45; its four initial failures were two probe-fixture errors and two application findings (the party endpoint, which accounted for two checks, and negative credit), and it now passes 45/45.

## 7. Evidence index

- [Role matrix JSON](evidence/adversarial/browser-role-matrix.json)
- [Administrator tab inventory](evidence/adversarial/browser-tab-inventory.json)
- [Safe interaction sweep](evidence/adversarial/browser-control-interactions.json)
- [API probe results](evidence/adversarial/api-probe.json)
- [Required-field screenshot](evidence/adversarial/form-01-required-fields.png)
- [Stored-XSS detail screenshot](evidence/adversarial/form-02-escaped-xss-detail.png)
- [Negative-credit screenshot](evidence/adversarial/form-03-negative-credit-blocked.png)
- [SQL-like search screenshot](evidence/adversarial/form-04-sql-like-search.png)
- [Impossible-date screenshot](evidence/adversarial/form-05-impossible-project-dates.png)
- [Empty purchase-request screenshot](evidence/adversarial/form-06-empty-purchase-request.png)
- [Executable-upload screenshot](evidence/adversarial/form-07-executable-upload-refused.png)
- Browser traces: captured locally during the adversarial run (session-bearing archives not committed).

## 8. What was not tested

- No real bank transfer, NRS submission, production invoice issuance or external email was executed; these are disabled by design.
- Financial activation and posting policy remain blocked pending management/accounting approval. This is a governance decision, not a code defect.
- The sweep opened create and view dialogs but did not save every create form. Destructive transitions (approve, post, cancel, deactivate, delete) were tested through dedicated QA fixtures and API probes rather than against every seeded row.
- The 4,718 control count includes repeated navigation/table controls across roles. It is not a count of unique widgets, and not every one was individually clicked. The 466 exercised controls, 104 tab states, 120 role-page visits and 69 detail dialogs are the actual interaction coverage.
- Five browser console messages remain on restricted workspaces; they are the browser reporting the backend's correct 403 before the Access Restricted panel renders. They expose no data and are recorded as a low residual issue.

## 9. Assumptions

- The QA clone is an acceptable stand-in for staging because the schema, seed data and permission matrix are identical.
- NGN is the only configured reporting currency, so defaulting currency selects to NGN is safe and matches the model default.
- Computed report rows are projections, not editable business records; opening their detail from the loaded row is the correct behaviour.
- Management/Auditor read access to access-administration is intentional and was verified as read-only.

## 10. Acceptance statement

**A. The application has passed the adversarial acceptance tests and is ready for formal management UAT.**

The basis is: no known critical, high or medium defect remains; 343 backend, 70 frontend and 18 browser tests pass; the 10-role matrix shows no privilege bypass; financial posting and external integrations remain safely disabled; and all six confirmed application defects have regression coverage. Formal UAT should still explicitly cover the operational procedures and the production-activation decisions listed in section 8.

This verdict covers the adversarial register. Pre-existing production-hardening items in the earlier full-system security audit (MFA enforcement and general API throttling) remain separately tracked and should be resolved before production go-live; they did not produce a failure in this exercise.
