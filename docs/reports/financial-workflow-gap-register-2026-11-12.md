# Financial Workflow Gap Register — 12 November 2026

This register supersedes the earlier financial workflow gap report for the receipt, allocation, banking and note scope. Production financial activation remains disabled.

| ID | Gap / control area | Current state | Evidence | Owner / next action | Severity |
|---|---|---|---|---|---|
| FW-01 | Customer receipt ledger posting | Implemented, fail-closed | 336 tests; receipt posting tests | Approve mappings/rules; activate Stage 7B | High — external dependency |
| FW-02 | Receipt approval thresholds | Configurable via `ApprovalPolicy(document_type=customer_receipt)`; no TMD bands seeded | Threshold test | TMD must approve limits and required roles | High — policy |
| FW-03 | Separation of recording/approval/posting | Enforced by distinct permissions and creator-approval refusal | Approval and permission tests | Assign roles for UAT | Medium |
| FW-04 | Receipt idempotency and duplicate journals | Unique idempotency scope, select-for-update, replay test | Posting test | None | Closed |
| FW-05 | Open-period enforcement | Existing posting engine reused; reversal also requires open current period | Accounting and receipt planning tests | Configure and open 2026 periods | Medium — configuration |
| FW-06 | Individual allocation reversal | Implemented with audit and balance recalculation | Allocation reversal test | None | Closed |
| FW-07 | Over/duplicate/concurrent allocation | Service and DB constraints; concurrency test | Concurrent allocation test | None | Closed |
| FW-08 | Invoice cancellation interaction | Blocked while active receipt allocation exists | Cancellation interaction test | Operations procedure | Closed |
| FW-09 | Posted receipt cancellation | Controlled reversal journal; blocked by reconciled bank line | Posting/cancellation test | Approve reversal policy | Medium — policy |
| FW-10 | Receipt/payment bank traceability | Company bank account and unreconciled `BankTransaction` expectation created | Banking integration tests | Provide statement data | Closed for linkage |
| FW-11 | Automatic reconciliation / transfers | Deliberately not implemented | Code review and bank match count assertions | Keep manual matching control | Closed by design |
| FW-12 | Supplier credit/debit note posting | No ledger posting; invoice balances adjust only | Note gap report and tests | TMD approve event matrix and rules | High — policy |
| FW-13 | Customer credit/debit note posting | No ledger posting; invoice balances adjust only | Note gap report and tests | TMD approve event matrix and rules | High — policy |
| FW-14 | Invoice/payment/receipt posting with approved notes | Refused to avoid gross ledger mismatch | Posting refusal tests | Implement note posting first | High |
| FW-15 | WHT posting | Blocked by policy | Existing WHT tests | Approve WHT accounts/rules | High — policy |
| FW-16 | Foreign-currency posting | Refused until FX policy exists | Posting guards | Approve FX policy | High — policy |
| FW-17 | Staging receipt posting evidence | Not run; staging deliberately test-only | Staging flags query | Activate in an approved UAT window | High — acceptance |
| FW-18 | Full bank-statement-to-receipt browser match | Not run; no matching statement data | Banking report limitation | Supply statement and run departmental UAT | Medium — acceptance |
| FW-19 | Screen-reader manual pass | Automated axe clean; manual NVDA/VoiceOver not performed | Accessibility report | TMD accessibility reviewer | Medium — acceptance |
| FW-20 | Production activation | Disabled | `test_mode=True`, `activated_at=None`, review missing | Formal activation checklist | Blocking |

## Overall assessment

The application-side financial controls are internally consistent and tested. Remaining gaps are policy approval, staging evidence and production activation, not missing receipt/allocation code. No unapproved accounting classification has been encoded.