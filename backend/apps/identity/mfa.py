"""TOTP multi-factor authentication primitives.

Secrets are encrypted at rest, recovery codes are one-way hashes, and a TOTP
counter is recorded so a code cannot be replayed. The implementation follows
RFC 6238 (HMAC-SHA1, six digits, 30-second period) so standard authenticator
apps can enrol without a proprietary dependency.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import timedelta
from urllib.parse import quote

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.utils import timezone

from apps.identity.models import MfaChallenge, MfaDevice, User

CHALLENGE_SALT = "tmd.identity.mfa.challenge"
TOTP_DIGITS = 6
TOTP_PERIOD_SECONDS = 30
TOTP_WINDOW = 1
RECOVERY_CODE_COUNT = 10


def _fernet() -> Fernet:
    configured = getattr(settings, "MFA_ENCRYPTION_KEY", "")
    if configured:
        return Fernet(configured.encode("utf-8"))
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(padded, casefold=True)


def _hotp(secret: str, counter: int) -> str:
    digest = hmac.new(_decode_secret(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10**TOTP_DIGITS):0{TOTP_DIGITS}d}"


def current_code(secret: str, *, at_time=None) -> str:
    """Return the code for the current 30-second step (used by tests and support tooling)."""
    now = at_time or timezone.now()
    return _hotp(secret, int(now.timestamp()) // TOTP_PERIOD_SECONDS)


def verify_totp(
    secret: str,
    code: str,
    *,
    last_counter: int = 0,
    at_time=None,
) -> int | None:
    """Return the accepted counter, or ``None`` for an invalid/replayed code."""
    normalized = "".join(character for character in code if character.isdigit())
    if len(normalized) != TOTP_DIGITS:
        return None
    now = at_time or timezone.now()
    current = int(now.timestamp()) // TOTP_PERIOD_SECONDS
    for offset in range(-TOTP_WINDOW, TOTP_WINDOW + 1):
        counter = current + offset
        if counter > last_counter and hmac.compare_digest(_hotp(secret, counter), normalized):
            return counter
    return None


def provisioning_uri(email: str, secret: str) -> str:
    issuer = settings.MFA_ISSUER
    label = quote(f"{issuer}:{email}", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}"
        f"&issuer={quote(issuer, safe='')}"
        f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


def generate_recovery_codes() -> tuple[list[str], list[str]]:
    plain = [
        f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        for _ in range(RECOVERY_CODE_COUNT)
    ]
    return plain, [make_password(code) for code in plain]


def verify_recovery_code(device: MfaDevice, code: str) -> bool:
    normalized = code.strip().upper()
    for index, hashed in enumerate(device.recovery_codes):
        if check_password(normalized, hashed):
            remaining = list(device.recovery_codes)
            remaining.pop(index)
            device.recovery_codes = remaining
            device.save(update_fields=["recovery_codes", "updated_at"])
            return True
    return False


def issue_challenge(user: User, purpose: str) -> str:
    challenge = MfaChallenge.objects.create(
        user=user,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(seconds=settings.MFA_CHALLENGE_TTL_SECONDS),
    )
    return signing.dumps(
        {"uid": user.pk, "jti": str(challenge.token_id), "purpose": purpose},
        salt=CHALLENGE_SALT,
    )


def resolve_challenge(token: str, purpose: str, *, lock: bool = False) -> MfaChallenge | None:
    try:
        payload = signing.loads(
            token,
            salt=CHALLENGE_SALT,
            max_age=settings.MFA_CHALLENGE_TTL_SECONDS,
        )
    except signing.BadSignature:
        return None
    if payload.get("purpose") != purpose:
        return None
    queryset = MfaChallenge.objects.select_related("user").filter(
        token_id=payload.get("jti"),
        user_id=payload.get("uid"),
        purpose=purpose,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    )
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    return queryset.first()


def consume_challenge(challenge: MfaChallenge) -> None:
    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at"])
