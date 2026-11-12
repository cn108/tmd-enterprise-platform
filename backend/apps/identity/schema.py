"""OpenAPI authentication scheme for the session-cookie API."""

from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAuthentication401Scheme(OpenApiAuthenticationExtension):
    target_class = "apps.identity.authentication.SessionAuthentication401"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "sessionid",
            "description": "Django session cookie issued by /api/v1/auth/login/.",
        }
