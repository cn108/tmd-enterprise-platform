# Decision Register

**Version:** 0.1 — 11 November 2026
**Guide references:** §9 Phase 0 step 7, §15.9
**Labels:** **CONFIRMED** (decided and signed) · **PROPOSED** (recommended, awaiting approval) · **ASSUMPTION** (needed to progress, must be disproved or confirmed) · **UNRESOLVED** (blocks the phase named)

Only CONFIRMED items may be implemented as company policy. PROPOSED and ASSUMPTION items are design proposals that must be ratified or replaced.

---

## 1. Scope and governance decisions

| ID | Decision | Label | Owner | Blocks | Consequence if unanswered |
| --- | --- | --- | --- | --- | --- |
| D-01 | Approve Phase 0 scope and the phased plan in `14-backlog.md` | **CONFIRMED** | Management — approved in writing, 11 Nov 2026 | Phase 1 | No build can begin |
| D-02 | Entity/office/warehouse/site structure | UNRESOLVED | Management | Phase 3 | Data model and reporting groups cannot be finalised |
| D-03 | Role and permission matrix | UNRESOLVED | Management + dept heads | Phase 2 | Access control built on guesses; high rework risk |
| D-04 | Approval limits and maker-checker design | UNRESOLVED | Management + Finance | Phase 2/4 | Approval engine can only be a stub |
| D-04a | Dual approval everywhere, or single approval with dual only above a value threshold | UNRESOLVED | Management | Phase 2 | Maker-checker rules cannot be finalised (`05-…` §4) |
| D-04b | Basis for determining approvers (amount, department, project, procurement type, or combination) | UNRESOLVED | Management | Phase 2 | Approval policy data model stays generic |
| D-05 | Chart of accounts, financial year, periods, posting matrix | UNRESOLVED | Accountant | Phase 6 | **No posting possible** |
| D-06 | Inventory costing method and GRNI policy | UNRESOLVED | Accountant | Phase 5/6 | Stock valuation and project cost incorrect |
| D-07 | Tax registrations, rates, e-invoicing scope | UNRESOLVED | Accountant / tax adviser | Phase 7 | Invoices may be non-compliant |
| D-08 | Invoice numbering scheme | UNRESOLVED | Accountant | Phase 7 | Cannot issue documents |
| D-09 | Technology stack (Angular, Django/DRF, PostgreSQL, Redis/Celery, Docker, GitHub Actions) | **CONFIRMED** | Management / IT — confirmed with the Phase 1 authorisation, 11 Nov 2026 | Phase 1 | Repository built on a stack that may be replaced |
| D-10 | Hosting model (cloud vs local) and site connectivity | UNRESOLVED | Management / IT | Phase 1/12 | Deployment and DR design unknown |
| D-11 | Migration cut-off and opening balance approach | UNRESOLVED | Finance + Management | Phase 13 | Cutover cannot be scheduled |
| D-11a | Whether prior-period comparatives are loaded, and at what summarisation level | UNRESOLVED | Accountant | Phase 13 | Report comparatives may be unavailable |
| D-11b | Opening balance basis: full trial balance vs balances plus open-item schedules | UNRESOLVED | Accountant | Phase 13 | Opening load format undefined |
| D-11c | Named signatories for migration reconciliation | UNRESOLVED | Management | Phase 13 | Reconciled data has no accountable owner |
| D-12 | Named support owner and escalation contacts | UNRESOLVED | Management | Phase 12 | No operational owner at go-live |
| D-13 | Acceptance of out-of-scope list (`02-brd.md` §3.2) | PROPOSED | Management | Phase 1 | Scope creep risk R-08 |

## 2. Business process decisions

| ID | Decision | Label | Owner | Blocks |
| --- | --- | --- | --- | --- |
| D-14 | Direct-to-project workflow steps as documented | PROPOSED | Procurement + Projects | Phase 4 |
| D-15 | Warehouse purchase and issue workflow as documented | PROPOSED | Warehouse + Finance | Phase 4/5 |
| D-16 | Service/leasing workflow as documented | PROPOSED | Operations | Phase 10 |
| D-17 | Record-level visibility (department/project scoping) | UNRESOLVED | Management | Phase 2 |
| D-18 | Delegation rules and escalation times | UNRESOLVED | Management | Phase 2 |

## 3. Accounting decisions (each also listed as P-nn in `07-accounting-events.md`)

| ID | Decision | Label | Owner | Blocks |
| --- | --- | --- | --- | --- |
| D-19 | Revenue recognition policy (milestone/completion/invoice) | UNRESOLVED | Accountant | Phase 6/8 |
| D-20 | Project cost/WIP treatment, including summary vs detail posting | UNRESOLVED | Accountant | Phase 6 |
| D-21 | Landed-cost allocation method | UNRESOLVED | Accountant | Phase 5/7 |
| D-22 | FX policy (rates, revaluation) — disabled until approved | UNRESOLVED | Accountant | Phase 6 (enablement only) |
| D-23 | Rounding policy per document type | UNRESOLVED | Accountant | Phase 6/7 |
| D-24 | Fixed asset capitalisation/depreciation (equipment) | UNRESOLVED | Accountant | Phase 10 |
| D-25 | Write-off / bad debt authority | UNRESOLVED | Management + Accountant | Phase 8 |
| D-26 | Report definitions (ageing buckets, statements, P&L groupings) | UNRESOLVED | Accountant | Phase 6/11 |

## 4. Technical and design decisions

| ID | Decision | Label | Why it is here |
| --- | --- | --- | --- |
| D-27 | Use a document-numbering service with no manual entry | PROPOSED | Prevents duplicate/gap fraud; needs accountant numbering scheme (D-08) |
| D-28 | Money as decimal, amounts `NUMERIC(18,2)`, prices `NUMERIC(18,6)`, quantities `NUMERIC(18,4)` | PROPOSED | Precision must be agreed before migrations |
| D-29 | Single central posting service with rule-driven mappings | PROPOSED | Core control; matches Guide §6 |
| D-30 | Append-only stock movements; balances as projections | PROPOSED | Matches Guide §1 |
| D-31 | Modular monolith, not microservices | PROPOSED | Matches Guide §7 |
| D-32 | Feature-flag all integrations, including NRS | PROPOSED | Allows go-live of core when tax integration is pending |
| D-33 | No external portals in release 1 | CONFIRMED | Stated in Guide §1 |
| D-34 | Internal employees only; supply/customer access by explicit future approval | CONFIRMED | Stated in Guide §1 |
| D-35 | NGN is the reporting currency; FX features disabled until a policy exists | CONFIRMED | Stated in Guide §1 |

## 5. Assumptions on record

| ID | Assumption | Impact if wrong | Owner to confirm |
| --- | --- | --- | --- |
| A-01 | Single legal entity | Multi-entity schema and consolidation reporting | Management (D-02) |
| A-02 | One warehouse at launch | Minimal — model supports many | Management (Q-05) |
| A-03 | Approval is maker-checker, not one person | Configuration change only | Management (D-04) |
| A-04 | Payments are executed in the bank and recorded in the system | Payment phase redesign if initiation is required | Finance (Q-33) |
| A-05 | Projects are billed by milestone and/or completion | Revenue timing changes | Accountant (D-19) |
| A-06 | Stock items are mostly consumables/materials without serial tracking | Enable per category; schema ready | Procurement (Q-17) |
| A-07 | Users have desktop or laptop access; no offline requirement | Phase 8 UI and hosting impact | IT (Q-39) |
| A-08 | Reports can be generated on demand; no data warehouse needed | Phase 11 rework | Engineering |
| A-09 | Staging can run on the same host as production (separate databases) for the pilot | Additional infrastructure cost | IT (D-10) |

## 6. Decisions taken by the build team (recorded for transparency)

These require no business approval, but are logged so they are not mistaken for company policy:

| ID | Decision | Rationale |
| --- | --- | --- |
| B-01 | Phase 0 produces documentation only; no application scaffolding | Guide §15.1 forbids generating the application at this stage |
| B-02 | Repository layout proposed as `tmd-platform/` with `backend/`, `frontend/`, `infra/`, `docs/`, `tests/` | Guide §7 layout |
| B-03 | Requirement IDs (ADM/PRC/INV/AP/AR/GL/BNK/TAX/PCS/SVC/AST/REP/DOC/AUD/NFR) adopted | Gives the backlog and tests a stable spine |
| B-04 | No tax rate, threshold, approval limit or account code appears anywhere in this pack | Guide §1, §14.5 |

### 6.1 Build decisions recorded during Phase 1 (11 November 2026)

Engineering choices with no business-policy content. They are logged so they are not mistaken for company decisions, and because reversing one later has a cost.

| ID | Decision | Rationale |
| --- | --- | --- |
| B-05 | The repository root is the workspace root: `backend/`, `frontend/`, `infra/`, `docs/`, `tests/`, `.github/` sit directly beneath it, with no `tmd-platform/` wrapper | `docs/` already lived at the root; the extra nesting level added nothing |
| B-06 | Local PostgreSQL is published on host port **5433** instead of 5432 | A native PostgreSQL service already listens on 5432 on the development machine |
| B-07 | Angular 22 with its built-in Vitest unit-test builder, and ESLint added through `angular-eslint` | Vitest runs headless without a browser; the generator ships no linter |
| B-08 | The API fails closed: `DEFAULT_PERMISSION_CLASSES = IsAuthenticated`, with health endpoints explicitly anonymous | A new endpoint should be private by default, not public by default |
| B-09 | One JSON error envelope (`code`, `message`, `details`, `request_id`) for API errors and non-DRF 404s | Gives the SPA a single predictable contract to build against |
| B-10 | No accounting, money or business libraries are installed in Phase 1 | Nothing can be built against them until D-05 and the finance review conclude |

## 7. Review routing

Each decision is closed in a specific review session, using the worksheet named here. See `reviews/00-review-plan.md` for the programme and `reviews/04-review-tracker.md` for live status.

| Review session | Decisions closed | Worksheet |
| --- | --- | --- |
| Management review | D-01, D-02, D-03, D-04, D-04a, D-04b, D-10, D-12, D-13, D-17, D-18 | `reviews/01-management-review-pack.md` worksheets 1–7 |
| Finance review | D-05, D-06, D-07, D-08, D-11a/b/c, D-19…D-26 | `reviews/02-finance-accounting-review-pack.md` worksheets 1–11 |
| Procurement walkthrough | D-14 (and Q-12, Q-13, Q-15, Q-16, Q-17b, Q-20, Q-20b, Q-20c, Q-21) | `reviews/03-operational-review-pack.md` session 1 |
| Warehouse walkthrough | D-15 (and Q-17, Q-17c, Q-19, Q-19b, Q-19c) | session 2 |
| Projects / operations walkthrough | D-16 (and Q-14b, Q-23b, Q-27, Q-27b, Q-31) | session 3 |
| Finance operations walkthrough | Q-33, Q-33b (and Q-25) | session 4 |

A decision becomes CONFIRMED only when the worksheet is filled, the owner's name is recorded and the date is entered here. Verbal agreement is captured as PROPOSED until then.

## 8. Sign-off block

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Managing Director / Management |  |  |  |
| Accountant / Finance lead |  |  |  |
| Procurement lead |  |  |  |
| Warehouse supervisor |  |  |  |
| Project management representative |  |  |  |
| Tax adviser (for D-07 and tax items) |  |  |  |

Phase 1 may begin once D-01 is signed. Phases 2, 3 and 4 additionally require D-03, D-04, D-02 and D-14/D-15 respectively. Phase 6 cannot begin at all without D-05.
