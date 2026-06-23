from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def vehicle_chat_group_name(chat_id) -> str:
    return f"vehicle_chat_{chat_id}"


def serialize_chat_message(message) -> dict:
    return {
        "id": str(message.id),
        "senderType": message.sender_type,
        "body": message.body,
        "createdAt": message.created_at.isoformat(),
    }


def broadcast_chat_message(message) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        vehicle_chat_group_name(message.conversation_id),
        {
            "type": "chat.message",
            "message": serialize_chat_message(message),
        },
    )
