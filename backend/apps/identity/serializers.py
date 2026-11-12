"""Serializers for authentication endpoints.

Fields are declared explicitly so that no request can set status-like
attributes (mass-assignment protection, S-07).
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
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
        # A role is a Django group. The access administrator names it and
        # chooses its permissions; no role or matrix is seeded here.
        return sorted(obj.groups.values_list("name", flat=True))

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(obj.get_all_permissions())


def permission_codename(permission: Permission) -> str:
    return f"{permission.content_type.app_label}.{permission.codename}"


class PermissionSerializer(serializers.ModelSerializer):
    codename = serializers.SerializerMethodField()
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)
    model = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "codename", "name", "app_label", "model"]

    def get_codename(self, obj: Permission) -> str:
        return permission_codename(obj)


class RoleSerializer(serializers.ModelSerializer):
    """A named permission bundle. Management decides its contents.

    The API accepts permissions by ``app_label.codename`` so a role definition
    is readable and portable. Nothing is created implicitly.
    """

    permissions = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    permission_codenames = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "permissions", "permission_codenames", "member_count"]

    def get_permission_codenames(self, obj: Group) -> list[str]:
        return sorted(permission_codename(permission) for permission in obj.permissions.all())

    def get_member_count(self, obj: Group) -> int:
        return obj.user_set.count()

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("A role needs a name.")
        existing = Group.objects.filter(name__iexact=name)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A role with this name already exists.")
        return name

    def validate_permissions(self, value: list[str]) -> list[Permission]:
        if not value:
            return []
        available = {
            permission_codename(item): item
            for item in Permission.objects.select_related("content_type")
        }
        unknown = sorted(set(value) - set(available))
        if unknown:
            raise serializers.ValidationError(
                f"Unknown permissions: {', '.join(unknown)}."
            )
        return [available[code] for code in sorted(set(value))]

    def create(self, validated_data):
        permissions = validated_data.pop("permissions", [])
        role = Group.objects.create(**validated_data)
        role.permissions.set(permissions)
        return role

    def update(self, instance, validated_data):
        permissions = validated_data.pop("permissions", None)
        instance.name = validated_data.get("name", instance.name)
        instance.save()
        if permissions is not None:
            instance.permissions.set(permissions)
        return instance


class AccessUserSerializer(serializers.ModelSerializer):
    """Administrator view of an account, including role assignment."""

    department_code = serializers.CharField(source="department.code", read_only=True, default=None)
    roles = serializers.SlugRelatedField(
        many=True, slug_field="name", queryset=Group.objects.all(), required=False
    )
    role_names = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "employee_ref",
            "department",
            "department_code",
            "is_active",
            "must_change_password",
            "roles",
            "role_names",
            "permissions",
            "password",
            "date_joined",
        ]
        read_only_fields = ["date_joined"]

    def get_role_names(self, obj: User) -> list[str]:
        return sorted(obj.groups.values_list("name", flat=True))

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(obj.get_all_permissions())

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A password is required."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        roles = validated_data.pop("roles", [])
        user = User.objects.create_user(password=password, **validated_data)
        user.groups.set(roles)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        roles = validated_data.pop("roles", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.groups.set(roles)
        return instance
