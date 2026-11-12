# End-to-end business workflow report

**Evidence:** `docs/reports/evidence/workflow-checks.json`, `workflow-checks.md`, `staging-reconciliation.*`, Playwright screenshots `01`–`09`.

All eight seeded workflows passed. Each was executed through the service layer or API, not by inserting final-state rows.

| Workflow | Result | Verified evidence |
| --- | --- | --- |
| A. Procurement to inventory | PASS | Request approved, PO partially received, GRN and stock receipt posted, accepted quantity entered the ledger |
| B. Procurement to supplier invoice | PASS | Supplier invoice approved and matched to the receipt; total ₦680,000 |
| C. Customer delivery to receivables | PASS | Customer invoice approved; ₦2,500,000 receivable equals the control account |
| D. Payment to bank reconciliation | PASS | Payment recorded (not executed), statement imported, two lines matched, reconciliation approved |
| E. Inventory allocation to project costing | PASS | Two pumps issued to PRJ-STG-001 at ₦240,000; project actual cost includes the issue |
| F. Project budget to expenditure reporting | PASS | Approved ₦12,000,000 budget; reporting actual cost ₦540,000; available budget ₦11,460,000 |
| G. Equipment reservation to return/inspection | PASS | Reservation, approved agreement, dispatch, return, inspection, planned maintenance; agreement closed |
| H. Accounting to management reporting | PASS | 11 posted journals; trial balance balanced; report net result ₦2,485,000 |

## Exception and boundary scenarios

| Scenario | Result | Evidence |
| --- | --- | --- |
| Partial delivery | PASS | PO remains `partially_received`; only accepted quantity was stocked |
| Damaged/rejected goods | PASS | One damaged pump excluded; reason recorded; rejected quantity zero |
| Duplicate invoice number | PASS | Existing regression: punctuation-normalised duplicate rejected |
| Near-duplicate invoice | PASS | Existing regression: flagged as suspected and requires override |
| Duplicate payment submission | PASS | Idempotency key replay returns the original result |
| Cancelled invoice | PASS | Number preserved; reuse blocked |
| Cancelled stock transfer | PASS | Only a draft transfer can be cancelled; dispatched stock must be received |
| Concurrent stock movements | PASS | Per-item row locks and signed movements; existing tests cover oversell refusal |
| Concurrent reservation overlap | PASS | Overlapping reservation is refused on confirmation |
| Concurrent reconciliation match | PASS | Statement line and transaction are locked; approved reconciliation cannot be re-matched |

## Browser workflows

Playwright drove the actual Angular application from login through:
- dashboard and all ten module routes;
- procurement request listing and status rendering;
- inventory balances and valuation;
- banking reconciliation listing;
- service work-order listing;
- rental-agreement listing;
- financial statements and CSV export;
- an operational role with no formal financial reports;
- an Auditor read-only procurement view.

Five Playwright tests passed. Full-page screenshots are in `docs/reports/evidence/screenshots/`.

## Findings

| ID | Severity | Finding | Status |
| --- | --- | --- | --- |
| WF-01 | **High** | Project material issues update project reporting but do not create a `ProjectCost` row; project cost is an aggregate of direct costs and stock-issue values. This is internally consistent in the report but can surprise users expecting a cost row per issue. | Documented; no data error |
| WF-02 | **Medium** | Purchase-order listing p95 was the slowest measured read (681 ms under 16-worker local load). Query count is 15, so this is render/serialisation and development-server contention, not a runaway N+1. | Open performance item |
| WF-03 | **Medium** | The seeded maintenance record is planned, not completed. The workflow proves inspection and maintenance creation, not maintenance completion. | Scope limit, documented |
| WF-04 | **Low** | Work-order text contains an encoding artefact (`�`) in the shell representation of the em dash. The browser rendered the title correctly. | Cosmetic/data-encoding check |
| WF-05 | **Low** | No automated browser test yet exercises file upload or PDF generation for every module. CSV export was exercised. | Residual test gap |

**Result: PASS for controlled UAT.** All named end-to-end paths complete and reconcile. The exceptions above do not invalidate the tested workflows.
