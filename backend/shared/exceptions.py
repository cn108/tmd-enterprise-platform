"""A single JSON shape for every API error.

Clients (the Angular portal first) can rely on ``error.code`` for branching,
``error.message`` for a safe human-readable summary, ``error.details`` for field
level problems, and ``error.request_id`` for support.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from shared.logging import get_request_id

logger = logging.getLogger(__name__)

_CODES = {
    status.HTTP_400_BAD_REQUEST: "invalid_request",
    status.HTTP_401_UNAUTHORIZED: "not_authenticated",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
}


def _message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        if isinstance(detail.get("detail"), str):
            return detail["detail"]
        return "One or more fields are invalid."
    if isinstance(detail, list) and detail:
        return _message(detail[0])
    return "The request could not be completed."


def _details(detail: Any) -> Any:
    if isinstance(detail, (dict, list)):
        return detail
    return None


def error_response(code: str, message: str, status_code: int, details: Any = None) -> Response:
    """Build the documented envelope for errors raised outside DRF's flow."""
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": get_request_id(),
            }
        },
        status=status_code,
    )


def error_envelope_handler(exc: Exception, context: dict) -> Response:
    """DRF exception handler that always returns the documented envelope."""
    response = drf_exception_handler(exc, context)

    if response is None:
        logger.error("Unhandled API exception", exc_info=exc)
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": "An unexpected error occurred.",
                    "details": None,
                    "request_id": get_request_id(),
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    response.data = {
        "error": {
            "code": _CODES.get(response.status_code, "error"),
            "message": _message(detail),
            "details": _details(detail),
            "request_id": get_request_id(),
        }
    }
    return response
