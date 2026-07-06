from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import Booking


class Command(BaseCommand):
    help = (
        "Remove duplicate active bookings so a buyer has at most one upcoming "
        "booking per vehicle, keeping the most recently created one."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be removed without deleting anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()
        active = Booking.objects.filter(
            status__in=[
                Booking.Status.PENDING,
                Booking.Status.CONFIRMED,
                Booking.Status.RESCHEDULED,
            ],
            scheduled_at__gte=now,
            buyer__isnull=False,
        ).order_by("-created_at", "-scheduled_at")

        seen = set()
        to_delete = []
        for booking in active:
            key = (booking.buyer_id, booking.vehicle_id)
            if key in seen:
                to_delete.append(booking)
            else:
                seen.add(key)

        if not to_delete:
            self.stdout.write(self.style.SUCCESS("No duplicate active bookings found."))
            return

        for booking in to_delete:
            label = f"{booking.buyer_name} - {booking.vehicle} ({booking.id})"
            if dry_run:
                self.stdout.write(self.style.WARNING(f"[dry-run] would remove {label}"))
            else:
                self.stdout.write(self.style.WARNING(f"removing {label}"))
                booking.delete()

        action = "would remove" if dry_run else "removed"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {len(to_delete)} duplicate booking(s).")
        )
