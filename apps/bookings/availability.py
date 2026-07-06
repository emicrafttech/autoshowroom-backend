from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.bookings.models import Appointment, Booking

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SLOT_LENGTH_OPTIONS = {15, 30, 45, 60}
DEFAULT_TIMEZONE = "Africa/Lagos"
BOOKING_LEAD_TIME = timedelta(hours=2)


def default_booking_availability() -> dict:
    weekly_hours = {
        day: {"enabled": True, "open": "09:00", "close": "17:00"}
        for day in ["mon", "tue", "wed", "thu", "fri"]
    }
    weekly_hours["sat"] = {"enabled": True, "open": "10:00", "close": "14:00"}
    weekly_hours["sun"] = {"enabled": False, "open": "09:00", "close": "17:00"}
    return {
        "timezone": DEFAULT_TIMEZONE,
        "slotLengthMinutes": 45,
        "maxBookingsPerDay": 8,
        "weeklyHours": weekly_hours,
        "blockedDates": [],
    }


def weekday_key(value: date) -> str:
    return WEEKDAY_KEYS[value.weekday()]


def normalize_booking_availability(raw: dict | None) -> dict:
    base = default_booking_availability()
    if not raw:
        return base

    normalized = deepcopy(base)
    if raw.get("timezone"):
        normalized["timezone"] = str(raw["timezone"])
    slot_length = raw.get("slotLengthMinutes")
    if slot_length in SLOT_LENGTH_OPTIONS:
        normalized["slotLengthMinutes"] = slot_length
    max_per_day = raw.get("maxBookingsPerDay")
    if isinstance(max_per_day, int) and 1 <= max_per_day <= 50:
        normalized["maxBookingsPerDay"] = max_per_day
    if isinstance(raw.get("blockedDates"), list):
        normalized["blockedDates"] = sorted(
            {
                str(item).strip()
                for item in raw["blockedDates"]
                if str(item).strip()
            }
        )
    weekly = raw.get("weeklyHours")
    if isinstance(weekly, dict):
        for day in WEEKDAY_KEYS:
            entry = weekly.get(day)
            if not isinstance(entry, dict):
                continue
            normalized["weeklyHours"][day] = {
                "enabled": bool(entry.get("enabled", normalized["weeklyHours"][day]["enabled"])),
                "open": _normalize_time(entry.get("open"), normalized["weeklyHours"][day]["open"]),
                "close": _normalize_time(entry.get("close"), normalized["weeklyHours"][day]["close"]),
            }
    return normalized


def get_dealer_booking_availability(dealer) -> dict:
    return normalize_booking_availability(getattr(dealer, "booking_availability", None))


def _normalize_time(value, fallback: str) -> str:
    try:
        hour, minute = _parse_hhmm(str(value))
        return f"{hour:02d}:{minute:02d}"
    except ValueError:
        return fallback


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Invalid time.")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid time.")
    return hour, minute


def _dealer_timezone(config: dict) -> ZoneInfo:
    try:
        return ZoneInfo(config.get("timezone") or DEFAULT_TIMEZONE)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _active_appointments(dealer, start: datetime, end: datetime):
    return (
        Appointment.objects.filter(
            dealer=dealer,
            scheduled_at__gte=start,
            scheduled_at__lt=end,
        )
        .select_related("booking")
        .exclude(booking__status=Booking.Status.CANCELLED)
    )


def _day_booking_count(dealer, day: date, tz: ZoneInfo) -> int:
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return _active_appointments(dealer, start, end).count()


def _slot_is_taken(dealer, slot_start: datetime, slot_end: datetime) -> bool:
    return (
        _active_appointments(dealer, slot_start, slot_end)
        .exists()
    )


def generate_booking_availability(
    *,
    dealer,
    from_date: date,
    to_date: date,
) -> dict:
    config = get_dealer_booking_availability(dealer)
    tz = _dealer_timezone(config)
    slot_length = timedelta(minutes=config["slotLengthMinutes"])
    max_per_day = config["maxBookingsPerDay"]
    blocked_dates = set(config.get("blockedDates") or [])
    now = timezone.now().astimezone(tz)
    earliest = now + BOOKING_LEAD_TIME

    days = []
    current = from_date
    next_available_at = None

    while current <= to_date:
        date_key = current.isoformat()
        day_config = config["weeklyHours"].get(weekday_key(current), {})
        enabled = bool(day_config.get("enabled"))
        day_count = _day_booking_count(dealer, current, tz)
        day_full = day_count >= max_per_day
        blocked = date_key in blocked_dates

        slots = []
        if enabled and not blocked and not day_full:
            open_hour, open_minute = _parse_hhmm(day_config["open"])
            close_hour, close_minute = _parse_hhmm(day_config["close"])
            slot_start = datetime.combine(current, time(open_hour, open_minute), tzinfo=tz)
            day_close = datetime.combine(current, time(close_hour, close_minute), tzinfo=tz)
            while slot_start + slot_length <= day_close:
                slot_end = slot_start + slot_length
                available = slot_start >= earliest and not _slot_is_taken(dealer, slot_start, slot_end)
                slot_payload = {
                    "startAt": slot_start.isoformat(),
                    "endAt": slot_end.isoformat(),
                    "available": available,
                }
                slots.append(slot_payload)
                if available and next_available_at is None:
                    next_available_at = slot_start
                slot_start = slot_end

        days.append(
            {
                "date": date_key,
                "available": any(slot["available"] for slot in slots),
                "slots": slots,
            }
        )
        current += timedelta(days=1)

    return {
        "timezone": str(tz),
        "slotLengthMinutes": config["slotLengthMinutes"],
        "maxBookingsPerDay": max_per_day,
        "nextAvailableAt": next_available_at.isoformat() if next_available_at else None,
        "days": days,
    }


def build_vehicle_booking_availability(vehicle, *, from_date: date | None = None, to_date: date | None = None) -> dict:
    tz = _dealer_timezone(get_dealer_booking_availability(vehicle.dealer))
    today = timezone.now().astimezone(tz).date()
    start = from_date or today
    end = to_date or (start + timedelta(days=13))
    if end < start:
        end = start
    payload = generate_booking_availability(dealer=vehicle.dealer, from_date=start, to_date=end)
    payload.update(
        {
            "vehicleId": str(vehicle.id),
            "dealerId": str(vehicle.dealer_id),
            "locationId": str(vehicle.location_id) if vehicle.location_id else None,
        }
    )
    return payload


def is_booking_slot_available(dealer, scheduled_at: datetime) -> bool:
    if timezone.is_naive(scheduled_at):
        scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
    config = get_dealer_booking_availability(dealer)
    tz = _dealer_timezone(config)
    local = scheduled_at.astimezone(tz)
    day = local.date()
    payload = generate_booking_availability(dealer=dealer, from_date=day, to_date=day)
    day_payload = payload["days"][0] if payload["days"] else None
    if not day_payload:
        return False
    for slot in day_payload["slots"]:
        if not slot["available"]:
            continue
        slot_start = datetime.fromisoformat(slot["startAt"])
        if abs((slot_start - local).total_seconds()) < 60:
            return True
    return False
