"""Root URL configuration.

Health and documentation exist from Phase 1. Phase 2 adds authentication.
Business endpoints are added by their authorised phase; see docs/14-backlog.md.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import HealthView, ReadinessView

handler404 = "shared.handlers.not_found"

urlpatterns = [
    # Unversioned probes for infrastructure (container healthchecks, load balancer).
    path("health/", HealthView.as_view(), name="health"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    # Versioned API surface.
    path("api/v1/health/", HealthView.as_view(), name="api-health"),
    path("api/v1/health/ready/", ReadinessView.as_view(), name="health-ready-api"),
    path("api/v1/auth/", include("apps.identity.urls")),
    path("api/v1/", include("apps.organisation.urls")),
    path("api/v1/", include("apps.parties.urls")),
    path("api/v1/", include("apps.catalogue.urls")),
    path("api/v1/", include("apps.warehousing.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.procurement.urls")),
    path("api/v1/", include("apps.accounting.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

# Break-glass only: disabled in production unless explicitly enabled (B-16).
if settings.ENABLE_DJANGO_ADMIN:
    urlpatterns.append(path("admin/", admin.site.urls))
