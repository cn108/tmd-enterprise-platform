"""Shared viewset behaviour for master data.

Two rules are enforced here once rather than in every view:

* records are deactivated, never deleted (M-05, MAS-08);
* ``created_by``/``updated_by`` are stamped from the authenticated user.
"""

from __future__ import annotations

from django.db.models import Q
from rest_framework import status, viewsets

from shared.exceptions import error_response
from shared.permissions import ModelPermission


class NoDeleteViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Master data is deactivated, not deleted. Set is_active to false instead.",
            status.HTTP_409_CONFLICT,
        )


class MasterDataViewSet(NoDeleteViewSet):
    """Adds ``?is_active=`` and ``?q=`` filtering without extra dependencies."""

    search_fields: tuple[str, ...] = ("code", "name")

    def get_queryset(self):
        queryset = super().get_queryset()

        has_active = any(field.name == "is_active" for field in queryset.model._meta.fields)
        active = self.request.query_params.get("is_active")
        if has_active and active is not None:
            is_active = active.strip().lower() in {"1", "true", "yes", "on"}
            queryset = queryset.filter(is_active=is_active)

        # Both spellings are accepted: `q` is the original portal parameter and
        # `search` is DRF's convention used by the new screens.
        term = (
            self.request.query_params.get("q")
            or self.request.query_params.get("search")
            or ""
        ).strip()
        if term:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": term})
            queryset = queryset.filter(query)

        return queryset


class ProtectedMasterDataViewSet(MasterDataViewSet):
    permission_classes = [ModelPermission]


class ProtectedNoDeleteViewSet(NoDeleteViewSet):
    permission_classes = [ModelPermission]
