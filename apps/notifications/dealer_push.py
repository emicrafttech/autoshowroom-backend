from __future__ import annotations

from apps.accounts.push_devices import list_dealer_fcm_tokens

from .fcm import send_multicast_notification


def send_dealer_push(
    *,
    dealer_id,
    title: str,
    body: str,
    data: dict[str, str],
) -> None:
    tokens = list_dealer_fcm_tokens(dealer_id)
    if not tokens:
        return
    send_multicast_notification(tokens, title=title, body=body, data=data)
