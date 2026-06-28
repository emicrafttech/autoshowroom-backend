from rest_framework import serializers

from apps.accounts.models import StaffUser
from apps.accounts.tokens import generate_invite_token, hash_invite_token, invite_expiry

from .models import Dealer, DealerLocation, DealerVerificationDocument


class DealerLocationSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    dealer = serializers.SerializerMethodField()
    citySlug = serializers.SlugField(source="city_slug", required=False, default="abuja")
    districtSlug = serializers.SlugField(
        source="district_slug",
        required=False,
        allow_null=True,
    )
    isPrimary = serializers.BooleanField(source="is_primary", read_only=True)
    premisesVerificationStatus = serializers.CharField(
        source="premises_verification_status",
        read_only=True,
    )
    premisesVerifiedAt = serializers.DateTimeField(
        source="premises_verified_at",
        read_only=True,
    )
    premisesRejectedAt = serializers.DateTimeField(
        source="premises_rejected_at",
        read_only=True,
    )
    premisesRejectionReason = serializers.CharField(
        source="premises_rejection_reason",
        read_only=True,
    )
    evidenceFiles = serializers.ListField(
        child=serializers.URLField(),
        source="evidence_files",
        required=False,
    )
    premisesEvidence = serializers.SerializerMethodField()
    geoChangedAt = serializers.DateTimeField(source="geo_changed_at", read_only=True)
    pendingGeo = serializers.JSONField(source="pending_geo", read_only=True)
    premisesRejectionCount = serializers.IntegerField(
        source="premises_rejection_count",
        read_only=True,
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = DealerLocation
        fields = [
            "id",
            "dealerId",
            "dealerName",
            "dealer",
            "name",
            "area",
            "citySlug",
            "districtSlug",
            "address",
            "latitude",
            "longitude",
            "isPrimary",
            "premisesVerificationStatus",
            "premisesVerifiedAt",
            "premisesRejectedAt",
            "premisesRejectionReason",
            "evidenceFiles",
            "premisesEvidence",
            "geoChangedAt",
            "pendingGeo",
            "premisesRejectionCount",
            "createdAt",
            "updatedAt",
        ]
        extra_kwargs = {
            "area": {"required": False},
            "address": {"required": False, "allow_null": True, "allow_blank": True},
            "latitude": {"required": False, "allow_null": True},
            "longitude": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("area") and attrs.get("district_slug"):
            attrs["area"] = attrs["district_slug"]
        return attrs

    def get_dealer(self, obj):
        dealer = getattr(obj, "dealer", None)
        if dealer is None:
            return None
        return {"id": str(dealer.id), "name": dealer.name}

    def get_premisesEvidence(self, obj):
        evidence = list(obj.evidence_files or [])
        dealer = getattr(obj, "dealer", None)
        if dealer is not None:
            latest_premises_document = None
            for document in dealer.verification_documents.all():
                if document.kind != DealerVerificationDocument.Kind.PREMISES or not document.file_url:
                    continue
                if latest_premises_document is None or document.created_at > latest_premises_document.created_at:
                    latest_premises_document = document
            if latest_premises_document is not None:
                evidence.append(latest_premises_document.file_url)
        seen = set()
        unique = []
        for url in evidence:
            if url not in seen:
                seen.add(url)
                unique.append(url)
        return unique


class DealerProfileSerializer(serializers.ModelSerializer):
    legalName = serializers.CharField(source="legal_name", required=False)
    entityType = serializers.CharField(source="entity_type", read_only=True)
    verificationStatus = serializers.CharField(source="verification_status", read_only=True)
    operationalStatus = serializers.CharField(source="operational_status", read_only=True)
    suspendedAt = serializers.DateTimeField(source="suspended_at", read_only=True)
    suspendedReason = serializers.CharField(source="suspended_reason", read_only=True)
    verifiedBadge = serializers.BooleanField(source="verified_badge", read_only=True)
    verifiedAt = serializers.DateTimeField(source="verified_at", read_only=True)
    citySlug = serializers.SlugField(source="city_slug", required=False)
    districtSlug = serializers.SlugField(
        source="district_slug",
        required=False,
        allow_null=True,
    )
    logoUrl = serializers.URLField(source="logo_url", required=False, allow_null=True)
    planId = serializers.CharField(source="plan_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    locations = DealerLocationSerializer(many=True, read_only=True)
    primaryLocationId = serializers.SerializerMethodField()

    class Meta:
        model = Dealer
        fields = [
            "id",
            "slug",
            "name",
            "legalName",
            "entityType",
            "verificationStatus",
            "operationalStatus",
            "suspendedAt",
            "suspendedReason",
            "verifiedBadge",
            "verifiedAt",
            "area",
            "citySlug",
            "districtSlug",
            "address",
            "latitude",
            "longitude",
            "phone",
            "whatsapp",
            "logoUrl",
            "description",
            "hours",
            "planId",
            "createdAt",
            "updatedAt",
            "locations",
            "primaryLocationId",
        ]
        read_only_fields = [
            "id",
            "slug",
            "entityType",
            "verificationStatus",
            "operationalStatus",
            "suspendedAt",
            "suspendedReason",
            "verifiedBadge",
            "verifiedAt",
            "planId",
            "createdAt",
            "updatedAt",
            "locations",
            "primaryLocationId",
        ]
        extra_kwargs = {
            "address": {"required": False, "allow_null": True, "allow_blank": True},
            "latitude": {"required": False, "allow_null": True},
            "longitude": {"required": False, "allow_null": True},
            "whatsapp": {"required": False, "allow_null": True, "allow_blank": True},
            "description": {"required": False, "allow_null": True, "allow_blank": True},
            "hours": {"required": False},
        }

    def get_primaryLocationId(self, obj):
        location = next((item for item in obj.locations.all() if item.is_primary), None)
        return str(location.id) if location else None


class DealerContextLocationSerializer(serializers.ModelSerializer):
    isPrimary = serializers.BooleanField(source="is_primary")
    listingCount = serializers.SerializerMethodField()

    class Meta:
        model = DealerLocation
        fields = ["id", "name", "area", "isPrimary", "listingCount"]

    def get_listingCount(self, obj) -> int:
        return 0


class DealerStaffSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    preferredLocationId = serializers.UUIDField(
        source="preferred_location_id",
        required=False,
        allow_null=True,
    )
    mustChangePassword = serializers.BooleanField(source="must_change_password", read_only=True)
    invitePending = serializers.BooleanField(source="invite_pending", read_only=True)
    inviteToken = serializers.CharField(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = StaffUser
        fields = [
            "id",
            "dealerId",
            "preferredLocationId",
            "email",
            "name",
            "role",
            "is_active",
            "mustChangePassword",
            "invitePending",
            "inviteToken",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
            "dealerId",
            "mustChangePassword",
            "invitePending",
            "inviteToken",
            "createdAt",
            "updatedAt",
        ]

    def create(self, validated_data):
        token = generate_invite_token()
        user = StaffUser(
            **validated_data,
            dealer=self.context["dealer"],
            must_change_password=True,
            invite_token_hash=hash_invite_token(token),
            invite_expires_at=invite_expiry(),
        )
        user.set_unusable_password()
        user.save()
        user.inviteToken = token
        return user


class DealerVerificationDocumentSerializer(serializers.ModelSerializer):
    fileUrl = serializers.URLField(source="file_url")
    rejectionReason = serializers.CharField(source="rejection_reason", read_only=True)
    reviewedAt = serializers.DateTimeField(source="reviewed_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = DealerVerificationDocument
        fields = [
            "id",
            "kind",
            "title",
            "fileUrl",
            "status",
            "rejectionReason",
            "reviewedAt",
            "createdAt",
        ]
        read_only_fields = ["id", "status", "rejectionReason", "reviewedAt", "createdAt"]


class DealerVerificationSerializer(DealerProfileSerializer):
    documents = serializers.SerializerMethodField()

    class Meta(DealerProfileSerializer.Meta):
        fields = DealerProfileSerializer.Meta.fields + ["documents"]

    def get_documents(self, obj):
        latest_by_kind = {}
        for document in obj.verification_documents.all():
            existing = latest_by_kind.get(document.kind)
            if existing is None or document.created_at > existing.created_at:
                latest_by_kind[document.kind] = document
        documents = sorted(
            latest_by_kind.values(),
            key=lambda document: document.created_at,
            reverse=True,
        )
        return DealerVerificationDocumentSerializer(documents, many=True).data


class DealerSelfServiceRequestSerializer(serializers.Serializer):
    reason = serializers.CharField()
