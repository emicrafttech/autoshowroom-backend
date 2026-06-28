from __future__ import annotations

import urllib.parse
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from apps.accounts.models import StaffUser
from apps.bookings.models import Booking
from apps.dealers.models import Dealer
from apps.vehicles.models import Vehicle
from apps.vehicles.storage import build_public_url


def format_ngn(amount: int | float | None) -> str:
    value = int(amount or 0)
    if value >= 1_000_000:
        compact = value / 1_000_000
        text = f"{compact:.1f}".rstrip("0").rstrip(".")
        return f"₦{text}M"
    return f"₦{value:,}"


def format_vehicle_title(vehicle: Vehicle | None) -> str:
    if not vehicle:
        return "Vehicle"
    trim = f" {vehicle.trim}" if getattr(vehicle, "trim", "") else ""
    return f"{vehicle.year} {vehicle.make} {vehicle.model}{trim}".strip()


def format_vehicle_short_title(vehicle: Vehicle | None) -> str:
    if not vehicle:
        return "vehicle"
    return f"{vehicle.make} {vehicle.model}".strip()


def format_vehicle_specs(vehicle: Vehicle | None) -> str:
    if not vehicle:
        return ""
    mileage = f"{vehicle.mileage_km:,} km"
    body = vehicle.get_body_type_display() if hasattr(
        vehicle, "get_body_type_display") else vehicle.body_type
    return f"{vehicle.year} · {mileage} · {body}"


def vehicle_image_url(vehicle: Vehicle | None) -> str:
    if not vehicle or not vehicle.cover_media_id:
        return ""
    media = vehicle.cover_media
    if not media:
        return ""
    return media.thumbnail_url or media.url or ""


def format_scheduled_at(value: datetime | None) -> str:
    if not value:
        return "Not scheduled"
    local = timezone.localtime(value)
    return local.strftime("%A, %-d %B %Y · %-I:%M %p")


def format_time_short(value: datetime | None) -> str:
    if not value:
        return ""
    return timezone.localtime(value).strftime("%-I:%M %p")


def google_calendar_url(*, title: str, start_at: datetime, location: str, details: str) -> str:
    start = timezone.localtime(start_at).strftime("%Y%m%dT%H%M%S")
    end = timezone.localtime(start_at).replace(hour=(start_at.hour + 1) % 24)
    end_text = timezone.localtime(end).strftime("%Y%m%dT%H%M%S")
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start}/{end_text}",
        "details": details,
        "location": location,
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"


def google_maps_directions_url(address: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(address)}"


def dealer_app_url(path: str = "") -> str:
    base = getattr(settings, "DEALER_APP_URL",
                   "http://localhost:5174").rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


def platform_app_url(path: str = "") -> str:
    base = getattr(settings, "PLATFORM_APP_URL",
                   "http://localhost:5173").rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


def build_staff_invite_url(token: str, *, portal: str = "dealer") -> str:
    base = platform_app_url() if portal == "platform" else dealer_app_url()
    return f"{base}/accept-invite?token={token}"


def build_dealer_verification_url(token: str) -> str:
    return f"{dealer_app_url()}/verify-email?token={token}"


def dealer_staff_emails(dealer: Dealer) -> list[str]:
    return list(
        StaffUser.objects.filter(
            dealer=dealer,
            is_active=True,
            email__isnull=False,
        )
        .exclude(email="")
        .values_list("email", flat=True)
    )


def booking_location_context(booking: Booking) -> dict:
    location = booking.location
    location_name = location.name if location else ""
    location_area = location.area if location else ""
    location_address = location.address if location else ""
    location_parts = [booking.dealer.name,
                      location_name, location_area or location_address]
    location_label = " · ".join(dict.fromkeys(
        part for part in location_parts if part))
    address = ", ".join(
        part for part in [location_address, location_area] if part)
    return {
        "location_label": location_label,
        "directions_url": google_maps_directions_url(address or location_label),
    }


def email_logo_url() -> str:
    explicit = getattr(settings, "EMAIL_LOGO_URL", "").strip()
    if explicit:
        return explicit
    key = f"{settings.STATIC_UPLOAD_PREFIX}/email/logo-main-light.png"
    return f"{build_public_url(key)}?v=3"


def base_email_context() -> dict:
    return {
        "brand_name": "AutoShowroom",
        "logo_url": email_logo_url(),
        "support_email": getattr(settings, "EMAIL_HOST_USER", "support@autoshowroom.ng"),
        "company_address": "AutoShowroom Technologies Ltd · 14, Adeola Odeku St, Victoria Island, Lagos",
        "help_center_url": dealer_app_url("account"),
        "accent_color": "#c5ef2e",
        "accent_text_color": "#0f0f12",
        "brand_green": "#14532d",
    }


def send_templated_email(
    *,
    subject: str,
    template_name: str,
    context: dict,
    recipient_list: list[str],
    plain_text: str | None = None,
) -> int:
    recipients = [email.strip()
                  for email in recipient_list if email and email.strip()]
    if not recipients:
        return 0

    merged_context = {**base_email_context(), **context}
    html_body = render_to_string(template_name, merged_context)
    text_body = plain_text or strip_tags(html_body)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=recipients,
    )
    message.attach_alternative(html_body, "text/html")
    return message.send(fail_silently=False)
