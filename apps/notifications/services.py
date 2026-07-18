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
    send_dealer_push_task,
    send_dealer_verification_success_email,
    send_dealer_verification_update_email,
    send_email_verification_reminder_email,
    send_dealer_password_reset_email,
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
    send_dealer_push_task.delay(
        str(vehicle.dealer_id),
        title="Listing review issue",
        body=f"{vehicle_title}: {issue.message}"[:140],
        data={
            "kind": "review_issue",
            "vehicleId": str(vehicle.id),
        },
    )
    return created


def _send_new_lead_push(lead: Lead) -> None:
    send_dealer_push_task.delay(
        str(lead.dealer_id),
        title="New lead",
        body="You received a new lead. Tap to review the details."[:140],
        data={
            "kind": "new_lead",
            "leadId": str(lead.id),
        },
    )


def notify_new_lead(lead: Lead) -> None:
    send_new_lead_alert_email.delay(str(lead.id))
    _send_new_lead_push(lead)


def notify_new_lead_from_vehicle_view(lead: Lead) -> None:
    _send_new_lead_push(lead)


def notify_buyer_chat_message(message: BuyerMessage) -> None:
    if message.sender_type != BuyerMessage.SenderType.BUYER:
        return
    send_new_chat_message_email.delay(str(message.id))
    conversation = message.conversation
    preview = message.body.strip() or "Sent you a photo"
    send_dealer_push_task.delay(
        str(conversation.dealer_id),
        title=conversation.buyer.name if conversation.buyer_id else "New chat message",
        body=preview[:140],
        data={
            "kind": "chat_message",
            "conversationId": str(conversation.id),
            "vehicleId": str(conversation.vehicle_id),
        },
    )


def notify_buyer_inbound_chat_message(message: BuyerMessage) -> None:
    if message.sender_type != BuyerMessage.SenderType.DEALER:
        return
    from .tasks import send_buyer_chat_message_push

    send_buyer_chat_message_push.delay(str(message.id))


def notify_booking_requested(booking: Booking) -> None:
    send_booking_alert_dealer_email.delay(str(booking.id))
    from .emails import format_vehicle_short_title

    vehicle_title = format_vehicle_short_title(booking.vehicle)
    send_dealer_push_task.delay(
        str(booking.dealer_id),
        title="New booking request",
        body=f"{booking.buyer.name if booking.buyer_id else 'A buyer'} wants to inspect {vehicle_title}."[:140],
        data={
            "kind": "booking_request",
            "bookingId": str(booking.id),
            "vehicleId": str(booking.vehicle_id),
        },
    )


def notify_booking_confirmed(booking: Booking) -> None:
    send_booking_confirmation_email.delay(str(booking.id))
    from .emails import format_vehicle_short_title
    from .tasks import send_buyer_booking_push

    vehicle_title = format_vehicle_short_title(booking.vehicle)
    send_buyer_booking_push.delay(
        str(booking.id),
        headline="Booking confirmed",
        body=f"Your inspection for {vehicle_title} is confirmed.",
    )


def notify_booking_rescheduled(booking: Booking) -> None:
    send_booking_update_buyer_email.delay(str(booking.id), Booking.Status.RESCHEDULED)


def notify_booking_cancelled(booking: Booking) -> None:
    send_booking_update_buyer_email.delay(str(booking.id), Booking.Status.CANCELLED)


def notify_dealer_verification_approved(dealer) -> None:
    send_dealer_verification_success_email.delay(str(dealer.id))
    send_dealer_push_task.delay(
        str(dealer.id),
        title="Verification approved",
        body="Your dealership is now verified."[:140],
        data={"kind": "verification", "status": "approved"},
    )


def notify_dealer_verification_rejected(dealer, reason: str) -> None:
    send_dealer_verification_update_email.delay(str(dealer.id), "rejected", reason)
    send_dealer_push_task.delay(
        str(dealer.id),
        title="Verification update",
        body="Your verification was rejected. Tap to review the reason."[:140],
        data={"kind": "verification", "status": "rejected"},
    )


def notify_dealer_verification_info_requested(dealer, reason: str) -> None:
    send_dealer_verification_update_email.delay(str(dealer.id), "info_requested", reason)
    send_dealer_push_task.delay(
        str(dealer.id),
        title="Verification info requested",
        body="We need more information to complete your verification."[:140],
        data={"kind": "verification", "status": "info_requested"},
    )


def notify_listing_approved(vehicle: Vehicle) -> None:
    send_listing_approved_email.delay(str(vehicle.id))
    send_dealer_push_task.delay(
        str(vehicle.dealer_id),
        title="Listing approved",
        body=f"{vehicle.year} {vehicle.make} {vehicle.model} is now live."[:140],
        data={"kind": "listing_approved", "vehicleId": str(vehicle.id)},
    )


def notify_platform_dealer_message(dealer, subject: str, message: str) -> None:
    send_platform_message_emails.delay(str(dealer.id), subject, message)
    send_dealer_push_task.delay(
        str(dealer.id),
        title=subject[:80] or "Platform message",
        body=message[:140],
        data={"kind": "platform_message"},
    )


def notify_staff_invite(user, token: str, *, portal: str = "dealer") -> None:
    send_staff_invite_email.delay(str(user.id), token, portal)


def notify_dealer_password_reset(user, token: str) -> None:
    send_dealer_password_reset_email.delay(str(user.id), token)


def notify_payment_received(invoice, reference: str = "") -> None:
    send_payment_received_email.delay(str(invoice.id), reference)
    send_dealer_push_task.delay(
        str(invoice.dealer_id),
        title="Payment received",
        body="Your payment was received. Tap to view the receipt."[:140],
        data={"kind": "payment", "invoiceId": str(invoice.id)},
    )


def notify_payment_failed(dealer, *, plan_name: str, amount_ngn: int, failure_reason: str, reference: str = "") -> None:
    send_payment_failed_email.delay(str(dealer.id), plan_name, amount_ngn, failure_reason, reference)
    send_dealer_push_task.delay(
        str(dealer.id),
        title="Payment failed",
        body=f"Payment for {plan_name} could not be completed."[:140],
        data={"kind": "payment_failed"},
    )


def notify_sanction_applied(sanction: DealerSanction) -> None:
    send_sanction_applied_email.delay(str(sanction.id))
    send_dealer_push_task.delay(
        str(sanction.dealer_id),
        title="Account sanction applied",
        body="A sanction was applied to your dealership. Tap to review and appeal."[:140],
        data={"kind": "sanction", "sanctionId": str(sanction.id)},
    )


def notify_sanction_appeal_outcome(appeal: SanctionAppeal) -> None:
    if appeal.status not in {SanctionAppeal.Status.APPROVED, SanctionAppeal.Status.REJECTED}:
        return
    send_sanction_appeal_outcome_email.delay(str(appeal.id))
    send_dealer_push_task.delay(
        str(appeal.dealer_id),
        title="Sanction appeal update",
        body="The outcome of your sanction appeal is available."[:140],
        data={"kind": "sanction_appeal", "appealId": str(appeal.id)},
    )


def notify_email_verification_reminder(user) -> None:
    send_email_verification_reminder_email.delay(str(user.id))
