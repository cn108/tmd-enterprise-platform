"""Structured JSON logging with request correlation.

Log lines are machine-readable so that staging and production logs can be
filtered by request ID. No business data, credentials or personal data is
added here; callers log identifiers, not payloads.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str] = ContextVar("request_id", default="")

# Only short, boring values are accepted from outside; anything else is
# replaced so that a caller cannot inject newlines or noise into every log line.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> object:
    return _request_id.set(value)


def reset_request_id(token: object) -> None:
    _request_id.reset(token)  # type: ignore[arg-type]


def sanitise_request_id(raw: str | None) -> str:
    if raw and _SAFE_REQUEST_ID.fullmatch(raw):
        return raw
    return ""


@contextmanager
def request_context(value: str) -> Iterator[str]:
    token = set_request_id(value)
    try:
        yield value
    finally:
        reset_request_id(token)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the correlation ID attached."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "") or get_request_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestIDFilter(logging.Filter):
    """Copies the current correlation ID onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
