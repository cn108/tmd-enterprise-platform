"""Access administration: roles (permission bundles) and user accounts.

This is the mechanism W4 needs, not the policy. Management still has to decide
which roles exist and which permissions each holds; the API starts with none,
and every write requires an access-administration permission. Nothing here
invents a role, a department scope or an approval threshold.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import create_audit_event
from apps.identity.models import User
from apps.identity.serializers import (
    AccessUserSerializer,
    PermissionSerializer,
    RoleSerializer,
)
from shared.exceptions import error_response


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.prefetch_related("permissions__content_type").all()
    serializer_class = RoleSerializer
    search_fields = ("name",)
    ordering_fields = ("name",)

    def list(self, request, *args, **kwargs):
        _require(request, "auth.view_group")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        _require(request, "auth.view_group")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        _require(request, "auth.add_group")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "auth.change_group")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Roles are renamed or emptied, not deleted; removing history would make past "
            "assignments unauditable.",
            status.HTTP_409_CONFLICT,
        )

    def perform_create(self, serializer):
        role = serializer.save()
        create_audit_event(
            actor=self.request.user,
            action="role.created",
            entity_type="auth.group",
            entity_id=role.pk,
            after={
                "name": role.name,
                "permissions": list(role.permissions.values_list("codename", flat=True)),
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        role = serializer.save()
        create_audit_event(
            actor=self.request.user,
            action="role.updated",
            entity_type="auth.group",
            entity_id=role.pk,
            after={
                "name": role.name,
                "permissions": list(role.permissions.values_list("codename", flat=True)),
            },
            request=self.request,
        )


class PermissionListView(APIView):
    """Every permission code the backend enforces, for role authoring."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require(request, "auth.view_permission")
        permissions = Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "codename"
        )
        return Response(PermissionSerializer(permissions, many=True).data)


class AccessUserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.select_related("department").prefetch_related("groups").all()
    serializer_class = AccessUserSerializer
    search_fields = ("email", "full_name", "employee_ref")
    ordering_fields = ("email", "full_name", "date_joined")

    def list(self, request, *args, **kwargs):
        _require(request, "identity.view_user")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        _require(request, "identity.view_user")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        _require(request, "identity.add_user")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "identity.change_user")
        instance = self.get_object()
        if instance.pk == request.user.pk and request.data.get("is_active") is False:
            return error_response(
                "self_deactivation",
                "You cannot deactivate your own account.",
                status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "User accounts are deactivated, never deleted, so their history keeps a subject.",
            status.HTTP_409_CONFLICT,
        )

    def perform_create(self, serializer):
        user = serializer.save()
        create_audit_event(
            actor=self.request.user,
            action="user.created",
            entity_type="identity.user",
            entity_id=user.pk,
            after={"email": user.email, "roles": list(user.groups.values_list("name", flat=True))},
            request=self.request,
        )

    def perform_update(self, serializer):
        user = serializer.save()
        create_audit_event(
            actor=self.request.user,
            action="user.updated",
            entity_type="identity.user",
            entity_id=user.pk,
            after={"email": user.email, "roles": list(user.groups.values_list("name", flat=True))},
            request=self.request,
        )
