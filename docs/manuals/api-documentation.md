# API documentation

## 1. Base URL and generated schema

- Base: `/api/v1/`
- Interactive docs: `/api/v1/docs/`
- OpenAPI schema: `/api/v1/schema/`

The generated schema is authoritative for request/response fields. `manage.py check --deploy` currently reports drf-spectacular warnings for some function-based/plain `APIView` endpoints; those views are documented by the report and manual but may be omitted from the generated schema. This is an API-documentation limitation, not an access-control waiver.

## 2. Authentication

Session cookie authentication:

1. `GET /api/v1/auth/csrf/` obtains the CSRF cookie.
2. `POST /api/v1/auth/login/` with email and password.
3. If login returns `mfa_required` or `mfa_enrollment_required` (HTTP 401), complete the MFA step before a session exists.
4. Send `X-CSRFToken` on POST/PUT/PATCH/DELETE.
5. `GET /api/v1/auth/me/` returns the current user, roles and permissions.
6. `POST /api/v1/auth/logout/`.

Authentication endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `auth/csrf/` | Set CSRF cookie |
| POST | `auth/login/` | Sign in |
| POST | `auth/mfa/setup/` | Create/refresh a TOTP device for an enrolment challenge |
| POST | `auth/mfa/confirm/` | Confirm enrolment with a TOTP code; starts the session |
| POST | `auth/mfa/verify/` | Complete a login challenge with a TOTP or recovery code; starts the session |
| POST | `auth/logout/` | Sign out |
| GET | `auth/me/` | Current user and permissions |
| POST | `auth/password/change/` | Change password |
| POST | `auth/password/reset/` | Request/complete password reset |

Anonymous access is refused except health, CSRF, login and password-reset request endpoints.

## 3. Permissions

- Every endpoint requires authentication by default.
- Model permissions and action-specific permissions are enforced server-side.
- Reporting requires `reporting.view_reporting`; formal reports additionally require `reporting.view_financialreporting`; exports require `reporting.export_reporting`.
- Approval endpoints check the relevant approve permission and block self-approval where configured.
- A hidden UI control does not grant or remove API permission.

## 4. Response conventions

Successful list responses are paginated:

```json
{
  "count": 25,
  "next": "...",
  "previous": null,
  "results": []
}
```

Search with `?search=` (or `?q=` on master-data endpoints), order with `?ordering=field`, filter by documented fields.

Errors use an envelope:

```json
{
  "error": {
    "code": "invalid_filter",
    "message": "Dates must use YYYY-MM-DD.",
    "details": {}
  }
}
```

Common statuses: 400 invalid input, 401 not signed in, 403 permission denied, 404 not found, 409 conflict/immutable record, 429 throttled, 500 unexpected server error.

MFA challenge tokens are single-use, expire after `MFA_CHALLENGE_TTL_SECONDS` (default 300), and are signed so they cannot be altered by the client. The MFA setup response is the only time the TOTP secret is returned; recovery codes are single-use and shown once.

## 5. Endpoint groups

| Prefix | Module |
| --- | --- |
| `/api/v1/health/`, `/health/` | Liveness/readiness |
| `/api/v1/auth/`, `/api/v1/access/` | Identity, users, roles, permissions |
| `/api/v1/governance/` | Policy decisions, approvals, configuration review |
| `/api/v1/` organisation endpoints | Departments, cost centres, destinations |
| `/api/v1/` parties endpoints | Suppliers, customers, contacts, addresses, tax registrations, bank details, bank-change requests, compliance |
| `/api/v1/` catalogue endpoints | Items, categories, units, manufacturers, prices, batches, serials, certificates |
| `/api/v1/` warehousing endpoints | Warehouses, storage locations |
| `/api/v1/` project endpoints | Projects, contracts, budgets, milestones, costs, profitability |
| `/api/v1/` procurement endpoints | Requests, RFQs, quotations, POs, schedules, goods receipts |
| `/api/v1/` inventory endpoints | Balances, movements, receipts, transfers, issues, returns, adjustments, damage, counts, reservations |
| `/api/v1/` accounting endpoints | Accounts, roles/mappings, fiscal years, periods, journals, rules, opening balances |
| `/api/v1/` invoicing endpoints | Supplier/customer invoices, notes, matching, payments, settings |
| `/api/v1/` banking endpoints | Bank accounts, statements, lines, matches, reconciliations, transfers, cash |
| `/api/v1/` services endpoints | Work orders, progress, reports, contracts |
| `/api/v1/` leasing endpoints | Equipment, rates, reservations, agreements, movements, maintenance |
| `/api/v1/reporting/<name>/` | Read-only reports |
| `/api/v1/documents/` | Private document upload/download |

## 6. Reporting API

Available names:

`overview`, `financial-statements`, `cash-flow`, `trial-balance`, `general-ledger`, `journal-register`, `receivables-ageing`, `payables-ageing`, `procurement`, `inventory`, `projects`, `operations`, `banking`, `tax`, `periods`.

Parameters:

- `start=YYYY-MM-DD`, `end=YYYY-MM-DD` (maximum five-year range);
- `account=<id>` for `general-ledger`;
- `output=csv|pdf` on the `/export/` path.

The response includes `source`, status labels and completeness warnings. Never treat an incomplete report as final.

## 7. Idempotency and concurrency

Payment recording uses an idempotency record. Concurrent state changes use row locks and return 409 when the current status no longer permits the action. Clients should reload after a 409 instead of blindly retrying a financial mutation.

## 8. Files

Uploads are multipart form data. Allowed extensions and maximum size are configured by the server. The API stores a checksum and returns metadata, not a public URL. Download through `GET /api/v1/documents/{id}/download/`; the download is audited.

## 9. Versioning

The current API is `/api/v1`. Breaking changes require a new version. The NRS adapter boundary is present but no network submission is implemented.

## 10. Rate limits

`DEFAULT_THROTTLE_CLASSES` applies authenticated and anonymous rate limits to every API view. Authentication, MFA and password-reset endpoints use scoped rates. A caller receiving HTTP 429 must wait for the retry window; do not loop or create a second account. Production defaults are documented in `infra/prod/.env.example`.
