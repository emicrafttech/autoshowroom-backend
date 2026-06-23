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
                "features": ["Basic listings"],
            },
            {
                "id": "growth",
                "name": "Growth",
                "price_ngn": 50000,
                "listing_limit": 50,
                "features": ["More listings", "Priority refresh"],
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "price_ngn": 150000,
                "listing_limit": 500,
                "features": ["High-volume listings", "Priority support"],
            },
        ]
        for plan in plans:
            BillingPlan.objects.update_or_create(
                id=plan["id"],
                defaults=plan,
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(plans)} billing plans."))
