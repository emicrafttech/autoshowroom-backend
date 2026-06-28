from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.buyers.auth import get_buyer_from_request
from apps.buyers.models import BuyerConversation, BuyerMessage
from apps.buyers.serializers import (
    BuyerConversationSerializer,
    OpenConversationSerializer,
    get_public_vehicle_or_error,
)
from apps.common.views import EnvelopeMixin

from .models import Vehicle
from .realtime import broadcast_chat_message


def authenticate_vehicle_chat_actor(request):
    user = getattr(request, "user", None)
    if (
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "dealer_id", None)
        and getattr(user, "is_active", False)
    ):
        return "dealer", user

    if not request.headers.get("Authorization", "").startswith("Bearer "):
        raise NotAuthenticated("Buyer or dealer bearer token is required.")

    try:
        authenticated = JWTAuthentication().authenticate(request)
    except Exception:
        authenticated = None

    if authenticated:
        user, _token = authenticated
        if getattr(user, "dealer_id", None) and getattr(user, "is_active", False):
            return "dealer", user
        raise PermissionDenied("Dealer staff credentials are required.")

    return "buyer", get_buyer_from_request(request)


def conversation_queryset():
    return BuyerConversation.objects.select_related(
        "buyer",
        "dealer",
        "vehicle",
        "vehicle__dealer",
        "vehicle__location",
        "vehicle__cover_media",
    ).prefetch_related("vehicle__media_items", "messages")


def scoped_vehicle_conversations(request, vehicle_id):
    actor_type, actor = authenticate_vehicle_chat_actor(request)
    queryset = conversation_queryset().filter(vehicle_id=vehicle_id)
    if actor_type == "dealer":
        get_object_or_404(Vehicle, id=vehicle_id, dealer_id=actor.dealer_id)
        return queryset.filter(dealer_id=actor.dealer_id), actor_type, actor

    get_object_or_404(Vehicle, id=vehicle_id)
    return queryset.filter(buyer=actor), actor_type, actor


class VehicleChatListCreateView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, vehicle_id):
        queryset, _actor_type, _actor = scoped_vehicle_conversations(request, vehicle_id)
        return Response(BuyerConversationSerializer(queryset, many=True).data)

    def post(self, request, vehicle_id):
        actor_type, buyer = authenticate_vehicle_chat_actor(request)
        if actor_type != "buyer":
            raise PermissionDenied("Only buyers can open a vehicle chat.")

        vehicle = get_public_vehicle_or_error(vehicle_id)
        serializer = OpenConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation, _created = BuyerConversation.objects.get_or_create(
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
            broadcast_chat_message(chat_message)
            from apps.notifications.services import notify_buyer_chat_message

            notify_buyer_chat_message(chat_message)
        return Response(BuyerConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class VehicleChatDetailView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, vehicle_id, chat_id):
        queryset, _actor_type, _actor = scoped_vehicle_conversations(request, vehicle_id)
        conversation = get_object_or_404(queryset, id=chat_id)
        return Response(BuyerConversationSerializer(conversation).data)


class VehicleChatMessageCreateView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, vehicle_id, chat_id):
        queryset, actor_type, _actor = scoped_vehicle_conversations(request, vehicle_id)
        conversation = get_object_or_404(queryset, id=chat_id)
        serializer = OpenConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data.get("message", "").strip()
        if message:
            chat_message = BuyerMessage.objects.create(
                conversation=conversation,
                sender_type=BuyerMessage.SenderType.DEALER
                if actor_type == "dealer"
                else BuyerMessage.SenderType.BUYER,
                body=message,
            )
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at", "updated_at"])
            broadcast_chat_message(chat_message)
            if chat_message.sender_type == BuyerMessage.SenderType.BUYER:
                from apps.notifications.services import notify_buyer_chat_message

                notify_buyer_chat_message(chat_message)
        return Response(BuyerConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)
