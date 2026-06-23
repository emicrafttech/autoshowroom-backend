from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import StaffUser
from apps.accounts.tokens import generate_invite_token, hash_invite_token, invite_expiry
from apps.buyers.models import BuyerConversation, BuyerMessage
from apps.buyers.serializers import BuyerConversationSerializer, OpenConversationSerializer
from apps.common.permissions import IsDealerStaff
from apps.common.views import EnvelopeMixin
from apps.platform.models import DataSubjectRequest, DealerSanction, SanctionAppeal
from apps.platform.views import IsPlatformStaff, write_audit

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
        serializer = DealerProfileSerializer(
            self.get_object(),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DealerContextView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

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
    permission_classes = [IsDealerStaff]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return DealerLocation.objects.filter(dealer_id=self.request.user.dealer_id)

    def perform_create(self, serializer):
        dealer = get_object_or_404(Dealer, id=self.request.user.dealer_id)
        is_first_location = not dealer.locations.exists()
        serializer.save(dealer=dealer, is_primary=is_first_location)

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


class DealerStaffViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = DealerStaffSerializer
    permission_classes = [IsDealerStaff]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return StaffUser.objects.filter(dealer_id=self.request.user.dealer_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["dealer"] = self.request.user.dealer
        return context

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

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
        return Response(DealerStaffSerializer(user).data)


class DealerChatViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = BuyerConversationSerializer
    permission_classes = [IsDealerStaff]

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
            BuyerMessage.objects.create(
                conversation=conversation,
                sender_type=BuyerMessage.SenderType.DEALER,
                body=body,
            )
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at", "updated_at"])
        return Response(BuyerConversationSerializer(conversation).data)


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
        dealer = self.get_dealer(request)
        dealer.verification_status = Dealer.VerificationStatus.PENDING
        dealer.save(update_fields=["verification_status", "updated_at"])
        return Response(DealerVerificationSerializer(dealer).data)


class DealerVerificationDocumentView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def post(self, request):
        serializer = DealerVerificationDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(dealer=request.user.dealer)
        return Response(
            DealerVerificationDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )


class DealerSanctionStatusView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

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
    permission_classes = [IsDealerStaff]

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
        return Response({"id": str(appeal.id), "status": appeal.status}, status=status.HTTP_201_CREATED)


class DealerPrivacyRequestView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

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
        return Response(self.get_serializer(dealer).data)
