from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.dealers.models import Dealer

from .models import StaffUser

EMAIL_SUSPENSION_REASON = "Email verification overdue."


@shared_task
def enforce_dealer_email_verification() -> dict[str, int]:
    grace_days = getattr(settings, "DEALER_EMAIL_VERIFICATION_GRACE_DAYS", 7)
    cutoff = timezone.now() - timedelta(days=grace_days)
    overdue_dealer_ids = (
        StaffUser.objects.filter(
            role=StaffUser.Role.OWNER,
            dealer__operational_status=Dealer.OperationalStatus.ACTIVE,
            email_verified_at__isnull=True,
            email_verification_required_at__lte=cutoff,
        )
        .exclude(email__endswith="@pending.autoshowroom.local")
        .values_list("dealer_id", flat=True)
        .distinct()
    )
    suspended = Dealer.objects.filter(id__in=overdue_dealer_ids).update(
        operational_status=Dealer.OperationalStatus.SUSPENDED,
        suspended_at=timezone.now(),
        suspended_reason=EMAIL_SUSPENSION_REASON,
        updated_at=timezone.now(),
    )

    verified_dealer_ids = (
        StaffUser.objects.filter(
            role=StaffUser.Role.OWNER,
            dealer__operational_status=Dealer.OperationalStatus.SUSPENDED,
            dealer__suspended_reason=EMAIL_SUSPENSION_REASON,
            email_verified_at__isnull=False,
        )
        .values_list("dealer_id", flat=True)
        .distinct()
    )
    reactivated = Dealer.objects.filter(id__in=verified_dealer_ids).update(
        operational_status=Dealer.OperationalStatus.ACTIVE,
        suspended_at=None,
        suspended_reason=None,
        updated_at=timezone.now(),
    )
    return {"suspended": suspended, "reactivated": reactivated}
