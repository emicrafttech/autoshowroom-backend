from pathlib import Path

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from apps.notifications.emails import base_email_context, dealer_app_url

SAMPLE_IMAGE = "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80"

PREVIEWS = [
    (
        "01-dealer-email-verification.html",
        "emails/dealer_email_verification.html",
        {
            "recipient_name": "Chidi",
            "dealer_name": "GrandView Motors",
            "verify_url": f"{dealer_app_url()}/verify-email?token=sample-token",
            "expiry_hours": 24,
        },
    ),
    (
        "02-new-lead-alert.html",
        "emails/new_lead_alert.html",
        {
            "buyer_name": "Emeka",
            "vehicle_short_title": "Lexus RC 350",
            "vehicle_title": "2020 Lexus RC 350 F Sport",
            "vehicle_specs": "2020 · 48,200 km · Coupe",
            "vehicle_price": "₦38.5M",
            "vehicle_image_url": SAMPLE_IMAGE,
            "lead_message": "Is the price negotiable? I can come Tuesday to inspect the car.",
            "lead_time": "10:42 AM",
            "dealer_name": "Prime Motors",
            "reply_url": dealer_app_url("chats"),
            "lead_details_url": dealer_app_url("leads"),
        },
    ),
    (
        "03-booking-confirmation.html",
        "emails/booking_confirmation.html",
        {
            "buyer_name": "Ada",
            "vehicle_short_title": "Toyota Camry",
            "vehicle_title": "2020 Toyota Camry XSE",
            "vehicle_price": "₦15.8M",
            "vehicle_image_url": SAMPLE_IMAGE,
            "scheduled_at_display": "Tuesday, 1 July 2026 · 10:00 AM",
            "location_label": "Prime Motors · Main Stand · Wuse 2, Abuja",
            "agent_name": "Prime Motors",
            "agent_phone": "+234 803 123 4567",
            "booking_id": "bkg-sample-001",
            "calendar_url": "https://calendar.google.com/calendar/render",
            "directions_url": "https://www.google.com/maps",
        },
    ),
    (
        "04-dealer-verification-success.html",
        "emails/dealer_verification_success.html",
        {
            "dealer_name": "GrandView Motors",
            "stand_url": dealer_app_url("account"),
            "account_url": dealer_app_url("account"),
            "verified_at": "28 Jun 2026",
        },
    ),
    (
        "05-listing-review-issue.html",
        "emails/listing_review_issue.html",
        {
            "vehicle_title": "2020 Toyota Camry XSE",
            "issue_message": "The mileage shown does not match the odometer photo. Please update and resubmit.",
            "stock_url": dealer_app_url("stock"),
        },
    ),
    (
        "06-platform-message.html",
        "emails/platform_message.html",
        {
            "subject_line": "Action needed on your verification",
            "message_body": "Please upload a clearer CAC document. The current scan is too blurry to review.",
            "dealer_name": "GrandView Motors",
            "account_url": dealer_app_url("account"),
        },
    ),
    (
        "07-staff-invite.html",
        "emails/staff_invite.html",
        {
            "recipient_name": "Amaka",
            "organization_name": "GrandView Motors",
            "portal_label": "dealer workspace",
            "role_label": "Sales",
            "invite_url": f"{dealer_app_url()}/accept-invite?token=sample",
            "expires_at": "5 Jul 2026 · 10:00 AM",
        },
    ),
    (
        "08-booking-alert-dealer.html",
        "emails/booking_alert_dealer.html",
        {
            "buyer_name": "Ada Okonkwo",
            "buyer_phone": "+234 805 555 5555",
            "vehicle_short_title": "Toyota Camry",
            "vehicle_title": "2020 Toyota Camry XSE",
            "vehicle_price": "₦15.8M",
            "scheduled_at_display": "Tuesday, 1 July 2026 · 10:00 AM",
            "bookings_url": dealer_app_url("bookings"),
        },
    ),
    (
        "09-payment-received.html",
        "emails/payment_received.html",
        {
            "plan_name": "Pro Plan",
            "amount_display": "₦75,000",
            "reference": "PAY-20260628-001",
            "billing_url": dealer_app_url("billing"),
            "invoice_url": "https://invoices.autoshowroom.local/sample.pdf",
        },
    ),
]


class Command(BaseCommand):
    help = "Render HTML previews of transactional email templates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="email_previews",
            help="Output directory relative to the backend project root.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output"])
        if not output_dir.is_absolute():
            output_dir = Path(__file__).resolve().parents[4] / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        preview_context = base_email_context()

        index_lines = [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'><title>AutoShowroom email previews</title>",
            "<style>body{font-family:system-ui;background:#111;color:#eee;padding:32px}",
            "a{color:#d4ff37}li{margin:8px 0}</style></head><body>",
            "<h1>AutoShowroom email previews</h1><ul>",
        ]

        for filename, template_name, context in PREVIEWS:
            html = render_to_string(template_name, {**preview_context, **context})
            path = output_dir / filename
            path.write_text(html, encoding="utf-8")
            index_lines.append(f"<li><a href='{filename}' target='_blank'>{filename}</a></li>")
            self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))

        index_lines.append("</ul></body></html>")
        index_path = output_dir / "index.html"
        index_path.write_text("\n".join(index_lines), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {index_path}"))
