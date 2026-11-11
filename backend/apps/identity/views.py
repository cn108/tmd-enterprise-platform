"""Authentication endpoints.

Session-cookie authentication (B-12). DRF's SessionAuthentication enforces CSRF
on authenticated mutations; anonymous login is exempt from CSRF because no
session exists yet to ride.

Lockout is handled by django-axes in the authentication backend, so every one of
these views benefits without repeating the logic.
"""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.identity.models import PasswordResetToken
from apps.identity.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    UserSerializer,
)
from shared.exceptions import error_response


class CsrfView(APIView):
    """Issues a CSRF cookie so the SPA can send the token header."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(tags=["auth"], summary="Obtain a CSRF token")
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Sign in",
        request=LoginSerializer,
        responses={
            200: UserSerializer,
            401: OpenApiResponse(description="Invalid credentials"),
            403: OpenApiResponse(description="Account locked after repeated failures"),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        user = authenticate(
            request,
            username=email,
            password=serializer.validated_data["password"],
        )
        if user is None:
            # django-axes refuses a locked account by setting this flag, but
            # Django's authenticate() swallows the backend's PermissionDenied and
            # returns None, so the distinction has to be recovered here.
            if getattr(request, "axes_locked_out", False):
                return error_response(
                    "account_locked",
                    "Account locked after repeated failed attempts. Try again later, "
                    "or ask an administrator to unlock it.",
                    status.HTTP_403_FORBIDDEN,
                )
            # Deliberately identical for unknown email, wrong password and a
            # disabled account: the response must not confirm which accounts exist.
            return error_response(
                "invalid_credentials",
                "Email or password is incorrect.",
                status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        request.session["session_started_at"] = timezone.now().isoformat()

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Sign out", responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Current user", responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["auth"],
        summary="Change own password",
        request=PasswordChangeSerializer,
        responses={204: None},
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        if not request.user.check_password(serializer.validated_data["current_password"]):
            raise ValidationError({"current_password": ["The current password is not correct."]})

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])

        # A password change invalidates every outstanding reset link and every
        # other session, while keeping this one signed in.
        PasswordResetToken.objects.filter(user=request.user, used_at__isnull=True).delete()
        update_session_auth_hash(request, request.user)

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(APIView):
    """Consumes an administrator-issued reset token."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=["auth"],
        summary="Complete a password reset",
        request=PasswordResetSerializer,
        responses={204: None, 400: OpenApiResponse(description="Invalid or expired token")},
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_hash = PasswordResetToken.hash_token(serializer.validated_data["token"])
        token = (
            PasswordResetToken.objects.select_related("user").filter(token_hash=token_hash).first()
        )
        if token is None or not token.is_valid():
            raise ValidationError({"token": ["This reset link is invalid or has expired."]})

        user = token.user
        if not user.is_active:
            raise ValidationError({"token": ["This account is disabled."]})

        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        PasswordResetToken.objects.filter(user=user, used_at__isnull=True).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
