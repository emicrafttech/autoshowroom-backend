"""Backfill existing S3 media through the transcode/compress pipeline.

Usage:
    python manage.py transcode_media            # queue Celery tasks
    python manage.py transcode_media --sync     # run inline (no worker needed)
    python manage.py transcode_media --kind video --limit 10
"""

from django.core.management.base import BaseCommand

from apps.vehicles.models import VehicleMedia
from apps.vehicles.tasks import process_vehicle_media


class Command(BaseCommand):
    help = "Transcode/compress existing vehicle media for feed-optimized delivery."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=["video", "photo"], help="Limit to a media kind.")
        parser.add_argument("--limit", type=int, default=0, help="Max items to process (0 = all).")
        parser.add_argument("--sync", action="store_true", help="Run inline instead of via Celery.")
        parser.add_argument("--force", action="store_true", help="Re-process even if already processed.")

    def handle(self, *args, **options):
        queryset = VehicleMedia.objects.exclude(s3_key="").filter(
            status__in=[VehicleMedia.Status.UPLOADED, VehicleMedia.Status.READY],
        )
        if options["kind"] == "video":
            queryset = queryset.filter(kind=VehicleMedia.Kind.VIDEO)
        elif options["kind"] == "photo":
            queryset = queryset.filter(kind=VehicleMedia.Kind.PHOTO)
        if not options["force"]:
            queryset = queryset.filter(processed_at__isnull=True)
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        media_ids = list(queryset.values_list("id", flat=True))
        if not media_ids:
            self.stdout.write(self.style.SUCCESS("No media to process."))
            return

        self.stdout.write(f"Processing {len(media_ids)} media item(s) "
                          f"({'sync' if options['sync'] else 'async'})...")
        for media_id in media_ids:
            if options["force"]:
                from apps.vehicles.models import VehicleMedia as _VM
                _VM.objects.filter(id=media_id, original_s3_key__isnull=False).update(processed_at=None)
            if options["sync"]:
                try:
                    process_vehicle_media.apply(args=[str(media_id)])
                except Exception:
                    self.stderr.write(self.style.WARNING(f"Failed: {media_id}"))
            else:
                process_vehicle_media.delay(str(media_id))

        self.stdout.write(self.style.SUCCESS("Done."))
