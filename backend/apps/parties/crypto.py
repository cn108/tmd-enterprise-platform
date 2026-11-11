"""Envelope encryption for supplier bank account numbers.

Fernet provides authenticated encryption (AES-128-CBC + HMAC-SHA256). Keys come
from ``BANK_ACCOUNT_ENCRYPTION_KEYS``: the first key encrypts, and every key is
tried on decrypt, so a key can be rotated by prepending a new one and
re-encrypting records over time.

Ciphertext carries a version prefix so an algorithm change is explicit rather
than inferred. This module deliberately has no model imports, so a data
migration can use it.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

CIPHERTEXT_VERSION = "v1:"


def _cipher() -> MultiFernet:
    keys = getattr(settings, "BANK_ACCOUNT_ENCRYPTION_KEYS", [])
    if not keys:
        raise ImproperlyConfigured(
            "BANK_ACCOUNT_ENCRYPTION_KEYS is not configured; bank account numbers "
            "cannot be encrypted or decrypted."
        )
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            "BANK_ACCOUNT_ENCRYPTION_KEYS contains an invalid Fernet key."
        ) from exc


def encrypt_account_number(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ValueError("An account number is required.")
    token = _cipher().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{CIPHERTEXT_VERSION}{token}"


def decrypt_account_number(stored: str) -> str:
    if not stored or not stored.startswith(CIPHERTEXT_VERSION):
        raise ValueError("Unrecognised bank account ciphertext.")
    token = stored[len(CIPHERTEXT_VERSION) :].encode("ascii")
    try:
        return _cipher().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("The bank account ciphertext could not be decrypted.") from exc
