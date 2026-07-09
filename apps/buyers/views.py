from datetime import timedelta
import mimetypes

from django.conf import settings
from django.utils import timezone
from uuid import uuid4
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.client_platform import buyer_token_ttl_seconds, is_mobile_client
from apps.common.views import EnvelopeMixin
from apps.vehicles.storage import create_presigned_upload

from .auth import create_buyer_token, get_buyer_from_request
from .chat_service import create_chat_attachment_upload_session, create_conversation_message
from .models import BuyerConversation, BuyerMessage, BlockedDealer, PriceAlert, SavedVehicle, VehicleVisit
from .price_alerts import serialize_price_alerts_summary
from .serializers import (
    BlockedDealerSerializer,
    BuyerProfileSerializer,
    BuyerConversationSerializer,
    BuyerMessageInputSerializer,
    BuyerSignInStartSerializer,
    BuyerSignInVerifySerializer,
    OpenConversationSerializer,
    PriceAlertSerializer,
    PriceAlertUpdateSerializer,
    SavedVehicleSerializer,
    VehicleVisitSerializer,
    get_public_vehicle_or_error,
)


class BuyerSignInStartView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = BuyerSignInStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.save()
        data = {"expiresAt": otp.expires_at}
        if settings.DEBUG:
            data["devCode"] = otp.code
        return Response(data, status=status.HTTP_201_CREATED)


class BuyerSignInVerifyView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = BuyerSignInVerifySerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                "buyer": BuyerProfileSerializer(result["buyer"]).data,
                "token": result["token"],
            }
        )


class BuyerSessionRefreshView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        buyer = get_buyer_from_request(request)
        return Response(
            {
                "buyer": BuyerProfileSerializer(buyer).data,
                "token": create_buyer_token(
                    buyer,
                    ttl_seconds=buyer_token_ttl_seconds(
                        mobile=is_mobile_client(request)
                    ),
                ),
            }
        )


class BuyerProfileView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        buyer = get_buyer_from_request(request)
        return Response(BuyerProfileSerializer(buyer).data)

    def patch(self, request):
        buyer = get_buyer_from_request(request)
        serializer = BuyerProfileSerializer(buyer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BuyerProfilePhotoUploadSessionView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        buyer = get_buyer_from_request(request)
        content_type = (request.data.get("contentType") or "").strip().lower()
        file_name = (request.data.get("fileName") or "").strip()

        if not content_type.startswith("image/"):
            raise ValidationError(
                {"contentType": "Photo must use an image content type."}
            )

        suffix = ""
        if file_name and "." in file_name:
            candidate = "." + file_name.rsplit(".", 1)[-1].lower()
            if len(candidate) <= 8 and candidate.isascii():
                suffix = candidate
        if not suffix:
            suffix = mimetypes.guess_extension(content_type) or ".jpg"

        key = f"buyer-photos/{buyer.id}/{uuid4().hex}{suffix}"
        upload = create_presigned_upload(key, content_type)
        expires_at = timezone.now() + timedelta(
            seconds=settings.MEDIA_UPLOAD_URL_EXPIRES_SECONDS
        )
        return Response(
            {
                "uploadUrl": upload.upload_url,
                "publicUrl": upload.public_url,
                "s3Key": upload.key,
                "expiresAt": expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class BuyerSavedVehiclesView(EnvelopeMixin, generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = SavedVehicleSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        buyer = get_buyer_from_request(self.request)
        return SavedVehicle.objects.filter(buyer=buyer).select_related(
            "vehicle",
            "vehicle__dealer",
            "vehicle__location",
            "vehicle__cover_media",
        ).prefetch_related("vehicle__media_items")


class BuyerSavedVehicleActionView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, vehicle_id):
        buyer = get_buyer_from_request(request)
        vehicle = get_public_vehicle_or_error(vehicle_id)
        saved, _ = SavedVehicle.objects.get_or_create(buyer=buyer, vehicle=vehicle)
        return Response(SavedVehicleSerializer(saved).data, status=status.HTTP_201_CREATED)

    def delete(self, request, vehicle_id):
        buyer = get_buyer_from_request(request)
        SavedVehicle.objects.filter(buyer=buyer, vehicle_id=vehicle_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BuyerVisitsView(EnvelopeMixin, generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = VehicleVisitSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        buyer = get_buyer_from_request(self.request)
        return VehicleVisit.objects.filter(buyer=buyer).select_related(
            "vehicle",
            "vehicle__dealer",
            "vehicle__location",
            "vehicle__cover_media",
        ).prefetch_related("vehicle__media_items")


class BuyerChatListView(EnvelopeMixin, generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = BuyerConversationSerializer

    def get_queryset(self):
        buyer = get_buyer_from_request(self.request)
        return BuyerConversation.objects.filter(buyer=buyer).select_related(
            "dealer",
            "vehicle",
            "vehicle__dealer",
            "vehicle__location",
            "vehicle__cover_media",
        ).prefetch_related("vehicle__media_items", "messages")


class BuyerOpenChatView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, vehicle_id):
        buyer = get_buyer_from_request(request)
        vehicle = get_public_vehicle_or_error(vehicle_id)
        serializer = OpenConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation, _ = BuyerConversation.objects.get_or_create(
            buyer=buyer,
            dealer=vehicle.dealer,
            vehicle=vehicle,
        )
        from apps.leads.services import sync_lead_from_buyer_chat

        sync_lead_from_buyer_chat(buyer=buyer, vehicle=vehicle)
        message = serializer.validated_data.get("message", "").strip()
        attachment_url = serializer.validated_data.get("attachmentUrl", "").strip()
        if message or attachment_url:
            create_conversation_message(
                conversation,
                sender_type=BuyerMessage.SenderType.BUYER,
                body=message,
                attachment_url=attachment_url,
            )
        return Response(BuyerConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class BuyerChatDetailView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, conversation_id):
        buyer = get_buyer_from_request(request)
        conversation = BuyerConversation.objects.filter(
            id=conversation_id,
            buyer=buyer,
        ).select_related("dealer", "vehicle", "vehicle__dealer", "vehicle__location").first()
        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(BuyerConversationSerializer(conversation).data)


class BuyerChatMarkReadView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, conversation_id):
        buyer = get_buyer_from_request(request)
        conversation = BuyerConversation.objects.filter(
            id=conversation_id,
            buyer=buyer,
        ).select_related(
            "dealer",
            "vehicle",
            "vehicle__dealer",
            "vehicle__location",
        ).first()
        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        conversation.buyer_last_read_at = timezone.now()
        conversation.save(update_fields=["buyer_last_read_at", "updated_at"])
        return Response(BuyerConversationSerializer(conversation).data)


class BuyerChatMessageView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, conversation_id):
        buyer = get_buyer_from_request(request)
        conversation = BuyerConversation.objects.filter(
            id=conversation_id,
            buyer=buyer,
        ).first()
        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = BuyerMessageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        create_conversation_message(
            conversation,
            sender_type=BuyerMessage.SenderType.BUYER,
            body=serializer.validated_data["body"],
            attachment_url=serializer.validated_data["attachmentUrl"],
        )
        return Response(
            BuyerConversationSerializer(conversation).data,
            status=status.HTTP_201_CREATED,
        )


class BuyerChatAttachmentUploadSessionView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, conversation_id):
        buyer = get_buyer_from_request(request)
        conversation = BuyerConversation.objects.filter(
            id=conversation_id,
            buyer=buyer,
        ).first()
        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        content_type = (request.data.get("contentType") or "").strip()
        file_name = (request.data.get("fileName") or "").strip()
        payload = create_chat_attachment_upload_session(
            conversation_id=conversation.id,
            content_type=content_type,
            file_name=file_name,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class BuyerPriceAlertsView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        buyer = get_buyer_from_request(request)
        return Response(serialize_price_alerts_summary(buyer, request=request))

    def post(self, request):
        buyer = get_buyer_from_request(request)
        serializer = PriceAlertSerializer(
            data=request.data,
            context={"buyer": buyer, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()
        summary = serialize_price_alerts_summary(buyer, request=request)
        summary["createdAlertId"] = str(alert.id)
        return Response(summary, status=status.HTTP_201_CREATED)


class BuyerPriceAlertDetailView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def patch(self, request, alert_id):
        buyer = get_buyer_from_request(request)
        alert = PriceAlert.objects.filter(id=alert_id, buyer=buyer).first()
        if not alert:
            return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PriceAlertUpdateSerializer(alert, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serialize_price_alerts_summary(buyer, request=request))

    def delete(self, request, alert_id):
        buyer = get_buyer_from_request(request)
        deleted, _ = PriceAlert.objects.filter(id=alert_id, buyer=buyer).delete()
        if not deleted:
            return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_price_alerts_summary(buyer, request=request))


class BuyerBlockedDealersView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        buyer = get_buyer_from_request(request)
        blocked = BlockedDealer.objects.filter(buyer=buyer).select_related("dealer")
        return Response(BlockedDealerSerializer(blocked, many=True).data)

    def post(self, request):
        from apps.dealers.models import Dealer

        buyer = get_buyer_from_request(request)
        dealer_slug = (request.data.get("dealerSlug") or "").strip()
        if not dealer_slug:
            raise ValidationError({"dealerSlug": "Dealer slug is required."})
        dealer = Dealer.objects.filter(slug=dealer_slug).first()
        if not dealer:
            raise ValidationError({"dealerSlug": "Dealer not found."})
        blocked, _ = BlockedDealer.objects.get_or_create(buyer=buyer, dealer=dealer)
        return Response(
            BlockedDealerSerializer(blocked).data,
            status=status.HTTP_201_CREATED,
        )


class BuyerBlockedDealerDetailView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def delete(self, request, dealer_slug):
        buyer = get_buyer_from_request(request)
        deleted, _ = BlockedDealer.objects.filter(
            buyer=buyer,
            dealer__slug=dealer_slug,
        ).delete()
        if not deleted:
            return Response({"detail": "Blocked dealer not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BuyerPushTokenView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def put(self, request):
        from .push_devices import upsert_buyer_push_device

        buyer = get_buyer_from_request(request)
        fcm_token = (request.data.get("token") or "").strip()
        platform = (request.data.get("platform") or "android").strip().lower()
        if not fcm_token:
            raise ValidationError({"token": "FCM token is required."})

        device = upsert_buyer_push_device(
            buyer=buyer,
            fcm_token=fcm_token,
            platform=platform,
        )
        return Response(
            {
                "id": str(device.id),
                "platform": device.platform,
                "lastSeenAt": device.last_seen_at,
            }
        )

    def delete(self, request):
        from .push_devices import delete_buyer_push_device

        buyer = get_buyer_from_request(request)
        fcm_token = (request.data.get("token") or "").strip()
        if not fcm_token:
            raise ValidationError({"token": "FCM token is required."})
        delete_buyer_push_device(buyer=buyer, fcm_token=fcm_token)
        return Response(status=status.HTTP_204_NO_CONTENT)
