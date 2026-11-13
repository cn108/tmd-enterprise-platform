# Production blockers register — updated after UAT

**Status date:** 13 November 2026
**Rule:** none of these blockers may be waived by a UAT pass. Production finance, payments, invoicing and NRS remain unauthorized.

| ID | Severity | Blocker | Owner | Required evidence to close | Status |
| --- | --- | --- | --- | --- | --- |
| PB-01 | **Critical** | MFA was not implemented or enforced for privileged roles | Security / Identity lead | TOTP enrolment, login challenge, recovery codes, role/global enforcement, replay and recovery tests | **Closed technically** — TOTP, recovery codes, reset command and production enforcement implemented; 5 backend and 2 frontend tests pass |
| PB-02 | **Critical** | Production chart of accounts and account-role mappings are unapproved | Finance Controller / Accountant | Signed chart, every posting rule mapped to approved accounts, reconciliation test | Open |
| PB-03 | **Critical** | Opening balances are not approved or imported | Finance Controller | Signed opening trial balance, controlled import, reconciliation to source, audit trail | Open |
| PB-04 | **Critical** | Tax policy (VAT, WHT, tax IDs, NRS) is unverified | Accountant / Tax adviser | Written tax opinion, approved rates and treatments, NRS test credentials and sandbox evidence | Open |
| PB-05 | **High** | Production TLS certificate and termination are not evidenced | Infrastructure owner | Certificate chain, renewal owner, HTTPS redirect, HSTS verification from an external client | Open |
| PB-06 | **High** | No off-host encrypted backup destination, retention or key custody | Infrastructure / Finance | Scheduled encrypted backup to independent storage, retention policy, key custody, restore drill with RPO/RTO | Open |
| PB-07 | **High** | Monitoring and alerting are not implemented | Operations | Health, 5xx, auth, database, backup, outbox and certificate alerts with an on-call owner | Open |
| PB-08 | **High** | Production-scale performance and capacity are unproven | Engineering | Load test on target workers/database, p95 targets, connection-pool and slow-query evidence | Open |
| PB-09 | **High** | Disaster recovery and database failover are untested | Infrastructure | Documented DR plan, failover test, measured recovery, data-integrity check | Open |
| PB-10 | **High** | No production migration trial and reconciliation to source documents | Finance / Data owner | Staged import, exception log, reconciled control accounts and sign-off | Open |
| PB-11 | **High** | Role matrix remains provisional (D-03) and approval policy (D-04) is unsigned | Management | Signed role matrix, segregation-of-duties review, approval thresholds and delegates | Open |
| PB-12 | **Medium** | 25 APIViews lack OpenAPI response schemas; 6 enum-name collisions | Engineering | Annotated views, generated schema reviewed, no unexplained schema errors | Open |
| PB-13 | **Medium** | Python dependency CVE scan is not part of the pipeline | Engineering | `pip-audit` (or equivalent) in CI, accepted-risk register, upgrade regression pass | Open |
| PB-14 | **Medium** | Several dependencies are behind current releases | Engineering | Tested upgrade plan, especially Django, DRF, cryptography and drf-spectacular | Open |
| PB-15 | **Medium** | File upload/PDF coverage is incomplete in browser automation | QA | Browser tests for permitted and rejected uploads, PDF download/preview per module | Open |
| PB-16 | **Medium** | Sustained write concurrency and database interruption are unproven | Engineering / QA | Disposable production-like environment, write load, lock/deadlock and recovery results | Open |
| PB-17 | **Medium** | No formal UAT sign-off or defect triage board | Management | Signed UAT acceptance, severity triage, named owners and target dates | Open |
| PB-18 | **Low** | Project issues do not create a `ProjectCost` row; reporting aggregates them | Product / Finance | Confirm the intended cost model and document it for users | Open |
| PB-19 | **Low** | Some UI controls outside procurement rely on API rejection | Frontend | Permission-aware create/edit controls across every module | Open |
| PB-20 | **Critical** | Live bank execution, production invoices and NRS submission are disabled and unauthorized | Management | Explicit written go-live authorization after PB-01…PB-17 close | Open by design |

## Go-live gate

Production may be considered only when:
1. PB-01 through PB-04 are closed and independently evidenced.
2. PB-05 through PB-11 are closed with infrastructure and finance sign-off.
3. UAT is signed by business owners and all Critical/High UAT defects are closed.
4. A production migration and opening-balance reconciliation is approved.
5. Management gives explicit written authorization; until then no live payment, invoice or NRS transaction may be enabled.
