from pathlib import Path
from uuid import uuid4

from django.conf import settings
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsActiveDealerStaff
from apps.common.views import EnvelopeMixin
from apps.platform.models import ContentReport
from apps.platform.serializers import ContentReportSerializer
from apps.vehicles.storage import create_presigned_upload

from .models import AnalyticsEvent, GenericUploadRequest, Lead, NotifyMeRequest
from .serializers import (
    AnalyticsEventSerializer,
    GenericUploadRequestSerializer,
    LeadSerializer,
    NotifyMeRequestSerializer,
)


class LeadViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsActiveDealerStaff()]

    def get_authenticators(self):
        if getattr(self, "action", None) == "create":
            return []
        return super().get_authenticators()

    def get_queryset(self):
        return Lead.objects.filter(dealer_id=self.request.user.dealer_id).select_related(
            "dealer",
            "location",
            "vehicle",
        )


class NotifyMeCreateView(EnvelopeMixin, generics.CreateAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    queryset = NotifyMeRequest.objects.all()
    serializer_class = NotifyMeRequestSerializer

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AnalyticsEventCreateView(EnvelopeMixin, generics.CreateAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    queryset = AnalyticsEvent.objects.all()
    serializer_class = AnalyticsEventSerializer

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PublicReportCreateView(EnvelopeMixin, generics.CreateAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    queryset = ContentReport.objects.all()
    serializer_class = ContentReportSerializer

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        report = serializer.save()
        from apps.notifications.platform_notifications import notify_content_report_filed

        notify_content_report_filed(report)


class GenericUploadCreateView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = GenericUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file_name = serializer.validated_data["file_name"]
        suffix = Path(file_name).suffix.lower()
        suffix = suffix if len(suffix) <= 16 else ""
        key = f"{settings.MEDIA_UPLOAD_PREFIX}/generic/{uuid4().hex}{suffix}"
        upload = create_presigned_upload(key, serializer.validated_data["content_type"])
        record = serializer.save(s3_key=upload.key, public_url=upload.public_url)
        data = GenericUploadRequestSerializer(record).data
        data["uploadUrl"] = upload.upload_url
        return Response(data, status=status.HTTP_201_CREATED)
