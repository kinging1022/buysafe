"""Auth API: register → verify phone (OTP) → session login, password reset,
and the signed-in user's profile and password (/api/me/).

Session auth (httpOnly cookie). CSRF is enforced on every auth POST, including
anonymous ones, so login and registration can't be forged cross-site.
"""

import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PhoneVerification, User
from .phone import mask_phone, normalize_ng_phone
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PhoneOnlySerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyOtpSerializer,
)
from .services.otp import OtpSendError, get_otp_service
from .services.password_reset import make_reset_token, user_for_reset_token
from .services.verification import (
    issue_code,
    latest_active_verification,
    record_send,
    send_code_if_allowed,
    send_limit_retry_after,
)

logger = logging.getLogger(__name__)

def otp_send_failed():
    return Response(
        {"code": "otp_send_failed", "detail": "We couldn’t send the code. Try again in a moment."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def session_response(request, user, http_status=status.HTTP_200_OK):
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response({"user": UserSerializer(user).data}, status=http_status)


@method_decorator(csrf_protect, name="dispatch")
class AuthView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """GET sets the csrftoken cookie the SPA sends back as X-CSRFToken."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(AuthView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            user = User.objects.select_for_update().filter(phone=data["phone"]).first()
            if user and user.phone_verified:
                return Response(
                    {"phone": ["An account with this number already exists."], "code": "phone_taken"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user is None:
                user = User(phone=data["phone"])
            # A returning unverified user just updates their details.
            user.first_name = data["first_name"]
            user.last_name = data["last_name"]
            user.set_password(data["password"])
            user.save()

        try:
            wait = send_code_if_allowed(user)
        except OtpSendError:
            return otp_send_failed()
        return Response(
            {"masked_phone": mask_phone(user.phone), "resend_available_in": wait},
            status=status.HTTP_201_CREATED,
        )


EXPIRED = {"code": "expired", "detail": "This code has expired. Request a new one."}


def check_code(verification, code):
    """None if `code` is right for this verification, else the error Response.
    The shapes are the same for every flow (sign up, password reset)."""
    if (
        verification is None
        or verification.expires_at <= timezone.now()
        or verification.attempts >= settings.OTP_MAX_ATTEMPTS
    ):
        return Response(EXPIRED, status=status.HTTP_400_BAD_REQUEST)

    try:
        ok = get_otp_service().verify_otp(verification.pin_id, code)
    except OtpSendError:
        return otp_send_failed()
    if ok:
        return None

    verification.attempts += 1
    attempts_left = settings.OTP_MAX_ATTEMPTS - verification.attempts
    if attempts_left <= 0:
        verification.used = True
    verification.save(update_fields=["attempts", "used"])
    if attempts_left <= 0:
        return Response(EXPIRED, status=status.HTTP_400_BAD_REQUEST)
    return Response({"code": "invalid_code", "attempts_left": attempts_left}, status=status.HTTP_400_BAD_REQUEST)


class VerifyOtpView(AuthView):
    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone, code = serializer.validated_data["phone"], serializer.validated_data["code"]

        verification = latest_active_verification(phone)
        if verification is not None and verification.user.phone_verified:
            verification = None
        error = check_code(verification, code)
        if error:
            return error

        user = verification.user
        with transaction.atomic():
            verification.used = True
            verification.save(update_fields=["used"])
            user.phone_verified = True
            user.save(update_fields=["phone_verified"])
        return session_response(request, user)


class ResendOtpView(AuthView):
    throttle_scope = "otp_resend"

    def post(self, request):
        serializer = PhoneOnlySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        # Limits apply per phone whether or not an account exists, so the
        # response never reveals which numbers are registered.
        wait = send_limit_retry_after(phone)
        if wait:
            return Response({"retry_after": wait}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        user = User.objects.filter(phone=phone, phone_verified=False).first()
        if user:
            try:
                issue_code(user)
            except OtpSendError:
                return otp_send_failed()
        else:
            record_send(phone)
        return Response({"resend_available_in": settings.OTP_RESEND_COOLDOWN})


class LoginView(AuthView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invalid = Response(
            {"code": "invalid_credentials", "detail": "Phone number or password is incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )

        try:
            phone = normalize_ng_phone(serializer.validated_data["phone"])
        except DjangoValidationError:
            phone = None
        # authenticate() still runs the password hasher for unknown users,
        # keeping timing roughly the same either way.
        user = authenticate(request, username=phone or "", password=serializer.validated_data["password"])
        if user is None:
            return invalid

        if not user.phone_verified:
            try:
                wait = send_code_if_allowed(user)
            except OtpSendError:
                return otp_send_failed()
            return Response(
                {"code": "phone_unverified", "masked_phone": mask_phone(user.phone), "resend_available_in": wait},
                status=status.HTTP_403_FORBIDDEN,
            )
        return session_response(request, user)


class LogoutView(AuthView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET /api/me/: the signed-in, verified user (403 otherwise).
    PATCH: update the profile fields; the phone can't be changed here."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """POST /api/me/password/. Signs out every other session (their stored
    password hash no longer matches) and keeps this one, with a new session key."""

    throttle_scope = "auth"

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not user.check_password(data["current_password"]):
            return Response(
                {"code": "wrong_password", "current_password": ["That’s not your current password."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.check_password(data["new_password"]):
            return Response(
                {"code": "password_unchanged", "new_password": ["Pick a password you haven’t used here."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)
        return Response(UserSerializer(user).data)


# ---------------------------------------------------------------------------
# Password reset: phone -> SMS code -> reset_token -> new password.


class PasswordResetRequestView(AuthView):
    """Always the same 200 body, whether or not the number has an account."""

    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PhoneOnlySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        # Limits are per phone for every number, so they don't reveal accounts.
        wait = send_limit_retry_after(phone)
        if not wait:
            user = User.objects.filter(phone=phone, phone_verified=True, is_active=True).first()
            if user:
                try:
                    issue_code(user, PhoneVerification.Purpose.PASSWORD_RESET)
                except OtpSendError:
                    # Logged, but not shown: a 503 here would reveal the account.
                    logger.warning("Password reset code could not be sent to %s", mask_phone(phone))
                    record_send(phone)
            else:
                record_send(phone)
            wait = settings.OTP_RESEND_COOLDOWN
        return Response({"masked_phone": mask_phone(phone), "resend_available_in": wait})


class PasswordResetVerifyView(AuthView):
    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone, code = serializer.validated_data["phone"], serializer.validated_data["code"]

        verification = latest_active_verification(phone, PhoneVerification.Purpose.PASSWORD_RESET)
        error = check_code(verification, code)
        if error:
            return error

        verification.used = True
        verification.save(update_fields=["used"])
        return Response({"reset_token": make_reset_token(verification.user)})


class PasswordResetConfirmView(AuthView):
    """Sets the new password and signs out every session. No auto-login."""

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = user_for_reset_token(data["reset_token"])
        if user is None:
            return Response(
                {"code": "reset_token_invalid", "detail": "This reset has expired. Start again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)
