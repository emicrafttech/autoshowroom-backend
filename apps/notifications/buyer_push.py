from __future__ import annotations

from apps.buyers.models import BuyerPushDevice

from .fcm import send_multicast_notification


def list_buyer_fcm_tokens(buyer_id) -> list[str]:
    return list(
        BuyerPushDevice.objects.filter(buyer_id=buyer_id).values_list("fcm_token", flat=True)
    )


def send_buyer_push(
    *,
    buyer_id,
    title: str,
    body: str,
    data: dict[str, str],
) -> None:
    tokens = list_buyer_fcm_tokens(buyer_id)
    if not tokens:
        return
    send_multicast_notification(tokens, title=title, body=body, data=data)
