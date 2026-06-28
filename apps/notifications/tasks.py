from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task
def send_vehicle_review_issue_email(recipient_email: str, vehicle_title: str, issue_message: str) -> int:
    subject = f"Action needed on your {vehicle_title} listing"
    body = (
        f"An admin reviewer flagged an issue on your {vehicle_title} listing.\n\n"
        f"Issue:\n{issue_message}\n\n"
        "Please sign in to your dealer workspace, update the listing, and submit it back for review."
    )
    return send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@autoshowroom.local"),
        [recipient_email],
        fail_silently=False,
    )
