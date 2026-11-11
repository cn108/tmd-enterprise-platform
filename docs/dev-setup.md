# Developer Setup

**Phase:** 1 (foundation)
**Verified on:** Windows 11, Git Bash, Python 3.13.16, Node 24.19.0, Docker 29.9.2
**Purpose:** get a clean checkout running without reading any other file.

---

## 1. Prerequisites

| Tool | Version used | Check |
| --- | --- | --- |
| Python | 3.13.x | `python --version` |
| Node.js | 24.x (Angular 22 requires ≥ 20.19) | `node --version` |
| npm | 11.x | `npm --version` |
| Docker Desktop | running | `docker info` |
| Git | any recent | `git --version` |

Docker Desktop must be **started** before step 3; the database and cache are containers, not local installs.

## 2. Repository layout

```
backend/     Django + DRF API (config/, apps/, shared/)
frontend/    Angular 22 workspace
infra/       docker-compose.yml (local PostgreSQL + Redis)
docs/        discovery pack, review packs, setup and phase reports
scripts/     repository checks (secret scan)
tests/       cross-cutting tests (empty until workflows exist)
.github/     CI pipeline
```

## 3. Start the database and cache

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps
```

Both services must report `healthy`. PostgreSQL is published on **host port 5433**, not 5432, because a native PostgreSQL service commonly occupies 5432 on developer machines. If 5433 is also taken, override it:

```bash
POSTGRES_PORT=5434 docker compose -f infra/docker-compose.yml up -d
```

and set the same `POSTGRES_PORT` in `backend/.env`.

## 4. Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/dev.txt

cp .env.example .env               # development values only; never committed
python manage.py migrate
python manage.py runserver 8000
```

Check it:

```bash
curl http://127.0.0.1:8000/health/
# {"status": "ok", "service": "tmd-platform-api", "version": "0.1.0"}

curl http://127.0.0.1:8000/health/ready/
# {"status": "ok", "checks": {"database": "ok"}}
```

API documentation (generated from the code, not hand-written):
<http://127.0.0.1:8000/api/v1/docs/>

## 5. Frontend

```bash
cd frontend
npm ci            # or npm install on first run
npm start
```

Open <http://localhost:4200>. The dev server proxies `/api` to `127.0.0.1:8000` (`proxy.conf.json`), so there is no CORS configuration and the browser sees a single origin. The status card shows the backend's readiness response; if the backend is stopped it says so plainly.

## 6. Checks

Run the same commands CI runs, before pushing:

```bash
# backend
cd backend
ruff check .
ruff format --check .
python manage.py check
python manage.py makemigrations --check --dry-run
pytest

# frontend
cd frontend
npm run lint
npm run build
npm test -- --watch=false

# repository
python scripts/check_secrets.py    # scans git-tracked files
```

Optional: `pip install pre-commit && pre-commit install` in `backend/` to run lint and formatting on each commit.

## 7. Environment variables

`backend/.env` (copy of `.env.example`) is for local development only and is git-ignored.

| Variable | Local default | Notes |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | `prod` is used by `wsgi.py`/`asgi.py` |
| `DJANGO_SECRET_KEY` | development placeholder | Production refuses to start with a placeholder |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Required in production |
| `POSTGRES_*` | `tmd` / `tmd_dev_password` / port `5433` | Matches `infra/docker-compose.yml` |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Reserved for Phase 12 background jobs |
| `LOG_LEVEL` | `INFO` | Logs are JSON with a `request_id` field |

Production additionally requires `DJANGO_CSRF_TRUSTED_ORIGINS` and sets secure-cookie/HSTS behaviour; see `backend/config/settings/prod.py`.

## 8. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `password authentication failed for user "tmd"` | A native PostgreSQL answered on 5432 | Use port 5433 as configured; confirm with `docker port tmd-postgres` |
| `port is already allocated` | Another container or service holds the port | Override `POSTGRES_PORT` / `REDIS_PORT` |
| Frontend shows "API not reachable" | Backend not running, or wrong port | Start `runserver 8000`; check the proxy target |
| `relation "..." does not exist` | Migrations not applied | `python manage.py migrate` |
| Tests cannot create the test database | Database user lacks `CREATEDB` | The compose user is the superuser; do not point local settings at a restricted user |

## 9. What is deliberately missing

No procurement, inventory, billing, ledger or tax modules exist yet, and no models beyond Django's own. That is intentional: those depend on decisions still open in `docs/13-decision-register.md`. Adding them before the finance and operational reviews conclude would build the wrong thing precisely.
