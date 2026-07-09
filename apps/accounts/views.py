from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.client_platform import dealer_refresh_lifetime, is_mobile_client
from apps.common.permissions import IsActiveDealerStaff, IsDealerStaff
from apps.common.views import EnvelopeMixin
from apps.dealers.models import Dealer, DealerLocation

from .models import StaffUser
from .serializers import (
    AcceptStaffInvitationSerializer,
    AuthUserSerializer,
    ChangePasswordSerializer,
    DealerSignupPasswordSerializer,
    DealerSignupSetupSerializer,
    DealerSignupStartSerializer,
    DealerSignupVerifySerializer,
    EmailVerificationSendSerializer,
    EmailVerificationVerifySerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    SessionLocationSerializer,
    StaffInvitationPreviewSerializer,
)
from apps.notifications.email_verification import issue_dealer_email_verification
from .tokens import generate_invite_token, hash_invite_token, password_reset_expiry


def resolve_active_location(user: StaffUser):
    if user.preferred_location_id and user.preferred_location.dealer_id == user.dealer_id:
        return user.preferred_location
    return (
        DealerLocation.objects.filter(dealer_id=user.dealer_id, is_primary=True).first()
        or DealerLocation.objects.filter(dealer_id=user.dealer_id).first()
    )


def issue_token_pair(
    user: StaffUser,
    active_location=None,
    *,
    mobile: bool = False,
) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    refresh.set_exp(lifetime=dealer_refresh_lifetime(mobile=mobile))
    refresh["dealer_id"] = str(user.dealer_id) if user.dealer_id else None
    refresh["role"] = user.role
    refresh["location_id"] = str(active_location.id) if active_location else None
    return {
        "accessToken": str(refresh.access_token),
        "refreshToken": str(refresh),
    }


def _issue_token_pair_for_request(request, user: StaffUser, active_location=None):
    return issue_token_pair(
        user,
        active_location,
        mobile=is_mobile_client(request),
    )


class LoginView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        active_location = resolve_active_location(user)
        tokens = _issue_token_pair_for_request(request, user, active_location)
        return Response(
            {
                **tokens,
                "user": AuthUserSerializer(
                    user,
                    context={"active_location": active_location},
                ).data,
            }
        )


class DealerSignupStartView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DealerSignupStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.save()
        response = {
            "phone": otp.phone,
            "expiresAt": otp.expires_at.isoformat(),
        }
        if settings.DEALER_SIGNUP_EXPOSE_OTP:
            response["devCode"] = otp.code
        return Response(response, status=status.HTTP_201_CREATED)


class DealerSignupVerifyView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DealerSignupVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        active_location = resolve_active_location(user)
        tokens = _issue_token_pair_for_request(request, user, active_location)
        return Response(
            {
                **tokens,
                "user": AuthUserSerializer(
                    user,
                    context={"active_location": active_location},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class DealerSignupSetupView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def patch(self, request):
        serializer = DealerSignupSetupSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        dev_token = None
        if not user.email_verified_at:
            dev_token = issue_dealer_email_verification(user)
        active_location = resolve_active_location(user)
        tokens = _issue_token_pair_for_request(request, user, active_location)
        response = {
            **tokens,
            "user": AuthUserSerializer(
                user,
                context={"active_location": active_location},
            ).data,
        }
        if settings.DEBUG and dev_token:
            response["devToken"] = dev_token
        return Response(response)


class DealerSignupPasswordView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def patch(self, request):
        serializer = DealerSignupPasswordSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"ok": True})


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
        return Response(_issue_token_pair_for_request(request, user, active_location))


class PasswordResetRequestView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = (
            StaffUser.objects.select_related("dealer")
            .filter(
                email=serializer.validated_data["email"],
                dealer__isnull=False,
                is_active=True,
            )
            .first()
        )
        dev_token = None
        if user:
            token = generate_invite_token()
            user.password_reset_token_hash = hash_invite_token(token)
            user.password_reset_expires_at = password_reset_expiry()
            user.save(
                update_fields=[
                    "password_reset_token_hash",
                    "password_reset_expires_at",
                    "updated_at",
                ]
            )
            from apps.notifications.services import notify_dealer_password_reset

            notify_dealer_password_reset(user, token)
            dev_token = token
        response = {"ok": True}
        if settings.DEBUG and dev_token:
            response["devToken"] = dev_token
        return Response(response)


class PasswordResetConfirmView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context["reset_user"]
        user.set_password(serializer.validated_data["password"])
        user.must_change_password = False
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        user.password_changed_at = timezone.now()
        user.save(
            update_fields=[
                "password",
                "must_change_password",
                "password_reset_token_hash",
                "password_reset_expires_at",
                "password_changed_at",
                "updated_at",
            ]
        )
        active_location = resolve_active_location(user)
        tokens = _issue_token_pair_for_request(request, user, active_location)
        return Response(
            {
                **tokens,
                "user": AuthUserSerializer(
                    user,
                    context={"active_location": active_location},
                ).data,
            }
        )


class MeView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def get(self, request):
        user = request.user
        return Response(
            AuthUserSerializer(
                user,
                context={"active_location": resolve_active_location(user)},
            ).data
        )


class EmailVerificationSendView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def post(self, request):
        serializer = EmailVerificationSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if user.email_verified_at:
            return Response(
                {
                    "user": AuthUserSerializer(
                        user,
                        context={"active_location": resolve_active_location(user)},
                    ).data,
                    "sent": False,
                }
            )
        token = issue_dealer_email_verification(user)
        response = {
            "user": AuthUserSerializer(
                user,
                context={"active_location": resolve_active_location(user)},
            ).data,
            "sent": True,
        }
        if settings.DEBUG:
            response["devToken"] = token
        return Response(response)


class EmailVerificationVerifyView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerificationVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context["verification_user"]
        user.email_verified_at = timezone.now()
        user.email_verification_token_hash = None
        user.email_verification_required_at = None
        user.save(
            update_fields=[
                "email_verified_at",
                "email_verification_token_hash",
                "email_verification_required_at",
                "updated_at",
            ]
        )
        dealer = user.dealer
        if (
            dealer
            and dealer.operational_status == Dealer.OperationalStatus.SUSPENDED
            and dealer.suspended_reason == "Email verification overdue."
        ):
            dealer.operational_status = Dealer.OperationalStatus.ACTIVE
            dealer.suspended_at = None
            dealer.suspended_reason = None
            dealer.save(update_fields=["operational_status", "suspended_at", "suspended_reason", "updated_at"])
        return Response({"ok": True})


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
        tokens = _issue_token_pair_for_request(request, user, active_location)
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
    permission_classes = [IsActiveDealerStaff]

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
    permission_classes = [IsActiveDealerStaff]

    def patch(self, request):
        serializer = SessionLocationSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        location = serializer.context["location"]
        request.user.preferred_location = location
        request.user.save(update_fields=["preferred_location", "updated_at"])
        tokens = _issue_token_pair_for_request(request, request.user, location)
        return Response(
            {
                **tokens,
                "user": AuthUserSerializer(
                    request.user,
                    context={"active_location": location},
                ).data,
            }
        )


