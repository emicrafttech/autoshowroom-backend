from apps.accounts.models import StaffUser
from apps.common.permissions import has_platform_capability
from apps.dealers.models import Dealer
from apps.platform.models import ContentReport, SanctionAppeal
from apps.vehicles.models import Vehicle

from .models import PlatformNotification


def _platform_recipients(capability: str, *, exclude_user=None) -> list[StaffUser]:
    queryset = StaffUser.objects.filter(
        is_active=True,
        is_staff=True,
        dealer_id__isnull=True,
    ).select_related("platform_role")
    if exclude_user:
        queryset = queryset.exclude(id=exclude_user.id)

    recipients: list[StaffUser] = []
    for user in queryset:
        if has_platform_capability(user, capability):
            recipients.append(user)
    return recipients


def notify_platform_staff(
    capability: str,
    *,
    notification_type: str,
    title: str,
    body: str,
    href: str = "",
    dealer: Dealer | None = None,
    vehicle: Vehicle | None = None,
    exclude_user=None,
) -> list[PlatformNotification]:
    recipients = _platform_recipients(capability, exclude_user=exclude_user)
    if not recipients:
        return []

    notifications = [
        PlatformNotification(
            recipient=recipient,
            type=notification_type,
            title=title,
            body=body,
            href=href,
            dealer=dealer,
            vehicle=vehicle,
        )
        for recipient in recipients
    ]
    return PlatformNotification.objects.bulk_create(notifications)


def _vehicle_title(vehicle: Vehicle) -> str:
    return f"{vehicle.year} {vehicle.make} {vehicle.model}".strip()


def notify_listing_review_submitted(vehicle: Vehicle) -> list[PlatformNotification]:
    dealer_name = vehicle.dealer.name if vehicle.dealer_id else "A dealer"
    return notify_platform_staff(
        "listing_review.read",
        notification_type=PlatformNotification.Type.LISTING_REVIEW_SUBMITTED,
        title="Listing submitted for review",
        body=f"{dealer_name} submitted {_vehicle_title(vehicle)} for review.",
        href="/listings/review",
        dealer=vehicle.dealer,
        vehicle=vehicle,
    )


def notify_dealer_verification_submitted(dealer: Dealer) -> list[PlatformNotification]:
    return notify_platform_staff(
        "dealer_verification.read",
        notification_type=PlatformNotification.Type.DEALER_VERIFICATION_SUBMITTED,
        title="Dealer verification submitted",
        body=f"{dealer.name} submitted verification documents for review.",
        href="/verification",
        dealer=dealer,
    )


def notify_content_report_filed(report: ContentReport) -> list[PlatformNotification]:
    vehicle_label = ""
    if report.vehicle_id:
        vehicle = report.vehicle
        vehicle_label = f" for {_vehicle_title(vehicle)}" if vehicle else ""
    return notify_platform_staff(
        "content_reports.read",
        notification_type=PlatformNotification.Type.CONTENT_REPORT_FILED,
        title="New content report",
        body=f"A buyer reported a listing{vehicle_label}.",
        href="/disputes",
        dealer=report.vehicle.dealer if report.vehicle_id and report.vehicle else None,
        vehicle=report.vehicle if report.vehicle_id else None,
    )


def notify_sanction_appeal_submitted(appeal: SanctionAppeal) -> list[PlatformNotification]:
    return notify_platform_staff(
        "sanctions.read",
        notification_type=PlatformNotification.Type.SANCTION_APPEAL_SUBMITTED,
        title="Sanction appeal submitted",
        body=f"{appeal.dealer.name} submitted an appeal against a sanction.",
        href="/appeals",
        dealer=appeal.dealer,
    )
