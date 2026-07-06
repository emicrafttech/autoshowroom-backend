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
    BlockedDealer,
    PriceAlert,
    SavedVehicle,
    VehicleVisit,
)
from .price_alerts import build_alert_title, infer_icon_kind


class BuyerSignInStartSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    name = serializers.CharField(
        max_length=160, required=False, allow_blank=True, allow_null=True
    )

    def create(self, validated_data):
        code = "123456" if settings.DEBUG else str(timezone.now().microsecond).zfill(6)[:6]
        otp = BuyerOtp.objects.create(
            phone=validated_data["phone"],
            name=validated_data.get("name", ""),
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
        name = (otp.name or "").strip()
        buyer, _ = Buyer.objects.get_or_create(phone=self.validated_data["phone"])
        if name and not buyer.name:
            buyer.name = name
            buyer.save(update_fields=["name"])
        return {"buyer": buyer, "token": create_buyer_token(buyer)}


class BuyerProfileSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Buyer
        fields = [
            "id",
            "phone",
            "email",
            "name",
            "bio",
            "location",
            "photoUrl",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "phone", "createdAt", "updatedAt"]
        extra_kwargs = {
            "email": {"required": False, "allow_null": True, "allow_blank": True},
            "name": {"required": False, "allow_blank": True},
            "bio": {"required": False, "allow_blank": True},
            "location": {"required": False, "allow_blank": True},
        }

    photoUrl = serializers.CharField(source="photo_url", required=False, allow_blank=True)


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
    attachmentUrl = serializers.URLField(source="attachment_url", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = BuyerMessage
        fields = ["id", "senderType", "body", "attachmentUrl", "createdAt"]


class DealerConversationVehicleSerializer(PublicVehicleSerializer):
    class Meta(PublicVehicleSerializer.Meta):
        fields = PublicVehicleSerializer.Meta.fields + ["status"]


class BuyerConversationSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    buyer = BuyerProfileSerializer(read_only=True)
    vehicle = PublicVehicleSerializer(read_only=True)
    bookingId = serializers.UUIDField(source="booking_id", read_only=True)
    lastMessageAt = serializers.DateTimeField(source="last_message_at", read_only=True)
    dealerLastReadAt = serializers.DateTimeField(source="dealer_last_read_at", read_only=True)
    buyerLastReadAt = serializers.DateTimeField(source="buyer_last_read_at", read_only=True)
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
            "dealerLastReadAt",
            "buyerLastReadAt",
            "messages",
        ]


class DealerConversationSerializer(BuyerConversationSerializer):
    vehicle = DealerConversationVehicleSerializer(read_only=True)


class OpenConversationSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True)
    attachmentUrl = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        attrs["message"] = attrs.get("message", "").strip()
        attrs["attachmentUrl"] = attrs.get("attachmentUrl", "").strip()
        return attrs


class BuyerMessageInputSerializer(serializers.Serializer):
    body = serializers.CharField(required=False, allow_blank=True)
    attachmentUrl = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        body = attrs.get("body", "").strip()
        attachment_url = attrs.get("attachmentUrl", "").strip()
        if not body and not attachment_url:
            raise serializers.ValidationError(
                "Message text or an image attachment is required."
            )
        attrs["body"] = body
        attrs["attachmentUrl"] = attachment_url
        return attrs


class PriceAlertSerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=False, allow_blank=True)
    bodyType = serializers.CharField(source="body_type", required=False, allow_blank=True)
    minYear = serializers.IntegerField(source="min_year", required=False, allow_null=True)
    maxPriceNgn = serializers.IntegerField(source="max_price_ngn", required=False, allow_null=True)
    minPriceNgn = serializers.IntegerField(source="min_price_ngn", required=False, allow_null=True)
    pushNotify = serializers.BooleanField(source="push_notify", required=False)
    iconKind = serializers.CharField(source="icon_kind", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = PriceAlert
        fields = [
            "id",
            "title",
            "bodyType",
            "make",
            "model",
            "minYear",
            "maxPriceNgn",
            "minPriceNgn",
            "area",
            "pushNotify",
            "iconKind",
            "active",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "createdAt", "updatedAt"]

    def validate(self, attrs):
        criteria = [
            attrs.get("title", "").strip(),
            attrs.get("body_type", "").strip(),
            attrs.get("make", "").strip(),
            attrs.get("model", "").strip(),
            attrs.get("area", "").strip(),
            attrs.get("min_year"),
            attrs.get("min_price_ngn"),
            attrs.get("max_price_ngn"),
        ]
        if not any(value for value in criteria):
            raise serializers.ValidationError(
                "Provide at least one alert filter such as body type, price, or location."
            )
        min_price = attrs.get("min_price_ngn")
        max_price = attrs.get("max_price_ngn")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise serializers.ValidationError(
                {"minPriceNgn": "Minimum price cannot exceed maximum price."}
            )
        return attrs

    def create(self, validated_data):
        buyer = self.context["buyer"]
        validated_data.setdefault(
            "icon_kind",
            infer_icon_kind(
                body_type=validated_data.get("body_type", ""),
                make=validated_data.get("make", ""),
                min_year=validated_data.get("min_year"),
                min_price_ngn=validated_data.get("min_price_ngn"),
                max_price_ngn=validated_data.get("max_price_ngn"),
            ),
        )
        if not validated_data.get("title"):
            draft = PriceAlert(buyer=buyer, **validated_data)
            validated_data["title"] = build_alert_title(draft)
        return PriceAlert.objects.create(buyer=buyer, **validated_data)


class PriceAlertUpdateSerializer(serializers.ModelSerializer):
    iconKind = serializers.CharField(source="icon_kind", required=False)

    class Meta:
        model = PriceAlert
        fields = ["active", "title", "iconKind"]


class BlockedDealerSerializer(serializers.ModelSerializer):
    dealerSlug = serializers.CharField(source="dealer.slug", read_only=True)
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    dealerArea = serializers.CharField(source="dealer.area", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = BlockedDealer
        fields = ["id", "dealerSlug", "dealerName", "dealerArea", "createdAt"]
