from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsDealerStaff
from apps.common.views import EnvelopeMixin
from apps.marketplace.views import public_vehicle_queryset

from .models import Appointment, Booking
from .serializers import (
    AppointmentSerializer,
    BookingSerializer,
    BookingSummarySerializer,
    booking_summary_for_vehicle,
)


class BookingCreateView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            return Response(
                {"detail": "Buyer bearer token is required before booking."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = BookingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingSummaryView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = BookingSummarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle = public_vehicle_queryset().filter(id=serializer.validated_data["vehicleId"]).first()
        if not vehicle:
            return Response({"detail": "Public vehicle not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(booking_summary_for_vehicle(vehicle))


class AppointmentViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [IsDealerStaff]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Appointment.objects.filter(
            dealer_id=self.request.user.dealer_id,
        ).select_related("booking", "location", "vehicle")
        location_id = self.request.query_params.get("locationId")
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(dealer=self.request.user.dealer)

    @action(detail=True, methods=["patch"], url_path="cancel")
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        if appointment.booking_id:
            appointment.booking.status = Booking.Status.CANCELLED
            appointment.booking.save(update_fields=["status", "updated_at"])
        appointment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
