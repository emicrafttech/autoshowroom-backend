from django.urls import path

from .views import (
    AcceptStaffInvitationView,
    ChangePasswordView,
    LoginView,
    RefreshView,
    SessionLocationView,
    StaffInvitationPreviewView,
)

auth_urlpatterns = [
    path("login", LoginView.as_view(), name="auth-login"),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("password", ChangePasswordView.as_view(), name="auth-password"),
    path("session/location", SessionLocationView.as_view(), name="auth-session-location"),
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
