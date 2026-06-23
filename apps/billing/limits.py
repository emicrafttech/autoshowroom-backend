from apps.vehicles.models import Vehicle

from .models import BillingPlan, Subscription


def get_listing_limit(dealer) -> int:
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
        return subscription.plan.listing_limit
    plan = BillingPlan.objects.filter(id=dealer.plan_id, is_active=True).first()
    return plan.listing_limit if plan else 10


def active_listing_count(dealer) -> int:
    return Vehicle.objects.filter(dealer=dealer).exclude(
        status__in=[Vehicle.Status.HIDDEN, Vehicle.Status.SOLD],
    ).count()


def can_publish_listing(dealer) -> bool:
    return active_listing_count(dealer) < get_listing_limit(dealer)
