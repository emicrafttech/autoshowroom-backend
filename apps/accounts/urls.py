from django.urls import path

from .views import (
    AcceptStaffInvitationView,
    ChangePasswordView,
    DealerSignupPasswordView,
    DealerSignupSetupView,
    DealerSignupStartView,
    DealerSignupVerifyView,
    EmailVerificationSendView,
    EmailVerificationVerifyView,
    LoginView,
    MeView,
    RefreshView,
    SessionLocationView,
    StaffInvitationPreviewView,
)

auth_urlpatterns = [
    path("dealer-signup/start", DealerSignupStartView.as_view(), name="auth-dealer-signup-start"),
    path("dealer-signup/verify", DealerSignupVerifyView.as_view(), name="auth-dealer-signup-verify"),
    path("dealer-signup/setup", DealerSignupSetupView.as_view(), name="auth-dealer-signup-setup"),
    path("dealer-signup/password", DealerSignupPasswordView.as_view(), name="auth-dealer-signup-password"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("me", MeView.as_view(), name="auth-me"),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("password", ChangePasswordView.as_view(), name="auth-password"),
    path("session/location", SessionLocationView.as_view(), name="auth-session-location"),
    path("email-verification/send", EmailVerificationSendView.as_view(), name="auth-email-verification-send"),
    path("email-verification/verify", EmailVerificationVerifyView.as_view(), name="auth-email-verification-verify"),
]

staff_invitation_urlpatterns = [
    path(
        "preview",
        StaffInvitationPreviewView.as_view(),
        name="staff-invitation-preview",
    ),
    path(
        "accept",
        AcceptStaffInvitationView.as_view(),
        name="staff-invitation-accept",
    ),
]
