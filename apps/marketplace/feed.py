import random
import zlib
from datetime import datetime, timezone as dt_timezone

from django.db.models import DateTimeField, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.billing.models import BillingPlan, Subscription
from apps.dealers.models import Dealer
from apps.vehicles.models import Vehicle

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
    active_subscription_priority = (
        Subscription.objects.filter(
            dealer_id=OuterRef("dealer_id"),
            status__in=[
                Subscription.Status.TRIALING,
                Subscription.Status.ACTIVE,
            ],
        )
        .order_by("-created_at")
        .values("plan__feed_priority")[:1]
    )
    dealer_plan_priority = BillingPlan.objects.filter(
        id=OuterRef("dealer__plan_id"),
        is_active=True,
    ).values("feed_priority")[:1]

    return queryset.annotate(
        feed_priority=Coalesce(
            Subquery(active_subscription_priority, output_field=IntegerField()),
            Subquery(dealer_plan_priority, output_field=IntegerField()),
            Value(0),
            output_field=IntegerField(),
        )
    )


def with_feed_publish_order(queryset):
    """Order by admin approval time (listing_approved_at), newest first."""
    return queryset.annotate(
        feed_sort_published_at=Coalesce(
            "listing_approved_at",
            "published_at",
            Value(_EPOCH, output_field=DateTimeField()),
        )
    ).order_by("-feed_sort_published_at", "-updated_at", "-id")


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


def rank_feed_page(vehicles, *, params, page_number: int):
    """
    Apply feed ranking for one paginated slice:
    1. Input is already sorted by publish time (newest first).
    2. Randomize order within the page (stable per feedSession/page/filters).
    3. Re-order by dealer feed priority so subscribers appear first.
    """
    if not vehicles:
        return vehicles

    shuffled = vehicles[:]
    random.Random(feed_shuffle_seed(params, page_number)).shuffle(shuffled)
    shuffled.sort(key=lambda vehicle: getattr(vehicle, "feed_priority", 0), reverse=True)
    return shuffled
