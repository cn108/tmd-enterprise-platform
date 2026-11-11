"""Session authentication with an honest unauthenticated response.

DRF returns 403 instead of 401 when no authenticator supplies a
``WWW-Authenticate`` header. A missing session is not a permission problem, and
clients should not have to guess which it is, so this class supplies the header
and lets DRF answer 401.
"""

from __future__ import annotations

from rest_framework.authentication import SessionAuthentication


class SessionAuthentication401(SessionAuthentication):
    def authenticate_header(self, request) -> str:
        return "Session"
