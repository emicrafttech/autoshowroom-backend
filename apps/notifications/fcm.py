from __future__ import annotations

import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging

from django.conf import settings


def _resolve_service_account_dict() -> dict | None:
    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            return None

    configured_path = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_PATH", "")
    path = Path(configured_path) if configured_path else Path(settings.BASE_DIR) / "firebase.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None


def is_firebase_configured() -> bool:
    return _resolve_service_account_dict() is not None


def ensure_firebase_app() -> bool:
    if firebase_admin._apps:
        return True

    service_account = _resolve_service_account_dict()
    if not service_account:
        return False

    try:
        cred = credentials.Certificate(service_account)
        firebase_admin.initialize_app(cred)
        return True
    except Exception:
        return False


def send_multicast_notification(
    tokens: list[str],
    *,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    cleaned_tokens = [token.strip() for token in tokens if token and token.strip()]
    if not cleaned_tokens or not ensure_firebase_app():
        return

    payload = {key: str(value) for key, value in (data or {}).items()}
    payload.setdefault("title", title)
    payload.setdefault("body", body)

    message = messaging.MulticastMessage(
        tokens=cleaned_tokens,
        notification=messaging.Notification(title=title, body=body),
        data=payload,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                icon="ic_notification",
                color="#C5FF00",
                channel_id="autoshowroom_buyer_alerts",
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default"),
            )
        ),
    )
    messaging.send_each_for_multicast(message, dry_run=False)
