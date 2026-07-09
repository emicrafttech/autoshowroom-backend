import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated

from .models import Buyer


def create_buyer_token(buyer: Buyer, *, ttl_seconds: int | None = None) -> str:
    lifetime = (
        settings.BUYER_TOKEN_TTL_SECONDS if ttl_seconds is None else int(ttl_seconds)
    )
    now = timezone.now()
    payload = {
        "sub": str(buyer.id),
        "typ": "buyer",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=lifetime)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def get_buyer_from_request(request) -> Buyer:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise NotAuthenticated("Buyer bearer token is required.")
    token = header.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("typ") != "buyer":
            raise AuthenticationFailed("Invalid buyer token.")
        buyer_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, jwt.PyJWTError) as exc:
        raise AuthenticationFailed("Invalid buyer token.") from exc
    try:
        return Buyer.objects.get(id=buyer_id)
    except Buyer.DoesNotExist as exc:
        raise AuthenticationFailed("Buyer not found.") from exc
