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

# The SPA runs on :4200 and proxies /api to :8000, so the browser's Origin
# differs from the API host. Django refuses that mismatch unless the origin is
# explicitly trusted. Production serves both from one origin, so this is a
# development-only concern.
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:4200,http://127.0.0.1:4200",
)

# The admin is a convenience locally and a break-glass surface in production (B-16).
ENABLE_DJANGO_ADMIN = True

LOGGING["root"]["level"] = "DEBUG" if env_bool("DJANGO_VERBOSE_LOGS", False) else "INFO"  # noqa: F405
