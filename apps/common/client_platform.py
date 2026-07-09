from __future__ import annotations

from datetime import timedelta

from django.conf import settings


MOBILE_CLIENT_HEADER = "HTTP_X_CLIENT_PLATFORM"


def is_mobile_client(request) -> bool:
    """True when the caller identifies as a native mobile app."""
    if request is None:
        return False
    value = (request.META.get(MOBILE_CLIENT_HEADER) or "").strip().lower()
    return value in {"mobile", "ios", "android"}


def dealer_refresh_lifetime(*, mobile: bool) -> timedelta:
    if mobile:
        return timedelta(days=settings.JWT_MOBILE_REFRESH_TOKEN_DAYS)
    return settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]


def buyer_token_ttl_seconds(*, mobile: bool) -> int:
    if mobile:
        return settings.BUYER_MOBILE_TOKEN_TTL_SECONDS
    return settings.BUYER_TOKEN_TTL_SECONDS
