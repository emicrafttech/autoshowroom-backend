from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import boto3
from django.conf import settings


@dataclass(frozen=True)
class PresignedUpload:
    key: str
    upload_url: str
    public_url: str


def build_media_key(vehicle_id: str, file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    safe_suffix = suffix if len(suffix) <= 16 else ""
    return f"{settings.MEDIA_UPLOAD_PREFIX}/{vehicle_id}/{uuid4().hex}{safe_suffix}"


def build_public_url(key: str) -> str:
    if settings.MEDIA_PUBLIC_BASE_URL:
        return f"{settings.MEDIA_PUBLIC_BASE_URL}/{key}"

    bucket = settings.AWS_STORAGE_BUCKET_NAME
    region = settings.AWS_S3_REGION_NAME
    if settings.AWS_S3_ENDPOINT_URL:
        return f"{settings.AWS_S3_ENDPOINT_URL.rstrip('/')}/{bucket}/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def create_presigned_upload(key: str, content_type: str) -> PresignedUpload:
    client_kwargs = {
        "region_name": settings.AWS_S3_REGION_NAME,
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
    }
    if settings.AWS_S3_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL

    client = boto3.client("s3", **client_kwargs)
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.MEDIA_UPLOAD_URL_EXPIRES_SECONDS,
    )
    return PresignedUpload(
        key=key,
        upload_url=upload_url,
        public_url=build_public_url(key),
    )


def delete_media_objects(keys: list[str]) -> None:
    if not keys:
        return

    client_kwargs = {
        "region_name": settings.AWS_S3_REGION_NAME,
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
    }
    if settings.AWS_S3_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL

    client = boto3.client("s3", **client_kwargs)
    for start in range(0, len(keys), 1000):
        chunk = keys[start:start + 1000]
        response = client.delete_objects(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
        )
        if response.get("Errors"):
            failed_keys = ", ".join(error.get("Key", "unknown") for error in response["Errors"])
            raise RuntimeError(f"Unable to delete media objects from storage: {failed_keys}")
