# Repository Assessment

**Deliverable:** Guide §9 Phase 0 step 1 and §15 item 1–2
**Inspected:** 11 November 2026
**Verdict:** Greenfield. Nothing to preserve, nothing to migrate.

---

## 1. What was found

| Check | Result |
| --- | --- |
| Files at project root | None |
| Directories | `.freebuff/` only (agent tooling metadata; not application code) |
| Git repository | **No** — `git rev-parse` reports "not a git repository" |
| Framework / language files | None (no `package.json`, `pyproject.toml`, `manage.py`, `angular.json`, lockfiles) |
| Dependencies | None declared |
| Tests | None |
| CI / CD | None |
| Environment or secret files | None present (nothing to risk leaking) |
| Documentation | None (this pack is the first) |
| Unfinished work | None |

There is no working code to overwrite, no legacy behaviour to preserve, and no conflicting branch history. Guide §9 Phase 0 step 1 ("Do not overwrite working code blindly") and working rule 6 ("preserve working behaviour") are satisfied trivially.

## 2. Local toolchain observed

Collected from the development machine that this repository is connected to, because it constrains what Phase 1 can run without extra installation:

| Tool | Observed | Implication |
| --- | --- | --- |
| Operating system | Windows (win32), shell is Git Bash | Commands must be POSIX-compatible; Docker Desktop is the practical route for PostgreSQL/Redis |
| Python | 3.13.16 | Satisfies Django 5.x. Requirements will pin exact versions in Phase 1 |
| Node.js | v24.19.0 | Satisfies current Angular tooling |
| Docker | 29.9.2 (build a82e528) | PostgreSQL and Redis can run locally via Docker Compose |
| PostgreSQL client (`psql`) | Not installed / not on PATH | Phase 1 must supply database access through the container, or document installing the client |
| Git | Available (command succeeds) but no repository initialised | `git init` is a Phase 1 task, not a discovery change |

No versions were installed or changed during Phase 0. Installing runtimes is Phase 1 work and is not authorised yet.

## 3. Security posture of the current state

The empty repository has no attack surface, and no secrets, dumps or customer data are present. Two forward-looking points are recorded here because they are cheap to enforce now and expensive to retrofit:

- **A-01 (ASSUMPTION)** The project will be version-controlled on a private remote. The brief forbids committing secrets, production exports, private keys, passwords or real bank data (Guide §7). Phase 1 must ship `.gitignore` coverage for `.env*`, `*.pem`, `*.key`, local database dumps, `media/` uploads and Python/Node build output before the first commit that contains settings.
- **A-02 (ASSUMPTION)** The development machine is a single developer laptop, not a shared staging environment. Guide §7 requires local, staging/UAT and production to be separate; that separation is a Phase 1 configuration deliverable, and staging/production hosts do not exist yet.

## 4. Recommended baseline

The brief's recommended architecture (Guide §7) is a good fit for an empty repository and is adopted as the **PROPOSED** baseline, pending D-09:

- **Modular monolith** — one deployable Django backend with explicit domain modules, service layers and domain events; no microservices.
- **Backend:** Python + Django + Django REST Framework.
- **Database:** PostgreSQL (relational integrity, real transactions, decimal types, row locking).
- **Frontend:** Angular + TypeScript + Angular Material.
- **Async work:** Redis + Celery for PDF generation, scheduled reminders, imports/exports and integration retries.
- **Documents:** private storage behind authenticated endpoints; no public static URLs for uploads.
- **Deployment:** Docker Compose locally; separate local/staging/production configuration; GitHub Actions CI.

Proposed repository structure (Guide §7 layout, adjusted for a single repository):

```
tmd-platform/
  backend/
    config/            settings, urls, environment, wsgi/asgi
    apps/              domain modules (see below)
    shared/            audit, permissions, documents, numbering, money, events
    manage.py
    pyproject.toml
  frontend/            Angular workspace
  infra/               docker-compose, deployment, backup, monitoring
  docs/                BRD, SRS, ERD, architecture, runbooks, manuals
  tests/               cross-cutting integration and end-to-end support
  .github/workflows/   CI pipelines
```

**Implementation note (11 November 2026):** the tree above names the repository as a wrapper for readability. In practice the repository root **is** the workspace root, so `backend/`, `frontend/`, `infra/`, `docs/`, `tests/` and `.github/` sit directly beneath it. Recorded as B-05 in `13-decision-register.md`.

Proposed domain modules: `organisation`, `identity`, `projects`, `partners` (customers/suppliers), `catalogue`, `procurement`, `inventory`, `billing` (AP/AR), `payments`, `ledger` (accounting), `banking`, `taxation`, `workorders`, `assets` (equipment leasing), `reporting`, `documents`, `audit`.

## 5. On not scaffolding the application yet

Guide §15.1 says: "If no repository exists, propose a clean repository structure but do not generate the complete application." Accordingly this phase creates documentation only. Creating Django apps, models, migrations and Angular components now would hard-code workflow and accounting assumptions ahead of the answers in `11-questions.md`, which is precisely the rework Phase 0 exists to prevent.

## 6. Recommendation

Accept this assessment and authorise Phase 1 (repository foundation and engineering standards, per `14-backlog.md`). Phase 1 is deliberately free of business logic, so it is safe to start while business questions are still being answered.

**Status:** Ready for review. No code changed.
