"""Plain HTTP error handlers outside the DRF layer."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from shared.logging import get_request_id


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse(
        {
            "error": {
                "code": "not_found",
                "message": "The requested resource does not exist.",
                "details": None,
                "request_id": get_request_id(),
            }
        },
        status=404,
    )
