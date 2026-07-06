import uuid
from urllib.parse import parse_qs

import jwt
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import StaffUser
from apps.buyers.models import Buyer, BuyerConversation, BuyerMessage

from .realtime import serialize_chat_message, vehicle_chat_group_name


class VehicleChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.vehicle_id = self.scope["url_route"]["kwargs"]["vehicle_id"]
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        token = self.get_token()
        self.actor_type, self.actor_id = await self.authenticate_token(token)
        if not self.actor_type:
            await self.close(code=4401)
            return

        self.conversation_id = await self.get_authorized_conversation_id()
        if not self.conversation_id:
            await self.close(code=4403)
            return

        self.group_name = vehicle_chat_group_name(self.conversation_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, _close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **_kwargs):
        body = str(content.get("message", "")).strip()
        if not body:
            await self.send_json({"type": "error", "detail": "Message is required."})
            return

        message = await self.create_message(body)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "message": message,
            },
        )

    async def chat_message(self, event):
        await self.send_json({"type": "message", "message": event["message"]})

    def get_token(self) -> str:
        for header_name, header_value in self.scope.get("headers", []):
            if header_name.lower() == b"authorization":
                value = header_value.decode("latin1").strip()
                if value.lower().startswith("bearer "):
                    return value[7:].strip()
        query = parse_qs(self.scope.get("query_string", b"").decode())
        return (query.get("token") or [""])[0].strip()

    @database_sync_to_async
    def authenticate_token(self, token):
        if not token:
            return None, None

        try:
            access = AccessToken(token)
            user = StaffUser.objects.get(id=access["user_id"], is_active=True)
            if user.dealer_id:
                return "dealer", user.id
        except Exception:
            pass

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            if payload.get("typ") != "buyer":
                return None, None
            buyer_id = uuid.UUID(payload["sub"])
            buyer = Buyer.objects.get(id=buyer_id)
            return "buyer", buyer.id
        except Exception:
            return None, None

    @database_sync_to_async
    def get_authorized_conversation_id(self):
        queryset = BuyerConversation.objects.filter(
            id=self.chat_id,
            vehicle_id=self.vehicle_id,
        )
        if self.actor_type == "dealer":
            queryset = queryset.filter(dealer__staff_users__id=self.actor_id)
        else:
            queryset = queryset.filter(buyer_id=self.actor_id)
        conversation = queryset.first()
        return conversation.id if conversation else None

    @database_sync_to_async
    def create_message(self, body: str) -> dict:
        sender_type = (
            BuyerMessage.SenderType.DEALER
            if self.actor_type == "dealer"
            else BuyerMessage.SenderType.BUYER
        )
        message = BuyerMessage.objects.create(
            conversation_id=self.conversation_id,
            sender_type=sender_type,
            body=body,
        )
        conversation = message.conversation
        conversation.last_message_at = message.created_at
        conversation.save(update_fields=["last_message_at", "updated_at"])
        if sender_type == BuyerMessage.SenderType.BUYER:
            from apps.notifications.services import notify_buyer_chat_message

            notify_buyer_chat_message(message)
        else:
            from apps.notifications.services import notify_buyer_inbound_chat_message

            notify_buyer_inbound_chat_message(message)
        return serialize_chat_message(message)
