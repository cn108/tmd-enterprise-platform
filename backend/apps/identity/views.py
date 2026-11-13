"""Authentication endpoints.

Session-cookie authentication (B-12). DRF's SessionAuthentication enforces CSRF
on authenticated mutations; anonymous login is exempt from CSRF because no
session exists yet to ride.

Lockout is handled by django-axes in the authentication backend, so every one of
these views benefits without repeating the logic.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.identity.mfa import (
    consume_challenge,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_secret,
    issue_challenge,
    provisioning_uri,
    resolve_challenge,
    verify_recovery_code,
    verify_totp,
)
from apps.identity.models import MfaChallenge, MfaDevice, PasswordResetToken
from apps.identity.serializers import (
    LoginSerializer,
    MfaCodeSerializer,
    MfaTokenSerializer,
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

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

        device = MfaDevice.objects.filter(user=user, confirmed_at__isnull=False).first()
        mfa_required = (
            user.mfa_required or settings.MFA_REQUIRED_FOR_ALL_USERS or device is not None
        )
        if mfa_required:
            purpose = MfaChallenge.Purpose.VERIFY if device else MfaChallenge.Purpose.ENROL
            token = issue_challenge(user, purpose)
            code = "mfa_required" if device else "mfa_enrollment_required"
            message = (
                "Enter the six-digit code from your authenticator app."
                if device
                else "Set up an authenticator app before continuing."
            )
            return error_response(
                code,
                message,
                status.HTTP_401_UNAUTHORIZED,
                {"challenge_token": token, "purpose": purpose},
            )

        _start_session(request, user, backend=getattr(user, "backend", None))
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


def _start_session(request, user, *, backend: str | None = None) -> None:
    login(request, user, backend=backend or "django.contrib.auth.backends.ModelBackend")
    request.session["session_started_at"] = timezone.now().isoformat()


class MfaSetupView(APIView):
    """Create or refresh an unconfirmed TOTP device for an enrolment challenge."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa"

    @extend_schema(tags=["auth"], summary="Start authenticator enrolment")
    def post(self, request):
        serializer = MfaTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge = resolve_challenge(
            serializer.validated_data["challenge_token"], MfaChallenge.Purpose.ENROL
        )
        if challenge is None or not challenge.user.is_active:
            return error_response(
                "invalid_mfa_challenge",
                "This enrolment challenge is invalid or has expired. Sign in again.",
                status.HTTP_400_BAD_REQUEST,
            )
        if MfaDevice.objects.filter(user=challenge.user, confirmed_at__isnull=False).exists():
            return error_response(
                "mfa_already_enrolled",
                "This account already has an authenticator. Sign in with a code instead.",
                status.HTTP_400_BAD_REQUEST,
            )

        secret = generate_secret()
        recovery_codes, hashed_codes = generate_recovery_codes()
        MfaDevice.objects.update_or_create(
            user=challenge.user,
            defaults={
                "secret_encrypted": encrypt_secret(secret),
                "confirmed_at": None,
                "last_used_counter": 0,
                "recovery_codes": hashed_codes,
            },
        )
        return Response(
            {
                "secret": secret,
                "otpauth_uri": provisioning_uri(challenge.user.email, secret),
                "recovery_codes": recovery_codes,
            }
        )


class MfaConfirmView(APIView):
    """Confirm a newly created TOTP device and complete sign-in."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa"

    @extend_schema(tags=["auth"], summary="Confirm authenticator enrolment")
    def post(self, request):
        serializer = MfaCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            challenge = resolve_challenge(
                serializer.validated_data["challenge_token"],
                MfaChallenge.Purpose.ENROL,
                lock=True,
            )
            if challenge is None or not challenge.user.is_active:
                return error_response(
                    "invalid_mfa_challenge",
                    "This enrolment challenge is invalid or has expired. Sign in again.",
                    status.HTTP_400_BAD_REQUEST,
                )
            device = (
                MfaDevice.objects.select_for_update()
                .filter(user=challenge.user, confirmed_at__isnull=True)
                .first()
            )
            if device is None:
                return error_response(
                    "invalid_mfa_challenge",
                    "Start authenticator setup again.",
                    status.HTTP_400_BAD_REQUEST,
                )
            counter = verify_totp(
                decrypt_secret(device.secret_encrypted),
                serializer.validated_data["code"],
                last_counter=device.last_used_counter,
            )
            if counter is None:
                return error_response(
                    "invalid_mfa_code",
                    "That authenticator code is not valid. Try the next code.",
                    status.HTTP_400_BAD_REQUEST,
                )
            device.confirmed_at = timezone.now()
            device.last_used_counter = counter
            device.save(update_fields=["confirmed_at", "last_used_counter", "updated_at"])
            consume_challenge(challenge)
            _start_session(request, challenge.user)
        return Response(UserSerializer(challenge.user).data, status=status.HTTP_200_OK)


class MfaVerifyView(APIView):
    """Complete a password-authenticated sign-in with TOTP or a recovery code."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa"

    @extend_schema(tags=["auth"], summary="Complete MFA challenge")
    def post(self, request):
        serializer = MfaCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            challenge = resolve_challenge(
                serializer.validated_data["challenge_token"],
                MfaChallenge.Purpose.VERIFY,
                lock=True,
            )
            if challenge is None or not challenge.user.is_active:
                return error_response(
                    "invalid_mfa_challenge",
                    "This sign-in challenge is invalid or has expired. Sign in again.",
                    status.HTTP_400_BAD_REQUEST,
                )
            device = (
                MfaDevice.objects.select_for_update()
                .filter(user=challenge.user, confirmed_at__isnull=False)
                .first()
            )
            if device is None:
                return error_response(
                    "mfa_not_enrolled",
                    "This account has no confirmed authenticator. Sign in again to set one up.",
                    status.HTTP_400_BAD_REQUEST,
                )
            code = serializer.validated_data["code"]
            counter = verify_totp(
                decrypt_secret(device.secret_encrypted),
                code,
                last_counter=device.last_used_counter,
            )
            if counter is None and not verify_recovery_code(device, code):
                return error_response(
                    "invalid_mfa_code",
                    "That authenticator or recovery code is not valid.",
                    status.HTTP_400_BAD_REQUEST,
                )
            if counter is not None:
                device.last_used_counter = counter
                device.save(update_fields=["last_used_counter", "updated_at"])
            consume_challenge(challenge)
            _start_session(request, challenge.user)
        return Response(UserSerializer(challenge.user).data, status=status.HTTP_200_OK)


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
