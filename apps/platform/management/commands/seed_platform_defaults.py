from django.core.management.base import BaseCommand

from apps.platform.models import PlatformRole, PlatformSetting


class Command(BaseCommand):
    help = "Seed default platform roles and settings."

    def handle(self, *args, **options):
        roles = [
            ("platform_admin", ["*"]),
            ("listing_reviewer", ["vehicles.review", "reports.review"]),
            ("support", ["reports.review", "dsr.review"]),
        ]
        for name, capabilities in roles:
            PlatformRole.objects.update_or_create(
                name=name,
                defaults={"capabilities": capabilities},
            )
        PlatformSetting.objects.update_or_create(
            key="marketplace",
            defaults={"value": {"maintenanceMode": False}},
        )
        self.stdout.write(self.style.SUCCESS("Seeded platform defaults."))
