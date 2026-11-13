# Final Adversarial Acceptance Report

**Date:** 13 November 2026  
**System:** TMD Enterprise System  
**Environment:** isolated QA clone `tmd_qa_adversarial_20261113`  
**Safety state:** test mode on, invoice issuance off, NRS disabled, email console sink, no external bank transfer  
**Final answer:** **A — the application has passed the adversarial acceptance tests and is ready for formal management UAT.**

---

## 1. Acceptance question

> Can the TMD Enterprise System withstand realistic employee behaviour, incorrect input, repeated operations, unauthorised access and unexpected situations?

**Yes, for the tested scope, with the stated limitations.**

The application now has no known critical, high or medium defect after the exercise. Six real defects were found and corrected. The remaining issue is a low-severity console-noise item on restricted modules; it does not expose data or permit an operation.

## 2. Evidence supporting the verdict

| Evidence area | Result |
|---|---|
| Roles tested through the real login | **10 / 10** |
| Workspaces visited per role | **12 / 12** (120 visits) |
| Administrator tab states | **104 / 104** |
| Visible controls discovered | **4,718** |
| Safe browser interactions | **466** |
| Create dialogs opened and cancelled | **82** |
| Detail dialogs opened and closed | **69** |
| Sorts exercised | **60** |
| Page JavaScript errors | **0** |
| API abuse probes | **45 / 45 passed** |
| Session/CSRF checks | **7 / 7 passed** |
| Cross-module/concurrency tests | **33 passed** |
| Backend suite | **343 passed** |
| Frontend unit suite | **70 passed** |
| Playwright suite | **18 passed** |
| Ruff / migrations / Django check | Passed / none pending / clean |
| Frontend lint / build | Passed / successful |

### Before and after

| Suite | Before | After |
|---|---:|---:|
| Backend tests | 341 | **343** |
| Frontend tests | 68 | **70** |
| Playwright tests | 10 | **18** |
| API probe checks | 45 (4 failing) | **45 passing** |
| Session/CSRF checks | 6 passing, 1 harness error | **7 passing** |
| 10-role browser matrix | Not present | **10 roles / 120 visits** |
| 104-tab interaction sweep | Not present | **104 tabs / 466 controls** |

The API probe's four initial failures were not four independent app defects: two checks were the same party-endpoint defect, one was a probe that posted a customer-only field to the supplier endpoint, and one was a rental-dispatch probe missing the required equipment. The party endpoint and negative-credit gaps were fixed; the two probe fixtures were corrected. The session-cookie assertion was a probe timing error (checked after logout).

## 3. Why the answer is A rather than B

A "B" would require an important defect to remain. The register contains:

- **0 critical** — no financial corruption, data loss, security compromise or unauthorised financial operation.
- **0 high** — the three high defects (party lookup denial, null currency blocking creation, dead computed-report View buttons) are fixed and regression-tested.
- **0 medium** — negative credit, hidden file error and RFQ View 404 are fixed and regression-tested.
- **1 low residual** — five expected 403 console messages on restricted modules; the UI correctly shows Access Restricted and no data leaks.

The safety controls held throughout: CSRF, foreign-origin rejection, object-level denial, creator/approver separation, no duplicate posting under races, no over-allocation, no receipt against closed orders, no posting in closed periods and no production financial activation.

**Scope qualifier:** this is the adversarial register. It does not close the pre-existing production-hardening backlog recorded in the earlier full-system security audit (for example MFA enforcement and general API throttling). Those items remain separately tracked and should be resolved before production go-live; they did not produce a failure in this exercise.

## 4. What changed

| ID | Change | Regression |
|---|---|---|
| TMD-ADV-01 | Restored model-aware permission for the party option endpoint | Existing master-data test extended; 24 party tests pass |
| TMD-ADV-02 | Rejected negative customer credit limits server-side | New backend test |
| TMD-ADV-03 | Defaulted all currency fields to the configured NGN currency | New frontend unit test |
| TMD-ADV-04 | Made file-upload rejection messages visible beside the control | Browser form test |
| TMD-ADV-05 | Added RFQ invitation detail retrieval | New backend test |
| TMD-ADV-06 | Computed report View now opens row detail locally | New frontend unit test; 104-tab sweep |

No business rule was invented. The only default introduced (NGN) is the only configured currency and matches the model default. Financial policy remains untouched.

## 5. Safety attestation

- No staging data was reset.
- No production database was accessed.
- No existing company record was deleted.
- No real bank transfer was executed.
- No NRS invoice was submitted.
- No real customer/supplier email was sent.
- No production invoice issuance or accounting posting was activated.
- No commit was pushed and no deployment was performed.
- QA fixtures are marked `QA-` and remain confined to the isolated QA clone.
- No password or secret is included in these reports.

## 6. Conditions for formal management UAT

The following are operational preconditions, not code defects:

1. Run the formal UAT against staging with the intended named role holders, not shared synthetic accounts.
2. Obtain the accounting/management decision required before enabling production invoice issuance and ledger posting.
3. Test external integrations (NRS, real email, bank statement sources) in a separately authorised environment; they were intentionally disabled here.
4. Accept or schedule the low-severity restricted-page console noise.
5. Extend file testing to oversized, corrupted and MIME-mismatched files if the document module is in the UAT critical path.
6. Exercise the remaining destructive lifecycle buttons with dedicated UAT records; this exercise used API/integration tests for those transitions rather than mass-clicking seeded rows.

## 7. Honest coverage statement

This report does **not** claim that all 4,718 discovered controls were clicked. The 4,718 figure is a discovery count across 120 role-page visits and repeats navigation and row controls for each role and record. Actual deliberate browser interactions were 466 across all 104 tab states, plus 5 form-attack scenarios, 45 API probes and 33 workflow/concurrency tests.

No coverage percentage is stated because the denominator is not a set of unique controls. What is claimed is that every role, every workspace, every tab, every create dialog, every available row-detail action in the sweep, the principal validation paths and the critical financial state transitions were exercised, and that no known critical/high/medium defect remains.

## 8. Final statement

**The TMD Enterprise System has passed the adversarial acceptance exercise and is ready for formal management UAT.**

The result is supported by repeatable browser evidence, API probes, integration tests, concurrency tests and a clean full regression run. The application should proceed to management UAT with the production financial controls still disabled until the required policy approval is recorded.

---

### Evidence

- [Master report](full-adversarial-testing-report.md)
- [Role results](role-by-role-test-results.md)
- [Control audit](button-and-control-audit.md)
- [Invalid input report](invalid-input-and-validation-report.md)
- [Security report](security-and-permission-test-report.md)
- [Cross-module report](cross-module-workflow-test-report.md)
- [Defect register](defect-register-and-fixes.md)
- [Role matrix JSON](evidence/adversarial/browser-role-matrix.json)
- [API probe JSON](evidence/adversarial/api-probe.json)
- [Interaction sweep JSON](evidence/adversarial/browser-control-interactions.json)
