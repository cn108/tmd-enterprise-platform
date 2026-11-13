"""Identity: the custom user model and administrator-issued reset tokens.

Email is the login identifier. No username, no password history in the row, and
no personal data beyond what employment already requires.

Roles and permissions arrive in work package W4; until then this module carries
only what authentication needs.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_staff and is_superuser set to True.")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=254, unique=True)
    full_name = models.CharField(max_length=150)
    employee_ref = models.CharField(max_length=30, blank=True)
    department = models.ForeignKey(
        "organisation.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Django admin (break-glass) access only. Not a business role.",
    )
    must_change_password = models.BooleanField(default=False)
    mfa_required = models.BooleanField(
        default=False,
        help_text="Set when MFA enforcement is configured for this user's roles.",
    )

    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["email"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.full_name or self.email


class MfaDevice(models.Model):
    """An encrypted TOTP secret and one-way recovery codes for one user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mfa_device")
    secret_encrypted = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_counter = models.BigIntegerField(default=0)
    recovery_codes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"MFA device for {self.user_id} ({'confirmed' if self.confirmed_at else 'pending'})"


class MfaChallenge(models.Model):
    """A short-lived, single-use challenge issued after a valid password."""

    class Purpose(models.TextChoices):
        VERIFY = "verify", "Verify"
        ENROL = "enrol", "Enrol"

    token_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_challenges")
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"MFA {self.purpose} challenge for {self.user_id}"


class PasswordResetToken(models.Model):
    """A single-use, expiring token issued by an administrator.

    Only the SHA-256 hash is stored, so a database reader cannot reset an
    account with what they find there.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "password reset token"
        verbose_name_plural = "password reset tokens"

    def __str__(self) -> str:
        return f"reset for {self.user_id} ({'used' if self.used_at else 'unused'})"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user: User, issued_by: User | None = None) -> tuple[PasswordResetToken, str]:
        raw_token = secrets.token_urlsafe(32)
        token = cls.objects.create(
            user=user,
            token_hash=cls.hash_token(raw_token),
            expires_at=timezone.now()
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES),
            issued_by=issued_by,
        )
        return token, raw_token

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()
