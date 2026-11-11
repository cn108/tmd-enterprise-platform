"""Break-glass administration surface (B-16).

Disabled in production unless ENABLE_DJANGO_ADMIN is explicitly set. Users are
created here without a usable password; an administrator then issues a reset
token with `python manage.py issue_password_reset <email>`.
"""

from django.contrib import admin

from apps.identity.models import PasswordResetToken, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "department", "is_active", "is_staff", "last_login")
    list_filter = ("is_active", "is_staff", "department")
    search_fields = ("email", "full_name", "employee_ref")
    ordering = ("email",)
    readonly_fields = ("last_login", "date_joined", "password")
    fieldsets = (
        (None, {"fields": ("email", "full_name", "employee_ref", "department")}),
        ("Access", {"fields": ("is_active", "is_staff", "mfa_required", "must_change_password")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("History", {"fields": ("last_login", "date_joined")}),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    readonly_fields = ("user", "token_hash", "created_at", "expires_at", "used_at", "issued_by")

    def has_add_permission(self, request) -> bool:
        return False
