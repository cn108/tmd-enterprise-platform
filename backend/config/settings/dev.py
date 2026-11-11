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

# The admin is a convenience locally and a break-glass surface in production (B-16).
ENABLE_DJANGO_ADMIN = True

LOGGING["root"]["level"] = "DEBUG" if env_bool("DJANGO_VERBOSE_LOGS", False) else "INFO"  # noqa: F405
