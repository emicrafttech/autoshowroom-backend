from django.core.management.base import BaseCommand

from apps.billing.models import BillingPlan


class Command(BaseCommand):
    help = "Seed default billing plans for local and staging environments."

    def handle(self, *args, **options):
        plans = [
            {
                "id": "free",
                "name": "Free",
                "price_ngn": 0,
                "listing_limit": 5,
                "stand_limit": 1,
                "features": [],
            },
            {
                "id": "growth",
                "name": "Growth",
                "price_ngn": 50000,
                "listing_limit": 50,
                "stand_limit": 3,
                "features": ["featured_slots", "performance_analytics", "multiple_stands", "priority_support"],
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "price_ngn": 150000,
                "listing_limit": 500,
                "stand_limit": 20,
                "features": [
                    "featured_slots",
                    "video_walkarounds",
                    "performance_analytics",
                    "multiple_stands",
                    "finance_offers",
                    "priority_support",
                    "verified_badge",
                    "inventory_api",
                ],
            },
        ]
        for plan in plans:
            BillingPlan.objects.update_or_create(
                id=plan["id"],
                defaults=plan,
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(plans)} billing plans."))
