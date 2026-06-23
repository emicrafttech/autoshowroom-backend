from django.contrib.auth import authenticate
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.views import EnvelopeMixin
from apps.accounts.models import StaffUser
from apps.dealers.models import Dealer, DealerLocation
from apps.dealers.serializers import DealerLocationSerializer, DealerProfileSerializer
from apps.vehicles.models import Vehicle

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
from .serializers import (
    AuditLogSerializer,
    ContentReportNoteSerializer,
    ContentReportSerializer,
    DataSubjectRequestSerializer,
    DealerSanctionSerializer,
    PlatformSettingSerializer,
    PlatformRoleSerializer,
    PlatformUserSerializer,
    SanctionAppealSerializer,
    SecurityIncidentSerializer,
    WatchlistEntrySerializer,
)


class IsPlatformStaff(permissions.BasePermission):
    message = "Platform staff credentials are required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_active", False)
            and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
        )


def write_audit(user, action: str, target, metadata=None):
    AuditLog.objects.create(
        actor=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        target_type=target.__class__.__name__,
        target_id=str(getattr(target, "id", "")),
        metadata=metadata or {},
    )


class AuditedModelViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    permission_classes = [IsPlatformStaff]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        instance = serializer.save()
        write_audit(self.request.user, f"{self.audit_name}.created", instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        write_audit(self.request.user, f"{self.audit_name}.updated", instance)

    @property
    def audit_name(self):
        return getattr(self, "audit_resource_name", self.__class__.__name__)


class PlatformRoleViewSet(AuditedModelViewSet):
    audit_resource_name = "platform_role"
    queryset = PlatformRole.objects.all().order_by("name")
    serializer_class = PlatformRoleSerializer


class ContentReportViewSet(AuditedModelViewSet):
    audit_resource_name = "content_report"
    queryset = ContentReport.objects.select_related("vehicle")
    serializer_class = ContentReportSerializer

    @action(detail=True, methods=["patch"], url_path="resolve")
    def resolve(self, request, pk=None):
        report = self.get_object()
        report.status = ContentReport.Status.RESOLVED
        report.save(update_fields=["status", "updated_at"])
        write_audit(request.user, "content_report.resolved", report)
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["patch"], url_path="assign")
    def assign(self, request, pk=None):
        report = self.get_object()
        report.status = ContentReport.Status.IN_REVIEW
        report.save(update_fields=["status", "updated_at"])
        write_audit(request.user, "content_report.assigned", report)
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["patch"], url_path="case")
    def case(self, request, pk=None):
        report = self.get_object()
        report.status = request.data.get("status", report.status)
        report.save(update_fields=["status", "updated_at"])
        write_audit(request.user, "content_report.case_updated", report)
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["post"], url_path="notes")
    def notes(self, request, pk=None):
        report = self.get_object()
        serializer = ContentReportNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(report=report, author=request.user)
        write_audit(request.user, "content_report.note_created", report)
        return Response(ContentReportNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class DataSubjectRequestViewSet(AuditedModelViewSet):
    audit_resource_name = "data_subject_request"
    queryset = DataSubjectRequest.objects.select_related("dealer")
    serializer_class = DataSubjectRequestSerializer

    @action(detail=True, methods=["post"], url_path="erase")
    def erase(self, request, pk=None):
        dsr = self.get_object()
        dsr.status = DataSubjectRequest.Status.COMPLETED
        dsr.notes = f"{dsr.notes}\nErase request completed.".strip()
        dsr.save(update_fields=["status", "notes", "updated_at"])
        write_audit(request.user, "dsr.erased", dsr)
        return Response(self.get_serializer(dsr).data)

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        dsr = self.get_object()
        return Response({"requestId": str(dsr.id), "dealerId": str(dsr.dealer_id) if dsr.dealer_id else None})

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, pk=None):
        dsr = self.get_object()
        return Response(self.get_serializer(dsr).data)


class DealerSanctionViewSet(AuditedModelViewSet):
    audit_resource_name = "dealer_sanction"
    queryset = DealerSanction.objects.select_related("dealer")
    serializer_class = DealerSanctionSerializer

    @action(detail=True, methods=["patch"], url_path="lift")
    def lift(self, request, pk=None):
        sanction = self.get_object()
        sanction.status = DealerSanction.Status.LIFTED
        sanction.lifted_at = timezone.now()
        sanction.save(update_fields=["status", "lifted_at"])
        write_audit(request.user, "dealer_sanction.lifted", sanction)
        return Response(self.get_serializer(sanction).data)


class AuditLogViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsPlatformStaff]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor")


class PlatformUserViewSet(AuditedModelViewSet):
    audit_resource_name = "platform_user"
    serializer_class = PlatformUserSerializer
    queryset = StaffUser.objects.filter(is_staff=True)

    def perform_create(self, serializer):
        user = serializer.save(is_staff=True)
        user.set_unusable_password()
        user.save(update_fields=["password"])
        write_audit(self.request.user, "platform_user.created", user)


class PlatformSettingViewSet(AuditedModelViewSet):
    audit_resource_name = "platform_setting"
    serializer_class = PlatformSettingSerializer
    queryset = PlatformSetting.objects.all()


class PlatformSettingsView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def get(self, request):
        settings = {item.key: item.value for item in PlatformSetting.objects.all()}
        return Response(settings)

    def patch(self, request):
        for key, value in request.data.items():
            PlatformSetting.objects.update_or_create(key=key, defaults={"value": value})
        return self.get(request)


class SecurityIncidentViewSet(AuditedModelViewSet):
    audit_resource_name = "security_incident"
    serializer_class = SecurityIncidentSerializer
    queryset = SecurityIncident.objects.all()


class WatchlistEntryViewSet(AuditedModelViewSet):
    audit_resource_name = "watchlist_entry"
    serializer_class = WatchlistEntrySerializer
    queryset = WatchlistEntry.objects.select_related("dealer", "vehicle")


class SanctionAppealViewSet(AuditedModelViewSet):
    audit_resource_name = "sanction_appeal"
    serializer_class = SanctionAppealSerializer
    queryset = SanctionAppeal.objects.select_related("dealer", "sanction")

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        appeal = self.get_object()
        if appeal.status in [SanctionAppeal.Status.APPROVED, SanctionAppeal.Status.REJECTED]:
            appeal.decided_at = appeal.decided_at or timezone.now()
            appeal.save(update_fields=["decided_at", "updated_at"])
        return response


class PlatformLoginView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField()
        password = serializers.CharField(write_only=True)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            username=serializer.validated_data["email"].lower(),
            password=serializer.validated_data["password"],
        )
        if not user or not user.is_staff:
            raise serializers.ValidationError("Invalid platform credentials.")
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "accessToken": str(refresh.access_token),
                "refreshToken": str(refresh),
                "user": PlatformUserSerializer(user).data,
            }
        )


class PlatformRefreshView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    class InputSerializer(serializers.Serializer):
        refreshToken = serializers.CharField()

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh = RefreshToken(serializer.validated_data["refreshToken"])
        user = get_object_or_404(StaffUser, id=refresh["user_id"], is_staff=True, is_active=True)
        new_refresh = RefreshToken.for_user(user)
        return Response(
            {
                "accessToken": str(new_refresh.access_token),
                "refreshToken": str(new_refresh),
            }
        )


class PlatformMeView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def get(self, request):
        return Response(PlatformUserSerializer(request.user).data)


class PlatformMfaView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def post(self, request):
        return Response({"enabled": True})


class PlatformOverviewView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def get(self, request):
        return Response(
            {
                "dealers": Dealer.objects.count(),
                "vehicles": Vehicle.objects.count(),
                "pendingDealerVerifications": Dealer.objects.filter(verification_status=Dealer.VerificationStatus.PENDING).count(),
                "pendingPremises": DealerLocation.objects.filter(premises_verification_status=DealerLocation.PremisesVerificationStatus.PENDING).count(),
                "openReports": ContentReport.objects.filter(status=ContentReport.Status.OPEN).count(),
            }
        )


class StatsView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]
    model = None
    status_field = "status"

    def get(self, request):
        rows = self.model.objects.values(self.status_field).annotate(count=Count("id"))
        return Response({"total": self.model.objects.count(), "byStatus": list(rows)})


class AuditExportView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def get(self, request):
        entries = AuditLog.objects.order_by("-created_at")[:100]
        return Response({"entries": AuditLogSerializer(entries, many=True).data})


class DealerDirectoryView(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsPlatformStaff]
    serializer_class = DealerProfileSerializer
    queryset = Dealer.objects.prefetch_related("locations")


class DealerProvisionView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def post(self, request):
        dealer = Dealer.objects.create(
            slug=request.data["slug"],
            name=request.data["name"],
            legal_name=request.data.get("legalName", request.data["name"]),
            area=request.data.get("area", ""),
            phone=request.data.get("phone", ""),
        )
        write_audit(request.user, "dealer.provisioned", dealer)
        return Response(DealerProfileSerializer(dealer).data, status=status.HTTP_201_CREATED)


class DealerQueueView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]
    queue_type = "dealer"

    def get(self, request):
        if self.queue_type == "premises":
            queryset = DealerLocation.objects.filter(
                premises_verification_status=DealerLocation.PremisesVerificationStatus.PENDING,
            )
            return Response(DealerLocationSerializer(queryset, many=True).data)
        queryset = Dealer.objects.filter(verification_status=Dealer.VerificationStatus.PENDING)
        return Response(DealerProfileSerializer(queryset, many=True).data)


class DealerDetailView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def get(self, request, dealer_id):
        dealer = get_object_or_404(Dealer.objects.prefetch_related("locations"), id=dealer_id)
        return Response(DealerProfileSerializer(dealer).data)


class PlatformLocationView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def get_location(self, location_id):
        return get_object_or_404(DealerLocation.objects.select_related("dealer"), id=location_id)

    def get(self, request, location_id):
        return Response(DealerLocationSerializer(self.get_location(location_id)).data)


class PlatformLocationActionView(PlatformLocationView):
    http_method_names = ["patch", "options"]
    action_name = "start-review"

    def patch(self, request, location_id):
        location = self.get_location(location_id)
        now = timezone.now()
        if self.action_name == "verify-premises":
            location.premises_verification_status = DealerLocation.PremisesVerificationStatus.VERIFIED
            location.premises_verified_at = now
            location.premises_rejected_at = None
            location.premises_rejection_reason = None
        elif self.action_name == "reject-premises":
            location.premises_verification_status = DealerLocation.PremisesVerificationStatus.REJECTED
            location.premises_rejected_at = now
            location.premises_rejection_reason = request.data.get("reason", "")
            location.premises_rejection_count += 1
        else:
            location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
        location.save()
        write_audit(request.user, f"location.{self.action_name}", location)
        return Response(DealerLocationSerializer(location).data)


class PlatformLocationStartReviewView(PlatformLocationActionView):
    action_name = "start-review"

    def patch(self, request, location_id):
        return super().patch(request, location_id)


class PlatformLocationVerifyPremisesView(PlatformLocationActionView):
    action_name = "verify-premises"

    def patch(self, request, location_id):
        return super().patch(request, location_id)


class PlatformLocationRejectPremisesView(PlatformLocationActionView):
    action_name = "reject-premises"

    def patch(self, request, location_id):
        return super().patch(request, location_id)
