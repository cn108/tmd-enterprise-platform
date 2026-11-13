# Final UAT Readiness Report

**Date:** 12 November 2026  
**Prepared for:** TMD Finance Controller and departmental UAT leads  
**Activation state:** TEST ONLY — production financial activation remains disabled

## Verdict

The application is **ready for supervised departmental UAT of receipt capture, approval workflow configuration, allocation/reversal, banking traceability and note document controls**. It is **not ready for live receipt or note posting** until TMD approves the accounting mappings, posting rules, approval limits and activation checklist.

## Verification completed

| Area | Result |
|---|---|
| Backend suite | 336 tests passed |
| Frontend unit suite | 54 tests passed |
| Frontend lint | Passed |
| Frontend production build | Passed |
| Django system check | Passed |
| Migration drift check | Passed (new migrations generated and applied locally) |
| Ruff | Passed |
| Accessibility axe scan | 0 WCAG A/AA violations on six tested surfaces |
| Keyboard focus | Visible 2px focus outline and keyboard reachability confirmed |
| Responsive | No page overflow at 360 px; sticky form actions visible |

## New workflow coverage

- Customer receipt approval lifecycle and configurable approval policy.
- Idempotent receipt posting with allocated AR and unapplied customer advances.
- Posted receipt cancellation with a reversal journal.
- Individual allocation reversal and reallocation.
- Duplicate, over-allocation and concurrent-allocation protection.
- Invoice cancellation blocked while receipt allocations are active.
- Customer receipt and supplier payment linked to company bank accounts as unreconciled expectations.
- Credit/debit note accounting event matrix documented; note posting remains blocked.

## Staging state

- `InvoiceSettings.test_mode=True`
- `InvoiceSettings.activated_at=None`
- `can_issue=False`
- Accounting posting review not recorded
- The existing staging receipt `RCT-2026-0001` is cancelled and its invoice balance is restored
- No temporary UAT account remains active; the Finance Controller staging account is retained for supervised testing

## Policy dependencies before live posting

1. Approve the chart mappings for AR, customer advances, bank, cash and all invoice/note roles.
2. Approve receipt and supplier-payment posting rules.
3. Record the Finance Controller's posting review and management activation.
4. Approve receipt approval bands and the independent approver role. No TMD limit has been invented.
5. Approve WHT and FX treatments.
6. Approve the credit/debit note event matrix and post-note adjustment policy.
7. Provide bank statement data for end-to-end manual reconciliation UAT.
8. Complete a manual screen-reader pass.

## UAT execution guidance

1. Run receipt record → submit → independent approval → post in an approved staging window with complete mappings and an open period.
2. Partially allocate, leave an unapplied balance, allocate later, reverse one allocation, then verify invoice and receipt balances.
3. Import a bank statement, manually match the receipt expectation and verify the receipt cannot be cancelled until the match is reversed.
4. Repeat the supplier invoice → approval → payment → bank expectation workflow.
5. Exercise note approval and confirm invoice posting remains blocked until note policy is approved.
6. Record results by department and escalate any policy decision rather than working around the gate.

## Browser evidence

- `docs/reports/evidence/final/receipts-approval-ui-1366.png`
- `docs/reports/evidence/final/receipt-create-form-1366.png`
- `docs/reports/evidence/final/receipt-form-validation-1366.png`
- `docs/reports/evidence/final/receipts-approval-ui-360.png`
- `docs/reports/evidence/final/administration-privileged-role-1366.png`

## Sign-off required

Finance Controller: accounting policy, mappings, posting review.  
Management: approval limits, activation authorization.  
Departmental UAT leads: workflow acceptance and manual accessibility confirmation.

Until those signatures are recorded, the correct state is **prepared for UAT, posting disabled**.