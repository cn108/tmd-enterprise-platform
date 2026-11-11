"""Root URL configuration.

Only health and API documentation exist in Phase 1. Business endpoints are
added by their authorised phase; see docs/14-backlog.md.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import HealthView, ReadinessView

handler404 = "shared.handlers.not_found"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Unversioned probes for infrastructure (container healthchecks, load balancer).
    path("health/", HealthView.as_view(), name="health"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    # Versioned API surface.
    path("api/v1/health/", HealthView.as_view(), name="api-health"),
    path("api/v1/health/ready/", ReadinessView.as_view(), name="api-health-ready"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
