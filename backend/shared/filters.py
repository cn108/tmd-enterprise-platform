from __future__ import annotations

from rest_framework.filters import BaseFilterBackend


class SortOrderFilter(BaseFilterBackend):
    """Accept the portal's ``?sort=&order=`` contract safely.

    Only concrete model fields may be sorted, so the parameter can never become
    an arbitrary ORM expression. Existing ``?ordering=`` support is untouched.
    """

    def filter_queryset(self, request, queryset, view):
        sort = (request.query_params.get("sort") or "").strip()
        if not sort:
            return queryset
        allowed = {field.name for field in queryset.model._meta.concrete_fields}
        if sort not in allowed:
            return queryset
        prefix = "-" if (request.query_params.get("order") or "asc").lower() == "desc" else ""
        return queryset.order_by(f"{prefix}{sort}")