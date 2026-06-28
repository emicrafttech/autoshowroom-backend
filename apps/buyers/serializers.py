from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.marketplace.serializers import PublicVehicleSerializer
from apps.marketplace.views import public_vehicle_queryset

from .auth import create_buyer_token
from .models import (
    Buyer,
    BuyerConversation,
    BuyerMessage,
    BuyerOtp,
    SavedVehicle,
    VehicleVisit,
)


class BuyerSignInStartSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)

    def create(self, validated_data):
        code = "123456" if settings.DEBUG else str(timezone.now().microsecond).zfill(6)[:6]
        otp = BuyerOtp.objects.create(
            phone=validated_data["phone"],
            code=code,
            expires_at=timezone.now() + timedelta(minutes=settings.OTP_CODE_TTL_MINUTES),
        )
        return otp


class BuyerSignInVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.CharField(max_length=8)

    def validate(self, attrs):
        otp = BuyerOtp.objects.filter(
            phone=attrs["phone"],
            code=attrs["code"],
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()
        if not otp:
            raise serializers.ValidationError("Invalid or expired code.")
        attrs["otp"] = otp
        return attrs

    def save(self, **kwargs):
        otp = self.validated_data["otp"]
        otp.consumed_at = timezone.now()
        otp.save(update_fields=["consumed_at"])
        buyer, _ = Buyer.objects.get_or_create(phone=self.validated_data["phone"])
        return {"buyer": buyer, "token": create_buyer_token(buyer)}


class BuyerProfileSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Buyer
        fields = ["id", "phone", "email", "name", "createdAt", "updatedAt"]
        read_only_fields = ["id", "phone", "createdAt", "updatedAt"]
        extra_kwargs = {
            "email": {"required": False, "allow_null": True, "allow_blank": True},
            "name": {"required": False, "allow_blank": True},
        }


class SavedVehicleSerializer(serializers.ModelSerializer):
    vehicle = PublicVehicleSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = SavedVehicle
        fields = ["vehicle", "createdAt"]


class VehicleVisitSerializer(serializers.ModelSerializer):
    vehicle = PublicVehicleSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = VehicleVisit
        fields = ["vehicle", "createdAt"]


def get_public_vehicle_or_error(vehicle_id):
    vehicle = public_vehicle_queryset().filter(id=vehicle_id).first()
    if not vehicle:
        raise serializers.ValidationError("Public vehicle not found.")
    return vehicle


class BuyerMessageSerializer(serializers.ModelSerializer):
    senderType = serializers.CharField(source="sender_type", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = BuyerMessage
        fields = ["id", "senderType", "body", "createdAt"]


class DealerConversationVehicleSerializer(PublicVehicleSerializer):
    class Meta(PublicVehicleSerializer.Meta):
        fields = PublicVehicleSerializer.Meta.fields + ["status"]


class BuyerConversationSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    buyer = BuyerProfileSerializer(read_only=True)
    vehicle = PublicVehicleSerializer(read_only=True)
    bookingId = serializers.UUIDField(source="booking_id", read_only=True)
    lastMessageAt = serializers.DateTimeField(source="last_message_at", read_only=True)
    messages = BuyerMessageSerializer(many=True, read_only=True)

    class Meta:
        model = BuyerConversation
        fields = [
            "id",
            "dealerId",
            "buyer",
            "vehicle",
            "bookingId",
            "lastMessageAt",
            "messages",
        ]


class DealerConversationSerializer(BuyerConversationSerializer):
    vehicle = DealerConversationVehicleSerializer(read_only=True)


class OpenConversationSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True)
