import mimetypes
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.vehicles.realtime import broadcast_chat_message
from apps.vehicles.storage import create_presigned_upload

from .models import BuyerConversation, BuyerMessage


def build_chat_attachment_key(conversation_id, file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    safe_suffix = suffix if suffix and len(suffix) <= 8 else ""
    if not safe_suffix:
        safe_suffix = ".jpg"
    return f"chat-attachments/{conversation_id}/{uuid4().hex}{safe_suffix}"


def create_chat_attachment_upload_session(
    *,
    conversation_id,
    content_type: str,
    file_name: str,
) -> dict:
    normalized_type = content_type.strip().lower()
    if not normalized_type.startswith("image/"):
        raise ValidationError({"contentType": "Chat attachments must be images."})

    suffix = ""
    if file_name and "." in file_name:
        candidate = "." + file_name.rsplit(".", 1)[-1].lower()
        if len(candidate) <= 8 and candidate.isascii():
            suffix = candidate
    if not suffix:
        suffix = mimetypes.guess_extension(normalized_type) or ".jpg"

    key = f"chat-attachments/{conversation_id}/{uuid4().hex}{suffix}"
    upload = create_presigned_upload(key, normalized_type)
    expires_at = timezone.now() + timedelta(
        seconds=settings.MEDIA_UPLOAD_URL_EXPIRES_SECONDS
    )
    return {
        "uploadUrl": upload.upload_url,
        "publicUrl": upload.public_url,
        "s3Key": upload.key,
        "expiresAt": expires_at.isoformat(),
    }


def create_conversation_message(
    conversation: BuyerConversation,
    *,
    sender_type: str,
    body: str = "",
    attachment_url: str = "",
) -> BuyerMessage:
    normalized_body = body.strip()
    normalized_attachment = attachment_url.strip()
    if not normalized_body and not normalized_attachment:
        raise ValidationError("Message text or an image attachment is required.")

    message = BuyerMessage.objects.create(
        conversation=conversation,
        sender_type=sender_type,
        body=normalized_body,
        attachment_url=normalized_attachment,
    )
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=["last_message_at", "updated_at"])
    broadcast_chat_message(message)
    if sender_type == BuyerMessage.SenderType.BUYER:
        from apps.notifications.services import notify_buyer_chat_message

        notify_buyer_chat_message(message)
        if conversation.vehicle_id and conversation.buyer_id:
            from apps.leads.services import sync_lead_from_buyer_chat

            sync_lead_from_buyer_chat(
                buyer=conversation.buyer,
                vehicle=conversation.vehicle,
                message=normalized_body,
            )
    elif sender_type == BuyerMessage.SenderType.DEALER:
        from apps.notifications.services import notify_buyer_inbound_chat_message

        notify_buyer_inbound_chat_message(message)
    return message
