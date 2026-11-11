"""Absolute session lifetime.

The session cookie provides a sliding idle timeout. This middleware adds an
absolute limit: however active a session is, it ends after the configured
period. That caps the damage from a stolen session cookie.

Both timings are configuration (D-36), not constants in code.
"""

from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from shared.logging import get_request_id

STARTED_KEY = "session_started_at"


class AbsoluteSessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            started_raw = request.session.get(STARTED_KEY)

            if not started_raw:
                request.session[STARTED_KEY] = now.isoformat()
            else:
                started = self._parse(started_raw)
                limit = settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS
                if started is None or (now - started).total_seconds() > limit:
                    logout(request)
                    return JsonResponse(
                        {
                            "error": {
                                "code": "session_expired",
                                "message": "Your session expired. Sign in again.",
                                "details": None,
                                "request_id": get_request_id(),
                            }
                        },
                        status=401,
                    )

        return self.get_response(request)

    @staticmethod
    def _parse(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed
