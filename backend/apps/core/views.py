"""Health and readiness endpoints.

Liveness answers "is the process running?" without touching the database.
Readiness answers "can it serve traffic?" and therefore checks the database.
Neither endpoint is allowed to expose configuration, versions of dependencies
or connection details.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import connection
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """Liveness probe: no database access."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["health"],
        summary="Liveness probe",
        responses={200: OpenApiResponse(description="Process is running.")},
    )
    def get(self, request):
        return Response(
            {"status": "ok", "service": "tmd-platform-api", "version": settings.APP_VERSION}
        )


class ReadinessView(APIView):
    """Readiness probe: verifies the database answers a trivial query."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["health"],
        summary="Readiness probe",
        responses={
            200: OpenApiResponse(description="Dependencies are reachable."),
            503: OpenApiResponse(description="At least one dependency is unavailable."),
        },
    )
    def get(self, request):
        checks = {"database": "ok"}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            logger.warning("Readiness check failed for database", exc_info=True)
            checks["database"] = "unavailable"
            return Response({"status": "degraded", "checks": checks}, status=503)

        return Response({"status": "ok", "checks": checks})
