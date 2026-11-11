# External Integration Register

**Version:** 0.1 — 11 November 2026
**Guide references:** §15.8, §9 (tax/fiscalisation phase), §12
**Rule:** No integration is enabled until its official requirements, credentials and approval path are confirmed. Any integration that is not approved is feature-flagged off and must leave the core workflow fully usable.

---

## 1. Register

| ID | Integration | Purpose | Needs credentials | Needs official onboarding / agreement | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| INT-01 | **NRS e-invoicing / fiscalisation** | Submit invoices, track acceptance/rejection, reconcile submissions | Yes (API credentials/certificate as officially issued to TMD) | **Yes** — TMD must be onboarded; API documentation and test environment from the official channel | Tax adviser + Finance | UNRESOLVED (Q-26) — build an adapter skeleton only behind a flag |
| INT-02 | **Bank statement import** | Import CSV/XLSX statements for reconciliation | No API credential; statement export access per bank | Possibly bank portal access for exports | Finance | Not started (Q-33b) — format unknown |
| INT-03 | **Email (transactional)** | Notifications: approval requests, overdue approvals, invoice delivery, statements | Yes (provider API key) | Provider account | IT | Deferred until provider chosen |
| INT-04 | **SMS (optional)** | Alerts for approvers in the field | Yes | Provider account + sender ID registration (may be regulated) | IT | Not in release 1 unless approved |
| INT-05 | **PDF generation** | PO, GRN, invoice, statement, report packs | No external credential (library) | No | Engineering | Phase 7 |
| INT-06 | **Spreadsheet import/export** | Validated migration and bulk templates | No | No | Engineering | Phase 3+ |
| INT-07 | **Private document storage** | Attachments, generated PDFs | Depends on host (object storage keys if cloud) | No | IT | Phase 1 decision with hosting (Q-34) |
| INT-08 | **Backup target** | Encrypted off-host backups | Yes (storage credentials) | No | IT | Phase 12 |
| INT-09 | **Error monitoring / uptime** | Alerts and incident visibility | Yes (service key) | No | IT | Phase 12 |
| INT-10 | **Payment execution / bank API** | Automatic payment initiation | **Out of scope** — storing online banking credentials is forbidden | n/a | n/a | Not permitted (Q-33) |
| INT-11 | **Fiscal device / POS** | Not applicable to release 1 | n/a | n/a | n/a | Out of scope |
| INT-12 | **Accounting export to external bookkeeping tool** | Only if TMD keeps a separate ledger package | Possibly | Possibly | Accountant | Not planned — confirm whether TMD expects one (Q-26b) |

## 2. Integration design rules

1. **Adapters, not inline calls.** Each integration is an adapter module with a typed interface so the domain never depends on a provider's payload shape.
2. **Outbox pattern.** Business transactions never wait on an external call. A successful local transaction writes an outbound record; a task delivers it with retry and backoff.
3. **Idempotency.** Every outbound call carries a stable idempotency key derived from the source document, and every inbound callback is validated and deduplicated.
4. **Status is visible.** Submitted/failed/retried states are shown on the source document and in an exception queue — never hidden in logs.
5. **Credentials stay server-side.** No key appears in the frontend bundle, repository, logs or the browser's storage.
6. **Feature flags.** Disabling an integration must not break invoice creation, posting or reporting; the affected action becomes "pending manual submission" with an audit note.
7. **Evidence retained.** Official API documentation version, test evidence and submission receipts are stored with the effective date (Guide Appendix B).

## 3. NRS / fiscalisation specifics (all unresolved)

| Item | Status |
| --- | --- |
| Whether TMD is currently in scope for e-invoicing | UNRESOLVED |
| TMD onboarding/registration status and identifiers | UNRESOLVED |
| API availability, environment, authentication method | UNRESOLVED |
| Required invoice data fields and formats | UNRESOLVED |
| Submission timing rule (invoice-time vs batched) | UNRESOLVED |
| Failure handling obligations (retry, escalate, credit note linkage) | UNRESOLVED |
| Test evidence required to go live | UNRESOLVED |

Because none of the above is settled, the build plan keeps fiscalisation as **Phase 7b**, separate from invoice issuance, behind a flag. The accountant can issue invoices internally and submit manually until the integration is approved — the system records that manual step with a reference and date so nothing is silently skipped.

## 4. What TMD must supply

1. Written confirmation of taxpayer category and e-invoicing scope.
2. Official onboarding/API documentation and any test credentials, or a statement that none exist yet.
3. Bank statement export samples and a naming convention.
4. Hosting decision (cloud or local), which drives storage and backup integrations (Q-34).
5. Named integration owner for each enabled adapter, responsible for credential rotation.

## 5. Consequences if not resolved

- INT-01 unresolved → invoices may be non-compliant at go-live; the release checklist item "NRS/tax integration status validated" cannot be ticked.
- INT-02 unresolved → reconciliation remains manual or impossible in-system, weakening cash control.
- INT-07/INT-08 unresolved → no verified recovery plan; a release blocker under Guide §16.
