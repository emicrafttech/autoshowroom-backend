from rest_framework import serializers

from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle, VehicleMedia


class PublicMediaSerializer(serializers.ModelSerializer):
    thumbnailUrl = serializers.URLField(source="thumbnail_url", read_only=True)
    sortOrder = serializers.IntegerField(source="sort_order", read_only=True)

    class Meta:
        model = VehicleMedia
        fields = ["id", "kind", "url", "thumbnailUrl", "status", "sortOrder"]


class PublicDealerSummarySerializer(serializers.ModelSerializer):
    verifiedBadge = serializers.BooleanField(source="verified_badge", read_only=True)
    logoUrl = serializers.URLField(source="logo_url", read_only=True)

    class Meta:
        model = Dealer
        fields = ["id", "slug", "name", "area", "verifiedBadge", "logoUrl"]


class PublicLocationSerializer(serializers.ModelSerializer):
    dealer = PublicDealerSummarySerializer(read_only=True)
    citySlug = serializers.SlugField(source="city_slug", read_only=True)
    districtSlug = serializers.SlugField(source="district_slug", read_only=True)

    class Meta:
        model = DealerLocation
        fields = [
            "id",
            "dealer",
            "name",
            "area",
            "citySlug",
            "districtSlug",
            "latitude",
            "longitude",
        ]


class PublicVehicleSerializer(serializers.ModelSerializer):
    dealer = PublicDealerSummarySerializer(read_only=True)
    location = PublicLocationSerializer(read_only=True)
    coverMedia = PublicMediaSerializer(source="cover_media", read_only=True)
    media = PublicMediaSerializer(source="media_items", many=True, read_only=True)
    priceNgn = serializers.IntegerField(source="price_ngn", read_only=True)
    mileageKm = serializers.IntegerField(source="mileage_km", read_only=True)
    bodyType = serializers.CharField(source="body_type", read_only=True)
    conditionGrade = serializers.CharField(source="condition_grade", read_only=True)
    publishedAt = serializers.DateTimeField(source="published_at", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "slug",
            "dealer",
            "location",
            "coverMedia",
            "media",
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
            "conditionGrade",
            "negotiable",
            "notes",
            "publishedAt",
        ]


class PublicDealerDetailSerializer(PublicDealerSummarySerializer):
    locations = PublicLocationSerializer(many=True, read_only=True)

    class Meta(PublicDealerSummarySerializer.Meta):
        fields = PublicDealerSummarySerializer.Meta.fields + [
            "description",
            "phone",
            "whatsapp",
            "hours",
            "locations",
        ]
