# 30-day post-launch monitoring plan

**Status:** prepared, not started. It begins only after authorised production go-live.

## 1. Daily checks (first 30 days)

| Area | Check | Threshold / action |
| --- | --- | --- |
| Availability | `/health/` and `/health/ready/` | Any failure: escalate immediately |
| Errors | 5xx rate and unhandled exceptions | Any financial-write 5xx: freeze the affected action and preserve logs |
| Authentication | Failed logins, lockouts, MFA failures | Spike above normal: review source and notify management |
| Financial | Unbalanced journals, duplicate postings, failed postings | Any occurrence: stop posting and investigate before retry |
| Receipts/payments | Unallocated cash, duplicate allocations, reconciliation exceptions | Investigate the same day |
| Inventory | Negative stock, unexpected valuation movement, failed transfers | Freeze the affected item/location and reconcile |
| Email | Delivery failures, bounces, missing PDFs | Retry only after checking the recipient and audit record |
| Backups | Completion, checksum, off-host copy | No verified backup: treat as a P1 incident |
| Integrations | NRS/bank adapters remain disabled unless separately authorised | Never enable as a monitoring shortcut |

## 2. Weekly review

- Reconcile bank ledger to statement; list unexplained differences.
- Review AR/AP ageing and large overdue items.
- Review purchase orders with no receipt, receipts with no invoice and invoices with no approval.
- Review stock count differences and damage/adjustment reasons.
- Review access changes, privileged grants and MFA resets.
- Review support tickets and user difficulties; classify as training, data or defect.

## 3. Metrics to record

| Metric | Target (provisional) | Owner |
| --- | --- | --- |
| Availability during business hours | 99.5% | Administrator |
| p95 API response, normal list/detail | Under 1 second | Administrator |
| Failed financial postings | 0 unexplained | Finance Controller |
| Duplicate journals | 0 | Finance Controller |
| Unreconciled bank items over 7 days | 0 | Finance Controller |
| Negative stock balances | 0 | Storekeeper |
| Backup success rate | 100% | Operations |
| Restore drill | Pass before go-live and quarterly | Operations |
| Open high-severity defects | 0 | Management |

## 4. First month-end close

The close is incomplete until:

1. All bank accounts reconcile to statements, with differences explained.
2. AP and AR control accounts agree to supplier/customer balances.
3. Inventory valuation agrees to stock records and the stock count policy.
4. VAT/WHT positions are reviewed by the tax adviser and supported by records.
5. The trial balance balances and the financial statements carry no unexplained completeness warning.
6. Journals are posted only in open periods; the period is closed by an authorised person.
7. Opening balances and the first month's activity are traceable to source documents.
8. The Managing Director signs the first-close acceptance record.

## 5. Exit criteria for the 30-day hypercare period

- No unresolved Critical or High production defect.
- No unexplained ledger, bank, stock or control-account difference.
- Backup and restore evidence is current.
- Users have completed training and support volume is stable.
- The first month-end close is signed.
- Management records operational acceptance or a dated remediation plan.

## 6. Escalation

Use the incident procedure in the administrator manual. Preserve logs, request IDs, audit events and source documents. Do not delete or rewrite records to make a metric look correct.
