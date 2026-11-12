"""Local development settings.

Everything here is safe to commit because it is only ever used on a developer
machine with synthetic data. The development key is deliberately obvious so it
can never be mistaken for a production secret.
"""

from __future__ import annotations

from config.env import env_bool, env_list

from .base import *  # noqa: F401,F403

DEBUG = True

# Obvious, non-secret key. Production requires DJANGO_SECRET_KEY and refuses this value.
SECRET_KEY = "dev-only-insecure-key-not-for-production"  # noqa: S105

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

# The SPA proxies /api to :8000, so the browser's Origin differs from the API
# host. Django refuses that mismatch unless the origin is explicitly trusted.
# Production serves both from one origin, so this is a development-only
# concern. Vite may fall back to another port when :4200 is already in use, so
# the current workspace's loopback origins are trusted as well.
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:4200,http://127.0.0.1:4200",
)
for _dev_port in ("49630",):
    for _dev_host in ("localhost", "127.0.0.1"):
        _dev_origin = f"http://{_dev_host}:{_dev_port}"
        if _dev_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_dev_origin)

# Local-only encryption key derivation, so development and tests need no extra
# secret. Production requires explicit BANK_ACCOUNT_ENCRYPTION_KEYS.
if not BANK_ACCOUNT_ENCRYPTION_KEYS:  # noqa: F405
    import base64
    import hashlib

    BANK_ACCOUNT_ENCRYPTION_KEYS = [
        base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()).decode()
    ]

# The admin is a convenience locally and a break-glass surface in production (B-16).
ENABLE_DJANGO_ADMIN = True

LOGGING["root"]["level"] = "DEBUG" if env_bool("DJANGO_VERBOSE_LOGS", False) else "INFO"  # noqa: F405
