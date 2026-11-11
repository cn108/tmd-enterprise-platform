"""The API error envelope is part of the contract with the frontend."""

from __future__ import annotations

import json

from django.test import override_settings
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from shared.exceptions import error_envelope_handler


def test_validation_error_uses_envelope():
    response = error_envelope_handler(ValidationError({"amount": ["This field is required."]}), {})

    assert response.status_code == 400
    error = response.data["error"]
    assert error["code"] == "invalid_request"
    assert error["details"] == {"amount": ["This field is required."]}
    assert "request_id" in error


def test_permission_denied_uses_envelope():
    response = error_envelope_handler(PermissionDenied(), {})

    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


def test_not_found_uses_envelope():
    response = error_envelope_handler(NotFound(), {})

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


def test_error_envelope_is_json_serialisable():
    response = error_envelope_handler(ValidationError({"amount": ["bad"]}), {})
    json.dumps(response.data)


@override_settings(DEBUG=False)
def test_unknown_route_returns_json_envelope_in_production_mode(client):
    response = client.get("/api/v1/does-not-exist/")

    assert response.status_code == 404
    assert response.headers["Content-Type"] == "application/json"
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert len(body["error"]["request_id"]) == 32
