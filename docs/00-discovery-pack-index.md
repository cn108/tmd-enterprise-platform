# Phase 0 — Discovery Pack: Index and Approval Request

**Project:** TMD Enterprise System — project-centred procurement, inventory and financial management platform
**Business:** Tico McDon Limited (TMD), Nigeria
**Controlling brief:** `TMD_Enterprise_System_AI_Agent_Development_Guide.pdf` v1.0 (11 Nov 2026)
**Phase status:** Phase 0 deliverables produced; **no production feature implementation has begun**
**Prepared:** 11 November 2026

---

## 1. Why this pack exists

The brief forbids starting construction before the company's real processes, roles, approval limits, accounting policy and tax position are known. Rework caused by building the wrong workflow is the single most expensive failure mode for a system like this, so Phase 0 produces evidence and decisions first, and code second.

This pack is the output of Guide §9 (Phase 0) and §15 (First assignment).

## 2. Deliverables and where they live

| # | Deliverable (Guide §15) | Document | Status |
| --- | --- | --- | --- |
| 1 | Repository inspection and assessment | `01-repository-assessment.md` | Complete — repository is empty, no code, no git history |
| 2 | Business Requirements Document | `02-brd.md` | Draft for review |
| 3 | Software Requirements Specification | `03-srs.md` | Draft for review |
| 4 | Current / future process workflows, three procurement routes with exception paths | `04-workflows.md` | Draft for review — subject to each department's confirmation |
| 5 | Role / permission and approval matrix | `05-roles-permissions-approvals.md` | Draft — **all monetary thresholds UNRESOLVED** |
| 6 | Preliminary ERD and data dictionary | `06-data-model.md` | Draft for review |
| 7 | Accounting event matrix and policy approvals list | `07-accounting-events.md` | Draft — **no debit/credit accounts selected; requires accountant** |
| 8 | Architecture proposal and repository structure | `08-architecture.md` | Proposal — stack choices need confirmation |
| 9 | Security and compliance register | `09-security-compliance.md` | Draft for review |
| 10 | Risk register | `10-risks.md` | Draft for review |
| 11 | Question and evidence register by department | `11-questions.md` | **Action required by TMD staff** |
| 12 | External integration register | `12-integrations.md` | Draft for review |
| 13 | Decision register (CONFIRMED / PROPOSED / ASSUMPTION / UNRESOLVED) | `13-decision-register.md` | Draft for review |
| 14 | Phased delivery backlog | `14-backlog.md` | Draft for review |
| 15 | Data migration and go-live plan | `15-migration-and-golive.md` | Draft for review (no cut-off date chosen) |

## 3. What is genuinely confirmed today

Only items established by the brief itself, plus what is observable in the repository:

- **CONFIRMED** — the business operates project-centred procurement, inventory and financial management across engineering, procurement, project management, equipment leasing, maintenance, HSE, construction and related service delivery (Guide §1).
- **CONFIRMED** — both accounts payable (supplier invoices) and accounts receivable (customer invoices) are in scope (Guide §1).
- **CONFIRMED** — purchases may be direct-to-project **or** received into a TMD warehouse, and the accounting destination is not identical in both cases (Guide §2).
- **CONFIRMED** — goods, services, labour, logistics, equipment hire and project-related expenses are all in scope; service lines must not be forced into inventory quantities (Guide §2, §4).
- **CONFIRMED** — NGN is the initial operating and reporting currency; foreign currency is considered only where real contracts require it (Guide §1).
- **CONFIRMED** — initial release is for **internal TMD employees only**; no external supplier or customer portal unless separately approved (Guide §1).
- **CONFIRMED** — repository is empty: no existing code, dependencies, tests or git history to preserve (see `01-repository-assessment.md`).

Everything else in this pack is **PROPOSED** or **UNRESOLVED** and must not be treated as company policy.

## 4. Evidence, gaps and consequences

| Area | Evidence available | Gap | Consequence if unresolved |
| --- | --- | --- | --- |
| Business scope | Brief §1–§4 | No interviews, no sample documents | Workflows may not match reality; procurement UI may be unusable |
| Organisational structure | None | Entities, offices, warehouses, project sites unknown | Cannot model departments, cost centres, warehouse hierarchy |
| Approval limits | None | No amounts, no delegation rules | Approval engine cannot be configured; **go-live blocker** |
| Chart of accounts and posting rules | None | No approved CoA or mapping | **Cannot enable posting; go-live blocker** |
| Tax and fiscalisation | Brief Appendix A/B only | Taxpayer category, NRS onboarding status unknown | Invoices may be non-compliant; **go-live blocker** |
| Inventory costing | None | No method chosen (e.g. FIFO/weighted average) | Stock valuation and COGS will be wrong |
| Migration data | None | No registers, balances, cut-off date | Cutover cannot be planned |
| Infrastructure | Local dev machine only | Hosting, internet, device constraints at sites unknown | Deployment design may be undeliverable |

Owners and due dates for each gap are in `11-questions.md` and `13-decision-register.md`.

## 5. Risk highlights (full detail in `10-risks.md`)

Highest-consequence risks identified at discovery, in the order the brief asks them to be prioritised:

1. **R-01** Posting to an unapproved chart of accounts produces incorrect financial statements.
2. **R-02** Duplicate supplier invoice or duplicate payment execution causes cash loss.
3. **R-03** Double-counting warehouse purchases (expensed at invoice **and** at stock issue) distorts project cost and margin.
4. **R-04** Stock lost or mis-stated because movements are overwritten rather than posted.
5. **R-05** Unauthorised approval or self-approval bypasses maker-checker.
6. **R-06** Supplier bank detail or employee data leakage.
7. **R-07** NRS/tax configuration wrong or shipped without adviser validation, making invoices non-compliant.
8. **R-08** Scope expansion into supplier/customer portals without approval, delaying the core build.

## 6. Decisions required from management before Phase 1

The full register is `13-decision-register.md`. These are the ones that block or reshape the build:

| ID | Decision | Owner | Status |
| --- | --- | --- | --- |
| D-01 | Approve Phase 0 scope and the phased plan in `14-backlog.md` | Management | UNRESOLVED |
| D-02 | Confirm legal entity count, offices, warehouses, project sites | Management | UNRESOLVED |
| D-03 | Approve roles and permission matrix (`05-…`) | Management + department heads | UNRESOLVED |
| D-04 | Supply approval limits by amount/department/project (or approve "single approver, configurable later") | Management + Finance | UNRESOLVED |
| D-05 | Approve chart of accounts, financial year, periods, posting matrix (`07-…`) | Accountant | UNRESOLVED |
| D-06 | Approve inventory costing method and GRNI policy | Accountant | UNRESOLVED |
| D-07 | Confirm tax registration, rates and NRS e-invoicing onboarding status | Accountant / tax adviser | UNRESOLVED |
| D-08 | Confirm invoice numbering scheme per document type | Accountant | UNRESOLVED |
| D-09 | Confirm technology stack in `08-architecture.md` (Angular + Django + PostgreSQL + Redis/Celery) | Management / IT | PROPOSED |
| D-10 | Confirm hosting model and site connectivity constraints | Management / IT | UNRESOLVED |
| D-11 | Confirm migration cut-off date and opening balance approach | Finance + Management | UNRESOLVED |
| D-12 | Confirm third-party service choices and who supplies credentials | Management / IT | UNRESOLVED |

## 7. Review programme (how these documents get turned into decisions)

The pack is reviewed in three sessions, in this order, then Phase 1 begins:

| Step | Session | Pack | Gate it clears |
| --- | --- | --- | --- |
| 1 | Management review — authority, limits, departments, responsibilities | `reviews/01-management-review-pack.md` | **G0** scope + **G1** authority |
| 2 | Finance review — chart of accounts, tax, valuation, policies | `reviews/02-finance-accounting-review-pack.md` | **G2** accounting |
| 3 | Operational review — procurement, warehouse, projects, invoicing | `reviews/03-operational-review-pack.md` | **G3** operations |
| 4 | Phase 1 — technical foundation only | `reviews/05-phase1-readiness.md` | — |

The order, participants and rules are in `reviews/00-review-plan.md`; live status is tracked in `reviews/04-review-tracker.md`. Only G0 is needed to start Phase 1, so it can begin while sessions 2 and 3 run.

## 8. Recommendation

**Not ready to begin feature development.** The pack is complete enough to run a management review, but the accounting, tax, approval-limit and organisational gaps are exactly the ones that cause expensive rework. My recommendation:

1. Hold the management review with department heads and the accountant present.
2. Answer the go-live-blocker questions in `11-questions.md` first — the rest can be resolved during Phase 1–3 without stopping work.
3. On written approval of D-01 (and interim answers to D-02 to D-05), proceed to Phase 1: repository foundation, CI, PostgreSQL schema baseline, and authentication.

Phase 1 delivers infrastructure and identity only. It does not touch procurement, inventory or accounting logic, so provisional answers to those questions do not block it.
