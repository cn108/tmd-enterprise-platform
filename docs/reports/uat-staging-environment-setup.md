# TMD UAT staging environment setup

**Date:** 12 November 2026
**Environment:** local Windows workstation, Docker Desktop, isolated PostgreSQL database `tmd_staging`
**Purpose:** controlled employee acceptance testing of the existing TMD Enterprise System. No production service, payment, invoice, NRS submission or deployment was activated.

## 1. Isolation and preservation

- The development database `tmd` was left untouched.
- A new database, `tmd_staging`, was created in the existing `tmd-postgres` container, owned by the existing `tmd` role.
- PostgreSQL remains on `127.0.0.1:5433`; Redis `tmd-redis` remained healthy.
- All 63 migrations were applied to `tmd_staging`.
- Provisional governance was applied: 10 role groups, 19 account roles, 4 posting rules and 13 approval bands.
- The repository was inspected before changes. No real company secrets, production keys or confidential records were found in the staging path. `.env`, media and database dumps remain ignored.
- Existing work was preserved in local checkpoint commit `5815f87` before the UAT changes. Nothing was pushed or deployed.

## 2. Staging commands

```bash
cd backend
POSTGRES_DB=tmd_staging ./.venv/Scripts/python.exe manage.py migrate --noinput
POSTGRES_DB=tmd_staging ./.venv/Scripts/python.exe manage.py apply_provisional_governance
POSTGRES_DB=tmd_staging ./.venv/Scripts/python.exe manage.py seed_staging_uat
POSTGRES_DB=tmd_staging ./.venv/Scripts/python.exe manage.py verify_staging_uat
POSTGRES_DB=tmd_staging ./.venv/Scripts/python.exe manage.py verify_workflows
POSTGRES_DB=tmd_staging ./.venv/Scripts/python.exe manage.py check_role_access
POSTGRES_DB=tmd_staging ./.venv/Scripts/python.exe manage.py load_test_staging
```

The seed command refuses to run unless `connection.settings_dict["NAME"] == "tmd_staging"`. It supports `--reset`, but the database was rebuilt from scratch during this exercise to guarantee a clean synthetic state.

## 3. Running services used for acceptance

| Service | Address | Notes |
| --- | --- | --- |
| Django API | `http://127.0.0.1:8000` | `POSTGRES_DB=tmd_staging`, `runserver --noreload` |
| Angular dev server | `http://127.0.0.1:49630` | Angular selected a free port because the parent environment set `PORT`; the configured proxy forwards `/api` to port 8000 |
| PostgreSQL | `127.0.0.1:5433` | container `tmd-postgres`, healthy |
| Redis | local container | `tmd-redis`, healthy |

The portal was also opened directly in the local Chromium browser for manual inspection before the Playwright suite was written.

## 4. Staging identities

All identities use the synthetic domain `@staging.tmd.local` and the shared UAT password `Tmd-Staging-2026!`. They must never be enabled in production.

| Role | Email |
| --- | --- |
| System Administrator | admin@staging.tmd.local |
| Management | management@staging.tmd.local |
| Accountant | accountant@staging.tmd.local |
| Finance Controller | controller@staging.tmd.local |
| Finance Officer | finance@staging.tmd.local |
| Procurement Officer | procurement@staging.tmd.local |
| Project Manager | project@staging.tmd.local |
| Storekeeper | store@staging.tmd.local |
| Operations / HSE | operations@staging.tmd.local |
| Auditor | auditor@staging.tmd.local |

## 5. Configuration decisions

- October 2026 is closed; November 2026 is open for UAT journals.
- Tax configurations are synthetic, clearly labelled provisional UAT data. They are not an approved Nigerian tax policy.
- The inventory method is provisional weighted average; the governance note records that an accountant has not approved it.
- Tenant, customer, supplier, employee, project and bank records are fictional. Supplier bank details are encrypted by the application.
- No bank transfer was executed. The recorded payment is marked as a test payment and remains in `recorded` execution state.

## 6. Result

**Staging setup: PASS.** The environment is isolated, reproducible, seeded through real service-layer workflows, and guards against accidental execution outside `tmd_staging`.
