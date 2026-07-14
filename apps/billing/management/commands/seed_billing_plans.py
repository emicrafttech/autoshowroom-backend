from django.core.management.base import BaseCommand

from apps.billing.models import BillingPlan
from apps.billing.plan_catalogue import upsert_plans


class Command(BaseCommand):
    help = "Seed June 2026 billing plans (Starter / Growth / Prestige)."

    def handle(self, *args, **options):
        upsert_plans(BillingPlan)
        self.stdout.write(self.style.SUCCESS("Seeded June 2026 billing plans."))
