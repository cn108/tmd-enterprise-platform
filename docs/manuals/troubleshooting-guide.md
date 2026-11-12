# Troubleshooting guide

## 1. Sign-in and session

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Invalid email or password | Wrong credentials | Re-enter carefully; do not keep retrying |
| Account locked | Repeated failures | Wait for lockout or contact administrator |
| 403 after sign-in | Role lacks permission | Request access review; do not use another account |
| CSRF failure | Origin not trusted or stale cookie | Clear session, confirm the exact SPA origin, sign in again |
| Session expires quickly | Inactivity timeout | Sign in again; save work more often |

## 2. Empty or missing data

- Check the active/inactive filter.
- Confirm the reporting period.
- Check whether the record is in draft and excluded from an approved-only report.
- Confirm your role can see the module.
- If the API returns 403, this is permission, not missing data.
- If a report says **Unavailable**, read the reason; do not expect a guessed figure.

## 3. Validation and conflicts

- **400:** a field or filter is invalid; read the message.
- **403:** permission denied.
- **404:** record or endpoint does not exist.
- **409:** status transition, duplicate, immutability or reconciliation conflict. Reload and inspect the current status.
- **429:** rate limit; wait and retry once.
- **500:** server defect; record time, user, screen and request ID, then escalate.

## 4. Financial report warnings

| Warning | Meaning | Resolution |
| --- | --- | --- |
| No chart of accounts | No posted statements possible | Accountant supplies approved chart |
| Posting not reviewed | Finance Controller review absent | Complete Stage 7B review |
| No bank GL link | Cash flow unavailable | Approve and link bank account to GL |
| Unclassified cash flow | Counterpart account has no approved role | Approve the mapping; do not guess |
| Gross profit unavailable | No `COST_OF_SALES` mapping | Approve cost-of-sales mapping |
| Multiple currencies | Totals cannot be added without conversion | Review per-currency totals |

## 5. Inventory

- Negative balance: investigate receipts/issues; never overwrite the balance.
- Valuation unavailable: configure the approved valuation method.
- Receipt rejected: check order status, outstanding quantity and schedule.
- Duplicate statement/receipt: the server refuses the second import; locate the original.

## 6. Performance

- Use a narrower date range.
- Use server search and filters instead of browsing all pages.
- Export large reports as CSV.
- If every screen is slow, check database capacity, backend CPU/memory and network; escalate with timestamps.

## 7. Backup and restore

- Backup failed: check `POSTGRES_PASSWORD`, container name, disk space and database connectivity.
- Restore refused: target must not equal the source and should end `_restore_test`.
- Restore succeeded but app fails: check migrations, media path, environment and logs.
- Never restore over production to test a backup.

## 8. Escalation information

Collect: time (with timezone), user email, screen/URL, record number, exact error text, request ID if shown, and whether the action changed any data. Do not include passwords, tokens, full bank account numbers or customer personal data in a ticket.
