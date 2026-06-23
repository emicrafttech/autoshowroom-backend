from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.common.permissions import (
    IsDealerStaffOrVehicleReviewer,
    has_vehicle_review_permission,
)
from apps.common.views import EnvelopeMixin
from apps.billing.limits import can_publish_listing, get_listing_limit

from .models import Vehicle, VehicleMedia
from .serializers import (
    VehicleMediaCompleteSerializer,
    VehicleMediaUploadSessionSerializer,
    VehicleReviewDecisionSerializer,
    VehicleSerializer,
    VehicleStatusSerializer,
)
from .storage import build_media_key, create_presigned_upload


class VehicleViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [IsDealerStaffOrVehicleReviewer]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Vehicle.objects.select_related(
            "dealer",
            "location",
            "cover_media",
        ).prefetch_related("media_items")
        user = self.request.user

        if not has_vehicle_review_permission(user):
            queryset = queryset.filter(dealer_id=user.dealer_id)
            location_id = self.request.query_params.get("locationId")
            if location_id:
                queryset = queryset.filter(location_id=location_id)

        filters = {
            "status": "status",
            "listingVerificationStatus": "listing_verification_status",
            "dealerId": "dealer_id",
            "locationId": "location_id",
            "make": "make__iexact",
            "model": "model__iexact",
        }
        for param, lookup in filters.items():
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{lookup: value})

        search = self.request.query_params.get("q")
        if search:
            queryset = queryset.filter(
                Q(make__icontains=search)
                | Q(model__icontains=search)
                | Q(trim__icontains=search)
                | Q(vin__icontains=search)
                | Q(chassis_number__icontains=search)
                | Q(dealer__name__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "dealer_id", None):
            raise PermissionDenied("Dealer staff credentials are required.")
        if Vehicle.objects.filter(dealer=user.dealer).count() >= get_listing_limit(user.dealer):
            raise PermissionDenied("Your current plan listing limit has been reached.")
        serializer.save(dealer=user.dealer)

    def perform_update(self, serializer):
        if serializer.instance.dealer_id != self.request.user.dealer_id:
            if not has_vehicle_review_permission(self.request.user):
                raise PermissionDenied("You cannot update this listing.")
        serializer.save()

    @action(detail=True, methods=["patch"], url_path="status")
    def status(self, request, pk=None):
        vehicle = self.get_object()
        if vehicle.dealer_id != request.user.dealer_id:
            raise PermissionDenied("Only the owning dealer can change listing status.")

        serializer = VehicleStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        previous_status = vehicle.status
        now = timezone.now()

        vehicle.status = new_status
        if new_status == Vehicle.Status.AVAILABLE:
            if previous_status in [Vehicle.Status.HIDDEN, Vehicle.Status.SOLD] and not can_publish_listing(vehicle.dealer):
                raise PermissionDenied("Your current plan listing limit has been reached.")
            vehicle.dealer_attestation_at = now
            vehicle.listing_verification_status = (
                Vehicle.ListingVerificationStatus.PENDING_REVIEW
            )
            vehicle.feed_ready = False
        elif new_status == Vehicle.Status.HIDDEN:
            vehicle.feed_ready = False
            vehicle.published_at = None
        vehicle.save(
            update_fields=[
                "status",
                "dealer_attestation_at",
                "listing_verification_status",
                "feed_ready",
                "published_at",
                "updated_at",
            ]
        )
        return Response(VehicleSerializer(vehicle, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="refresh")
    def refresh(self, request, pk=None):
        vehicle = self.get_object()
        if vehicle.dealer_id != request.user.dealer_id:
            raise PermissionDenied("Only the owning dealer can refresh this listing.")

        vehicle.refreshed_at = timezone.now()
        vehicle.save(update_fields=["refreshed_at", "updated_at"])
        return Response(VehicleSerializer(vehicle, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="media/upload-session")
    def create_media_upload_session(self, request, pk=None):
        vehicle = self.get_object()
        if vehicle.dealer_id != request.user.dealer_id:
            raise PermissionDenied("Only the owning dealer can add media.")

        serializer = VehicleMediaUploadSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        expires_at = now + timedelta(seconds=settings.MEDIA_UPLOAD_URL_EXPIRES_SECONDS)
        existing_count = vehicle.media_items.count()
        items = []

        for index, item in enumerate(serializer.validated_data["items"], start=1):
            key = build_media_key(str(vehicle.id), item["fileName"])
            upload = create_presigned_upload(key, item["contentType"])
            media = VehicleMedia.objects.create(
                vehicle=vehicle,
                kind=item["kind"],
                url=upload.public_url,
                content_type=item["contentType"],
                file_name=item["fileName"],
                file_size=item.get("fileSize"),
                s3_key=upload.key,
                sort_order=item.get("sortOrder", existing_count + index),
                upload_expires_at=expires_at,
            )
            items.append(
                {
                    "mediaId": str(media.id),
                    "uploadUrl": upload.upload_url,
                    "publicUrl": upload.public_url,
                    "expiresAt": expires_at.isoformat(),
                }
            )

        return Response({"items": items}, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"media/(?P<media_id>[^/.]+)/complete",
    )
    def complete_media_upload(self, request, pk=None, media_id=None):
        vehicle = self.get_object()
        if vehicle.dealer_id != request.user.dealer_id:
            raise PermissionDenied("Only the owning dealer can complete media uploads.")

        media = vehicle.media_items.filter(id=media_id).first()
        if not media:
            raise ValidationError("Media item not found for this vehicle.")

        serializer = VehicleMediaCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media.status = serializer.validated_data.get(
            "status",
            VehicleMedia.Status.UPLOADED,
        )
        if "thumbnailUrl" in serializer.validated_data:
            media.thumbnail_url = serializer.validated_data["thumbnailUrl"]
        media.save(update_fields=["status", "thumbnail_url", "updated_at"])

        if vehicle.cover_media_id is None and media.kind == VehicleMedia.Kind.PHOTO:
            vehicle.cover_media = media
            vehicle.save(update_fields=["cover_media", "updated_at"])

        vehicle = self.get_queryset().get(id=vehicle.id)
        return Response(VehicleSerializer(vehicle, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="review/approve")
    def approve_review(self, request, pk=None):
        self.require_reviewer()
        vehicle = self.get_object()
        if (
            vehicle.listing_verification_status
            != Vehicle.ListingVerificationStatus.PENDING_REVIEW
        ):
            raise ValidationError("Listing is not pending review.")

        now = timezone.now()
        vehicle.listing_verification_status = Vehicle.ListingVerificationStatus.APPROVED
        vehicle.listing_approved_at = now
        vehicle.listing_rejected_reason = None
        vehicle.feed_ready = vehicle.status == Vehicle.Status.AVAILABLE
        vehicle.published_at = now if vehicle.feed_ready else vehicle.published_at
        vehicle.save()
        return Response(VehicleSerializer(vehicle, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="review/reject")
    def reject_review(self, request, pk=None):
        self.require_reviewer()
        vehicle = self.get_object()
        serializer = VehicleReviewDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason") or "Listing rejected"

        vehicle.listing_verification_status = Vehicle.ListingVerificationStatus.REJECTED
        vehicle.listing_rejected_reason = reason
        vehicle.feed_ready = False
        vehicle.published_at = None
        vehicle.save()
        return Response(VehicleSerializer(vehicle, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="review/remove-from-feed")
    def remove_from_feed(self, request, pk=None):
        self.require_reviewer()
        vehicle = self.get_object()
        serializer = VehicleReviewDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason") or "Removed from feed"

        vehicle.feed_ready = False
        vehicle.published_at = None
        vehicle.listing_rejected_reason = reason
        vehicle.save()
        return Response(VehicleSerializer(vehicle, context={"request": request}).data)

    def require_reviewer(self):
        if not has_vehicle_review_permission(self.request.user):
            raise PermissionDenied("Listing review permission is required.")
