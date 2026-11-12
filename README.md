# TMD Enterprise System

Internal, project-centred procurement, inventory and financial management platform for **Tico McDon Limited (TMD)**, Nigeria. Reporting currency: **NGN**.

This repository contains the **Phase 0 discovery pack**, the **Phase 1 engineering foundation**, Phase 2 identity and access administration, the **Phase 3–6 functional scope**, and **Stage 7A** of accounts payable and invoice issuance. The Angular Material portal is interactive across those modules, including reports, access administration and the invoicing workspace. Stage 7A documents are test-only; live invoice issuance, NRS submission and ledger posting are disabled until Stage 7B activation.

**13 November 2026 UI update:** the portal now uses the fixed navy sidebar layout with a 260 px desktop rail, icon-only tablet rail and mobile drawer, plus updated design tokens and table behaviour. All 32 master-data registers have a dedicated high-density workspace behind the `MASTER_DATA_V2` flag, previewable with `?layout=v2`; it defaults off until UAT. All financial workflows remain in test mode. See the [`master-data V2 report`](docs/reports/master-data-v2-implementation-2026-11-13.md), [`sidebar UI report`](docs/reports/uiux-sidebar-redesign-2026-11-13.md), [`final UAT readiness report`](docs/reports/final-uat-readiness-report.md), [`financial workflow gap register`](docs/reports/financial-workflow-gap-register-2026-11-12.md), [`receipt posting report`](docs/reports/customer-receipt-posting-completion-report.md), [`accessibility report`](docs/reports/accessibility-acceptance-report.md) and [`note accounting gap report`](docs/reports/credit-debit-note-accounting-gap-report.md).

## Current status

| Item | State |
| --- | --- |
| Phase | Phases 3–6 functional scope plus **Stage 7A** implemented and interactive. No module is COMPLETE: the role matrix is provisional, the chart and opening balances are absent, and production posting is disabled. Current position and the module matrix: [`docs/frontend-backend-gap-analysis.md`](docs/frontend-backend-gap-analysis.md) |
| Code | Django 5.2 + DRF, Angular 22 + Angular Material, Docker Compose, CI; custom user model, session auth, roles/permission bundles and user administration, suppliers/customers and relationships, catalogue and traceability, warehouses and locations, projects/contracts/budgets/milestones, documents, purchase requests → RFQ → quotation → selection → PO → delivery schedule → GRN, an immutable stock ledger, a double-entry accounting engine, and Stage 7A supplier/customer invoices, duplicate and matching controls, VAT/WHT configuration, notes, PDF test previews, payment recording/allocation and NRS adapter state |
| Tests | 340 backend tests, 67 frontend tests, lint and formatting clean, production build clean with no component-style budget warning, secret scan clean, plus live portal-to-PostgreSQL verification scripts for master data and Stage 7A invoicing |
| Gate | G0 partially signed: D-01 approved; D-13 still needs a management signature. **Provisional policy applied 12 Nov 2026:** nine operational roles plus an unassigned Finance Controller, ₦5m approval bands, role-based chart, monthly periods, weighted-average/specific-identification valuation, GRNI and the five accounting events. Stage 7A invoices are test-only. Report: [`docs/reports/phase-7a-completion-report.md`](docs/reports/phase-7a-completion-report.md) |
| Next phase | Stage 7B activation review: confirm roles, chart/mappings, opening balances, tax, numbering and legal details; record the Finance Controller posting review; then obtain management authorisation. Use the prioritized [`activation checklist`](docs/reports/phase-7b-activation-checklist.md), the [`blocker register`](docs/reports/phase-7b-activation-blockers.md) and the [`review gap register`](docs/reports/development-gap-register-2026-11-12.md) |

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
