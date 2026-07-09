from rest_framework import serializers

from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle

from .models import AnalyticsEvent, GenericUploadRequest, Lead, LeadNote, NotifyMeRequest


class LeadNoteSerializer(serializers.ModelSerializer):
    authorName = serializers.CharField(source="author.name", read_only=True)
    sharedWithTeam = serializers.BooleanField(source="shared_with_team", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = LeadNote
        fields = ["id", "lead", "authorName", "body", "sharedWithTeam", "createdAt"]
        read_only_fields = ["id", "lead", "authorName", "createdAt"]


class LeadSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", required=False, write_only=True)
    dealerSlug = serializers.SlugField(required=False, write_only=True)
    locationId = serializers.UUIDField(source="location_id", required=False, allow_null=True)
    vehicleId = serializers.UUIDField(source="vehicle_id", required=False, allow_null=True)
    vehicleTitle = serializers.SerializerMethodField()
    followUpAt = serializers.DateTimeField(source="follow_up_at", required=False, allow_null=True)
    notes = LeadNoteSerializer(many=True, read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "dealerId",
            "dealerSlug",
            "locationId",
            "vehicleId",
            "vehicleTitle",
            "name",
            "phone",
            "email",
            "message",
            "source",
            "stage",
            "followUpAt",
            "notes",
            "createdAt",
        ]
        read_only_fields = ["id", "createdAt"]
        extra_kwargs = {
            "email": {"required": False, "allow_null": True, "allow_blank": True},
            "message": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def get_vehicleTitle(self, obj):
        if not obj.vehicle_id:
            return None
        return f"{obj.vehicle.year} {obj.vehicle.make} {obj.vehicle.model}"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance:
            return attrs
        dealer_slug = attrs.pop("dealerSlug", None)
        vehicle_id = attrs.get("vehicle_id")
        dealer_id = attrs.get("dealer_id")
        location_id = attrs.get("location_id")

        vehicle = None
        if vehicle_id:
            vehicle = Vehicle.objects.filter(
                id=vehicle_id,
                status=Vehicle.Status.AVAILABLE,
                listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
                feed_ready=True,
            ).first()
            if not vehicle:
                raise serializers.ValidationError({"vehicleId": "Public vehicle not found."})
            attrs["vehicle"] = vehicle
            attrs["dealer"] = vehicle.dealer
            attrs["location"] = vehicle.location
            attrs.pop("vehicle_id", None)
            attrs.pop("dealer_id", None)
            attrs.pop("location_id", None)
            return attrs

        dealer = None
        if dealer_id:
            dealer = Dealer.objects.filter(id=dealer_id).first()
        elif dealer_slug:
            dealer = Dealer.objects.filter(slug=dealer_slug).first()
        if not dealer:
            raise serializers.ValidationError("A vehicle or dealer is required.")

        attrs["dealer"] = dealer
        attrs.pop("dealer_id", None)
        if location_id:
            location = DealerLocation.objects.filter(id=location_id, dealer=dealer).first()
            if not location:
                raise serializers.ValidationError({"locationId": "Location not found for dealer."})
            attrs["location"] = location
            attrs.pop("location_id", None)
        return attrs


class NotifyMeRequestSerializer(serializers.ModelSerializer):
    minYear = serializers.IntegerField(source="min_year", required=False, allow_null=True)
    maxPriceNgn = serializers.IntegerField(source="max_price_ngn", required=False, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = NotifyMeRequest
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "make",
            "model",
            "minYear",
            "maxPriceNgn",
            "area",
            "createdAt",
        ]
        read_only_fields = ["id", "createdAt"]
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_null": True, "allow_blank": True},
            "make": {"required": False, "allow_blank": True},
            "model": {"required": False, "allow_blank": True},
            "area": {"required": False, "allow_blank": True},
        }


class AnalyticsEventSerializer(serializers.ModelSerializer):
    anonymousId = serializers.CharField(source="anonymous_id", required=False, allow_blank=True)
    buyerId = serializers.UUIDField(source="buyer_id", required=False, allow_null=True)
    vehicleId = serializers.UUIDField(source="vehicle_id", required=False, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AnalyticsEvent
        fields = ["id", "name", "anonymousId", "buyerId", "vehicleId", "payload", "createdAt"]
        read_only_fields = ["id", "createdAt"]


class GenericUploadRequestSerializer(serializers.ModelSerializer):
    fileName = serializers.CharField(source="file_name")
    contentType = serializers.CharField(source="content_type")
    fileSize = serializers.IntegerField(source="file_size", required=False, allow_null=True)
    uploadUrl = serializers.CharField(read_only=True)
    publicUrl = serializers.URLField(source="public_url", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = GenericUploadRequest
        fields = [
            "id",
            "purpose",
            "fileName",
            "contentType",
            "fileSize",
            "uploadUrl",
            "publicUrl",
            "createdAt",
        ]
        read_only_fields = ["id", "uploadUrl", "publicUrl", "createdAt"]
