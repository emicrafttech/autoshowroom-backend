from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.permissions import IsActiveDealerStaff
from apps.common.views import EnvelopeMixin
from apps.platform.views import IsPlatformStaff

from .models import DealerNotification, PlatformNotification
from .serializers import DealerNotificationSerializer, PlatformNotificationSerializer


class DealerNotificationViewSet(
    EnvelopeMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DealerNotificationSerializer
    permission_classes = [IsActiveDealerStaff]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return DealerNotification.objects.select_related(
            "vehicle",
            "review_issue",
        ).filter(
            recipient=self.request.user,
            dealer_id=self.request.user.dealer_id,
        )

    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.recipient_id != request.user.id:
            raise PermissionDenied("You cannot update this notification.")
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated}, status=status.HTTP_200_OK)


class PlatformNotificationViewSet(
    EnvelopeMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PlatformNotificationSerializer
    permission_classes = [IsPlatformStaff]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return PlatformNotification.objects.select_related(
            "dealer",
            "vehicle",
        ).filter(
            recipient=self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.recipient_id != request.user.id:
            raise PermissionDenied("You cannot update this notification.")
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated}, status=status.HTTP_200_OK)
