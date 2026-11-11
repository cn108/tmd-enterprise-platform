"""Health endpoint and correlation ID behaviour."""

from __future__ import annotations

import json
import logging

import pytest

from shared.logging import JsonFormatter, request_context, sanitise_request_id


def test_liveness_returns_ok_without_database(client):
    response = client.get("/health/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "tmd-platform-api"


@pytest.mark.django_db
def test_readiness_checks_database(client):
    response = client.get("/health/ready/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_incoming_request_id_is_echoed(client):
    response = client.get("/health/", headers={"X-Request-ID": "support-ticket-1234"})

    assert response.headers["X-Request-ID"] == "support-ticket-1234"


def test_missing_request_id_is_generated(client):
    response = client.get("/health/")

    assert len(response.headers["X-Request-ID"]) == 32


def test_unsafe_request_id_is_replaced():
    assert sanitise_request_id("bad id\ninjected") == ""
    assert sanitise_request_id("a" * 200) == ""
    assert sanitise_request_id("") == ""
    assert sanitise_request_id("c0ffee-42") == "c0ffee-42"


def test_json_logs_carry_the_request_id():
    record = logging.LogRecord("tmd.test", logging.INFO, __file__, 1, "hello", None, None)

    with request_context("rid-abc"):
        payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] == "rid-abc"
    assert payload["level"] == "INFO"
    assert payload["message"] == "hello"
