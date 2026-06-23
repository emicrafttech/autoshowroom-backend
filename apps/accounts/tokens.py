import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

INVITE_TOKEN_TTL = timedelta(days=7)


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def invite_expiry():
    return timezone.now() + INVITE_TOKEN_TTL
