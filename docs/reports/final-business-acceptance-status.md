# Final Business Acceptance Status — 12 November 2026

> **Superseded on 13 November 2026 by `final-business-acceptance-report.md`.** Customer receipt ledger posting, MFA and throttling were completed after this snapshot.

**Overall:** Ready for formal TMD UAT on staging with synthetic data. Not ready for production.

## Implemented and browser-tested

- Dashboard financial, approval, procurement, project, activity and role-aware module views.
- Shared responsive shell and navigation at 360–1920 px.
- Administration users, roles, permission assignment, activation/deactivation and password update.
- Privileged-permission acknowledgement, enforced by both UI and API.
- Customer receipt creation, partial/multiple invoice allocation, unapplied funds, cancellation and
  statement PDF.
- Invoice, supplier-payment and note workflows with posting controls remaining fail-closed.
- Keyboard focus visibility and one H1 per page.

## Implemented and test-verified

- Invoice and supplier-payment idempotency and single-journal concurrency.
- Partial payments, multiple allocations, advances, rejection and cancellation.
- Approved note guards and over-credit refusal.
- Foreign-currency, WHT and mapping refusal.
- Customer receipt over-allocation, cross-customer, draft-invoice and cancellation controls.
- Transaction rollback after posting failure.

## Incomplete

- Customer receipt ledger posting and reconciliation.
- Individual allocation reversal.
- Customer receipt approval workflow.
- Production chart/mappings, opening balances and company legal details.
- Production email identity, MFA, backups, monitoring and hosting.

## Policy-blocked

- Credit/debit note ledger posting.
- WHT payable/receivable and remittance.
- Foreign-currency posting and revaluation.
- Production invoice activation and NRS submission.
- Live payment execution (not planned through this system).

## Verification

| Check | Result |
| --- | --- |
| Backend tests | **331 passed** |
| Frontend tests | **54 passed** |
| Ruff | Passed |
| Django check | Passed |
| Migration drift | None |
| Frontend lint | Passed |
| Production build | Passed |
| Staging test mode | True |
| `can_issue` | False |
| Public tunnel | Not running |

## Evidence

- [Administration users](evidence/final/administration-users-1366.png)
- [Privileged role warning](evidence/final/administration-privileged-role-1366.png)
- [Customer receipts at 1366](evidence/final/customer-receipts-list-1366.png)
- [Customer receipts at 360](evidence/final/customer-receipts-360.png)
- [Dashboard at 1366](evidence/final/dashboard-1366-final.png)
- [Dashboard at 390](evidence/final/dashboard-390.png)

## Acceptance recommendation

Proceed to formal UAT for user administration and customer receipts. Record UAT sign-off separately
for finance, operations and management. Keep Stage 7B and all production posting disabled until the
blockers above are signed and the customer-receipt posting policy is approved.
