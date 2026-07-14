from django.db import migrations, models


def upsert_june_2026_plans(apps, schema_editor):
    BillingPlan = apps.get_model("billing", "BillingPlan")
    Dealer = apps.get_model("dealers", "Dealer")
    Subscription = apps.get_model("billing", "Subscription")

    plans = [
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

    for plan in plans:
        BillingPlan.objects.update_or_create(id=plan["id"], defaults=plan)

    remap = {"free": "starter", "enterprise": "prestige"}
    for old_id, new_id in remap.items():
        if not BillingPlan.objects.filter(id=new_id).exists():
            continue
        Dealer.objects.filter(plan_id=old_id).update(plan_id=new_id)
        Subscription.objects.filter(plan_id=old_id).update(plan_id=new_id)
        Subscription.objects.filter(pending_plan_id=old_id).update(pending_plan_id=new_id)
        BillingPlan.objects.filter(id=old_id).update(is_active=False)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0007_early_plan_termination"),
        ("dealers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingplan",
            name="price_yearly_ngn",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="staff_limit",
            field=models.PositiveIntegerField(blank=True, default=1, null=True),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="videos_per_vehicle",
            field=models.PositiveSmallIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="photos_per_vehicle",
            field=models.PositiveSmallIntegerField(default=15),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="max_clip_seconds",
            field=models.PositiveIntegerField(default=120),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="featured_slots_per_month",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="bulk_upload",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="follow_up_reminders",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="billingplan",
            name="analytics_tier",
            field=models.CharField(
                choices=[("basic", "Basic"), ("full", "Full")],
                default="basic",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="billingplan",
            name="listing_limit",
            field=models.PositiveIntegerField(blank=True, default=10, null=True),
        ),
        migrations.AlterField(
            model_name="billingplan",
            name="stand_limit",
            field=models.PositiveIntegerField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="subscription",
            name="billing_interval",
            field=models.CharField(
                choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
                default="monthly",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="amount_ex_vat_ngn",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="invoice",
            name="vat_ngn",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.RunPython(upsert_june_2026_plans, noop_reverse),
    ]
