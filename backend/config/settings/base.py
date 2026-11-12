"""Settings shared by every environment.

Environment specific files (``dev``, ``prod``) import from here and override.
Nothing in this file contains a credential, a business policy or a tax rate.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from config.env import env_bool, env_int, env_list, env_str

# backend/ — the manage.py directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Local developer convenience: backend/.env is git-ignored. Staging and production
# receive real environment variables from the platform and have no .env file.
load_dotenv(BASE_DIR / ".env")

APP_VERSION = env_str("APP_VERSION", "0.1.0")
SECRET_KEY = env_str("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# --- Applications -----------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "axes",
]

# Domain modules are added here only when their phase is authorised.
LOCAL_APPS = [
    "apps.core",
    "apps.organisation",
    "apps.identity",
    "apps.parties",
    "apps.catalogue",
    "apps.warehousing",
    "apps.projects",
    "apps.procurement",
    "apps.accounting",
    "apps.inventory",
    "apps.invoicing",
    "apps.documents",
    "apps.banking",
    "apps.services",
    "apps.leasing",
    "apps.reporting",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --- Middleware -------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "shared.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.identity.middleware.AbsoluteSessionTimeoutMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# django-axes' middleware is deliberately not used: the backend still refuses
# locked accounts, and the login view returns our JSON envelope instead of a
# plain-text 403. The warning asks for the middleware that does that formatting.
SILENCED_SYSTEM_CHECKS = ["axes.W002"]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------
# PostgreSQL only: the ledger depends on real transactions, NUMERIC types and
# row locking, so SQLite is not an option even for development.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB", "tmd"),
        "USER": env_str("POSTGRES_USER", "tmd"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", "tmd_dev_password"),
        "HOST": env_str("POSTGRES_HOST", "127.0.0.1"),
        "PORT": env_str("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
        "OPTIONS": {"connect_timeout": 5},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env_str("REDIS_URL", "redis://127.0.0.1:6379/0")

# --- Outbound email ---------------------------------------------------------
# Invoice delivery uses the company's Gmail mailbox. The app password is read
# from the environment and is never stored in this repository. Set
# EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend only for local
# dry runs where no message should leave the machine.
EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", "tmdtico@gmail.com")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "Tico McDon Limited <tmdtico@gmail.com>")
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT_SECONDS", 15)

# A document still marked as test can only be emailed here. Production
# activation removes the restriction on non-test approved invoices.
INVOICE_EMAIL_TEST_RECIPIENT = env_str("INVOICE_EMAIL_TEST_RECIPIENT", "tmdtico@gmail.com")

# --- Authentication ---------------------------------------------------------
AUTH_USER_MODEL = "identity.User"

AUTHENTICATION_BACKENDS = [
    # django-axes refuses locked accounts; ModelBackend performs the real check.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# PROPOSED defaults (D-36). Configuration values, never constants in views.
PASSWORD_MIN_LENGTH = env_int("PASSWORD_MIN_LENGTH", 12)
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE_SECONDS", 3600)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_ABSOLUTE_TIMEOUT_SECONDS = env_int("SESSION_ABSOLUTE_TIMEOUT_SECONDS", 43200)

# Lockout: per-account and per-IP counters, so neither scope can be dodged alone.
AXES_ENABLED = env_bool("AXES_ENABLED", True)
AXES_FAILURE_LIMIT = env_int("AXES_FAILURE_LIMIT", 5)
AXES_COOLOFF_TIME = env_int("AXES_COOLOFF_HOURS", 1)
AXES_LOCKOUT_PARAMETERS = [["ip_address"], ["username"]]
AXES_RESET_ON_SUCCESS = True

PASSWORD_RESET_TOKEN_TTL_MINUTES = env_int("PASSWORD_RESET_TOKEN_TTL_MINUTES", 60)

# Django admin is a break-glass surface (B-16); off unless explicitly enabled.
ENABLE_DJANGO_ADMIN = env_bool("ENABLE_DJANGO_ADMIN", False)

# Supplier bank account numbers are encrypted at rest (B-26). Values are Fernet
# keys: the first encrypts, all are tried when decrypting so keys can rotate.
# Empty here; development derives one and production refuses to start without.
BANK_ACCOUNT_ENCRYPTION_KEYS = env_list("BANK_ACCOUNT_ENCRYPTION_KEYS")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": PASSWORD_MIN_LENGTH},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation ---------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Lagos"  # reporting currency and operations are Nigerian (NGN)
USE_I18N = True
USE_TZ = True

# --- Static files -----------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded documents are private. MEDIA_URL is intentionally not routed in
# urls.py, so files are reachable only through the authenticated download
# endpoint (DOC-01).
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
DOCUMENT_MAX_UPLOAD_BYTES = env_int("DOCUMENT_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
DOCUMENT_ALLOWED_EXTENSIONS = env_list(
    "DOCUMENT_ALLOWED_EXTENSIONS",
    ".pdf,.png,.jpg,.jpeg,.webp,.docx,.xlsx,.csv,.txt",
)

# --- API --------------------------------------------------------------------
REST_FRAMEWORK = {
    # Fail closed: a new endpoint is private unless it says otherwise.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.identity.authentication.SessionAuthentication401",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "shared.exceptions.error_envelope_handler",
    # Consistent list contract (spec 4.4): paginated, searchable and orderable
    # unless a view opts out. Report APIViews return their own bounded rows.
    "DEFAULT_PAGINATION_CLASS": "shared.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_THROTTLE_RATES": {"password_reset": env_str("PASSWORD_RESET_RATE", "20/hour")},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "TMD Platform API",
    "DESCRIPTION": (
        "Project-centred procurement, inventory and financial management API. "
        "Phase 1 shell: health endpoints and generated documentation only."
    ),
    "VERSION": APP_VERSION or "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
}

# --- Logging ----------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "shared.logging.JsonFormatter"},
    },
    "filters": {
        "request_id": {"()": "shared.logging.RequestIDFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": env_str("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
