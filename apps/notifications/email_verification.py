from django.conf import settings
from django.utils import timezone

from apps.accounts.models import StaffUser
from apps.accounts.tokens import generate_invite_token, hash_invite_token


def build_dealer_verification_url(token: str) -> str:
    base = getattr(settings, "DEALER_APP_URL", "http://localhost:5174").rstrip("/")
    return f"{base}/verify-email?token={token}"


def issue_dealer_email_verification(user: StaffUser) -> str:
    token = generate_invite_token()
    user.email_verification_token_hash = hash_invite_token(token)
    user.email_verification_sent_at = timezone.now()
    update_fields = [
        "email_verification_token_hash",
        "email_verification_sent_at",
        "updated_at",
    ]
    if user.email_verification_required_at is None:
        user.email_verification_required_at = timezone.now()
        update_fields.append("email_verification_required_at")
    user.save(update_fields=update_fields)
    from .tasks import send_dealer_email_verification_email

    send_dealer_email_verification_email.delay(str(user.id), token)
    return token
