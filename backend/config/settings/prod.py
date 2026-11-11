"""Production settings.

Fail-closed: the process refuses to start if the secret key, hosts or secure
cookie configuration are missing. No development default is accepted.
"""

from __future__ import annotations

from config.env import env_bool, env_int, env_list, env_str

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = env_str("DJANGO_SECRET_KEY", required=True)
if not SECRET_KEY or SECRET_KEY.startswith("dev-only"):
    raise RuntimeError("DJANGO_SECRET_KEY must be set to a real secret in production.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must list the production hostnames.")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# --- Transport and cookie security -----------------------------------------
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # the SPA must read the CSRF token
SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Logging ----------------------------------------------------------------
LOGGING["root"]["level"] = env_str("LOG_LEVEL", "INFO")  # noqa: F405
