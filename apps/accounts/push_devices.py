from django.utils import timezone

from .models import DealerPushDevice, StaffUser


def upsert_dealer_push_device(
    *,
    staff_user: StaffUser,
    fcm_token: str,
    platform: str,
) -> DealerPushDevice:
    normalized_token = fcm_token.strip()
    normalized_platform = platform.strip().lower() or DealerPushDevice.Platform.ANDROID
    if normalized_platform not in DealerPushDevice.Platform.values:
        normalized_platform = DealerPushDevice.Platform.ANDROID

    device, _ = DealerPushDevice.objects.update_or_create(
        staff_user=staff_user,
        fcm_token=normalized_token,
        defaults={
            "platform": normalized_platform,
            "last_seen_at": timezone.now(),
        },
    )
    return device


def delete_dealer_push_device(*, staff_user: StaffUser, fcm_token: str) -> None:
    DealerPushDevice.objects.filter(
        staff_user=staff_user,
        fcm_token=fcm_token.strip(),
    ).delete()


def list_dealer_fcm_tokens(dealer_id) -> list[str]:
    return list(
        DealerPushDevice.objects.filter(
            staff_user__dealer_id=dealer_id,
            staff_user__is_active=True,
        ).values_list("fcm_token", flat=True)
    )
