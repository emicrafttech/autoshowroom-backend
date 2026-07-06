from django.db.models import Count
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.views import EnvelopeMixin
from apps.buyers.auth import get_buyer_from_request
from apps.buyers.models import BuyerConversation, BuyerMessage
from apps.buyers.visit_tracking import record_vehicle_visit
from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle, VehicleMedia

from .feed import (
    annotate_feed_priority,
    apply_feed_filters,
    rank_feed_page,
    with_feed_publish_order,
)
from .serializers import (
    PublicDealerDetailSerializer,
    PublicLocationSerializer,
    PublicVehicleSerializer,
)


def public_vehicle_queryset():
    return (
        Vehicle.objects.filter(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
            dealer__operational_status=Dealer.OperationalStatus.ACTIVE,
        )
        .select_related("dealer", "location", "cover_media")
        .prefetch_related("media_items")
    )


class FeedView(EnvelopeMixin, ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicVehicleSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = public_vehicle_queryset()
        queryset = apply_feed_filters(queryset, self.request.query_params)
        queryset = annotate_feed_priority(queryset)
        return with_feed_publish_order(queryset)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            page_number = self.paginator.page.number
            ranked_page = rank_feed_page(
                page,
                params=request.query_params,
                page_number=page_number,
            )
            serializer = self.get_serializer(ranked_page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class FeedVehicleDetailView(EnvelopeMixin, RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicVehicleSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return public_vehicle_queryset()

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        if request.headers.get("Authorization"):
            try:
                buyer = get_buyer_from_request(request)
            except Exception:
                buyer = None
            if buyer:
                vehicle = self.get_object()
                record_vehicle_visit(buyer=buyer, vehicle=vehicle)
                from apps.leads.services import sync_lead_from_vehicle_view

                sync_lead_from_vehicle_view(buyer=buyer, vehicle=vehicle)
        return response


class FeedDealerDetailView(EnvelopeMixin, RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicDealerDetailSerializer
    lookup_field = "slug"

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Dealer.objects.filter(
            operational_status=Dealer.OperationalStatus.ACTIVE,
        ).prefetch_related("locations")

    def retrieve(self, request, *args, **kwargs):
        dealer = self.get_object()
        data = self.get_serializer(dealer).data

        vehicles_qs = (
            Vehicle.objects.filter(dealer=dealer)
            .select_related("dealer", "location", "cover_media")
            .prefetch_related("media_items")
        )
        active_qs = vehicles_qs.filter(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
        )
        inventory_qs = (
            vehicles_qs.filter(
                status__in=[Vehicle.Status.AVAILABLE, Vehicle.Status.RESERVED],
                listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            )
            .order_by("-published_at", "-updated_at")
        )

        data["activeListings"] = active_qs.count()
        data["soldCount"] = vehicles_qs.filter(status=Vehicle.Status.SOLD).count()
        data["responseTimeMins"] = self._response_time_mins(dealer)
        data["coverImageUrl"] = self._cover_image_url(active_qs, inventory_qs)
        data["vehicles"] = PublicVehicleSerializer(
            inventory_qs,
            many=True,
            context={"request": request},
        ).data
        return Response(data)

    def _cover_image_url(self, active_qs, inventory_qs):
        cover_vehicle = (
            active_qs.exclude(cover_media__isnull=True).order_by("-published_at").first()
        )
        if cover_vehicle and cover_vehicle.cover_media_id:
            return cover_vehicle.cover_media.url or ""
        showcase = inventory_qs.first()
        if showcase is not None:
            photo = (
                showcase.media_items.filter(kind=VehicleMedia.Kind.PHOTO)
                .order_by("sort_order")
                .first()
            )
            if photo:
                return photo.url or ""
        return ""

    def _response_time_mins(self, dealer):
        conversations = (
            BuyerConversation.objects.filter(dealer=dealer)
            .order_by("-created_at")[:100]
        )
        deltas = []
        for convo in conversations:
            messages = list(convo.messages.order_by("created_at"))
            first_buyer_at = None
            first_dealer_after = None
            for message in messages:
                if (
                    message.sender_type == BuyerMessage.SenderType.BUYER
                    and first_buyer_at is None
                ):
                    first_buyer_at = message.created_at
                elif (
                    message.sender_type == BuyerMessage.SenderType.DEALER
                    and first_buyer_at is not None
                ):
                    first_dealer_after = message.created_at
                    break
            if first_buyer_at and first_dealer_after:
                delta = (first_dealer_after - first_buyer_at).total_seconds() / 60
                if delta >= 0:
                    deltas.append(delta)
        if not deltas:
            return None
        deltas.sort()
        return int(deltas[len(deltas) // 2])


class FeedLocationsView(EnvelopeMixin, ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicLocationSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            DealerLocation.objects.filter(
                dealer__operational_status=Dealer.OperationalStatus.ACTIVE,
                vehicles__status=Vehicle.Status.AVAILABLE,
                vehicles__listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
                vehicles__feed_ready=True,
            )
            .select_related("dealer")
            .distinct()
        )


class FeedMetaView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        vehicles = public_vehicle_queryset()
        return Response(
            {
                "makes": list(
                    vehicles.values("make")
                    .annotate(count=Count("id"))
                    .order_by("make")
                ),
                "bodyTypes": list(
                    vehicles.values("body_type")
                    .annotate(count=Count("id"))
                    .order_by("body_type")
                ),
                "totalVehicles": vehicles.count(),
            }
        )
