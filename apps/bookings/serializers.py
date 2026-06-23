from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.buyers.auth import get_buyer_from_request
from apps.dealers.models import DealerLocation
from apps.marketplace.views import public_vehicle_queryset

from .models import Appointment, Booking


class BookingSerializer(serializers.ModelSerializer):
    vehicleId = serializers.UUIDField(source="vehicle_id", write_only=True)
    buyerName = serializers.CharField(source="buyer_name", required=False, allow_blank=True)
    buyerPhone = serializers.CharField(source="buyer_phone", required=False, allow_blank=True)
    buyerEmail = serializers.EmailField(source="buyer_email", required=False, allow_null=True, allow_blank=True)
    scheduledAt = serializers.DateTimeField(source="scheduled_at")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "vehicleId",
            "buyerName",
            "buyerPhone",
            "buyerEmail",
            "scheduledAt",
            "status",
            "notes",
            "createdAt",
        ]
        read_only_fields = ["id", "status", "createdAt"]
        extra_kwargs = {"notes": {"required": False, "allow_null": True, "allow_blank": True}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        vehicle = public_vehicle_queryset().filter(id=attrs["vehicle_id"]).first()
        if not vehicle:
            raise serializers.ValidationError({"vehicleId": "Public vehicle not found."})
        return attrs

    def create(self, validated_data):
        vehicle = public_vehicle_queryset().get(id=validated_data.pop("vehicle_id"))
        request = self.context.get("request")
        buyer = get_buyer_from_request(request)
        buyer_name = validated_data.pop("buyer_name", "") or buyer.name or buyer.phone
        buyer_phone = validated_data.pop("buyer_phone", "") or buyer.phone
        buyer_email = validated_data.pop("buyer_email", None) or buyer.email
        booking = Booking.objects.create(
            **validated_data,
            vehicle=vehicle,
            dealer=vehicle.dealer,
            location=vehicle.location,
            buyer=buyer,
            buyer_name=buyer_name,
            buyer_phone=buyer_phone,
            buyer_email=buyer_email,
            status=Booking.Status.CONFIRMED,
        )
        Appointment.objects.get_or_create(
            booking=booking,
            defaults={
                "dealer": booking.dealer,
                "location": booking.location,
                "vehicle": booking.vehicle,
                "title": f"Inspection for {booking.vehicle}",
                "scheduled_at": booking.scheduled_at,
                "notes": booking.notes,
            },
        )
        return booking


class BookingSummarySerializer(serializers.Serializer):
    vehicleId = serializers.UUIDField()
    requestedAt = serializers.DateTimeField(required=False)


class AppointmentSerializer(serializers.ModelSerializer):
    bookingId = serializers.UUIDField(source="booking_id", required=False, allow_null=True)
    locationId = serializers.UUIDField(source="location_id", required=False, allow_null=True)
    vehicleId = serializers.UUIDField(source="vehicle_id", required=False, allow_null=True)
    scheduledAt = serializers.DateTimeField(source="scheduled_at")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "bookingId",
            "locationId",
            "vehicleId",
            "title",
            "scheduledAt",
            "notes",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "createdAt", "updatedAt"]
        extra_kwargs = {"notes": {"required": False, "allow_null": True, "allow_blank": True}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context["request"].user
        location_id = attrs.get("location_id")
        if location_id and not DealerLocation.objects.filter(id=location_id, dealer_id=user.dealer_id).exists():
            raise serializers.ValidationError({"locationId": "Location not found for dealer."})
        return attrs


def booking_summary_for_vehicle(vehicle):
    now = timezone.now()
    booked = Booking.objects.filter(
        vehicle=vehicle,
        scheduled_at__gte=now,
        status=Booking.Status.CONFIRMED,
    ).count()
    return {
        "vehicleId": str(vehicle.id),
        "dealerId": str(vehicle.dealer_id),
        "locationId": str(vehicle.location_id),
        "nextAvailableAt": (now + timedelta(days=1)).isoformat(),
        "openBookingCount": booked,
    }
