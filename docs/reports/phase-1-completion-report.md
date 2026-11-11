## Phase: 1 — Engineering foundations and standards

**Date:** 11 November 2026
**Prepared by:** Build agent, for review by TMD management and the technical owner
**Status:** ready for review

### Requirements addressed

`NFR-01…NFR-12` (foundations) and Guide §9 Phase 1.

No business requirement IDs (`ADM`, `MAS`, `PRC`, `INV`, `AP`, `AR`, `GL`, `BNK`, `TAX`, `PCS`, `SVC`, `AST`, `REP`) are implemented, by design: each depends on decisions still open in `13-decision-register.md`.

### Implemented

- **Repository:** Git initialised on branch `main`; `.gitignore` covering secrets, keys, dumps, media, build output and local env files; `.editorconfig`; pre-commit configuration; PR-ready CI workflow.
- **Backend:** Django 5.2.19 + DRF 3.16.1 project. Settings split into `base` / `dev` / `prod`, all environment-driven. Production refuses to start without a real secret key and explicit allowed hosts.
- **Database and cache:** PostgreSQL 16 and Redis 7 in Docker Compose with health checks and named volumes. PostgreSQL is published on host port **5433**, because a native PostgreSQL service already occupies 5432 on the development machine.
- **Operational endpoints:** `/health/` (liveness, no database access) and `/health/ready/` (database check), plus the versioned equivalents under `/api/v1/`.
- **Observability:** request correlation middleware that accepts a safe inbound `X-Request-ID` or generates one, echoes it in the response, and attaches it to every JSON log line.
- **API contract:** single JSON error envelope (`error.code`, `error.message`, `error.details`, `error.request_id`), including non-DRF 404s when `DEBUG=False`.
- **Documentation:** OpenAPI 3 schema generated from the code at `/api/v1/schema/`, Swagger UI at `/api/v1/docs/`.
- **Frontend:** Angular 22 workspace, strict TypeScript, ESLint, Vitest test builder, dev-server proxy so the SPA calls the API same-origin, and a shell that reports the backend's real readiness.
- **Quality gates:** 11 backend tests, 3 frontend tests, Ruff lint and formatting, Django system checks, migration completeness check, and a repository secret scan.
- **Onboarding:** `docs/dev-setup.md`, written so a clean checkout can be set up from that file alone.

### Files/modules changed

- Root: `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `README.md`
- `backend/`: `manage.py`, `pyproject.toml`, `requirements/{base,dev,prod}.txt`, `.env.example`
- `backend/config/`: `env.py`, `settings/{base,dev,prod}.py`, `urls.py`, `wsgi.py`, `asgi.py`
- `backend/shared/`: `logging.py`, `middleware.py`, `exceptions.py`, `handlers.py`
- `backend/apps/core/`: `views.py`, `apps.py`, `tests/{test_health,test_error_envelope}.py`
- `frontend/`: generated Angular 22 workspace, `proxy.conf.json`, `eslint.config.js`, `src/app/{app.ts,app.html,app.scss,app.config.ts,app.spec.ts}`, `src/app/core/health.service.ts`, `src/index.html`, `src/styles.scss`
- `infra/docker-compose.yml`, `scripts/check_secrets.py`, `tests/README.md`
- Docs: `docs/dev-setup.md`, `docs/reports/phase-1-completion-report.md`, plus decision-register and tracker updates

### Database changes

**No domain migrations.** Only Django's built-in migrations were applied locally (`contenttypes`, `auth`, `admin`, `sessions`). No table exists for procurement, inventory, billing, ledger, tax or audit. `makemigrations --check` reports no pending model changes, which is the correct state for a phase with no business models.

### Tests run

| Command | Result |
| --- | --- |
| `pytest` (backend) | **11 passed**, exit 0 |
| `ruff check .` | All checks passed, exit 0 |
| `ruff format --check .` | 22 files already formatted, exit 0 |
| `python manage.py check` | No issues, exit 0 |
| `python manage.py makemigrations --check --dry-run` | No changes detected, exit 0 |
| `python manage.py migrate` | Applied built-in migrations, exit 0 |
| `npm run lint` | All files pass linting, exit 0 |
| `npm run build` | Production build succeeded, 227 kB initial (62 kB transfer) |
| `npm test -- --watch=false` | **3 passed** (1 file), exit 0 |
| `python scripts/check_secrets.py` | Passed: no tracked secrets or forbidden files, exit 0 |

### Acceptance evidence

- **Automated output:** the commands above, run against the live Docker PostgreSQL 16 instance. Test database creation, readiness checks and the JSON error envelope are exercised, not assumed.
- **Runtime verification:**
  - `GET /health/` → `200 {"status":"ok","service":"tmd-platform-api","version":"0.1.0"}` with an `X-Request-ID` response header.
  - `GET /health/ready/` → `200 {"status":"ok","checks":{"database":"ok"}}`.
  - `GET /api/v1/docs/` → 200; `GET /api/v1/schema/` → 200.
  - SPA on `http://127.0.0.1:4200` → 200, and `GET /api/v1/health/ready/` through the dev-server proxy returns the same database-ok JSON, proving the proxy path the portal will use.
- **Secret handling:** `git ls-files` contains no `.env`, key or dump file; scan clean with 81 tracked files.
- **Reconciliation evidence:** not applicable — no financial records exist in this phase.
- **UAT scenario:** not applicable — there is no user workflow to accept yet; the portal shell is a status page.

### Unresolved decisions

| ID | Decision | Owner | Impact if unanswered |
| --- | --- | --- | --- |
| D-13 | Acceptance of the out-of-scope list | Management | Scope-creep risk R-08; no technical impact |
| D-03, D-04, D-04a, D-04b | Roles, permission matrix, approval limits | Management + Finance | Phase 2 cannot start |
| D-17, D-18 | Record visibility, delegation and escalation | Management | Phase 2 cannot start |
| D-10 | Hosting model, site connectivity | Management / IT | Blocks Phase 12; local development unaffected |
| D-12 | Support owner and escalation contacts | Management | No operational owner at go-live |
| D-05 | Chart of accounts, financial year, periods | Accountant | Blocks Phase 6 entirely |

### Risks and limitations

| Risk | Severity | Mitigation / workaround |
| --- | --- | --- |
| The CI workflow has not executed on GitHub: there is no remote repository yet | Medium | Every job's commands were run locally with the same results; the first push must be watched, not assumed green |
| Angular Material is not installed yet | Low | Deliberate: component work belongs with the Phase 2 screens; adding it now would ship unused dependencies |
| `config.settings.staging` does not exist as a separate file | Low | Staging differences are environment variables; a dedicated file is added when a staging host is chosen (D-10) |
| Development database password is a known placeholder | Low | Compose binds to localhost only and holds synthetic data; production uses managed secrets |
| No browser end-to-end test yet | Low | Nothing to test end to end; the SPA has unit tests and the API has integration tests over HTTP |

### Recommendation

Ready for review. The foundation meets the exit gate in `14-backlog.md`: a clean checkout can be built and tested from `docs/dev-setup.md` alone, the checks pass locally, and no secret is committed. The one honest gap is that CI has been verified by running its commands locally, not by a GitHub run, because no remote exists.

### Next phase proposal

Phase 2 — identity, roles, permissions and audit — after the management review closes D-03, D-04, D-04a, D-04b, D-17 and D-18. Nothing in this phase needs rework to accommodate those answers: roles, permissions and approval policy are data, and the current API default is already fail-closed.

---

## Rules applied to this report

- No financial feature is reported as production-ready; none was built.
- "Implemented" means code, tests and documentation together — not a page that renders.
- No real company data, credentials or personal data appear here.
