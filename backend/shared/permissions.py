"""Model-level permission for master-data endpoints.

DRF's default is authentication only. Master data still needs its Django model
permissions so an employee cannot edit suppliers, catalogue items, warehouses,
departments or party records merely by being signed in.

DELETE is intentionally left to the viewset: TMD master-data viewsets return a
controlled 409 (deactivate, never delete) instead of exposing deletion.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class ModelPermission(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        queryset = getattr(view, "queryset", None)
        model = getattr(queryset, "model", None)
        if model is None:
            return False
        action_name = getattr(view, "action", None)
        standard_actions = {
            None,
            "create",
            "update",
            "partial_update",
            "destroy",
            "list",
            "retrieve",
        }
        if action_name not in standard_actions:
            # Custom actions perform their own authorization (for example the
            # bank-account change reviewer checks the approve permission).
            return True
        if request.method in SAFE_METHODS:
            action = "view"
        elif request.method == "POST":
            action = "add"
        elif request.method in {"PUT", "PATCH"}:
            action = "change"
        elif request.method == "DELETE":
            return True
        else:
            return False
        return request.user.has_perm(f"{model._meta.app_label}.{action}_{model._meta.model_name}")
