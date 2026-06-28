from datetime import datetime, time, timedelta

from django.contrib.auth import authenticate
from django.conf import settings
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tokens import generate_invite_token, hash_invite_token, invite_expiry
from apps.common.views import EnvelopeMixin
from apps.accounts.models import StaffUser
from apps.dealers.models import Dealer, DealerLocation, DealerVerificationDocument
from apps.dealers.serializers import (
    DealerLocationSerializer,
    DealerProfileSerializer,
    DealerVerificationDocumentSerializer,
    DealerVerificationSerializer,
)
from apps.notifications.models import DealerNotification
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


def platform_capabilities(user):
    if getattr(user, "is_superuser", False):
        return {"*"}
    role = getattr(user, "platform_role", None)
    return set(getattr(role, "capabilities", None) or [])


class HasPlatformCapability(IsPlatformStaff):
    capability = None
    read_capability = None
    write_capability = None

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if getattr(request.user, "is_superuser", False):
            return True
        if request.method in permissions.SAFE_METHODS:
            capability = self.read_capability or getattr(view, "read_capability", None)
        else:
            capability = self.write_capability or getattr(view, "write_capability", None)
        capability = capability or self.capability or getattr(view, "required_capability", None)
        return capability in platform_capabilities(request.user)


class HasPlatformUserAccess(IsPlatformStaff):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in permissions.SAFE_METHODS:
            return getattr(request.user, "is_superuser", False) or "platform_users.read" in platform_capabilities(request.user)
        return getattr(request.user, "is_superuser", False) or "platform_users.write" in platform_capabilities(request.user)


def write_audit(user, action: str, target, metadata=None):
    AuditLog.objects.create(
        actor=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        target_type=target.__class__.__name__,
        target_id=str(getattr(target, "id", "")),
        metadata=metadata or {},
    )


def dealer_verification_review_queryset():
    return (
        Dealer.objects.prefetch_related("locations", "verification_documents")
        .filter(
            Q(verification_status=Dealer.VerificationStatus.PENDING)
            | (
                Q(verification_documents__isnull=False)
                & ~Q(
                    verification_status__in=[
                        Dealer.VerificationStatus.APPROVED,
                        Dealer.VerificationStatus.REJECTED,
                    ]
                )
            )
        )
        .distinct()
    )


class AuditedModelViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    permission_classes = [HasPlatformCapability]
    http_method_names = ["get", "post", "patch", "head", "options"]
    read_capability = None
    write_capability = None

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
    read_capability = "platform_users.read"
    write_capability = "platform_users.write"


class ContentReportViewSet(AuditedModelViewSet):
    audit_resource_name = "content_report"
    queryset = ContentReport.objects.select_related("vehicle").prefetch_related("notes__author")
    serializer_class = ContentReportSerializer
    read_capability = "content_reports.read"
    write_capability = "content_reports.write"

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
    read_capability = "settings.read"
    write_capability = "settings.write"

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
    read_capability = "sanctions.read"
    write_capability = "sanctions.write"

    def perform_create(self, serializer):
        super().perform_create(serializer)
        from apps.notifications.services import notify_sanction_applied

        notify_sanction_applied(serializer.instance)

    @action(detail=True, methods=["patch"], url_path="lift")
    def lift(self, request, pk=None):
        sanction = self.get_object()
        sanction.status = DealerSanction.Status.LIFTED
        sanction.lifted_at = timezone.now()
        sanction.save(update_fields=["status", "lifted_at"])
        write_audit(request.user, "dealer_sanction.lifted", sanction)
        return Response(self.get_serializer(sanction).data)


class AuditLogViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [HasPlatformCapability]
    required_capability = "audit.read"
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor")


class PlatformUserViewSet(AuditedModelViewSet):
    audit_resource_name = "platform_user"
    permission_classes = [HasPlatformUserAccess]
    serializer_class = PlatformUserSerializer
    queryset = StaffUser.objects.filter(is_staff=True).select_related("platform_role")

    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        is_deactivating_self = (
            user.id == request.user.id
            and request.data.get("is_active") is False
        )
        if is_deactivating_self:
            raise serializers.ValidationError("You cannot disable your own platform admin account.")
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        token = generate_invite_token()
        user = serializer.save(
            is_staff=True,
            dealer=None,
            preferred_location=None,
            must_change_password=True,
            invite_token_hash=hash_invite_token(token),
            invite_expires_at=invite_expiry(),
        )
        user.set_unusable_password()
        user.save(
            update_fields=[
                "password",
                "must_change_password",
                "invite_token_hash",
                "invite_expires_at",
                "updated_at",
            ]
        )
        from apps.notifications.services import notify_staff_invite

        notify_staff_invite(user, token, portal="platform")
        write_audit(self.request.user, "platform_user.created", user)


class PlatformSettingViewSet(AuditedModelViewSet):
    audit_resource_name = "platform_setting"
    serializer_class = PlatformSettingSerializer
    queryset = PlatformSetting.objects.all()
    read_capability = "settings.read"
    write_capability = "settings.write"


class PlatformSettingsView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    read_capability = "settings.read"
    write_capability = "settings.write"

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
    read_capability = "settings.read"
    write_capability = "settings.write"


class WatchlistEntryViewSet(AuditedModelViewSet):
    audit_resource_name = "watchlist_entry"
    serializer_class = WatchlistEntrySerializer
    queryset = WatchlistEntry.objects.select_related("dealer", "vehicle")
    read_capability = "watchlists.read"
    write_capability = "watchlists.write"


class SanctionAppealViewSet(AuditedModelViewSet):
    audit_resource_name = "sanction_appeal"
    serializer_class = SanctionAppealSerializer
    queryset = SanctionAppeal.objects.select_related("dealer", "sanction")
    read_capability = "sanctions.read"
    write_capability = "sanctions.write"

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        appeal = self.get_object()
        if appeal.status in [SanctionAppeal.Status.APPROVED, SanctionAppeal.Status.REJECTED]:
            appeal.decided_at = appeal.decided_at or timezone.now()
            appeal.save(update_fields=["decided_at", "updated_at"])
            if appeal.status == SanctionAppeal.Status.APPROVED and appeal.sanction:
                appeal.sanction.status = DealerSanction.Status.LIFTED
                appeal.sanction.lifted_at = appeal.sanction.lifted_at or timezone.now()
                appeal.sanction.save(update_fields=["status", "lifted_at"])
            write_audit(
                request.user,
                f"sanction_appeal.{appeal.status}",
                appeal,
                {"sanctionId": str(appeal.sanction_id) if appeal.sanction_id else None},
            )
            from apps.notifications.services import notify_sanction_appeal_outcome

            notify_sanction_appeal_outcome(appeal)
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
    permission_classes = [HasPlatformCapability]
    required_capability = "overview.read"

    def get(self, request):
        return Response(
            {
                "dealers": Dealer.objects.count(),
                "vehicles": Vehicle.objects.count(),
                "pendingDealerVerifications": dealer_verification_review_queryset().count(),
                "pendingPremises": DealerLocation.objects.filter(
                    premises_verification_status=DealerLocation.PremisesVerificationStatus.PENDING,
                ).count(),
                "openReports": ContentReport.objects.filter(status=ContentReport.Status.OPEN).count(),
            }
        )


class StatsView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    model = None
    status_field = "status"
    filter_kwargs = None
    exclude_kwargs = None
    required_capability = None

    def get_queryset(self):
        queryset = self.model.objects.all()
        if self.filter_kwargs:
            queryset = queryset.filter(**self.filter_kwargs)
        if self.exclude_kwargs:
            queryset = queryset.exclude(**self.exclude_kwargs)
        return queryset

    def get(self, request):
        queryset = self.get_queryset()
        rows = queryset.values(self.status_field).annotate(count=Count("id"))
        return Response({"total": queryset.count(), "byStatus": list(rows)})


class AuditExportView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "audit.read"
    page_size = 100

    def _date_range(self, request):
        start_date = parse_date(request.query_params.get("startDate") or "")
        end_date = parse_date(request.query_params.get("endDate") or "")
        if start_date or end_date:
            start_at = timezone.make_aware(datetime.combine(start_date, time.min)) if start_date else None
            end_at = timezone.make_aware(datetime.combine(end_date, time.max)) if end_date else None
            return start_at, end_at

        period = request.query_params.get("period")
        if period == "1d":
            return timezone.now() - timedelta(days=1), None
        if period == "7d":
            return timezone.now() - timedelta(days=7), None
        if period == "1m":
            return timezone.now() - timedelta(days=30), None
        return None, None

    def get(self, request):
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
        except (TypeError, ValueError):
            offset = 0
        limit = self.page_size
        queryset = AuditLog.objects.select_related("actor").order_by("-created_at")
        start_at, end_at = self._date_range(request)
        if start_at:
            queryset = queryset.filter(created_at__gte=start_at)
        if end_at:
            queryset = queryset.filter(created_at__lte=end_at)
        total = queryset.count()
        entries = list(queryset[offset : offset + limit])
        next_offset = offset + limit if offset + limit < total else None
        return Response(
            {
                "entries": AuditLogSerializer(entries, many=True).data,
                "count": total,
                "pageSize": limit,
                "nextOffset": next_offset,
                "hasMore": next_offset is not None,
            }
        )


class DealerDirectoryView(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [HasPlatformCapability]
    required_capability = "dealers.read"
    serializer_class = DealerVerificationSerializer
    queryset = Dealer.objects.prefetch_related("locations", "verification_documents")


class DealerProvisionView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "dealers.write"

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
    permission_classes = [HasPlatformCapability]
    queue_type = "dealer"

    @property
    def required_capability(self):
        return "premises.read" if self.queue_type == "premises" else "dealer_verification.read"

    def get(self, request):
        if self.queue_type == "premises":
            queryset = (
                DealerLocation.objects.select_related("dealer")
                .prefetch_related("dealer__verification_documents")
                .filter(
                    premises_verification_status=DealerLocation.PremisesVerificationStatus.PENDING,
                )
            )
            return Response(DealerLocationSerializer(queryset, many=True).data)
        queryset = dealer_verification_review_queryset()
        return Response(DealerVerificationSerializer(queryset, many=True).data)


class DealerVerificationStatsView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "dealer_verification.read"

    def get(self, request):
        pending = dealer_verification_review_queryset().count()
        rows = [
            {"status": row["verification_status"], "count": row["count"]}
            for row in Dealer.objects.values("verification_status").annotate(count=Count("id"))
        ]
        has_pending_row = any(row["status"] == Dealer.VerificationStatus.PENDING for row in rows)
        if has_pending_row:
            for row in rows:
                if row["status"] == Dealer.VerificationStatus.PENDING:
                    row["count"] = pending
        else:
            rows.append({"status": Dealer.VerificationStatus.PENDING, "count": pending})
        return Response({"total": pending, "byStatus": rows})


class DealerDetailView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "dealers.read"

    def get(self, request, dealer_id):
        dealer = get_object_or_404(Dealer.objects.prefetch_related("locations"), id=dealer_id)
        return Response(DealerProfileSerializer(dealer).data)


class PlatformDealerMessageView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "dealers.write"

    class InputSerializer(serializers.Serializer):
        subject = serializers.CharField(max_length=180, required=False, allow_blank=True)
        message = serializers.CharField(max_length=4000)

    def post(self, request, dealer_id):
        dealer = get_object_or_404(Dealer, id=dealer_id)
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subject = serializer.validated_data.get("subject", "").strip() or "Message from AutoShowroom platform"
        message = serializer.validated_data["message"].strip()
        if not message:
            raise serializers.ValidationError({"message": "Message is required."})

        recipients = StaffUser.objects.filter(
            dealer=dealer,
            is_active=True,
            email__isnull=False,
        ).exclude(email="")
        if not recipients.exists():
            raise serializers.ValidationError({"detail": "This dealer has no active staff email recipients."})

        notifications = DealerNotification.objects.bulk_create(
            [
                DealerNotification(
                    dealer=dealer,
                    recipient=recipient,
                    type=DealerNotification.Type.PLATFORM_MESSAGE,
                    title=subject,
                    body=message,
                )
                for recipient in recipients
            ]
        )
        from apps.notifications.services import notify_platform_dealer_message

        notify_platform_dealer_message(dealer, subject, message)
        write_audit(request.user, "dealer.message_sent", dealer, {"recipientCount": len(notifications)})
        return Response({"sent": len(notifications), "dealerId": str(dealer.id)})


class PlatformDealerSuspendView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "dealers.write"

    class InputSerializer(serializers.Serializer):
        reason = serializers.CharField(max_length=4000)

    def patch(self, request, dealer_id):
        dealer = get_object_or_404(Dealer, id=dealer_id)
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"].strip()
        if not reason:
            raise serializers.ValidationError({"reason": "Suspension reason is required."})

        dealer.operational_status = Dealer.OperationalStatus.SUSPENDED
        dealer.suspended_at = timezone.now()
        dealer.suspended_reason = reason
        dealer.save(update_fields=["operational_status", "suspended_at", "suspended_reason", "updated_at"])
        write_audit(request.user, "dealer.suspended", dealer, {"reason": reason})
        return Response(DealerVerificationSerializer(dealer).data)


class PlatformDealerDocumentActionView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "dealer_verification.write"
    http_method_names = ["patch", "options"]
    action_name = "approve"

    def patch(self, request, document_id):
        document = get_object_or_404(
            DealerVerificationDocument.objects.select_related("dealer"),
            id=document_id,
        )
        now = timezone.now()

        if self.action_name == "approve":
            document.status = DealerVerificationDocument.Status.APPROVED
            document.rejection_reason = ""
        elif self.action_name == "reject":
            reason = request.data.get("reason", "").strip()
            if not reason:
                raise serializers.ValidationError({"reason": "A rejection reason is required."})
            document.status = DealerVerificationDocument.Status.REJECTED
            document.rejection_reason = reason
        else:
            document.status = DealerVerificationDocument.Status.PENDING

        document.reviewed_at = now
        document.save(update_fields=["status", "rejection_reason", "reviewed_at"])
        write_audit(
            request.user,
            f"dealer_document.{self.action_name}",
            document,
            {"dealerId": str(document.dealer_id), "reason": request.data.get("reason", "")},
        )
        return Response(DealerVerificationDocumentSerializer(document).data)


class PlatformDealerDocumentApproveView(PlatformDealerDocumentActionView):
    action_name = "approve"


class PlatformDealerDocumentRejectView(PlatformDealerDocumentActionView):
    action_name = "reject"


class PlatformLocationView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "premises.read"

    def get_location(self, location_id):
        return get_object_or_404(DealerLocation.objects.select_related("dealer"), id=location_id)

    def get(self, request, location_id):
        return Response(DealerLocationSerializer(self.get_location(location_id)).data)


class PlatformLocationActionView(PlatformLocationView):
    http_method_names = ["patch", "options"]
    action_name = "start-review"
    required_capability = "premises.write"

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
        elif self.action_name == "request-info":
            location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
        else:
            location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
        location.save()
        write_audit(request.user, f"location.{self.action_name}", location, {"reason": request.data.get("reason", "")})
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


class PlatformLocationRequestInfoView(PlatformLocationActionView):
    action_name = "request-info"

    def patch(self, request, location_id):
        if not request.data.get("reason", "").strip():
            raise serializers.ValidationError({"reason": "A request reason is required."})
        return super().patch(request, location_id)
