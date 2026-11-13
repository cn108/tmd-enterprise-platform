from django.urls import path

from apps.identity import views

app_name = "identity"

urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="csrf"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("mfa/setup/", views.MfaSetupView.as_view(), name="mfa-setup"),
    path("mfa/confirm/", views.MfaConfirmView.as_view(), name="mfa-confirm"),
    path("mfa/verify/", views.MfaVerifyView.as_view(), name="mfa-verify"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password-change"),
    path("password/reset/", views.PasswordResetView.as_view(), name="password-reset"),
]
