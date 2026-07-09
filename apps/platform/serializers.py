from rest_framework import serializers

from apps.accounts.models import StaffUser

from .models import (
    AuditLog,
    ContentReport,
    ContentReportNote,
    DataSubjectRequest,
    DealerMessage,
    DealerMessageThread,
    DealerSanction,
    PlatformRole,
    PlatformSetting,
    SanctionAppeal,
    SecurityIncident,
    WatchlistEntry,
)

PLATFORM_CAPABILITIES = {
    "session.read",
    "overview.read",
    "premises.read",
    "premises.write",
    "dealer_verification.read",
    "dealer_verification.write",
    "listing_review.read",
    "listing_review.write",
    "content_reports.read",
    "content_reports.write",
    "media_moderation.read",
    "media_moderation.write",
    "watchlists.read",
    "watchlists.write",
    "sanctions.read",
    "sanctions.write",
    "dealers.read",
    "dealers.write",
    "dsr.read",
    "dsr.write",
    "billing.read",
    "billing.write",
    "settings.read",
    "settings.write",
    "audit.read",
    "uploads.write",
    "platform_users.read",
    "platform_users.write",
}


class PlatformRoleSerializer(serializers.ModelSerializer):
    requireStepUp = serializers.BooleanField(source="require_step_up", required=False)

    def validate_capabilities(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Capabilities must be a list.")
        invalid = sorted({item for item in value if item not in PLATFORM_CAPABILITIES})
        if invalid:
            raise serializers.ValidationError(f"Unknown capabilities: {', '.join(invalid)}")
        return sorted({"session.read", *value})

    class Meta:
        model = PlatformRole
        fields = ["id", "name", "description", "color", "requireStepUp", "capabilities", "created_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    actorId = serializers.UUIDField(source="actor_id", read_only=True)
    actorName = serializers.CharField(source="actor.name", read_only=True)
    actorEmail = serializers.EmailField(source="actor.email", read_only=True)
    targetType = serializers.CharField(source="target_type")
    targetId = serializers.CharField(source="target_id", required=False, allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actorId", "actorName", "actorEmail", "action", "targetType", "targetId", "metadata", "createdAt"]


class DealerMessageSerializer(serializers.ModelSerializer):
    senderName = serializers.CharField(source="sender.name", read_only=True)
    senderType = serializers.CharField(source="sender_type", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = DealerMessage
        fields = ["id", "senderName", "senderType", "body", "createdAt"]


class DealerMessageThreadSerializer(serializers.ModelSerializer):
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    createdByName = serializers.CharField(source="created_by.name", read_only=True)
    messages = DealerMessageSerializer(many=True, read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = DealerMessageThread
        fields = [
            "id",
            "dealer",
            "dealerName",
            "subject",
            "status",
            "createdByName",
            "messages",
            "createdAt",
            "updatedAt",
        ]


class ContentReportSerializer(serializers.ModelSerializer):
    vehicleId = serializers.UUIDField(source="vehicle_id", required=False, allow_null=True)
    reporterName = serializers.CharField(source="reporter_name", required=False, allow_blank=True)
    reporterContact = serializers.CharField(source="reporter_contact", required=False, allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    notes = serializers.SerializerMethodField()

    class Meta:
        model = ContentReport
        fields = [
            "id",
            "vehicleId",
            "reporterName",
            "reporterContact",
            "reason",
            "status",
            "notes",
            "createdAt",
            "updatedAt",
        ]

    def get_notes(self, obj):
        return ContentReportNoteSerializer(obj.notes.select_related("author").all(), many=True).data


class DataSubjectRequestSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", required=False, allow_null=True)
    requesterName = serializers.CharField(source="requester_name")
    requesterContact = serializers.CharField(source="requester_contact")
    requestType = serializers.CharField(source="request_type")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = DataSubjectRequest
        fields = [
            "id",
            "dealerId",
            "requesterName",
            "requesterContact",
            "requestType",
            "status",
            "notes",
            "createdAt",
            "updatedAt",
        ]


class DealerSanctionSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id")
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    liftedAt = serializers.DateTimeField(source="lifted_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = DealerSanction
        fields = ["id", "dealerId", "dealerName", "reason", "status", "createdAt", "liftedAt"]


class ContentReportNoteSerializer(serializers.ModelSerializer):
    authorId = serializers.UUIDField(source="author_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ContentReportNote
        fields = ["id", "authorId", "body", "createdAt"]


class SanctionAppealSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id")
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    sanctionId = serializers.UUIDField(source="sanction_id", required=False, allow_null=True)
    sanctionReason = serializers.SerializerMethodField()
    sanctionStatus = serializers.SerializerMethodField()
    decidedAt = serializers.DateTimeField(source="decided_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = SanctionAppeal
        fields = [
            "id",
            "dealerId",
            "dealerName",
            "sanctionId",
            "sanctionReason",
            "sanctionStatus",
            "reason",
            "status",
            "decidedAt",
            "createdAt",
            "updatedAt",
        ]

    def get_sanctionReason(self, obj):
        return obj.sanction.reason if obj.sanction else None

    def get_sanctionStatus(self, obj):
        return obj.sanction.status if obj.sanction else None


class PlatformSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSetting
        fields = ["id", "key", "value", "updated_at"]


class SecurityIncidentSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = SecurityIncident
        fields = ["id", "title", "severity", "status", "description", "createdAt", "updatedAt"]


class WatchlistEntrySerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", required=False, allow_null=True)
    vehicleId = serializers.UUIDField(source="vehicle_id", required=False, allow_null=True)
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    vehicleTitle = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WatchlistEntry
        fields = [
            "id",
            "dealerId",
            "dealerName",
            "vehicleId",
            "vehicleTitle",
            "reason",
            "status",
            "createdAt",
            "updatedAt",
        ]

    def get_vehicleTitle(self, obj):
        if not obj.vehicle:
            return None
        return " ".join(
            str(part)
            for part in [
                obj.vehicle.year,
                obj.vehicle.make,
                obj.vehicle.model,
                obj.vehicle.trim,
            ]
            if part
        )


class PlatformUserSerializer(serializers.ModelSerializer):
    roleId = serializers.PrimaryKeyRelatedField(
        source="platform_role",
        queryset=PlatformRole.objects.all(),
        required=False,
        allow_null=True,
    )
    roleName = serializers.CharField(source="platform_role.name", read_only=True)
    roleCapabilities = serializers.SerializerMethodField()
    invitePending = serializers.BooleanField(source="invite_pending", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = StaffUser
        fields = [
            "id",
            "email",
            "name",
            "role",
            "roleId",
            "roleName",
            "roleCapabilities",
            "invitePending",
            "is_active",
            "is_staff",
            "is_superuser",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "roleName", "roleCapabilities", "invitePending", "is_staff", "is_superuser", "createdAt", "updatedAt"]

    def get_roleCapabilities(self, obj):
        if obj.is_superuser:
            return sorted(PLATFORM_CAPABILITIES)
        if obj.platform_role:
            return sorted(set(obj.platform_role.capabilities or []))
        return ["session.read"]
