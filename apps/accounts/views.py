from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.permissions import IsDealerStaff
from apps.common.views import EnvelopeMixin
from apps.dealers.models import DealerLocation

from .models import StaffUser
from .serializers import (
    AcceptStaffInvitationSerializer,
    AuthUserSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    RefreshSerializer,
    SessionLocationSerializer,
    StaffInvitationPreviewSerializer,
)


def resolve_active_location(user: StaffUser):
    if user.preferred_location_id and user.preferred_location.dealer_id == user.dealer_id:
        return user.preferred_location
    return (
        DealerLocation.objects.filter(dealer_id=user.dealer_id, is_primary=True).first()
        or DealerLocation.objects.filter(dealer_id=user.dealer_id).first()
    )


def issue_token_pair(user: StaffUser, active_location=None) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    refresh["dealer_id"] = str(user.dealer_id) if user.dealer_id else None
    refresh["role"] = user.role
    refresh["location_id"] = str(active_location.id) if active_location else None
    return {
        "accessToken": str(refresh.access_token),
        "refreshToken": str(refresh),
    }


class LoginView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        active_location = resolve_active_location(user)
        tokens = issue_token_pair(user, active_location)
        return Response(
            {
                **tokens,
                "user": AuthUserSerializer(
                    user,
                    context={"active_location": active_location},
                ).data,
            }
        )


class RefreshView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data["refreshToken"])
        except TokenError as exc:
            raise AuthenticationFailed("Invalid refresh token") from exc

        user = get_object_or_404(StaffUser, id=refresh["user_id"], is_active=True)
        active_location = resolve_active_location(user)
        return Response(issue_token_pair(user, active_location))


class StaffInvitationPreviewView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = StaffInvitationPreviewSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        user = serializer.context["invite_user"]
        return Response(
            {
                "dealerName": user.dealer.name,
                "memberName": user.name,
                "role": user.role,
                "expiresAt": user.invite_expires_at.isoformat(),
            }
        )


class AcceptStaffInvitationView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AcceptStaffInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context["invite_user"]
        user.set_password(serializer.validated_data["password"])
        user.must_change_password = False
        user.invite_token_hash = None
        user.invite_expires_at = None
        user.save(
            update_fields=[
                "password",
                "must_change_password",
                "invite_token_hash",
                "invite_expires_at",
                "updated_at",
            ]
        )

        active_location = resolve_active_location(user)
        tokens = issue_token_pair(user, active_location)
        return Response(
            {
                **tokens,
                "user": AuthUserSerializer(
                    user,
                    context={"active_location": active_location},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def patch(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["currentPassword"]):
            raise ValidationError("Current password is incorrect")

        request.user.set_password(serializer.validated_data["newPassword"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password", "updated_at"])
        update_session_auth_hash(request, request.user)
        return Response({"ok": True})


class SessionLocationView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def patch(self, request):
        serializer = SessionLocationSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        location = serializer.context["location"]
        request.user.preferred_location = location
        request.user.save(update_fields=["preferred_location", "updated_at"])
        tokens = issue_token_pair(request.user, location)
        return Response(
            {
                **tokens,
                "user": AuthUserSerializer(
                    request.user,
                    context={"active_location": location},
                ).data,
            }
        )


