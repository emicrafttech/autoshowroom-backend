import logging
from pathlib import Path

from celery import shared_task
from django.utils import timezone

from .models import VehicleMedia
from .processing import (
    cleanup_work_dir,
    compress_image,
    make_work_dir,
    process_video,
)
from .storage import (
    build_processed_key,
    download_media_object,
    upload_media_object,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=2,
)
def process_vehicle_media(self, media_id: str) -> None:
    media = VehicleMedia.objects.filter(id=media_id).first()
    if media is None:
        logger.warning("process_vehicle_media: media %s not found", media_id)
        return

    if media.processed_at and media.original_s3_key:
        logger.info("process_vehicle_media: media %s already processed", media_id)
        return

    if not media.s3_key:
        logger.warning("process_vehicle_media: media %s has no s3_key", media_id)
        return

    source_key = media.original_s3_key or media.s3_key

    media.status = VehicleMedia.Status.PROCESSING
    media.save(update_fields=["status", "updated_at"])

    work_dir = make_work_dir()
    try:
        source_path = work_dir / _source_filename(media)
        download_media_object(source_key, source_path)

        if media.kind == VehicleMedia.Kind.VIDEO:
            _process_video_media(media, source_path, work_dir)
        else:
            _process_photo_media(media, source_path, work_dir)

        media.processed_at = timezone.now()
        media.status = VehicleMedia.Status.READY
        media.save(
            update_fields=[
                "status",
                "url",
                "thumbnail_url",
                "s3_key",
                "original_s3_key",
                "original_url",
                "processed_at",
                "updated_at",
            ]
        )
    except Exception:
        logger.exception("process_vehicle_media: failed for media %s", media_id)
        media.status = VehicleMedia.Status.READY
        media.save(update_fields=["status", "updated_at"])
        raise
    finally:
        cleanup_work_dir(work_dir)


def _source_filename(media: VehicleMedia) -> str:
    suffix = Path(media.file_name or media.s3_key).suffix or ".bin"
    return f"source{suffix}"


def _process_video_media(
    media: VehicleMedia,
    source_path: Path,
    work_dir: Path,
) -> None:
    result = process_video(source_path, work_dir)

    processed_key = build_processed_key(str(media.vehicle_id), ".mp4")
    new_url = upload_media_object(processed_key, result.video_path, "video/mp4")

    if not media.original_s3_key:
        media.original_s3_key = media.s3_key
        media.original_url = media.url
    media.s3_key = processed_key
    media.url = new_url
    media.content_type = "video/mp4"

    if result.poster_path is not None:
        poster_key = build_processed_key(str(media.vehicle_id), ".jpg")
        poster_url = upload_media_object(poster_key, result.poster_path, "image/jpeg")
        media.thumbnail_url = poster_url


def _process_photo_media(
    media: VehicleMedia,
    source_path: Path,
    work_dir: Path,
) -> None:
    output_path = compress_image(source_path, work_dir / "compressed.jpg")

    processed_key = build_processed_key(str(media.vehicle_id), ".jpg")
    new_url = upload_media_object(processed_key, output_path, "image/jpeg")

    if not media.original_s3_key:
        media.original_s3_key = media.s3_key
        media.original_url = media.url
    media.s3_key = processed_key
    media.url = new_url
    media.content_type = "image/jpeg"
    if not media.thumbnail_url:
        media.thumbnail_url = new_url
