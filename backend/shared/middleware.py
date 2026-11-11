"""Request correlation middleware.

Accepts an inbound ``X-Request-ID`` when it is safe, otherwise generates one,
exposes it to logging for the life of the request, and echoes it back so that a
user-reported error can be traced to its log lines.
"""

from __future__ import annotations

from uuid import uuid4

from django.http import HttpRequest, HttpResponse

from shared.logging import (
    REQUEST_ID_HEADER,
    reset_request_id,
    sanitise_request_id,
    set_request_id,
)


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = sanitise_request_id(incoming) or uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]

        token = set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)

        response[REQUEST_ID_HEADER] = request_id
        return response
