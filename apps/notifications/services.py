from apps.accounts.models import StaffUser
from apps.vehicles.models import Vehicle, VehicleReviewIssue

from .models import DealerNotification
from .tasks import send_vehicle_review_issue_email


def notify_review_issue(vehicle: Vehicle, issue: VehicleReviewIssue) -> list[DealerNotification]:
    recipients = StaffUser.objects.filter(
        dealer=vehicle.dealer,
        is_active=True,
        email__isnull=False,
    ).exclude(email="")
    vehicle_title = f"{vehicle.year} {vehicle.make} {vehicle.model}"
    notifications = [
        DealerNotification(
            dealer=vehicle.dealer,
            recipient=recipient,
            vehicle=vehicle,
            review_issue=issue,
            type=DealerNotification.Type.REVIEW_ISSUE,
            title="Listing review issue",
            body=f"{vehicle_title}: {issue.message}",
        )
        for recipient in recipients
    ]
    created = DealerNotification.objects.bulk_create(notifications)
    for recipient in recipients:
        send_vehicle_review_issue_email.delay(recipient.email, vehicle_title, issue.message)
    return created
