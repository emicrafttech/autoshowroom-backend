import random
import zlib
from datetime import datetime, timezone as dt_timezone

from django.db.models import BooleanField, Case, DateTimeField, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

_EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)


def apply_feed_filters(queryset, params):
    filters = {
        "make": "make__iexact",
        "model": "model__iexact",
        "bodyType": "body_type",
        "dealerSlug": "dealer__slug",
        "area": "location__area__iexact",
    }
    for param, lookup in filters.items():
        value = params.get(param)
        if value:
            queryset = queryset.filter(**{lookup: value})

    min_price = params.get("minPriceNgn")
    max_price = params.get("maxPriceNgn")
    min_year = params.get("minYear")
    max_year = params.get("maxYear")
    if min_price:
        queryset = queryset.filter(price_ngn__gte=min_price)
    if max_price:
        queryset = queryset.filter(price_ngn__lte=max_price)
    if min_year:
        queryset = queryset.filter(year__gte=min_year)
    if max_year:
        queryset = queryset.filter(year__lte=max_year)

    search = params.get("q")
    if search:
        queryset = queryset.filter(
            Q(make__icontains=search)
            | Q(model__icontains=search)
            | Q(trim__icontains=search)
            | Q(dealer__name__icontains=search)
        )
    return queryset


def annotate_feed_priority(queryset):
    """Boost explicitly featured listings only (no silent plan-wide boost)."""
    now = timezone.now()
    return queryset.annotate(
        feed_is_featured=Case(
            When(
                is_featured=True,
                featured_until__isnull=True,
                then=Value(True),
            ),
            When(
                is_featured=True,
                featured_until__gt=now,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        feed_priority=Case(
            When(
                is_featured=True,
                featured_until__isnull=True,
                then=Value(100),
            ),
            When(
                is_featured=True,
                featured_until__gt=now,
                then=Value(100),
            ),
            default=Value(0),
            output_field=IntegerField(),
        ),
    )


def with_feed_publish_order(queryset):
    """Order featured first, then by admin approval time (newest first)."""
    return queryset.annotate(
        feed_sort_published_at=Coalesce(
            "listing_approved_at",
            "published_at",
            Value(_EPOCH, output_field=DateTimeField()),
        )
    ).order_by("-feed_priority", "-feed_sort_published_at", "-updated_at", "-id")


def feed_filter_seed_key(params) -> str:
    ignored = {"page", "pageSize", "seed", "feedSession"}
    pairs = sorted(
        f"{key}={value}"
        for key, value in params.items()
        if key not in ignored and value not in (None, "")
    )
    return "|".join(pairs)


def feed_shuffle_seed(params, page_number: int) -> int:
    """
    Derive a deterministic shuffle seed for one paginated page.

    Uses `feedSession` from the client so each refresh gets a new order while
    page 2+ of the same session stays consistent. `seed` is kept for tests.
    """
    explicit_seed = params.get("seed")
    if explicit_seed not in (None, ""):
        return zlib.adler32(f"{explicit_seed}|{page_number}".encode())

    feed_session = params.get("feedSession")
    if feed_session not in (None, ""):
        filter_key = feed_filter_seed_key(params)
        raw = f"{feed_session}|{page_number}|{filter_key}"
        return zlib.adler32(raw.encode())

    filter_key = feed_filter_seed_key(params)
    raw = f"{page_number}|{filter_key}|{timezone.now().timestamp()}"
    return zlib.adler32(raw.encode())


def _vehicle_is_featured(vehicle) -> bool:
    if getattr(vehicle, "feed_is_featured", None) is not None:
        return bool(vehicle.feed_is_featured)
    if not getattr(vehicle, "is_featured", False):
        return False
    featured_until = getattr(vehicle, "featured_until", None)
    return featured_until is None or featured_until > timezone.now()


def rank_feed_page(vehicles, *, params, page_number: int):
    """
    Apply feed ranking for one paginated slice:
    1. Input is already sorted with featured first.
    2. Shuffle organic and featured groups separately (stable per session).
    3. Keep featured group ahead of organic; featured stay labelled via isFeatured.
    """
    if not vehicles:
        return vehicles

    rng = random.Random(feed_shuffle_seed(params, page_number))
    featured = [v for v in vehicles if _vehicle_is_featured(v)]
    organic = [v for v in vehicles if not _vehicle_is_featured(v)]
    rng.shuffle(featured)
    rng.shuffle(organic)
    return featured + organic
