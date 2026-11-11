# TMD Enterprise System

Internal, project-centred procurement, inventory and financial management platform for **Tico McDon Limited (TMD)**, Nigeria. Reporting currency: **NGN**.

This repository contains the **Phase 0 discovery pack** and the **Phase 1 engineering foundation**. Phase 1 was authorised on 11 November 2026 (D-01) and delivers a runnable, tested skeleton only: no procurement, inventory, billing, ledger or tax logic exists yet.

## Current status

| Item | State |
| --- | --- |
| Phase | Phase 2 in progress — W1/W2 (identity and authentication) delivered; W3–W9 await G1 |
| Code | Django 5.2 + DRF, Angular 22, Docker Compose, CI; custom user model, departments, session auth with lockout and reset tokens |
| Tests | 40 backend tests, 3 frontend tests, lint and formatting clean, secret scan clean |
| Gate | G0 partially signed: D-01 approved; D-13 still needs a management signature. Roles, approvals and audit need D-03, D-04, D-17, D-18 |
| Next phase | W4 — roles and permissions (blocked by D-03/Q-08 and D-04) |

## Quickstart

Full instructions: [`docs/dev-setup.md`](docs/dev-setup.md).

```bash
docker compose -f infra/docker-compose.yml up -d

cd backend
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements/dev.txt && cp .env.example .env
python manage.py migrate && python manage.py runserver 8000

cd ../frontend
npm ci && npm start
```

The API answers on `http://127.0.0.1:8000` and the portal on `http://localhost:4200`, which proxies `/api` to the backend.

## Review programme (the approved next steps)

The sequence agreed with management is run through three review packs, in order, before Phase 1 begins:

1. [`docs/reviews/00-review-plan.md`](docs/reviews/00-review-plan.md) — order, participants, gates G0–G3, and how outcomes are recorded.
2. [`docs/reviews/01-management-review-pack.md`](docs/reviews/01-management-review-pack.md) — authority, spending limits, departments, responsibilities.
3. [`docs/reviews/02-finance-accounting-review-pack.md`](docs/reviews/02-finance-accounting-review-pack.md) — chart of accounts, tax intake, inventory valuation, accounting policies.
4. [`docs/reviews/03-operational-review-pack.md`](docs/reviews/03-operational-review-pack.md) — procurement, warehouse, project delivery and invoicing walkthroughs with scenario cards.
5. [`docs/reviews/04-review-tracker.md`](docs/reviews/04-review-tracker.md) — live status of gates, sessions and decisions.
6. [`docs/reviews/05-phase1-readiness.md`](docs/reviews/05-phase1-readiness.md) — exactly what starts once scope is approved, and what Phase 1 will not touch.

## Read the discovery pack in this order

1. [`docs/00-discovery-pack-index.md`](docs/00-discovery-pack-index.md) — index, evidence, gaps and the approval request.
2. [`docs/01-repository-assessment.md`](docs/01-repository-assessment.md) — what exists today and the recommended baseline.
3. [`docs/02-brd.md`](docs/02-brd.md) — business requirements.
4. [`docs/03-srs.md`](docs/03-srs.md) — functional and non-functional requirements with IDs.
5. [`docs/04-workflows.md`](docs/04-workflows.md) — the three procurement routes, order-to-cash, stock and cash workflows, exception paths.
6. [`docs/05-roles-permissions-approvals.md`](docs/05-roles-permissions-approvals.md) — roles, permission matrix and approval matrix (thresholds unresolved).
7. [`docs/06-data-model.md`](docs/06-data-model.md) — preliminary ERD and data dictionary.
8. [`docs/07-accounting-events.md`](docs/07-accounting-events.md) — posting requirements; **no accounts chosen**.
9. [`docs/08-architecture.md`](docs/08-architecture.md) — proposed technical architecture and repository structure.
10. [`docs/09-security-compliance.md`](docs/09-security-compliance.md) — controls and compliance register.
11. [`docs/10-risks.md`](docs/10-risks.md) — risk register.
12. [`docs/11-questions.md`](docs/11-questions.md) — questions by owner, prioritised.
13. [`docs/12-integrations.md`](docs/12-integrations.md) — external integrations and what they need.
14. [`docs/13-decision-register.md`](docs/13-decision-register.md) — every item labelled CONFIRMED / PROPOSED / ASSUMPTION / UNRESOLVED.
15. [`docs/14-backlog.md`](docs/14-backlog.md) — phased delivery backlog with exit gates.
16. [`docs/15-migration-and-golive.md`](docs/15-migration-and-golive.md) — migration and cutover plan.
17. [`docs/16-phase2-access-control-design.md`](docs/16-phase2-access-control-design.md) — Phase 2 design: identity, permissions, approval engine, audit trail and its test plan.

## Rules this project runs under

- Correctness before appearance. A polished dashboard never compensates for wrong procurement, inventory or accounting logic.
- No invented policy: no fabricated approval limits, tax rules, chart-of-accounts mappings, prices, legal details, bank details or opening balances. Every unknown is labelled **UNRESOLVED** with an owner.
- Permissions are enforced on the backend API, not by hiding buttons.
- Posted financial records are never edited or deleted; they are reversed or corrected through controlled workflows.
- Inventory balances are derived from traceable stock movements, never overwritten.
- Money is stored in fixed-precision decimals; every journal balances.
- Work happens in approved phases; no phase closes while critical acceptance criteria are unmet.

## Governance

The management team and TMD's qualified accountant/tax adviser approve business, accounting and tax decisions. This repository documents proposals and assumptions; it does not decide company policy. See `docs/13-decision-register.md` for what needs a signature and from whom.
