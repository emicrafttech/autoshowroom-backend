from apps.accounts.models import StaffUser
from apps.bookings.models import Booking
from apps.buyers.models import BuyerMessage
from apps.leads.models import Lead
from apps.platform.models import DealerSanction, SanctionAppeal
from apps.vehicles.models import Vehicle, VehicleReviewIssue

from .models import DealerNotification
from .tasks import (
    send_booking_alert_dealer_email,
    send_booking_confirmation_email,
    send_booking_update_buyer_email,
    send_dealer_verification_success_email,
    send_dealer_verification_update_email,
    send_email_verification_reminder_email,
    send_listing_approved_email,
    send_listing_review_issue_email,
    send_new_chat_message_email,
    send_new_lead_alert_email,
    send_payment_failed_email,
    send_payment_received_email,
    send_platform_message_emails,
    send_sanction_applied_email,
    send_sanction_appeal_outcome_email,
    send_staff_invite_email,
)


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
    send_listing_review_issue_email.delay(str(vehicle.id), str(issue.id))
    return created


def notify_new_lead(lead: Lead) -> None:
    send_new_lead_alert_email.delay(str(lead.id))


def notify_buyer_chat_message(message: BuyerMessage) -> None:
    if message.sender_type != BuyerMessage.SenderType.BUYER:
        return
    send_new_chat_message_email.delay(str(message.id))


def notify_booking_confirmed(booking: Booking) -> None:
    send_booking_confirmation_email.delay(str(booking.id))
    send_booking_alert_dealer_email.delay(str(booking.id))


def notify_booking_rescheduled(booking: Booking) -> None:
    send_booking_update_buyer_email.delay(str(booking.id), Booking.Status.RESCHEDULED)


def notify_booking_cancelled(booking: Booking) -> None:
    send_booking_update_buyer_email.delay(str(booking.id), Booking.Status.CANCELLED)


def notify_dealer_verification_approved(dealer) -> None:
    send_dealer_verification_success_email.delay(str(dealer.id))


def notify_dealer_verification_rejected(dealer, reason: str) -> None:
    send_dealer_verification_update_email.delay(str(dealer.id), "rejected", reason)


def notify_dealer_verification_info_requested(dealer, reason: str) -> None:
    send_dealer_verification_update_email.delay(str(dealer.id), "info_requested", reason)


def notify_listing_approved(vehicle: Vehicle) -> None:
    send_listing_approved_email.delay(str(vehicle.id))


def notify_platform_dealer_message(dealer, subject: str, message: str) -> None:
    send_platform_message_emails.delay(str(dealer.id), subject, message)


def notify_staff_invite(user, token: str, *, portal: str = "dealer") -> None:
    send_staff_invite_email.delay(str(user.id), token, portal)


def notify_payment_received(invoice, reference: str = "") -> None:
    send_payment_received_email.delay(str(invoice.id), reference)


def notify_payment_failed(dealer, *, plan_name: str, amount_ngn: int, failure_reason: str, reference: str = "") -> None:
    send_payment_failed_email.delay(str(dealer.id), plan_name, amount_ngn, failure_reason, reference)


def notify_sanction_applied(sanction: DealerSanction) -> None:
    send_sanction_applied_email.delay(str(sanction.id))


def notify_sanction_appeal_outcome(appeal: SanctionAppeal) -> None:
    if appeal.status not in {SanctionAppeal.Status.APPROVED, SanctionAppeal.Status.REJECTED}:
        return
    send_sanction_appeal_outcome_email.delay(str(appeal.id))


def notify_email_verification_reminder(user) -> None:
    send_email_verification_reminder_email.delay(str(user.id))
