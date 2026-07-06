from __future__ import annotations

from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from apps.marketplace.serializers import PublicVehicleSerializer
from apps.marketplace.views import public_vehicle_queryset

from .models import PriceAlert


def _city_slug_from_area(area: str) -> str:
    token = area.strip().split(",")[0].strip()
    return slugify(token)


def area_filter(area: str) -> Q:
    city_slug = _city_slug_from_area(area)
    filters = Q(location__area__iexact=area) | Q(dealer__area__iexact=area)
    if city_slug:
        filters |= Q(location__city_slug__iexact=city_slug) | Q(
            dealer__city_slug__iexact=city_slug
        )
    return filters


def format_compact_ngn(amount: int) -> str:
    if amount >= 1_000_000_000:
        return f"₦{amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        millions = amount / 1_000_000
        formatted = f"{millions:.0f}" if millions == int(millions) else f"{millions:.1f}"
        return f"₦{formatted}M"
    if amount >= 1_000:
        return f"₦{amount // 1_000}K"
    return f"₦{amount}"


def infer_icon_kind(
    *,
    body_type: str = "",
    make: str = "",
    min_year: int | None = None,
    min_price_ngn: int | None = None,
    max_price_ngn: int | None = None,
) -> str:
    if body_type:
        return PriceAlert.IconKind.CAR
    if make and min_year:
        return PriceAlert.IconKind.CLOCK
    if min_price_ngn or max_price_ngn:
        return PriceAlert.IconKind.PULSE
    if make:
        return PriceAlert.IconKind.CLOCK
    return PriceAlert.IconKind.CAR


def build_alert_title(alert: PriceAlert) -> str:
    if alert.title.strip():
        return alert.title.strip()
    parts: list[str] = []
    if alert.body_type:
        parts.append(alert.body_type.upper())
    elif alert.make:
        parts.append(alert.make)
        if alert.model:
            parts.append(alert.model)
    if alert.max_price_ngn:
        parts.append(f"under {format_compact_ngn(alert.max_price_ngn)}")
    elif alert.min_price_ngn and alert.max_price_ngn is None:
        parts.append(f"from {format_compact_ngn(alert.min_price_ngn)}")
    if alert.min_year:
        parts.append(f"{alert.min_year}+")
    return " · ".join(parts) if parts else "Custom alert"


def apply_alert_filters(queryset, alert: PriceAlert):
    if alert.body_type:
        queryset = queryset.filter(body_type__iexact=alert.body_type)
    if alert.make:
        queryset = queryset.filter(make__iexact=alert.make)
    if alert.model:
        queryset = queryset.filter(model__iexact=alert.model)
    if alert.min_year:
        queryset = queryset.filter(year__gte=alert.min_year)
    if alert.min_price_ngn:
        queryset = queryset.filter(price_ngn__gte=alert.min_price_ngn)
    if alert.max_price_ngn:
        queryset = queryset.filter(price_ngn__lte=alert.max_price_ngn)
    if alert.area:
        queryset = queryset.filter(area_filter(alert.area))
    return queryset


def alert_match_count(alert: PriceAlert) -> int:
    return apply_alert_filters(public_vehicle_queryset(), alert).count()


def build_alert_subtitle(alert: PriceAlert, match_count: int) -> str:
    parts: list[str] = []
    if alert.area:
        parts.append(alert.area)
    elif alert.max_price_ngn and not alert.body_type and not alert.make:
        parts.append(f"Any price")
    elif alert.min_price_ngn and alert.max_price_ngn:
        parts.append(
            f"{format_compact_ngn(alert.min_price_ngn)}—{format_compact_ngn(alert.max_price_ngn)}"
        )
    elif alert.max_price_ngn:
        parts.append(f"Up to {format_compact_ngn(alert.max_price_ngn)}")
    elif alert.make and alert.min_year:
        parts.append("Any price")
    prefix = " · ".join(parts) if parts else "Any price"
    noun = "car" if match_count == 1 else "cars"
    return f"{prefix} · {match_count} {noun} match now"


def vehicle_matches_alert(vehicle, alert: PriceAlert) -> bool:
    if alert.body_type and (vehicle.body_type or "").lower() != alert.body_type.lower():
        return False
    if alert.make and vehicle.make.lower() != alert.make.lower():
        return False
    if alert.model and vehicle.model.lower() != alert.model.lower():
        return False
    if alert.min_year and vehicle.year < alert.min_year:
        return False
    if alert.min_price_ngn and vehicle.price_ngn < alert.min_price_ngn:
        return False
    if alert.max_price_ngn and vehicle.price_ngn > alert.max_price_ngn:
        return False
    if alert.area:
        area = (vehicle.location.area if vehicle.location_id else "") or vehicle.dealer.area
        city_slug = ""
        if vehicle.location_id and vehicle.location.city_slug:
            city_slug = vehicle.location.city_slug
        elif vehicle.dealer.city_slug:
            city_slug = vehicle.dealer.city_slug
        alert_city = _city_slug_from_area(alert.area)
        area_matches = (area or "").lower() == alert.area.lower()
        city_matches = alert_city and city_slug.lower() == alert_city
        if not area_matches and not city_matches:
            return False
    return True


def find_new_price_matches(buyer, *, limit: int = 5):
    from apps.vehicles.models import VehiclePriceHistory

    active_alerts = list(
        PriceAlert.objects.filter(buyer=buyer, active=True).order_by("-updated_at")
    )
    if not active_alerts:
        return []

    matches = []
    vehicles = (
        public_vehicle_queryset()
        .prefetch_related("price_history")
        .filter(price_history__isnull=False)
        .distinct()
    )
    for vehicle in vehicles:
        history = list(vehicle.price_history.order_by("-recorded_at")[:2])
        if len(history) < 2:
            continue
        latest, previous = history[0], history[1]
        if latest.price_ngn >= previous.price_ngn:
            continue

        matched_alert = next(
            (alert for alert in active_alerts if vehicle_matches_alert(vehicle, alert)),
            None,
        )
        if not matched_alert:
            continue

        matches.append(
            {
                "vehicle": vehicle,
                "previousPriceNgn": previous.price_ngn,
                "currentPriceNgn": latest.price_ngn,
                "droppedAt": latest.recorded_at,
                "droppedLabel": f"Dropped {naturaltime(latest.recorded_at)}",
                "matchedAlertId": str(matched_alert.id),
                "matchedAlertName": build_alert_title(matched_alert),
                "matchKind": "price_drop",
            }
        )

    matches.sort(key=lambda item: item["droppedAt"], reverse=True)
    return matches[:limit]


def find_new_listing_matches(buyer, *, limit: int = 5):
    active_alerts = list(
        PriceAlert.objects.filter(buyer=buyer, active=True).order_by("-updated_at")
    )
    if not active_alerts:
        return []

    matches = []
    vehicles = public_vehicle_queryset()
    for alert in active_alerts:
        for vehicle in apply_alert_filters(vehicles, alert):
            published_at = vehicle.listing_approved_at or vehicle.published_at
            if not published_at or published_at <= alert.created_at:
                continue
            matches.append(
                {
                    "vehicle": vehicle,
                    "previousPriceNgn": vehicle.price_ngn,
                    "currentPriceNgn": vehicle.price_ngn,
                    "droppedAt": published_at,
                    "droppedLabel": f"Listed {naturaltime(published_at)}",
                    "matchedAlertId": str(alert.id),
                    "matchedAlertName": build_alert_title(alert),
                    "matchKind": "new_listing",
                }
            )

    matches.sort(key=lambda item: item["droppedAt"], reverse=True)
    return matches[:limit]


def find_new_matches(buyer, *, limit: int = 5):
    combined = find_new_price_matches(buyer, limit=limit * 2)
    combined.extend(find_new_listing_matches(buyer, limit=limit * 2))
    seen = set()
    unique = []
    for item in sorted(combined, key=lambda entry: entry["droppedAt"], reverse=True):
        key = (str(item["vehicle"].id), item["matchedAlertId"], item["matchKind"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def serialize_price_alerts_summary(buyer, *, request=None):
    alerts = PriceAlert.objects.filter(buyer=buyer).order_by("-updated_at")
    alert_items = []
    for alert in alerts:
        match_count = alert_match_count(alert)
        alert_items.append(
            {
                "id": str(alert.id),
                "title": build_alert_title(alert),
                "subtitle": build_alert_subtitle(alert, match_count),
                "iconKind": alert.icon_kind,
                "active": alert.active,
                "matchCount": match_count,
            }
        )

    new_matches = []
    for item in find_new_matches(buyer):
        vehicle_data = PublicVehicleSerializer(
            item["vehicle"],
            context={"request": request} if request else {},
        ).data
        new_matches.append(
            {
                "vehicle": vehicle_data,
                "previousPriceNgn": item["previousPriceNgn"],
                "currentPriceNgn": item["currentPriceNgn"],
                "droppedAt": item["droppedAt"],
                "droppedLabel": item["droppedLabel"],
                "matchedAlertId": item["matchedAlertId"],
                "matchedAlertName": item["matchedAlertName"],
                "matchKind": item.get("matchKind", "price_drop"),
            }
        )

    return {
        "activeCount": alerts.filter(active=True).count(),
        "alerts": alert_items,
        "newMatches": new_matches,
    }
