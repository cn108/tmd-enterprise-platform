# Phase 1 Readiness Pack

**Purpose:** state exactly what will be built the moment G0 clears, what TMD must provide, and what Phase 1 deliberately will not touch.
**Version:** 1.0 — 11 November 2026
**Guide references:** §9 Phase 1, §7, §14

---

## 1. Entry criteria (all required)

| # | Criterion | Status |
| --- | --- | --- |
| 1 | D-01 signed — scope and phased plan approved | ☐ |
| 2 | D-13 out-of-scope list accepted | ☐ |
| 3 | D-09 confirmed, or the brief's recommended stack accepted by default | ☐ |
| 4 | D-10 hosting answer sufficient to choose local Docker Compose now and cloud/local for staging | ☐ |
| 5 | D-12 support owner named | ☐ |
| 6 | A private Git remote exists (or management authorises creating one) | ☐ |
| 7 | Named administrator for the first account | ☐ |

Phase 1 needs **no accounting, tax or workflow decisions**. That is why it can start once management review closes, even while finance and operations sessions are still running.

## 2. Work items

| # | Item | Deliverable | Evidence |
| --- | --- | --- | --- |
| 1 | Initialise Git repository with `main`/`develop` rules, PR template, CODEOWNERS guidance | Repo skeleton | Commit history, PR template present |
| 2 | `.gitignore` covering `.env*`, keys, media, dumps, build output | Ignore rules | Secret scan clean |
| 3 | Directory layout: `backend/`, `frontend/`, `infra/`, `docs/`, `tests/` | Structure | Tree documented |
| 4 | Django project + settings split (base/dev/staging/prod) using environment variables | Backend skeleton | App starts locally with no secrets committed |
| 5 | Angular workspace with lint and strict TypeScript | Frontend skeleton | `ng build` succeeds |
| 6 | PostgreSQL + Redis via Docker Compose with health checks | Compose file | Containers healthy, DB connects |
| 7 | Code standards: formatter, linter, type checks, pre-commit hooks | Config files | Commands documented and passing |
| 8 | Test framework for backend and frontend with one meaningful test each | Test suites | `pytest` and frontend test run green |
| 9 | CI pipeline: lint, types, tests, migration check, secret scan | Workflow file | Green run link |
| 10 | Health/readiness endpoint and structured logging with request IDs | Backend utility | `/health` returns OK; log sample shows request ID |
| 11 | OpenAPI schema generation and a documented error envelope | API shell | Schema served, docs page loads |
| 12 | Developer onboarding document (setup from clean checkout) | `docs/dev-setup.md` | A second machine follows it successfully |
| 13 | `docs/` index updated to include this pack and the review programme | Docs | Links resolve |
| 14 | Phase report using `templates/phase-completion-report.md` | Report | Filed with CI and test evidence |

## 3. What TMD must supply for Phase 1

| Item | Why | Owner |
| --- | --- | --- |
| Decision on Git remote (private repository under TMD's GitHub account, or authorise creation) | Code must live somewhere durable and private | Management / IT |
| Names and emails of the initial administrator and up to two technical contacts | First accounts and access | Management |
| Confirmation of local development machine(s) that will run Docker | Setup instructions must match reality | IT |
| Staging host decision, or "decide at Phase 12" recorded | Avoids designing for a host that is never used | IT |

No credentials, bank data or real customer/supplier data are needed for Phase 1. Development uses synthetic data only.

## 4. What Phase 1 will not do

- No procurement, stock, invoice, payment, ledger or tax models.
- No approval engine, permission matrix or business rules beyond the authentication skeleton.
- No report definitions, no chart of accounts, no numbering scheme.
- No data migration or import of real records.
- No deployment to production.

This boundary is deliberate: everything above depends on decisions that the finance and operational reviews are still producing. Building it now would mean rebuilding it later (R-10).

## 5. Definition of done

1. A clean checkout on a machine that has never run the project can be set up by following `docs/dev-setup.md` alone.
2. CI is green on the default branch: lint, type checks, tests, migration check, secret scan.
3. No secret, key or real data exists in the repository (verified by scan, not assumption).
4. Health endpoint responds; logs carry correlation IDs.
5. API documentation is generated, not hand-written.
6. Phase report filed with command output, not a summary of intentions.

Relative size: **M**. No calendar estimate until hosting and the Git remote are settled.

## 6. Immediately after Phase 1

| Order | Phase | Gate that must be cleared |
| --- | --- | --- |
| 2 | Identity, roles, permissions, audit | G1 (management review) |
| 3 | Master data | G3 partial (organisation + cost codes) |
| 4 | Procurement and fulfilment | G1 + procurement session |
| 5 | Inventory | G2 (valuation) + warehouse session |
| 6 | Ledger and posting | **G2 complete** |

If G2 is not complete when Phases 2–5 finish, Phases 2–5 still deliver value (users, master data, procurement, stock) and the ledger waits rather than posting to unapproved accounts.

## 7. Authorisation

| Item | Name | Signature | Date |
| --- | --- | --- | --- |
| Phase 1 authorised to begin |  |  |  |
| Git remote approved |  |  |  |
| Administrator account nominated |  |  |  |
