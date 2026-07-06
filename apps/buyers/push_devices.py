from django.utils import timezone

from apps.buyers.models import Buyer, BuyerPushDevice


def upsert_buyer_push_device(
    *,
    buyer: Buyer,
    fcm_token: str,
    platform: str,
) -> BuyerPushDevice:
    normalized_token = fcm_token.strip()
    normalized_platform = platform.strip().lower() or BuyerPushDevice.Platform.ANDROID
    if normalized_platform not in BuyerPushDevice.Platform.values:
        normalized_platform = BuyerPushDevice.Platform.ANDROID

    device, _ = BuyerPushDevice.objects.update_or_create(
        buyer=buyer,
        fcm_token=normalized_token,
        defaults={
            "platform": normalized_platform,
            "last_seen_at": timezone.now(),
        },
    )
    return device


def delete_buyer_push_device(*, buyer: Buyer, fcm_token: str) -> None:
    BuyerPushDevice.objects.filter(
        buyer=buyer,
        fcm_token=fcm_token.strip(),
    ).delete()
