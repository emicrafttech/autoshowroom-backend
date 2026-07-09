from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import StaffUser
from apps.accounts.tokens import generate_invite_token, hash_invite_token, invite_expiry
from apps.bookings.models import Booking
from apps.billing.models import Invoice
from apps.buyers.models import BuyerMessage
from apps.dealers.models import Dealer
from apps.leads.models import Lead
from apps.platform.models import DealerSanction, SanctionAppeal
from apps.vehicles.models import Vehicle, VehicleReviewIssue

from .emails import (
    booking_location_context,
    build_dealer_password_reset_url,
    build_dealer_verification_url,
    build_staff_invite_url,
    dealer_app_url,
    dealer_staff_emails,
    format_ngn,
    format_scheduled_at,
    format_time_short,
    format_vehicle_short_title,
    format_vehicle_specs,
    format_vehicle_title,
    google_calendar_url,
    send_templated_email,
    vehicle_image_url,
)


def _role_label(role: str) -> str:
    return role.replace("_", " ").strip().title() or "Team member"


@shared_task
def send_listing_review_issue_email(vehicle_id: str, issue_id: str) -> int:
    vehicle = Vehicle.objects.select_related("dealer").get(id=vehicle_id)
    issue = VehicleReviewIssue.objects.get(id=issue_id)
    vehicle_title = format_vehicle_title(vehicle)
    return send_templated_email(
        subject=f"Action needed on your {vehicle_title} listing",
        template_name="emails/listing_review_issue.html",
        context={
            "vehicle_title": vehicle_title,
            "issue_message": issue.message,
            "stock_url": dealer_app_url("stock"),
        },
        recipient_list=dealer_staff_emails(vehicle.dealer),
        plain_text=f"Issue on {vehicle_title}: {issue.message}",
    )


@shared_task
def send_vehicle_review_issue_email(recipient_email: str, vehicle_title: str, issue_message: str) -> int:
    return send_templated_email(
        subject=f"Action needed on your {vehicle_title} listing",
        template_name="emails/listing_review_issue.html",
        context={
            "vehicle_title": vehicle_title,
            "issue_message": issue_message,
            "stock_url": dealer_app_url("stock"),
        },
        recipient_list=[recipient_email],
        plain_text=f"Issue on {vehicle_title}: {issue_message}",
    )


@shared_task
def send_dealer_email_verification_email(user_id: str, token: str) -> int:
    user = StaffUser.objects.select_related("dealer").get(id=user_id)
    dealer_name = user.dealer.name if user.dealer_id else "your dealership"
    verify_url = build_dealer_verification_url(token)
    expiry_hours = getattr(settings, "EMAIL_VERIFICATION_EXPIRY_HOURS", 24)
    return send_templated_email(
        subject="Confirm your email to start selling cars",
        template_name="emails/dealer_email_verification.html",
        context={
            "recipient_name": user.name or "there",
            "dealer_name": dealer_name,
            "verify_url": verify_url,
            "expiry_hours": expiry_hours,
        },
        recipient_list=[user.email],
    )


@shared_task
def send_email_verification_reminder_email(user_id: str) -> int:
    user = StaffUser.objects.select_related("dealer").get(id=user_id)
    if user.email_verified_at:
        return 0
    token = generate_invite_token()
    user.email_verification_token_hash = hash_invite_token(token)
    user.email_verification_sent_at = timezone.now()
    user.save(update_fields=["email_verification_token_hash", "email_verification_sent_at", "updated_at"])
    grace_days = getattr(settings, "DEALER_EMAIL_VERIFICATION_GRACE_DAYS", 7)
    days_remaining = getattr(settings, "EMAIL_VERIFICATION_REMINDER_DAYS_BEFORE", 1)
    verify_url = build_dealer_verification_url(token)
    return send_templated_email(
        subject="Verify your email to keep your dealer account active",
        template_name="emails/email_verification_reminder.html",
        context={
            "recipient_name": user.name or "there",
            "dealer_name": user.dealer.name if user.dealer_id else "your dealership",
            "verify_url": verify_url,
            "expiry_hours": getattr(settings, "EMAIL_VERIFICATION_EXPIRY_HOURS", 24),
            "days_remaining": days_remaining,
        },
        recipient_list=[user.email],
        plain_text=f"Verify your email within {days_remaining} day(s). Grace period: {grace_days} days.",
    )


@shared_task
def send_dealer_password_reset_email(user_id: str, token: str) -> int:
    user = StaffUser.objects.select_related("dealer").get(id=user_id)
    reset_url = build_dealer_password_reset_url(token)
    return send_templated_email(
        subject="Reset your AutoShowroom dealer password",
        template_name="emails/dealer_password_reset.html",
        context={
            "recipient_name": user.name or "there",
            "dealer_name": user.dealer.name if user.dealer_id else "your dealership",
            "reset_url": reset_url,
            "expiry_hours": 1,
        },
        recipient_list=[user.email],
        plain_text=f"Reset your password using this link: {reset_url}",
    )


@shared_task
def send_new_lead_alert_email(lead_id: str) -> int:
    lead = Lead.objects.select_related("dealer", "vehicle", "vehicle__cover_media").get(id=lead_id)
    vehicle = lead.vehicle
    vehicle_title = format_vehicle_title(vehicle)
    vehicle_short = format_vehicle_short_title(vehicle)
    reply_url = f"{dealer_app_url('chats')}?vehicleId={vehicle.id}" if vehicle else dealer_app_url("chats")
    return send_templated_email(
        subject=f"{lead.name} is interested in your {vehicle_short}",
        template_name="emails/new_lead_alert.html",
        context={
            "buyer_name": lead.name,
            "vehicle_short_title": vehicle_short,
            "vehicle_title": vehicle_title,
            "vehicle_specs": format_vehicle_specs(vehicle),
            "vehicle_price": format_ngn(vehicle.price_ngn) if vehicle else "",
            "vehicle_image_url": vehicle_image_url(vehicle),
            "lead_message": lead.message or "I'd like more information about this vehicle.",
            "lead_time": format_time_short(lead.created_at),
            "dealer_name": lead.dealer.name,
            "reply_url": reply_url,
            "lead_details_url": dealer_app_url("leads"),
        },
        recipient_list=dealer_staff_emails(lead.dealer),
    )


@shared_task
def send_new_chat_message_email(message_id: str) -> int:
    message = BuyerMessage.objects.select_related(
        "conversation",
        "conversation__buyer",
        "conversation__dealer",
        "conversation__vehicle",
        "conversation__vehicle__cover_media",
    ).get(id=message_id)
    if message.sender_type != BuyerMessage.SenderType.BUYER:
        return 0
    conversation = message.conversation
    vehicle = conversation.vehicle
    buyer = conversation.buyer
    buyer_name = buyer.name or buyer.phone
    vehicle_title = format_vehicle_title(vehicle)
    return send_templated_email(
        subject=f"{buyer_name} sent you a message about your {format_vehicle_short_title(vehicle)}",
        template_name="emails/new_chat_message.html",
        context={
            "buyer_name": buyer_name,
            "vehicle_short_title": format_vehicle_short_title(vehicle),
            "vehicle_title": vehicle_title,
            "vehicle_specs": format_vehicle_specs(vehicle),
            "vehicle_price": format_ngn(vehicle.price_ngn),
            "vehicle_image_url": vehicle_image_url(vehicle),
            "lead_message": message.body,
            "lead_time": format_time_short(message.created_at),
            "dealer_name": conversation.dealer.name,
            "reply_url": f"{dealer_app_url('chats')}?vehicleId={vehicle.id}",
            "lead_details_url": dealer_app_url("chats"),
        },
        recipient_list=dealer_staff_emails(conversation.dealer),
    )


@shared_task
def send_booking_confirmation_email(booking_id: str) -> int:
    booking = Booking.objects.select_related("vehicle", "vehicle__cover_media", "dealer", "location").get(id=booking_id)
    if not booking.buyer_email:
        return 0
    vehicle = booking.vehicle
    location_context = booking_location_context(booking)
    vehicle_title = format_vehicle_title(vehicle)
    return send_templated_email(
        subject="Your inspection is confirmed",
        template_name="emails/booking_confirmation.html",
        context={
            "buyer_name": booking.buyer_name,
            "vehicle_short_title": format_vehicle_short_title(vehicle),
            "vehicle_title": vehicle_title,
            "vehicle_price": format_ngn(vehicle.price_ngn),
            "vehicle_image_url": vehicle_image_url(vehicle),
            "scheduled_at_display": format_scheduled_at(booking.scheduled_at),
            "location_label": location_context["location_label"],
            "agent_name": booking.dealer.name,
            "agent_phone": booking.dealer.phone,
            "booking_id": str(booking.id),
            "calendar_url": google_calendar_url(
                title=f"Inspection: {vehicle_title}",
                start_at=booking.scheduled_at,
                location=location_context["location_label"],
                details=f"Inspection booking with {booking.dealer.name}. Reference {booking.id}.",
            ),
            "directions_url": location_context["directions_url"],
        },
        recipient_list=[booking.buyer_email],
    )


@shared_task
def send_booking_alert_dealer_email(booking_id: str) -> int:
    booking = Booking.objects.select_related("vehicle", "dealer", "location").get(id=booking_id)
    vehicle = booking.vehicle
    return send_templated_email(
        subject=f"New inspection booking from {booking.buyer_name}",
        template_name="emails/booking_alert_dealer.html",
        context={
            "buyer_name": booking.buyer_name,
            "buyer_phone": booking.buyer_phone,
            "vehicle_short_title": format_vehicle_short_title(vehicle),
            "vehicle_title": format_vehicle_title(vehicle),
            "vehicle_price": format_ngn(vehicle.price_ngn),
            "scheduled_at_display": format_scheduled_at(booking.scheduled_at),
            "bookings_url": dealer_app_url("bookings"),
        },
        recipient_list=dealer_staff_emails(booking.dealer),
    )


@shared_task
def send_booking_update_buyer_email(booking_id: str, update_type: str) -> int:
    booking = Booking.objects.select_related("vehicle", "dealer", "location").get(id=booking_id)
    if not booking.buyer_email:
        return 0
    vehicle = booking.vehicle
    location_context = booking_location_context(booking)
    vehicle_title = format_vehicle_title(vehicle)
    if update_type == Booking.Status.CANCELLED:
        headline = "Your inspection was cancelled"
        subtitle = f"Hi {booking.buyer_name}, your visit to see the {format_vehicle_short_title(vehicle)} has been cancelled."
        status_icon = "✕"
        show_actions = False
        calendar_url = ""
    else:
        headline = "Your inspection was rescheduled"
        subtitle = f"Hi {booking.buyer_name}, your visit to see the {format_vehicle_short_title(vehicle)} has a new time."
        status_icon = "↻"
        show_actions = True
        calendar_url = google_calendar_url(
            title=f"Inspection: {vehicle_title}",
            start_at=booking.scheduled_at,
            location=location_context["location_label"],
            details=f"Updated inspection booking with {booking.dealer.name}. Reference {booking.id}.",
        )
    return send_templated_email(
        subject=headline,
        template_name="emails/booking_update_buyer.html",
        context={
            "headline": headline,
            "subtitle": subtitle,
            "status_icon": status_icon,
            "vehicle_title": vehicle_title,
            "scheduled_at_display": format_scheduled_at(booking.scheduled_at),
            "location_label": location_context["location_label"],
            "show_actions": show_actions,
            "calendar_url": calendar_url,
            "directions_url": location_context["directions_url"],
        },
        recipient_list=[booking.buyer_email],
    )


@shared_task
def send_dealer_verification_success_email(dealer_id: str) -> int:
    dealer = Dealer.objects.get(id=dealer_id)
    verified_at = timezone.localtime(dealer.verified_at).strftime("%d %b %Y") if dealer.verified_at else ""
    return send_templated_email(
        subject=f"{dealer.name} is now verified",
        template_name="emails/dealer_verification_success.html",
        context={
            "dealer_name": dealer.name,
            "stand_url": dealer_app_url("account"),
            "account_url": dealer_app_url("account"),
            "verified_at": verified_at,
        },
        recipient_list=dealer_staff_emails(dealer),
    )


@shared_task
def send_dealer_verification_update_email(dealer_id: str, action: str, reason: str) -> int:
    dealer = Dealer.objects.get(id=dealer_id)
    if action == "info_requested":
        headline = "More information needed for verification"
        subtitle = f"{dealer.name} needs to provide additional verification details."
    else:
        headline = "Verification was not approved"
        subtitle = f"{dealer.name} did not pass verification at this time."
    return send_templated_email(
        subject=headline,
        template_name="emails/dealer_verification_update.html",
        context={
            "headline": headline,
            "subtitle": subtitle,
            "reason": reason,
            "verification_url": dealer_app_url("account"),
        },
        recipient_list=dealer_staff_emails(dealer),
    )


@shared_task
def send_listing_approved_email(vehicle_id: str) -> int:
    vehicle = Vehicle.objects.select_related("dealer", "cover_media").get(id=vehicle_id)
    vehicle_title = format_vehicle_title(vehicle)
    return send_templated_email(
        subject=f"Your listing is live: {vehicle_title}",
        template_name="emails/listing_approved.html",
        context={
            "vehicle_title": vehicle_title,
            "vehicle_specs": format_vehicle_specs(vehicle),
            "vehicle_price": format_ngn(vehicle.price_ngn),
            "vehicle_image_url": vehicle_image_url(vehicle),
            "stock_url": dealer_app_url("stock"),
        },
        recipient_list=dealer_staff_emails(vehicle.dealer),
    )


@shared_task
def send_platform_message_emails(dealer_id: str, subject: str, message: str) -> int:
    dealer = Dealer.objects.get(id=dealer_id)
    return send_templated_email(
        subject=subject,
        template_name="emails/platform_message.html",
        context={
            "subject_line": subject,
            "message_body": message,
            "dealer_name": dealer.name,
            "account_url": dealer_app_url("account"),
        },
        recipient_list=dealer_staff_emails(dealer),
        plain_text=message,
    )


@shared_task
def send_staff_invite_email(user_id: str, token: str, portal: str = "dealer") -> int:
    user = StaffUser.objects.select_related("dealer", "platform_role").get(id=user_id)
    expires_at = user.invite_expires_at or invite_expiry()
    organization_name = user.dealer.name if portal == "dealer" and user.dealer_id else "AutoShowroom Platform"
    portal_label = "dealer workspace" if portal == "dealer" else "platform admin console"
    return send_templated_email(
        subject=f"You're invited to join {organization_name} on AutoShowroom",
        template_name="emails/staff_invite.html",
        context={
            "recipient_name": user.name or "there",
            "organization_name": organization_name,
            "portal_label": portal_label,
            "role_label": _role_label(user.role),
            "invite_url": build_staff_invite_url(token, portal=portal),
            "expires_at": timezone.localtime(expires_at).strftime("%d %b %Y · %-I:%M %p"),
        },
        recipient_list=[user.email],
    )


@shared_task
def send_payment_received_email(invoice_id: str, reference: str = "") -> int:
    invoice = Invoice.objects.select_related("dealer", "subscription", "subscription__plan").get(id=invoice_id)
    plan_name = invoice.subscription.plan.name if invoice.subscription_id else "Subscription"
    return send_templated_email(
        subject=f"Payment received for {plan_name}",
        template_name="emails/payment_received.html",
        context={
            "plan_name": plan_name,
            "amount_display": format_ngn(invoice.amount_ngn),
            "reference": reference or str(invoice.id),
            "billing_url": dealer_app_url("billing"),
            "invoice_url": invoice.pdf_url or "",
        },
        recipient_list=dealer_staff_emails(invoice.dealer),
    )


@shared_task
def send_payment_failed_email(dealer_id: str, plan_name: str, amount_ngn: int, failure_reason: str, reference: str = "") -> int:
    dealer = Dealer.objects.get(id=dealer_id)
    return send_templated_email(
        subject="Payment failed — update your billing details",
        template_name="emails/payment_failed.html",
        context={
            "plan_name": plan_name,
            "amount_display": format_ngn(amount_ngn),
            "failure_reason": failure_reason or "The payment could not be completed.",
            "reference": reference,
            "billing_url": dealer_app_url("billing"),
        },
        recipient_list=dealer_staff_emails(dealer),
    )


@shared_task
def send_sanction_applied_email(sanction_id: str) -> int:
    sanction = DealerSanction.objects.select_related("dealer").get(id=sanction_id)
    return send_templated_email(
        subject=f"Sanction applied to {sanction.dealer.name}",
        template_name="emails/sanction_applied.html",
        context={
            "dealer_name": sanction.dealer.name,
            "reason": sanction.reason,
            "account_url": dealer_app_url("account"),
        },
        recipient_list=dealer_staff_emails(sanction.dealer),
    )


@shared_task
def send_sanction_appeal_outcome_email(appeal_id: str) -> int:
    appeal = SanctionAppeal.objects.select_related("dealer").get(id=appeal_id)
    if appeal.status == SanctionAppeal.Status.APPROVED:
        headline = "Your sanction appeal was approved"
        subtitle = f"{appeal.dealer.name}'s appeal was accepted and the sanction has been lifted."
        status_icon = "✓"
    else:
        headline = "Your sanction appeal was declined"
        subtitle = f"{appeal.dealer.name}'s appeal was reviewed and not approved at this time."
        status_icon = "✕"
    return send_templated_email(
        subject=headline,
        template_name="emails/sanction_appeal_outcome.html",
        context={
            "headline": headline,
            "subtitle": subtitle,
            "status_icon": status_icon,
            "appeal_reason": appeal.reason,
            "account_url": dealer_app_url("account"),
        },
        recipient_list=dealer_staff_emails(appeal.dealer),
    )


@shared_task
def send_buyer_price_alert_push(
    buyer_id: str,
    *,
    vehicle_id: str,
    alert_id: str,
    title: str,
    body: str,
    match_kind: str,
) -> None:
    from apps.notifications.buyer_push import send_buyer_push

    send_buyer_push(
        buyer_id=buyer_id,
        title=title,
        body=body,
        data={
            "kind": "price_alert",
            "matchKind": match_kind,
            "vehicleId": vehicle_id,
            "alertId": alert_id,
        },
    )


@shared_task
def send_buyer_chat_message_push(message_id: str) -> None:
    from apps.notifications.buyer_push import send_buyer_push

    message = BuyerMessage.objects.select_related(
        "conversation__buyer",
        "conversation__dealer",
        "conversation__vehicle",
    ).get(id=message_id)
    if message.sender_type != BuyerMessage.SenderType.DEALER:
        return

    conversation = message.conversation
    preview = message.body.strip() or "Sent you a photo"
    send_buyer_push(
        buyer_id=conversation.buyer_id,
        title=conversation.dealer.name,
        body=preview[:140],
        data={
            "kind": "chat_message",
            "conversationId": str(conversation.id),
            "vehicleId": str(conversation.vehicle_id),
        },
    )


@shared_task
def send_buyer_booking_push(booking_id: str, *, headline: str, body: str) -> None:
    from apps.notifications.buyer_push import send_buyer_push

    booking = Booking.objects.select_related("buyer", "vehicle").get(id=booking_id)
    if not booking.buyer_id:
        return
    send_buyer_push(
        buyer_id=booking.buyer_id,
        title=headline,
        body=body,
        data={
            "kind": "booking_update",
            "bookingId": str(booking.id),
            "vehicleId": str(booking.vehicle_id),
        },
    )


@shared_task
def dispatch_price_alert_pushes_for_vehicle(
    vehicle_id: str,
    *,
    previous_price_ngn: int | None = None,
    match_kind: str = "price_drop",
) -> int:
    from apps.buyers.models import PriceAlert
    from apps.buyers.price_alerts import build_alert_title, vehicle_matches_alert
    from apps.notifications.emails import format_ngn

    vehicle = Vehicle.objects.select_related("dealer", "location").get(id=vehicle_id)
    sent = 0
    alerts = PriceAlert.objects.filter(active=True, push_notify=True).select_related("buyer")
    for alert in alerts:
        if not vehicle_matches_alert(vehicle, alert):
            continue

        if match_kind == "new_listing":
            published_at = vehicle.listing_approved_at or vehicle.published_at
            if not published_at or published_at <= alert.created_at:
                continue
            title = "New listing matches your alert"
            body = (
                f"{vehicle.year} {vehicle.make} {vehicle.model} · "
                f"{format_ngn(vehicle.price_ngn)} · {build_alert_title(alert)}"
            )
        else:
            if previous_price_ngn is None or vehicle.price_ngn >= previous_price_ngn:
                continue
            title = "Price drop on a matching car"
            body = (
                f"{vehicle.year} {vehicle.make} {vehicle.model} dropped to "
                f"{format_ngn(vehicle.price_ngn)} · {build_alert_title(alert)}"
            )

        send_buyer_price_alert_push.delay(
            str(alert.buyer_id),
            vehicle_id=str(vehicle.id),
            alert_id=str(alert.id),
            title=title,
            body=body,
            match_kind=match_kind,
        )
        sent += 1
    return sent


@shared_task
def send_dealer_push_task(
    dealer_id: str,
    *,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    from apps.notifications.dealer_push import send_dealer_push

    send_dealer_push(
        dealer_id=dealer_id,
        title=title,
        body=body,
        data=data or {},
    )
