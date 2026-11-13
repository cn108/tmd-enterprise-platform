# Administrator sweep: every page and every feature — 13 November 2026

**Scope.** Signed in as the platform administrator (`admin@staging.tmd.local`) the sweep opened
**107 page states**: the dashboard, all nine business modules with every one of their tabs, the
reporting workspace, administration, and all 31 master-data registers.

**Method.** `frontend/e2e/admin-sweep.spec.ts` (run on demand) walks the routes, clicks each tab,
waits for the panel to settle, and records for every page:

- browser console errors and uncaught exceptions;
- API responses with status ≥ 400;
- visible messages from `[role="alert"]`, `.error` and `.notice`;
- the row count of the table, so an empty register is distinguishable from a broken one;
- matches of known build-tracking phrases (stage numbers, "test mode", "synthetic", "the backend",
  "endpoint", "API", "not yet", "remains blank", "no … is executed/posted").

Raw evidence: `docs/reports/evidence/admin-sweep.json`.

## Functional result

| Measure | Result |
| --- | --- |
| Page states visited | 107 |
| Pages with failed API calls | 1 — `401 /api/v1/auth/me/` on the sign-in screen, which is the expected pre-authentication session probe |
| Pages with console errors other than that probe | 0 |
| Pages showing an error or alert message | 0 |
| Pages whose heading failed to render | 0 |

No feature raised a server error, an unhandled exception or a broken panel during the sweep.

**Registers that are empty** (they render "No records yet." — no seed data, not a fault):
procurement supplier selection; inventory reorder alerts, transfers, returns, adjustments, damaged
stock, stock counts, reservations and reorder levels; accounting opening balances; invoice credit and
debit notes and NRS submissions; banking matching suggestions, unmatched transactions, petty cash,
cash vouchers, replenishments and account transfers; project contract revisions and project
documents; service assignments and HSE records; master-data supplier categories, tax registrations,
bank changes, compliance documents, document categories, documents, manufacturers, specifications,
batches, serials, certificates, project locations and contract revisions.

## Copy that was a note to the developer, not to the user

Removed or rewritten on the page itself:

| Where | Was | Now |
| --- | --- | --- |
| Banking header | "…for independent approval. **No bank transfer is executed and no reconciliation is posted to the ledger.**" | "…submit reconciliations for approval." |
| Master data header | "Live register · writes are validated by the server" and a "Staging" chip | "Live register" |
| Master data, procurement, inventory, accounting headers | references to the live API, the backend and lifecycle endpoints | plain descriptions of what each module holds |
| Projects header | "…without double counting procurement, receipts or stock transfers" | "…compare budget, commitments and actual cost" |
| Leasing header | "…Asset classification and accounting treatment remain blank until finance approves a policy." | removed |
| Project documents | "…authenticated document endpoints … link it to a project with the document-links API." | "Documents are private and only visible to signed-in users. Upload a file in Master data, then link it to this project." |
| Reports header | "Formal statements are calculated by the server from posted journal lines … commitments are never presented as expenses." | "Financial statements, ledger, receivables, payables and operational reports for the selected period." |
| Dashboard | "Test environment" badge and the notices "Invoice issuance is in test mode … until Finance Controller and management activation" and "N … record(s) are marked as test data." | removed |
| Accounting journal, bank account, contract revision, project notes | "the backend allows/validates/assigns/encrypts…" | statements of the rule itself |
| Reconciliation approval, voucher, leasing inspection, invoice approval | negative disclaimers ("does not post to the ledger") | removed; the confirmation asks the question only |

## Copy that remains, and why

Seven page states still match a tracking phrase, all of them **seeded staging values rather than page
copy**: accounting journals and fiscal years, service progress history and completion reports,
leasing utilisation and master-data addresses contain record names such as "UAT synthetic fiscal year
2026", "UAT synthetic VAT 7.5% (not approved policy)" and synthetic test descriptions; invoice
settings shows the real **Test mode** column, which is a stored setting, not a banner.

Renaming those records is a data change to the staging seed, deliberately left alone here.

## Re-running the sweep

```bash
cd frontend
ADMIN_SWEEP=1 UAT_BASE_URL=http://127.0.0.1:49630 npx playwright test e2e/admin-sweep.spec.ts
```

It takes about four minutes and rewrites `docs/reports/evidence/admin-sweep.json`. It is skipped
unless `ADMIN_SWEEP` is set so the normal suite stays fast.

## What the sweep does not cover

It reads every page and exercises navigation; it does not perform a write on every action (approve,
post, allocate, reconcile) across all nine modules. Those lifecycle paths are covered by the backend
suite (350 tests) and the existing Playwright UAT, adversarial and MFA suites. Outgoing email is
delivered to the console backend, so a successful "Email PDF" is logged rather than sent.
