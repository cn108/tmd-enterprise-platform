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

# --- Bank account encryption (B-26) ----------------------------------------
from cryptography.fernet import Fernet  # noqa: E402

BANK_ACCOUNT_ENCRYPTION_KEYS = env_list("BANK_ACCOUNT_ENCRYPTION_KEYS")
if not BANK_ACCOUNT_ENCRYPTION_KEYS:
    raise RuntimeError(
        "BANK_ACCOUNT_ENCRYPTION_KEYS must contain at least one Fernet key in production."
    )
for _key in BANK_ACCOUNT_ENCRYPTION_KEYS:
    try:
        Fernet(_key)
    except ValueError as exc:
        raise RuntimeError("BANK_ACCOUNT_ENCRYPTION_KEYS contains an invalid Fernet key.") from exc

# --- Multi-factor authentication -------------------------------------------
MFA_REQUIRED_FOR_ALL_USERS = env_bool("MFA_REQUIRED_FOR_ALL_USERS", True)
MFA_ENCRYPTION_KEY = env_str("MFA_ENCRYPTION_KEY", required=MFA_REQUIRED_FOR_ALL_USERS)
if MFA_ENCRYPTION_KEY:
    try:
        Fernet(MFA_ENCRYPTION_KEY.encode("utf-8"))
    except ValueError as exc:
        raise RuntimeError("MFA_ENCRYPTION_KEY must be a valid Fernet key.") from exc

# Production email must use a company-controlled identity. A personal mailbox
# default is never accepted silently.
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", required=True)
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", required=True)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", required=True)
if "gmail.com" in (EMAIL_HOST_USER or "").lower():
    raise RuntimeError(
        "Production EMAIL_HOST_USER must be a company-controlled mailbox, "
        "not a personal Gmail address."
    )

# Tighter production defaults; operators may override them from the secret store.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update(  # noqa: F405
    {
        "user": env_str("API_USER_RATE", "5000/hour"),
        "anon": env_str("API_ANON_RATE", "120/hour"),
        "login": env_str("LOGIN_RATE", "10/min"),
        "mfa": env_str("MFA_RATE", "10/min"),
    }
)

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
