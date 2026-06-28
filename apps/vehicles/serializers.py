from django.utils.text import slugify
from rest_framework import serializers

from apps.dealers.models import DealerLocation

from .catalog import normalize_make
from .models import Vehicle, VehicleMedia, VehicleReviewIssue


def unique_vehicle_slug_for_dealer(dealer_id, base_slug: str) -> str:
    slug = base_slug[:160] or "vehicle"
    candidate = slug
    suffix = 2

    while Vehicle.objects.filter(dealer_id=dealer_id, slug=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{slug[:160 - len(suffix_text)]}{suffix_text}"
        suffix += 1

    return candidate


class VehicleMediaSerializer(serializers.ModelSerializer):
    vehicleId = serializers.UUIDField(source="vehicle_id", read_only=True)
    thumbnailUrl = serializers.URLField(
        source="thumbnail_url",
        required=False,
        allow_null=True,
    )
    contentType = serializers.CharField(source="content_type", read_only=True)
    fileName = serializers.CharField(source="file_name", read_only=True)
    fileSize = serializers.IntegerField(source="file_size", read_only=True)
    sortOrder = serializers.IntegerField(source="sort_order")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = VehicleMedia
        fields = [
            "id",
            "vehicleId",
            "kind",
            "url",
            "thumbnailUrl",
            "contentType",
            "fileName",
            "fileSize",
            "status",
            "sortOrder",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
            "vehicleId",
            "url",
            "contentType",
            "fileName",
            "fileSize",
            "status",
            "createdAt",
            "updatedAt",
        ]


class VehicleSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    locationId = serializers.UUIDField(source="location_id", required=False)
    coverMediaId = serializers.UUIDField(
        source="cover_media_id",
        required=False,
        allow_null=True,
        write_only=True,
    )
    coverMedia = VehicleMediaSerializer(source="cover_media", read_only=True)
    media = VehicleMediaSerializer(source="media_items", many=True, read_only=True)
    priceNgn = serializers.IntegerField(source="price_ngn")
    mileageKm = serializers.IntegerField(source="mileage_km")
    bodyType = serializers.ChoiceField(source="body_type", choices=Vehicle.BodyType.choices)
    conditionGrade = serializers.ChoiceField(
        source="condition_grade",
        choices=Vehicle.ConditionGrade.choices,
    )
    chassisNumber = serializers.CharField(
        source="chassis_number",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    importType = serializers.ChoiceField(
        source="import_type",
        choices=Vehicle.ImportType.choices,
        required=False,
        allow_null=True,
    )
    yearOfManufacture = serializers.IntegerField(
        source="year_of_manufacture",
        required=False,
        allow_null=True,
    )
    engineCapacityCc = serializers.IntegerField(
        source="engine_capacity_cc",
        required=False,
        allow_null=True,
    )
    registrationPlate = serializers.CharField(
        source="registration_plate",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    registrationState = serializers.CharField(
        source="registration_state",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    registrationLga = serializers.CharField(
        source="registration_lga",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    customsDutyStatus = serializers.ChoiceField(
        source="customs_duty_status",
        choices=Vehicle.CustomsDutyStatus.choices,
        required=False,
    )
    customsReference = serializers.CharField(
        source="customs_reference",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    customsClearedAt = serializers.DateTimeField(
        source="customs_cleared_at",
        required=False,
        allow_null=True,
    )
    bodyHistory = serializers.ChoiceField(
        source="body_history",
        choices=Vehicle.BodyHistory.choices,
        required=False,
    )
    papersStatus = serializers.ChoiceField(
        source="papers_status",
        choices=Vehicle.PapersStatus.choices,
        required=False,
    )
    dutyPaidClaim = serializers.ChoiceField(
        source="duty_paid_claim",
        choices=Vehicle.ClaimVerificationLevel.choices,
        required=False,
    )
    dutyPaidVerifiedAt = serializers.DateTimeField(
        source="duty_paid_verified_at",
        read_only=True,
    )
    listingVerificationStatus = serializers.CharField(
        source="listing_verification_status",
        read_only=True,
    )
    publishedAt = serializers.DateTimeField(source="published_at", read_only=True)
    dealerAttestationAt = serializers.DateTimeField(
        source="dealer_attestation_at",
        read_only=True,
    )
    listingApprovedAt = serializers.DateTimeField(
        source="listing_approved_at",
        read_only=True,
    )
    listingRejectedReason = serializers.CharField(
        source="listing_rejected_reason",
        read_only=True,
    )
    reviewIssues = serializers.SerializerMethodField()
    openReviewIssueCount = serializers.SerializerMethodField()
    feedReady = serializers.BooleanField(source="feed_ready", read_only=True)
    refreshedAt = serializers.DateTimeField(source="refreshed_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "dealerId",
            "dealerName",
            "locationId",
            "coverMediaId",
            "coverMedia",
            "slug",
            "make",
            "model",
            "year",
            "trim",
            "priceNgn",
            "mileageKm",
            "transmission",
            "fuel",
            "colour",
            "bodyType",
            "drivetrain",
            "conditionGrade",
            "negotiable",
            "notes",
            "vin",
            "chassisNumber",
            "importType",
            "yearOfManufacture",
            "engineCapacityCc",
            "registrationPlate",
            "registrationState",
            "registrationLga",
            "customsDutyStatus",
            "customsReference",
            "customsClearedAt",
            "bodyHistory",
            "papersStatus",
            "dutyPaidClaim",
            "dutyPaidVerifiedAt",
            "status",
            "listingVerificationStatus",
            "publishedAt",
            "dealerAttestationAt",
            "listingApprovedAt",
            "listingRejectedReason",
            "reviewIssues",
            "openReviewIssueCount",
            "feedReady",
            "refreshedAt",
            "createdAt",
            "updatedAt",
            "media",
        ]
        extra_kwargs = {
            "slug": {"required": False},
            "notes": {"required": False, "allow_null": True, "allow_blank": True},
            "vin": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def get_reviewIssues(self, obj):
        issues = obj.review_issues.all()
        return VehicleReviewIssueSerializer(issues, many=True, context=self.context).data

    def get_openReviewIssueCount(self, obj):
        return obj.review_issues.filter(status=VehicleReviewIssue.Status.OPEN).count()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context["request"]
        dealer_id = request.user.dealer_id
        location_id = attrs.get("location_id")
        cover_media_id = attrs.get("cover_media_id")

        if not self.instance and not location_id:
            location = request.user.preferred_location
            if not location or location.dealer_id != dealer_id:
                location = DealerLocation.objects.filter(
                    dealer_id=dealer_id,
                    is_primary=True,
                ).first()
            if location is None:
                raise serializers.ValidationError(
                    {"locationId": "A dealer location is required."}
                )
            attrs["location"] = location
        elif location_id:
            location = DealerLocation.objects.filter(
                id=location_id,
                dealer_id=dealer_id,
            ).first()
            if not location:
                raise serializers.ValidationError(
                    {"locationId": "Location not found for this dealer."}
                )
            attrs["location"] = location
            attrs.pop("location_id", None)

        if cover_media_id is not None:
            cover_media = VehicleMedia.objects.filter(
                id=cover_media_id,
                vehicle__dealer_id=dealer_id,
            ).first()
            if not cover_media:
                raise serializers.ValidationError(
                    {"coverMediaId": "Media item not found for this dealer."}
                )
            if self.instance and cover_media.vehicle_id != self.instance.id:
                raise serializers.ValidationError(
                    {"coverMediaId": "Cover media must belong to this vehicle."}
                )
            if not self.instance:
                raise serializers.ValidationError(
                    {"coverMediaId": "Set cover media after vehicle creation."}
                )
            attrs["cover_media"] = cover_media
            attrs.pop("cover_media_id", None)

        if "make" in attrs:
            attrs["make"] = normalize_make(attrs["make"])
        if "slug" not in attrs and not self.instance:
            base_slug = slugify(
                f"{attrs.get('year')} {attrs.get('make')} {attrs.get('model')} {attrs.get('trim')}"
            )
            attrs["slug"] = unique_vehicle_slug_for_dealer(dealer_id, base_slug)
        return attrs

    def update(self, instance, validated_data):
        changed_fields = {
            field
            for field, value in validated_data.items()
            if field not in {"cover_media"} and getattr(instance, field, None) != value
        }
        instance = super().update(instance, validated_data)
        if (
            changed_fields
            and instance.listing_verification_status
            == Vehicle.ListingVerificationStatus.REJECTED
            and instance.review_issues.filter(
                status=VehicleReviewIssue.Status.RESOLVED,
            ).exists()
        ):
            instance.listing_verification_status = Vehicle.ListingVerificationStatus.PENDING_REVIEW
            instance.feed_ready = False
            instance.save(update_fields=["listing_verification_status", "feed_ready", "updated_at"])
            from apps.notifications.platform_notifications import notify_listing_review_submitted

            notify_listing_review_submitted(instance)
        return instance


class VehicleStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Vehicle.Status.choices)
    attestationAccepted = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if (
            attrs["status"] == Vehicle.Status.AVAILABLE
            and attrs.get("attestationAccepted") is not True
        ):
            raise serializers.ValidationError(
                {
                    "attestationAccepted": (
                        "Confirm that listing information is accurate before going available."
                    )
                }
            )
        return attrs


class VehicleReviewIssueInputSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=VehicleReviewIssue.Category.choices,
        default=VehicleReviewIssue.Category.OTHER,
    )
    message = serializers.CharField()

    def validate_message(self, value):
        message = value.strip()
        if not message:
            raise serializers.ValidationError("Issue message is required.")
        return message


class VehicleReviewDecisionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
    issues = VehicleReviewIssueInputSerializer(many=True, required=False)

    def validate_reason(self, value):
        return value.strip()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("reason") and not attrs.get("issues"):
            raise serializers.ValidationError("Provide a review reason or at least one issue.")
        return attrs


class VehicleReviewIssueSerializer(serializers.ModelSerializer):
    vehicleId = serializers.UUIDField(source="vehicle_id", read_only=True)
    reviewerId = serializers.UUIDField(source="reviewer_id", read_only=True)
    reviewerName = serializers.CharField(source="reviewer.name", read_only=True)
    dealerResponse = serializers.CharField(source="dealer_response", read_only=True)
    vehicleSnapshot = serializers.JSONField(source="vehicle_snapshot", read_only=True)
    vehicleChanges = serializers.SerializerMethodField()
    resolvedAt = serializers.DateTimeField(source="resolved_at", read_only=True)
    reviewedAt = serializers.DateTimeField(source="reviewed_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = VehicleReviewIssue
        fields = [
            "id",
            "vehicleId",
            "reviewerId",
            "reviewerName",
            "status",
            "category",
            "message",
            "dealerResponse",
            "vehicleSnapshot",
            "vehicleChanges",
            "resolvedAt",
            "reviewedAt",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = fields

    def get_vehicleChanges(self, obj):
        snapshot = obj.vehicle_snapshot or {}
        vehicle = obj.vehicle
        current = {
            "make": vehicle.make,
            "model": vehicle.model,
            "year": vehicle.year,
            "trim": vehicle.trim,
            "priceNgn": vehicle.price_ngn,
            "mileageKm": vehicle.mileage_km,
            "status": vehicle.status,
            "listingVerificationStatus": vehicle.listing_verification_status,
            "mediaCount": vehicle.media_items.count(),
            "updatedAt": vehicle.updated_at.isoformat() if vehicle.updated_at else None,
        }
        return {
            key: {"before": snapshot.get(key), "after": value}
            for key, value in current.items()
            if snapshot.get(key) != value
        }


class VehicleReviewIssueResolveSerializer(serializers.Serializer):
    dealerResponse = serializers.CharField()

    def validate_dealerResponse(self, value):
        response = value.strip()
        if not response:
            raise serializers.ValidationError("Add a response explaining what was fixed.")
        return response


class VehicleMediaUploadItemSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=VehicleMedia.Kind.choices)
    contentType = serializers.CharField(max_length=120)
    fileName = serializers.CharField(max_length=255)
    fileSize = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    sortOrder = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        content_type = attrs["contentType"].lower()
        kind = attrs["kind"]
        if kind == VehicleMedia.Kind.PHOTO and not content_type.startswith("image/"):
            raise serializers.ValidationError({"contentType": "Photo uploads must use an image content type."})
        if kind == VehicleMedia.Kind.VIDEO and not content_type.startswith("video/"):
            raise serializers.ValidationError({"contentType": "Video uploads must use a video content type."})
        file_size = attrs.get("fileSize")
        if file_size and file_size > 100 * 1024 * 1024:
            raise serializers.ValidationError({"fileSize": "Uploads must be 100MB or smaller."})
        return attrs


class VehicleMediaUploadSessionSerializer(serializers.Serializer):
    items = VehicleMediaUploadItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one media item is required.")
        if len(value) > 20:
            raise serializers.ValidationError("Upload at most 20 media items at once.")
        return value


class VehicleMediaCompleteSerializer(serializers.Serializer):
    thumbnailUrl = serializers.URLField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[VehicleMedia.Status.UPLOADED, VehicleMedia.Status.READY],
        required=False,
    )
