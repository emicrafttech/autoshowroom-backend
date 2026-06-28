from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import StaffUser
from apps.accounts.tokens import generate_invite_token, hash_invite_token, invite_expiry
from apps.billing.limits import get_stand_limit
from apps.buyers.models import BuyerConversation, BuyerMessage
from apps.buyers.serializers import (
    DealerConversationSerializer,
    OpenConversationSerializer,
)
from apps.common.permissions import IsActiveDealerStaff, IsDealerStaff
from apps.common.views import EnvelopeMixin
from apps.platform.models import DataSubjectRequest, DealerSanction, SanctionAppeal
from apps.platform.views import IsPlatformStaff, write_audit
from apps.vehicles.realtime import broadcast_chat_message

from .models import Dealer, DealerLocation, DealerVerificationDocument
from .serializers import (
    DealerContextLocationSerializer,
    DealerLocationSerializer,
    DealerProfileSerializer,
    DealerSelfServiceRequestSerializer,
    DealerStaffSerializer,
    DealerVerificationDocumentSerializer,
    DealerVerificationSerializer,
)


class DealerProfileView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def get_object(self):
        return get_object_or_404(
            Dealer.objects.prefetch_related("locations"),
            id=self.request.user.dealer_id,
        )

    def get(self, request):
        return Response(DealerProfileSerializer(self.get_object()).data)

    def patch(self, request):
        if request.user.dealer.operational_status != Dealer.OperationalStatus.ACTIVE:
            raise ValidationError("Verify your email to reactivate your dealer account before making changes.")
        serializer = DealerProfileSerializer(
            self.get_object(),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DealerContextView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def get(self, request):
        dealer = get_object_or_404(
            Dealer.objects.prefetch_related("locations"),
            id=request.user.dealer_id,
        )
        active_location = request.user.preferred_location
        if active_location and active_location.dealer_id != dealer.id:
            active_location = None
        if active_location is None:
            active_location = dealer.locations.filter(is_primary=True).first()

        return Response(
            {
                "dealerName": dealer.name,
                "activeLocationId": str(active_location.id)
                if active_location
                else None,
                "locations": DealerContextLocationSerializer(
                    dealer.locations.all(),
                    many=True,
                ).data,
            }
        )


class DealerLocationViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = DealerLocationSerializer
    permission_classes = [IsActiveDealerStaff]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return DealerLocation.objects.filter(dealer_id=self.request.user.dealer_id)

    def perform_create(self, serializer):
        dealer = get_object_or_404(Dealer, id=self.request.user.dealer_id)
        stand_limit = get_stand_limit(dealer)
        if dealer.locations.count() >= stand_limit:
            raise ValidationError(
                {
                    "detail": "Your current plan has reached its stand limit.",
                    "standLimit": stand_limit,
                }
            )
        is_first_location = not dealer.locations.exists()
        evidence_files = serializer.validated_data.get("evidence_files", [])
        has_kyd_premises_proof = DealerVerificationDocument.objects.filter(
            dealer=dealer,
            kind=DealerVerificationDocument.Kind.PREMISES,
        ).exists()
        serializer.save(
            dealer=dealer,
            is_primary=is_first_location,
            premises_verification_status=(
                DealerLocation.PremisesVerificationStatus.PENDING
                if evidence_files or (is_first_location and has_kyd_premises_proof)
                else DealerLocation.PremisesVerificationStatus.NOT_SUBMITTED
            ),
        )

    def perform_update(self, serializer):
        location = serializer.save()
        if location.evidence_files and location.premises_verification_status in [
            DealerLocation.PremisesVerificationStatus.NOT_SUBMITTED,
            DealerLocation.PremisesVerificationStatus.REJECTED,
        ]:
            location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
            location.premises_rejected_at = None
            location.premises_rejection_reason = None
            location.save(
                update_fields=[
                    "premises_verification_status",
                    "premises_rejected_at",
                    "premises_rejection_reason",
                    "updated_at",
                ]
            )

    def primary_location_has_kyd_premises_proof(self, location):
        return bool(
            location.is_primary
            and DealerVerificationDocument.objects.filter(
                dealer=location.dealer,
                kind=DealerVerificationDocument.Kind.PREMISES,
            ).exists()
        )

    def perform_destroy(self, instance):
        if instance.is_primary and self.get_queryset().exclude(id=instance.id).exists():
            replacement = self.get_queryset().exclude(id=instance.id).first()
            with transaction.atomic():
                instance.delete()
                replacement.is_primary = True
                replacement.save(update_fields=["is_primary", "updated_at"])
            return
        instance.delete()

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        location = self.get_object()
        with transaction.atomic():
            self.get_queryset().update(is_primary=False)
            location.is_primary = True
            location.save(update_fields=["is_primary", "updated_at"])
            request.user.preferred_location = location
            request.user.save(update_fields=["preferred_location", "updated_at"])

        return Response(
            DealerLocationSerializer(location).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="request-verification")
    def request_verification(self, request, pk=None):
        location = self.get_object()
        if not location.evidence_files and not self.primary_location_has_kyd_premises_proof(location):
            raise ValidationError({"evidenceFiles": "Upload at least one premises image before requesting verification."})
        location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
        location.premises_rejected_at = None
        location.premises_rejection_reason = None
        location.save(
            update_fields=[
                "premises_verification_status",
                "premises_rejected_at",
                "premises_rejection_reason",
                "updated_at",
            ]
        )
        return Response(DealerLocationSerializer(location).data)


def _can_deactivate_staff(actor: StaffUser, target: StaffUser) -> bool:
    """Role hierarchy for deactivating team members.

    owner  -> any member (managers, sales, other owners)
    manager -> sales only
    sales  -> nobody
    """
    if actor.role == StaffUser.Role.OWNER:
        return True
    if actor.role == StaffUser.Role.MANAGER:
        return target.role == StaffUser.Role.SALES
    return False


class DealerStaffViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = DealerStaffSerializer
    permission_classes = [IsActiveDealerStaff]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return StaffUser.objects.filter(dealer_id=self.request.user.dealer_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["dealer"] = self.request.user.dealer
        return context

    def perform_destroy(self, instance):
        actor = self.request.user
        if instance.id == actor.id:
            raise ValidationError({"detail": "You cannot deactivate your own account."})
        if not _can_deactivate_staff(actor, instance):
            raise PermissionDenied(
                {"detail": "You do not have permission to deactivate this team member."}
            )
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    def perform_update(self, serializer):
        instance = serializer.instance
        actor = self.request.user
        new_is_active = serializer.validated_data.get("is_active", None)
        if new_is_active is not None and new_is_active != instance.is_active:
            if instance.id == actor.id:
                raise ValidationError({"detail": "You cannot change your own active state."})
            if not _can_deactivate_staff(actor, instance):
                raise PermissionDenied(
                    {"detail": "You do not have permission to change this team member's status."}
                )
        serializer.save()

    def perform_create(self, serializer):
        user = serializer.save()
        token = getattr(user, "inviteToken", None)
        if token:
            from apps.notifications.services import notify_staff_invite

            notify_staff_invite(user, token, portal="dealer")

    @action(detail=True, methods=["post"], url_path="resend-invite")
    def resend_invite(self, request, pk=None):
        user = self.get_object()
        token = generate_invite_token()
        user.invite_token_hash = hash_invite_token(token)
        user.invite_expires_at = invite_expiry()
        user.must_change_password = True
        user.save(
            update_fields=[
                "invite_token_hash",
                "invite_expires_at",
                "must_change_password",
                "updated_at",
            ]
        )
        user.inviteToken = token
        from apps.notifications.services import notify_staff_invite

        notify_staff_invite(user, token, portal="dealer")
        return Response(DealerStaffSerializer(user).data)


class DealerChatViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = DealerConversationSerializer
    permission_classes = [IsActiveDealerStaff]

    def get_queryset(self):
        queryset = BuyerConversation.objects.filter(
            dealer_id=self.request.user.dealer_id,
        ).select_related(
            "buyer",
            "dealer",
            "vehicle",
            "vehicle__dealer",
            "vehicle__location",
            "vehicle__cover_media",
        ).prefetch_related("vehicle__media_items", "messages")
        vehicle_id = self.request.query_params.get("vehicleId")
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        return queryset

    @action(detail=True, methods=["post"], url_path="respond")
    def respond(self, request, pk=None):
        conversation = self.get_object()
        serializer = OpenConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data.get("message", "").strip()
        if body:
            chat_message = BuyerMessage.objects.create(
                conversation=conversation,
                sender_type=BuyerMessage.SenderType.DEALER,
                body=body,
            )
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at", "updated_at"])
            broadcast_chat_message(chat_message)
        return Response(DealerConversationSerializer(conversation).data)


class DealerSelfVerificationView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def get_dealer(self, request):
        return get_object_or_404(
            Dealer.objects.prefetch_related("locations", "verification_documents"),
            id=request.user.dealer_id,
        )

    def get(self, request):
        return Response(DealerVerificationSerializer(self.get_dealer(request)).data)

    def post(self, request, action_name=None):
        if request.user.dealer.operational_status != Dealer.OperationalStatus.ACTIVE:
            raise ValidationError("Verify your email to reactivate your dealer account before making changes.")
        dealer = self.get_dealer(request)
        dealer.verification_status = Dealer.VerificationStatus.PENDING
        dealer.save(update_fields=["verification_status", "updated_at"])
        from apps.notifications.platform_notifications import notify_dealer_verification_submitted

        notify_dealer_verification_submitted(dealer)
        return Response(DealerVerificationSerializer(dealer).data)


class DealerVerificationDocumentView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]
    document_titles = {
        DealerVerificationDocument.Kind.CAC: "Business registration",
        DealerVerificationDocument.Kind.IDENTITY: "Dealer identity",
        DealerVerificationDocument.Kind.PREMISES: "Premises proof",
        DealerVerificationDocument.Kind.TAX: "Tax and compliance",
    }

    def post(self, request):
        serializer = DealerVerificationDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]
        document, _ = DealerVerificationDocument.objects.update_or_create(
            dealer=request.user.dealer,
            kind=kind,
            defaults={
                "title": self.document_titles.get(kind, serializer.validated_data["title"]),
                "file_url": serializer.validated_data["file_url"],
                "status": DealerVerificationDocument.Status.PENDING,
                "rejection_reason": "",
                "reviewed_at": None,
            },
        )
        dealer = request.user.dealer
        dealer.verification_status = Dealer.VerificationStatus.PENDING
        dealer.verified_badge = False
        dealer.save(update_fields=["verification_status", "verified_badge", "updated_at"])
        if kind == DealerVerificationDocument.Kind.PREMISES:
            primary_location = dealer.locations.filter(is_primary=True).first()
            if primary_location and primary_location.premises_verification_status in [
                DealerLocation.PremisesVerificationStatus.NOT_SUBMITTED,
                DealerLocation.PremisesVerificationStatus.REJECTED,
            ]:
                primary_location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
                primary_location.premises_rejected_at = None
                primary_location.premises_rejection_reason = None
                primary_location.save(
                    update_fields=[
                        "premises_verification_status",
                        "premises_rejected_at",
                        "premises_rejection_reason",
                        "updated_at",
                    ]
                )
        return Response(
            DealerVerificationDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )


class DealerSanctionStatusView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def get(self, request):
        sanctions = DealerSanction.objects.filter(
            dealer_id=request.user.dealer_id,
            status=DealerSanction.Status.ACTIVE,
        )
        return Response(
            {
                "hasActiveSanction": sanctions.exists(),
                "sanctions": [
                    {
                        "id": str(item.id),
                        "reason": item.reason,
                        "createdAt": item.created_at.isoformat(),
                    }
                    for item in sanctions
                ],
            }
        )


class DealerSanctionAppealView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def post(self, request):
        serializer = DealerSelfServiceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sanction = DealerSanction.objects.filter(
            dealer_id=request.user.dealer_id,
            status=DealerSanction.Status.ACTIVE,
        ).first()
        appeal = SanctionAppeal.objects.create(
            dealer=request.user.dealer,
            sanction=sanction,
            reason=serializer.validated_data["reason"],
        )
        from apps.notifications.platform_notifications import notify_sanction_appeal_submitted

        notify_sanction_appeal_submitted(appeal)
        return Response({"id": str(appeal.id), "status": appeal.status}, status=status.HTTP_201_CREATED)


class DealerPrivacyRequestView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def post(self, request):
        serializer = DealerSelfServiceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dsr = DataSubjectRequest.objects.create(
            dealer=request.user.dealer,
            requester_name=request.user.name,
            requester_contact=request.user.email,
            request_type="dealer_privacy",
            notes=serializer.validated_data["reason"],
        )
        return Response({"id": str(dsr.id), "status": dsr.status}, status=status.HTTP_201_CREATED)


class DealerDeleteAccountView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def post(self, request):
        dealer = request.user.dealer
        with transaction.atomic():
            dealer.operational_status = Dealer.OperationalStatus.SUSPENDED
            dealer.suspended_at = timezone.now()
            dealer.suspended_reason = "Account deleted by dealer."
            dealer.save(update_fields=["operational_status", "suspended_at", "suspended_reason", "updated_at"])
            StaffUser.objects.filter(dealer=dealer).update(is_active=False, updated_at=timezone.now())
        write_audit(request.user, "dealer.account_deleted", dealer)
        return Response({"status": "deleted"}, status=status.HTTP_200_OK)


class DealerVerificationViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = DealerProfileSerializer
    permission_classes = [IsPlatformStaff]
    queryset = Dealer.objects.prefetch_related("locations")

    @action(detail=True, methods=["patch"], url_path="verification/approve")
    def approve_verification(self, request, pk=None):
        dealer = self.get_object()
        dealer.verification_status = Dealer.VerificationStatus.APPROVED
        dealer.verified_badge = True
        dealer.verified_at = timezone.now()
        dealer.save(update_fields=["verification_status", "verified_badge", "verified_at", "updated_at"])
        write_audit(request.user, "dealer.verification.approved", dealer)
        from apps.notifications.services import notify_dealer_verification_approved

        notify_dealer_verification_approved(dealer)
        return Response(self.get_serializer(dealer).data)

    @action(detail=True, methods=["patch"], url_path="verification/reject")
    def reject_verification(self, request, pk=None):
        dealer = self.get_object()
        reason = request.data.get("reason", "").strip()
        if not reason:
            raise ValidationError({"reason": "A rejection reason is required."})
        dealer.verification_status = Dealer.VerificationStatus.REJECTED
        dealer.verified_badge = False
        dealer.save(update_fields=["verification_status", "verified_badge", "updated_at"])
        write_audit(request.user, "dealer.verification.rejected", dealer, {"reason": reason})
        from apps.notifications.services import notify_dealer_verification_rejected

        notify_dealer_verification_rejected(dealer, reason)
        return Response(self.get_serializer(dealer).data)

    @action(detail=True, methods=["patch"], url_path="verification/request-info")
    def request_verification_info(self, request, pk=None):
        dealer = self.get_object()
        reason = request.data.get("reason", "").strip()
        if not reason:
            raise ValidationError({"reason": "A request reason is required."})
        write_audit(request.user, "dealer.verification.info_requested", dealer, {"reason": reason})
        from apps.notifications.services import notify_dealer_verification_info_requested

        notify_dealer_verification_info_requested(dealer, reason)
        return Response(self.get_serializer(dealer).data)
