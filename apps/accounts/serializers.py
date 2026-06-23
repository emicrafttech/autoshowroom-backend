from django.contrib.auth import authenticate, password_validation
from django.utils import timezone
from rest_framework import serializers

from apps.dealers.models import DealerLocation
from apps.dealers.serializers import DealerContextLocationSerializer

from .models import StaffUser
from .tokens import hash_invite_token


class AuthUserSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id")
    mustChangePassword = serializers.BooleanField(source="must_change_password")
    locationId = serializers.SerializerMethodField()

    class Meta:
        model = StaffUser
        fields = [
            "id",
            "dealerId",
            "email",
            "name",
            "role",
            "mustChangePassword",
            "locationId",
        ]

    def get_locationId(self, obj):
        location = self.context.get("active_location") or obj.preferred_location
        return str(location.id) if location else None


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.dealer:
            raise serializers.ValidationError("Dealer staff account is not configured")
        if user.dealer.operational_status == "banned":
            raise serializers.ValidationError(
                user.dealer.suspended_reason
                or "This dealer account has been permanently banned."
            )
        attrs["user"] = user
        return attrs


class RefreshSerializer(serializers.Serializer):
    refreshToken = serializers.CharField(min_length=1)


class StaffInvitationPreviewSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=16)

    def validate_token(self, value):
        token_hash = hash_invite_token(value)
        user = (
            StaffUser.objects.select_related("dealer")
            .filter(
                invite_token_hash=token_hash,
                invite_expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not user:
            raise serializers.ValidationError("Invite link is invalid or expired")
        self.context["invite_user"] = user
        return value


class AcceptStaffInvitationSerializer(StaffInvitationPreviewSerializer):
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        password_validation.validate_password(attrs["password"])
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(min_length=8, write_only=True)
    newPassword = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate(self, attrs):
        password_validation.validate_password(attrs["newPassword"], self.context["user"])
        return attrs


class SessionLocationSerializer(serializers.Serializer):
    locationId = serializers.UUIDField()

    def validate_locationId(self, value):
        user = self.context["user"]
        location = DealerLocation.objects.filter(id=value, dealer_id=user.dealer_id).first()
        if not location:
            raise serializers.ValidationError("Location not found for this dealer")
        self.context["location"] = location
        return value


class DealerConsoleContextSerializer(serializers.Serializer):
    dealerName = serializers.CharField()
    activeLocationId = serializers.UUIDField(allow_null=True)
    locations = DealerContextLocationSerializer(many=True)
