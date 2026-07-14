"""June 2026 dealer plan matrix. Used by data migrations and seed command."""

VAT_RATE = 0.075
FOUNDING_TRIAL_DAYS = 90

# null listing/staff = unlimited; null stand = unlimited (stands are not plan-gated)
PLAN_MATRIX = [
    {
        "id": "starter",
        "name": "Starter",
        "price_ngn": 20_000,
        "price_yearly_ngn": 180_000,
        "listing_limit": 20,
        "stand_limit": None,
        "staff_limit": 1,
        "feed_priority": 0,
        "videos_per_vehicle": 5,
        "photos_per_vehicle": 15,
        "max_clip_seconds": 120,
        "featured_slots_per_month": 0,
        "bulk_upload": False,
        "follow_up_reminders": False,
        "analytics_tier": "basic",
        "is_active": True,
        "features": [
            "verified_badge",
            "dealer_profile",
            "video_listings",
            "lead_capture",
            "inspection_booking",
            "whatsapp_handoff",
        ],
    },
    {
        "id": "growth",
        "name": "Growth",
        "price_ngn": 50_000,
        "price_yearly_ngn": 450_000,
        "listing_limit": 75,
        "stand_limit": None,
        "staff_limit": 5,
        "feed_priority": 0,
        "videos_per_vehicle": 8,
        "photos_per_vehicle": 30,
        "max_clip_seconds": 120,
        "featured_slots_per_month": 3,
        "bulk_upload": True,
        "follow_up_reminders": True,
        "analytics_tier": "full",
        "is_active": True,
        "features": [
            "verified_badge",
            "dealer_profile",
            "video_listings",
            "lead_capture",
            "inspection_booking",
            "whatsapp_handoff",
            "bulk_upload",
            "follow_up_reminders",
            "performance_analytics",
            "featured_slots",
        ],
    },
    {
        "id": "prestige",
        "name": "Prestige",
        "price_ngn": 150_000,
        "price_yearly_ngn": 1_350_000,
        "listing_limit": None,
        "stand_limit": None,
        "staff_limit": None,
        "feed_priority": 0,
        "videos_per_vehicle": 10,
        "photos_per_vehicle": 40,
        "max_clip_seconds": 180,
        "featured_slots_per_month": 15,
        "bulk_upload": True,
        "follow_up_reminders": True,
        "analytics_tier": "full",
        "is_active": True,
        "features": [
            "verified_badge",
            "dealer_profile",
            "video_listings",
            "lead_capture",
            "inspection_booking",
            "whatsapp_handoff",
            "bulk_upload",
            "follow_up_reminders",
            "performance_analytics",
            "featured_slots",
            "monthly_report",
            "video_production_support",
            "dedicated_account_manager",
        ],
    },
]

PLAN_ID_REMAP = {
    "free": "starter",
    "enterprise": "prestige",
}


def vat_breakdown(gross_ngn: int) -> dict:
    """Prices are VAT-inclusive at 7.5%."""
    gross = int(gross_ngn)
    net = round(gross / (1 + VAT_RATE))
    vat = gross - net
    return {"amountNgn": gross, "amountExVatNgn": net, "vatNgn": vat, "vatRate": VAT_RATE}


def upsert_plans(BillingPlan):
    for plan in PLAN_MATRIX:
        BillingPlan.objects.update_or_create(id=plan["id"], defaults=dict(plan))
    # Deactivate legacy plan rows that are no longer sold
    BillingPlan.objects.filter(id__in=["free", "enterprise"]).update(is_active=False)
