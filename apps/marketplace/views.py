from django.db.models import Count, Q
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.views import EnvelopeMixin
from apps.buyers.auth import get_buyer_from_request
from apps.buyers.models import VehicleVisit
from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle

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
        params = self.request.query_params
        filters = {
            "make": "make__iexact",
            "model": "model__iexact",
            "bodyType": "body_type",
            "dealerSlug": "dealer__slug",
            "area": "location__area__iexact",
        }
        for param, lookup in filters.items():
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{lookup: value})

        min_price = params.get("minPriceNgn")
        max_price = params.get("maxPriceNgn")
        min_year = params.get("minYear")
        max_year = params.get("maxYear")
        if min_price:
            queryset = queryset.filter(price_ngn__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_ngn__lte=max_price)
        if min_year:
            queryset = queryset.filter(year__gte=min_year)
        if max_year:
            queryset = queryset.filter(year__lte=max_year)

        search = params.get("q")
        if search:
            queryset = queryset.filter(
                Q(make__icontains=search)
                | Q(model__icontains=search)
                | Q(trim__icontains=search)
                | Q(dealer__name__icontains=search)
            )
        return queryset.order_by("-published_at", "-updated_at")


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
                VehicleVisit.objects.create(buyer=buyer, vehicle=self.get_object())
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
