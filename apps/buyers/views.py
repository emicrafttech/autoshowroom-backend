from django.conf import settings
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.views import EnvelopeMixin

from .auth import create_buyer_token, get_buyer_from_request
from .models import BuyerConversation, BuyerMessage, SavedVehicle, VehicleVisit
from .serializers import (
    BuyerProfileSerializer,
    BuyerConversationSerializer,
    BuyerSignInStartSerializer,
    BuyerSignInVerifySerializer,
    OpenConversationSerializer,
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
        serializer = BuyerSignInVerifySerializer(data=request.data)
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
        return Response({"token": create_buyer_token(buyer)})


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
        message = serializer.validated_data.get("message", "").strip()
        if message:
            chat_message = BuyerMessage.objects.create(
                conversation=conversation,
                sender_type=BuyerMessage.SenderType.BUYER,
                body=message,
            )
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at", "updated_at"])
            from apps.notifications.services import notify_buyer_chat_message

            notify_buyer_chat_message(chat_message)
        return Response(BuyerConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)
