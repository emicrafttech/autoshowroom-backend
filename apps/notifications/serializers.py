from rest_framework import serializers

from .models import DealerNotification, PlatformNotification


class DealerNotificationSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    vehicleId = serializers.UUIDField(source="vehicle_id", read_only=True)
    reviewIssueId = serializers.UUIDField(source="review_issue_id", read_only=True)
    reviewIssueStatus = serializers.CharField(source="review_issue.status", read_only=True)
    vehicleTitle = serializers.SerializerMethodField()
    readAt = serializers.DateTimeField(source="read_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = DealerNotification
        fields = [
            "id",
            "dealerId",
            "vehicleId",
            "reviewIssueId",
            "reviewIssueStatus",
            "vehicleTitle",
            "type",
            "title",
            "body",
            "readAt",
            "createdAt",
        ]
        read_only_fields = fields

    def get_vehicleTitle(self, obj):
        if not obj.vehicle_id:
            return None
        return f"{obj.vehicle.year} {obj.vehicle.make} {obj.vehicle.model}"


class PlatformNotificationSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    vehicleId = serializers.UUIDField(source="vehicle_id", read_only=True)
    vehicleTitle = serializers.SerializerMethodField()
    readAt = serializers.DateTimeField(source="read_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = PlatformNotification
        fields = [
            "id",
            "type",
            "title",
            "body",
            "href",
            "dealerId",
            "dealerName",
            "vehicleId",
            "vehicleTitle",
            "readAt",
            "createdAt",
        ]
        read_only_fields = fields

    def get_vehicleTitle(self, obj):
        if not obj.vehicle_id:
            return None
        return f"{obj.vehicle.year} {obj.vehicle.make} {obj.vehicle.model}"
