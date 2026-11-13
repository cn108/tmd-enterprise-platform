from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.identity import access_views

app_name = "access"

router = DefaultRouter()
router.register("roles", access_views.RoleViewSet, basename="role")
router.register("users", access_views.AccessUserViewSet, basename="access-user")

urlpatterns = [
    path("permissions/", access_views.PermissionListView.as_view(), name="permissions"),
    *router.urls,
]
