import hashlib
import hmac
import json
import re
import uuid
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings

PAYSTACK_BASE = "https://api.paystack.co"
PAYSTACK_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
REFERENCE_PATTERN = re.compile(r"[^A-Za-z0-9\-=.]")


class PaystackError(Exception):
    pass


def is_configured() -> bool:
    return bool(getattr(settings, "PAYSTACK_SECRET_KEY", "").strip())


def secret_key() -> str:
    key = getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()
    if not key:
        raise PaystackError("PAYSTACK_SECRET_KEY is not configured.")
    return key


def public_key() -> str:
    return getattr(settings, "PAYSTACK_PUBLIC_KEY", "").strip()


def payment_currency() -> str:
    return getattr(settings, "PAYMENT_CURRENCY", "NGN").strip() or "NGN"


def billing_callback_url() -> str:
    base = getattr(settings, "DEALER_APP_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/billing"


def build_checkout_reference(dealer_id, plan_id: str) -> str:
    del plan_id
    del dealer_id
    reference = f"ASR{uuid.uuid4().hex.upper()}"
    return REFERENCE_PATTERN.sub("", reference)[:64]


def build_payment_method_reference() -> str:
    reference = f"ASRPMC{uuid.uuid4().hex.upper()}"
    return REFERENCE_PATTERN.sub("", reference)[:64]


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        f"{PAYSTACK_BASE}{path}",
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {secret_key()}",
            "Content-Type": "application/json",
            "User-Agent": PAYSTACK_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("message") or detail
        except json.JSONDecodeError:
            message = detail or f"Paystack request failed ({exc.code})"
        raise PaystackError(message) from exc

    parsed = json.loads(raw)
    if not parsed.get("status") or parsed.get("data") is None:
        raise PaystackError(parsed.get("message") or "Paystack request failed.")
    return parsed["data"]


def verify_transaction(reference: str) -> dict[str, Any]:
    return _request("GET", f"/transaction/verify/{reference}")


def verify_webhook_signature(payload: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    digest = hmac.new(
        secret_key().encode("utf-8"),
        payload,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(digest, signature_header)
