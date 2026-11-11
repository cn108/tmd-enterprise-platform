"""Serializers for authentication endpoints.

Fields are declared explicitly so that no request can set status-like
attributes (mass-assignment protection, S-07).
"""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.identity.models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_new_password(self, value: str) -> str:
        user = self.context["request"].user
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class UserSerializer(serializers.ModelSerializer):
    """What the SPA needs about the signed-in user. Not a security boundary."""

    department = serializers.CharField(source="department.code", allow_null=True, read_only=True)
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "employee_ref",
            "department",
            "must_change_password",
            "mfa_required",
            "roles",
            "permissions",
        ]

    def get_roles(self, obj: User) -> list[str]:
        # Role assignments are introduced in W4; until then the list is empty
        # rather than fabricated from group memberships.
        return []

    def get_permissions(self, obj: User) -> list[str]:
        return []
