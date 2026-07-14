from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.vehicles.models import Vehicle

from .models import BillingPlan, Subscription


def get_dealer_plan(dealer) -> BillingPlan | None:
    subscription = (
        Subscription.objects.filter(
            dealer=dealer,
            status__in=[
                Subscription.Status.TRIALING,
                Subscription.Status.ACTIVE,
            ],
        )
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )
    if subscription:
        return subscription.plan
    return BillingPlan.objects.filter(id=dealer.plan_id, is_active=True).first()


def get_listing_limit(dealer) -> int | None:
    plan = get_dealer_plan(dealer)
    if not plan:
        return 20
    return plan.listing_limit


def get_stand_limit(dealer) -> int | None:
    """Stands are not plan-gated; always unlimited."""
    return None


def get_staff_limit(dealer) -> int | None:
    plan = get_dealer_plan(dealer)
    if not plan:
        return 1
    return plan.staff_limit


def active_stand_count(dealer) -> int:
    return dealer.locations.count()


def can_add_stand(dealer) -> bool:
    return True


def active_listing_count(dealer) -> int:
    return (
        Vehicle.objects.filter(dealer=dealer)
        .exclude(status__in=[Vehicle.Status.HIDDEN, Vehicle.Status.SOLD])
        .count()
    )


def can_publish_listing(dealer) -> bool:
    limit = get_listing_limit(dealer)
    if limit is None:
        return True
    return active_listing_count(dealer) < limit


def active_staff_count(dealer) -> int:
    return dealer.staff_users.filter(is_active=True).count()


def can_invite_staff(dealer) -> bool:
    limit = get_staff_limit(dealer)
    if limit is None:
        return True
    return active_staff_count(dealer) < limit


def get_featured_limit(dealer) -> int:
    plan = get_dealer_plan(dealer)
    if not plan:
        return 0
    return int(plan.featured_slots_per_month or 0)


def featured_period_start() -> timezone.datetime:
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def featured_used_this_month(dealer) -> int:
    start = featured_period_start()
    return Vehicle.objects.filter(
        dealer=dealer,
        featured_at__gte=start,
    ).count()


def active_featured_count(dealer) -> int:
    now = timezone.now()
    return Vehicle.objects.filter(
        dealer=dealer,
        is_featured=True,
    ).filter(Q(featured_until__isnull=True) | Q(featured_until__gt=now)).count()


def can_feature_listing(dealer) -> bool:
    limit = get_featured_limit(dealer)
    if limit <= 0:
        return False
    return featured_used_this_month(dealer) < limit


def plan_allows_bulk_upload(dealer) -> bool:
    plan = get_dealer_plan(dealer)
    return bool(plan and plan.bulk_upload)


def plan_allows_follow_up_reminders(dealer) -> bool:
    plan = get_dealer_plan(dealer)
    return bool(plan and plan.follow_up_reminders)


def get_analytics_tier(dealer) -> str:
    plan = get_dealer_plan(dealer)
    if not plan:
        return BillingPlan.AnalyticsTier.BASIC
    return plan.analytics_tier or BillingPlan.AnalyticsTier.BASIC


def get_media_limits(dealer) -> dict:
    plan = get_dealer_plan(dealer)
    if not plan:
        return {"videosPerVehicle": 5, "photosPerVehicle": 15, "maxClipSeconds": 120}
    return {
        "videosPerVehicle": plan.videos_per_vehicle,
        "photosPerVehicle": plan.photos_per_vehicle,
        "maxClipSeconds": plan.max_clip_seconds,
    }


def soft_inactivate_excess_listings(dealer) -> int:
    """Hide oldest active listings when over the plan listing limit. Returns count hidden."""
    limit = get_listing_limit(dealer)
    if limit is None:
        return 0
    active = (
        Vehicle.objects.filter(dealer=dealer)
        .exclude(status__in=[Vehicle.Status.HIDDEN, Vehicle.Status.SOLD])
        .order_by("created_at", "id")
    )
    excess = active.count() - limit
    if excess <= 0:
        return 0
    to_hide = list(active[:excess])
    for vehicle in to_hide:
        vehicle.status = Vehicle.Status.HIDDEN
        vehicle.feed_ready = False
        vehicle.is_featured = False
        vehicle.featured_until = None
        vehicle.save(
            update_fields=[
                "status",
                "feed_ready",
                "is_featured",
                "featured_until",
                "updated_at",
            ]
        )
    return len(to_hide)


def feature_vehicle(dealer, vehicle: Vehicle, *, days: int = 30) -> Vehicle:
    if vehicle.dealer_id != dealer.id:
        raise ValueError("Vehicle does not belong to this dealer.")
    if not can_feature_listing(dealer):
        raise ValueError("Featured placement quota exhausted for this month.")
    now = timezone.now()
    vehicle.is_featured = True
    vehicle.featured_at = now
    vehicle.featured_until = now + timedelta(days=days)
    vehicle.save(update_fields=["is_featured", "featured_at", "featured_until", "updated_at"])
    return vehicle


def unfeature_vehicle(vehicle: Vehicle) -> Vehicle:
    vehicle.is_featured = False
    vehicle.featured_until = None
    vehicle.save(update_fields=["is_featured", "featured_until", "updated_at"])
    return vehicle


def entitlements_payload(dealer) -> dict:
    plan = get_dealer_plan(dealer)
    media = get_media_limits(dealer)
    listing_limit = get_listing_limit(dealer)
    staff_limit = get_staff_limit(dealer)
    featured_limit = get_featured_limit(dealer)
    featured_used = featured_used_this_month(dealer)
    return {
        "bulkUpload": plan_allows_bulk_upload(dealer),
        "followUpReminders": plan_allows_follow_up_reminders(dealer),
        "analyticsTier": get_analytics_tier(dealer),
        "videosPerVehicle": media["videosPerVehicle"],
        "photosPerVehicle": media["photosPerVehicle"],
        "maxClipSeconds": media["maxClipSeconds"],
        "listingLimit": listing_limit,
        "staffLimit": staff_limit,
        "featuredLimit": featured_limit,
        "featuredUsed": featured_used,
        "canFeature": can_feature_listing(dealer),
        "canBulkUpload": plan_allows_bulk_upload(dealer),
        "canInviteStaff": can_invite_staff(dealer),
        "canPublish": can_publish_listing(dealer),
    }
