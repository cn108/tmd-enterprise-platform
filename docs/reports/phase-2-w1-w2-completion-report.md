## Phase: 2 — Identity and authentication (W1/W2)

**Date:** 11 November 2026
**Prepared by:** Build agent, for review by TMD management and the technical owner
**Status:** ready for review — **partial phase report.** W1 and W2 of W1–W9 are delivered; the Phase 2 exit gate in `../14-backlog.md` is **not** met.

### Requirements addressed

`ADM-01` (create, update, disable — partly: no offboarding workflow yet), `ADM-02` (password policy, lockout, rate limiting), `ADM-03` (time-limited single-use reset token), `ADM-04` (secure sessions, CSRF, cookie flags), and the parts of `NFR-05`, `S-01…S-06`, `S-10` and `S-11` that concern authentication.

**Not addressed, by design:** `ADM-05…ADM-11`, `AUD-01`, `AUD-02`. Roles, permission matrix, record visibility, approvals, delegation and the audit trail are W4–W7 and are blocked by G1. The signed-in payload therefore returns `roles: []` and `permissions: []` — an explicit empty list, not a fabricated default.

### Implemented

- **Custom user model:** `identity.User` with email as the login identifier, `full_name`, optional `employee_ref`, department foreign key (`PROTECT`), `is_active`, `is_staff` (Django admin break-glass only, not a business role), `must_change_password`, `mfa_required`. `AUTH_USER_MODEL` switched from the first Phase 2 migration (B-11).
- **Departments:** `organisation.Department` with upper-cased codes, protected against deletion while users or records reference it.
- **Session authentication (B-12):** `SessionAuthentication401` supplies a `WWW-Authenticate` header so an absent session returns **401**, not DRF's misleading 403. Six endpoints under `/api/v1/auth/`: `csrf/`, `login/`, `logout/`, `me/`, `password/change/`, `password/reset/`.
- **Login behaviour:** uniform `401 invalid_credentials` for unknown email, wrong password and disabled account, so the response never confirms which accounts exist. Lockout is `403 account_locked`, recovered from the `axes_locked_out` flag because Django's `authenticate()` swallows the backend's `PermissionDenied`.
- **Sessions:** sliding idle timeout (`SESSION_COOKIE_AGE`, 1 hour, saved on every request), `HttpOnly`, `SameSite=Lax`, plus an **absolute** lifetime enforced by middleware (12 hours) that returns `401 session_expired`. Both values are configuration, not constants (D-36).
- **CSRF:** `csrftoken` cookie issued to the SPA and echoed in `X-CSRFToken`; DRF's `SessionAuthentication` enforces it on authenticated mutations. Development trusted origins added for the split-origin dev proxy (see *Defect found and fixed*).
- **Password policy:** minimum length 12 (configurable), similarity, common-password and numeric validators, Argon2 first in `PASSWORD_HASHERS`.
- **Password reset (ADM-03):** 32-byte URL-safe token, only its SHA-256 hash stored, 60-minute TTL (configurable), single use, invalidated with any outstanding tokens when a password changes or resets. The reset endpoint is throttled (`20/hour`).
- **Bootstrap commands:** `create_initial_admin` refuses to run when any user exists, forces a password change at first login, and reads the password from `INITIAL_ADMIN_PASSWORD` or a prompt rather than an argument; `issue_password_reset` prints the raw token once and never stores it.
- **Lockout (B-18):** `django-axes` with per-account **and** per-IP counters, 5 failures, 1-hour cool-off, reset on success. The middleware that would reformat errors is deliberately omitted, so locked logins still return the project's JSON envelope (`axes.W002` silenced with a comment explaining why).
- **Django admin (B-16):** disabled unless `ENABLE_DJANGO_ADMIN=True`.
- **Portal:** sign-in screen with labelled, keyboard-usable fields and inline error handling; dashboard showing the authenticated user, department and live readiness; `SessionStore` (signals only, no `HttpClient`, to avoid an interceptor↔service↔`HttpClient` DI cycle); `authInterceptor` sending cookies and clearing a dead session **without redirecting**; `authGuard`/`guestGuard` owning routing with a `returnUrl`; an app initializer that fetches the CSRF cookie and resolves an existing session before the first guard runs.

### Files/modules changed

- `backend/config/settings/{base,dev}.py`, `backend/config/urls.py` (auth routes mounted under `/api/v1/auth/`)
- `backend/apps/organisation/`: `models.py`, `admin.py`, `apps.py`, `migrations/0001_initial.py`
- `backend/apps/identity/`: `models.py`, `authentication.py`, `middleware.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `migrations/0001_initial.py`
- `backend/apps/identity/management/commands/`: `create_initial_admin.py`, `issue_password_reset.py`
- `backend/apps/identity/tests/`: `conftest.py`, `test_user_model.py`, `test_auth_api.py`, `test_password_reset.py`, `test_commands.py`
- `frontend/src/app/`: `app.config.ts`, `app.routes.ts`, `app.html`, `app.scss`, `app.spec.ts`
- `frontend/src/app/core/`: `auth.models.ts`, `auth.service.ts`, `auth.interceptor.ts`, `auth.guard.ts`, `session.store.ts`, `testing/auth.fixtures.ts`, `auth.service.spec.ts`, `auth.guard.spec.ts`
- `frontend/src/app/features/`: `login/` (component, template, styles, spec), `dashboard/` (component, template, styles, spec)
- Docs: `docs/16-phase2-access-control-design.md` (§11 status), `docs/13-decision-register.md` (B-11…B-18, D-36), `docs/dev-setup.md` (CSRF troubleshooting), `backend/.env.example`

### Database changes

Two domain migrations, both new: `organisation.0001_initial` (departments) and `identity.0001_initial` (user, password reset tokens). No procurement, inventory, billing, ledger, tax or audit table exists. `makemigrations --check` reports no pending model changes.

**Required reset, stated plainly:** because Phase 1 had already migrated Django's built-in `auth` tables, switching `AUTH_USER_MODEL` required destroying and recreating the **development** database volume. It was done once, locally, with synthetic data only. It must never be run against an environment holding real records; there is none today.

### Tests run

| Command | Result |
| --- | --- |
| `pytest` (backend) | **42 passed**, exit 0 — 11 core (health, error envelope) + 31 identity (15 auth API, 7 reset, 5 user model, 4 commands) |
| `ruff check .` | All checks passed, exit 0 |
| `ruff format --check .` | 49 files already formatted, exit 0 |
| `python manage.py check` | No issues, exit 0 (1 silenced: `axes.W002`, justified in settings) |
| `python manage.py makemigrations --check --dry-run` | No changes detected, exit 0 |
| `npm test -- --watch=false` | **20 passed** (5 files), exit 0 |
| `npm run lint` | All files pass linting, exit 0 |
| `npm run build` | Production build succeeded, exit 0 |
| `python scripts/check_secrets.py` | Passed: no tracked secrets or forbidden files, exit 0 |
| Cross-reference audit (36 markdown files) | All links resolve; all cited `Q-`, `D-`, `P-`, `B-` IDs defined, exit 0 |

What the tests actually assert, rather than merely execute: email normalisation and uniqueness, no hard delete of a department in use, Argon2 hashing, uniform 401 for unknown email, `403 account_locked` after the threshold, CSRF refusal on an unauthenticated-token mutation, `204` on a valid logout, absolute-timeout expiry, reset token single use and expiry, reset invalidation on password change, and the bootstrap commands' refusal paths.

### Acceptance evidence

- **API, live:**
  - `GET /api/v1/auth/csrf/` → `200`, sets `csrftoken` (readable by the SPA).
  - `GET /api/v1/auth/me/` anonymous → `401 not_authenticated`.
  - `POST /api/v1/auth/login/` with an unknown email → `401 invalid_credentials`.
  - `POST /api/v1/auth/login/` with valid credentials → `200`, `Set-Cookie: sessionid=…; HttpOnly; SameSite=Lax` plus a rotated `csrftoken`.
  - `POST /api/v1/auth/logout/` without a CSRF header → `403`; with the token → `204`, and `me/` afterwards → `401`.
  - `/api/v1/schema/` lists all six auth routes.
- **Portal, in a real browser (manual session):**
  - Anonymous visit to `/` → redirected to `/login?returnUrl=%2F`.
  - Sign-in through the form → dashboard "Welcome, Demo User", department `FIN`, readiness `ok`. Network sequence `csrf 200 → me 401 → login 200 → readiness 200`.
  - `document.cookie` contains `csrftoken` and **not** `sessionid` — the session cookie is `HttpOnly`, as intended.
  - Full page reload → still signed in, resolved from the server rather than from memory.
  - Sign-out button → `204`, redirect to `/login`, `me/` → `401`, session genuinely destroyed.
- **Reconciliation evidence:** not applicable — no financial records exist.
- **UAT scenario:** not applicable — the only workflow is sign-in/sign-out, verified above; business UAT starts when business modules do.

### Defect found and fixed during verification

The first browser sign-out **appeared** to succeed — the UI returned to `/login` — while `me/` still answered `200`. The logout POST was returning `403`:

> `CSRF Failed: Origin checking failed - http://127.0.0.1:4200 does not match any trusted origins.`

Cause: the SPA runs on `:4200` and proxies `/api` to `:8000`, so the browser's `Origin` differs from the API host, and Django refuses that mismatch. The token was correct; an explicit-token probe failed identically, which ruled out the CSRF interceptor before any frontend code was touched.

Fix: `CSRF_TRUSTED_ORIGINS` for the two loopback origins in `dev.py`, the variable in `.env.example`, a troubleshooting row in `docs/dev-setup.md`, and two regression tests — a trusted origin succeeds with a valid token, an untrusted origin is refused even with one. Production serves SPA and API from one origin, so this was development-specific; any future split-origin deployment must set the same list.

### Unresolved decisions

| ID | Decision | Owner | Impact if unanswered |
| --- | --- | --- | --- |
| D-03, Q-08 | Roles, holders and permission matrix | Management + department heads | W4 cannot start; no user holds any business permission |
| D-04, D-04a, D-04b, Q-09 | Approval structure and limits | Management + Finance | W6 approval engine has no policy data; every submission would fail closed |
| D-17, Q-07 | Record-level visibility model | Management | W5 defaults to the most restrictive scope |
| D-18, Q-10 | Delegation rules and escalation times | Management | W6 delegation stays disabled |
| D-36, Q-36 | Session idle timeout, lockout threshold, MFA enforcement | Management / IT | Current values are marked PROPOSED in settings; MFA cannot be enforced |
| D-13 | Acceptance of the out-of-scope list | Management | Scope-creep risk R-08; no technical impact |

### Risks and limitations

| Risk | Severity | Mitigation / workaround |
| --- | --- | --- |
| The portal clears local session state even when the sign-out request fails, so a user can believe they signed out while the server session lives | Medium | Session still ends at the 1-hour idle or 12-hour absolute limit; the browser error should be surfaced rather than swallowed in W8 |
| No automated browser end-to-end test: this report's browser evidence is a manual session | Medium | API behaviour is covered by 42 tests; the joined-up flow should be automated before W8 grows the UI |
| The CI workflow still has not executed on GitHub — no remote repository | Medium | Every job's commands pass locally; the first push must be watched, not assumed green |
| `must_change_password` is advisory: it is returned to the SPA but no route forces the change yet | Low | Flag is set by both bootstrap commands; enforcement belongs to the access-administration UI (W8) |
| `mfa_required` exists as data with no enforcement | Medium | W3 deliverable, blocked by D-36/Q-36; login is unchanged while the flag is off |
| Cookie `Secure` and HTTPS-only behaviour were not exercised locally (development is HTTP) | Low | Production settings own those flags; the local run proves only the `HttpOnly`/`SameSite` attributes |
| Roles and permissions are empty arrays in the signed-in payload | Low (by design) | No endpoint exists beyond authentication, so there is nothing to authorise yet; fail-closed API default remains |
| A demo account (`demo@tmd.local`) exists in the local development database for verification | Low | Not a seed, not committed, not documented as a credential; deleted when the volume is recreated |

### Recommendation

W1 and W2 are ready for review. The evidence shows that authentication is enforced by the backend, not by the interface: anonymous requests are refused, a dead session is refused with a distinct code, CSRF is required on mutations, and sign-out destroys the server session. The Phase 2 exit gate is **not** met and this report does not claim otherwise — roles, permissions, approvals and audit are the substance of the phase and none of them exists yet.

### Next phase proposal

W4 → W5 → W6 → W7 → W3 → W8 → W9, in the order set out in `../16-phase2-access-control-design.md` §11, once G1 signs D-03, D-04/D-04a/D-04b, D-17 and D-18. Nothing delivered here needs rework to accept those answers: roles and permissions are data, policies are versioned, and the API default is already fail-closed. W3 additionally needs D-36/Q-36.

---

## Rules applied to this report

- No financial feature is reported as production-ready; none was built.
- "Implemented" means code, tests and documentation together — not a page that renders.
- No real company data, credentials or personal data appear here; the demo account is named but its password is not recorded.
