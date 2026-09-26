from django.urls import path

from .views import (
    CsrfView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    RegisterView,
    ResendOtpView,
    VerifyOtpView,
)

# Mounted at /api/auth/.
urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOtpView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOtpView.as_view(), name="resend-otp"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="password-reset-verify"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
