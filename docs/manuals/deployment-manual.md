# Deployment manual

## 1. Status

Deployment assets exist for staging/production, but this assignment does not authorise a production go-live. TLS certificates, production secrets, monitored backup storage and management approval must be supplied first.

## 2. Prerequisites

- Docker Engine/Compose on the host
- A DNS name pointing to the host
- TLS certificate and private key
- Private PostgreSQL and Redis (provided by the compose topology)
- A secret store or protected environment file
- Outbound network only where required

## 3. Topology

`infra/prod/docker-compose.yml` defines:

- `db`: PostgreSQL 16, private network, persistent volume
- `redis`: Redis 7 with password and append-only persistence
- `backend`: Django + Gunicorn, non-root container, media volume
- `web`: nginx TLS termination, Angular static files, `/api/` proxy

Only ports 80/443 are published. The database and Redis are not exposed.

## 4. Configuration

Copy `infra/prod/.env.example` to a protected environment file outside version control. Required values include:

- `COMPOSE_PROJECT_NAME`
- `TMD_DOMAIN`, `TLS_CERT_DIR`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `DJANGO_SECRET_KEY` (long random value)
- `BANK_ACCOUNT_ENCRYPTION_KEYS` (Fernet key; retain old keys for decryption during rotation)
- `MFA_ENCRYPTION_KEY` (a separate Fernet key; production MFA is mandatory by default)
- `MFA_REQUIRED_FOR_ALL_USERS=true`, `MFA_ISSUER=Tico McDon Limited`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` (company-controlled mailbox, never a personal Gmail address)
- `API_USER_RATE`, `API_ANON_RATE`, `LOGIN_RATE`, `MFA_RATE` (production defaults are in the template)
- optional `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT`, `LOG_LEVEL`

Validate without revealing secrets:

```bash
docker compose --env-file /secure/path/tmd.env -f infra/prod/docker-compose.yml config >/dev/null
```

## 5. Build and start

```bash
docker compose --env-file /secure/path/tmd.env -f infra/prod/docker-compose.yml build
docker compose --env-file /secure/path/tmd.env -f infra/prod/docker-compose.yml up -d
```

The backend entrypoint waits for the database, runs migrations and collects static files, then starts Gunicorn. Check:

```bash
curl -fsS https://$TMD_DOMAIN/health/
curl -fsS https://$TMD_DOMAIN/health/ready/
docker compose ... logs --tail=100 backend
```

The backend refuses to start if the production secret key, allowed hosts, bank encryption key, MFA encryption key or company email credentials are missing. This is deliberate fail-closed behaviour, not a deployment defect.

## 6. First-run administration

Create the initial administrator interactively or from a protected environment variable:

```bash
docker compose ... exec backend python manage.py create_initial_admin
```

Do not put a password in a command line, ticket or chat.

At first sign-in the administrator must enrol a TOTP authenticator and store the recovery codes. Test the flow on staging before production. A lost authenticator is reset with `python manage.py reset_mfa <email>` by a second administrator after identity verification.

## 7. Security headers

nginx sets HSTS, CSP, `X-Content-Type-Options`, `X-Frame-Options`, Referrer-Policy and Permissions-Policy. TLS 1.2/1.3 only. Django enforces HTTPS redirects, secure cookies and trusted CSRF origins.

## 8. Migration and rollback

1. Take and verify a backup.
2. Review `python manage.py showmigrations` and the release migration list.
3. Run migrations during a maintenance window.
4. Check health, sign-in, a read-only report and an audited write.
5. If the release fails, stop the new containers and restore the previous application image. Database rollback requires the tested restore procedure; do not invent a reverse migration under pressure.

## 9. Monitoring gaps

The repository includes health endpoints and structured logs, but no production error tracker, metrics backend, alert routing or off-host backup monitoring is configured. Treat this as an open production blocker.

## 10. Prohibited

- Do not expose PostgreSQL or Redis publicly.
- Do not reuse development secrets.
- Do not deploy with `DEBUG=True`.
- Do not enable live financial processing as part of a deployment test.
