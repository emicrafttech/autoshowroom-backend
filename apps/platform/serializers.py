from rest_framework import serializers

from apps.accounts.models import StaffUser

from .models import (
    AuditLog,
    ContentReport,
    ContentReportNote,
    DataSubjectRequest,
    DealerSanction,
    PlatformRole,
    PlatformSetting,
    SanctionAppeal,
    SecurityIncident,
    WatchlistEntry,
)


class PlatformRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformRole
        fields = ["id", "name", "capabilities", "created_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    actorId = serializers.UUIDField(source="actor_id", read_only=True)
    targetType = serializers.CharField(source="target_type")
    targetId = serializers.CharField(source="target_id", required=False, allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actorId", "action", "targetType", "targetId", "metadata", "createdAt"]


class ContentReportSerializer(serializers.ModelSerializer):
    vehicleId = serializers.UUIDField(source="vehicle_id", required=False, allow_null=True)
    reporterName = serializers.CharField(source="reporter_name", required=False, allow_blank=True)
    reporterContact = serializers.CharField(source="reporter_contact", required=False, allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = ContentReport
        fields = [
            "id",
            "vehicleId",
            "reporterName",
            "reporterContact",
            "reason",
            "status",
            "createdAt",
            "updatedAt",
        ]


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
    liftedAt = serializers.DateTimeField(source="lifted_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = DealerSanction
        fields = ["id", "dealerId", "reason", "status", "createdAt", "liftedAt"]


class ContentReportNoteSerializer(serializers.ModelSerializer):
    authorId = serializers.UUIDField(source="author_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ContentReportNote
        fields = ["id", "authorId", "body", "createdAt"]


class SanctionAppealSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id")
    sanctionId = serializers.UUIDField(source="sanction_id", required=False, allow_null=True)
    decidedAt = serializers.DateTimeField(source="decided_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = SanctionAppeal
        fields = [
            "id",
            "dealerId",
            "sanctionId",
            "reason",
            "status",
            "decidedAt",
            "createdAt",
            "updatedAt",
        ]


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
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WatchlistEntry
        fields = ["id", "dealerId", "vehicleId", "reason", "status", "createdAt", "updatedAt"]


class PlatformUserSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = StaffUser
        fields = [
            "id",
            "email",
            "name",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "createdAt", "updatedAt"]
