from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.dateparse import parse_datetime

from apps.common.permissions import IsActiveDealerStaff
from apps.common.views import EnvelopeMixin
from apps.buyers.auth import get_buyer_from_request
from apps.marketplace.views import public_vehicle_queryset

from .availability import build_vehicle_booking_availability
from .models import Appointment, Booking
from .serializers import (
    AppointmentSerializer,
    BookingAvailabilityRequestSerializer,
    BookingSerializer,
    BookingSummarySerializer,
    booking_summary_for_vehicle,
)


class BookingCreateView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        buyer = get_buyer_from_request(request)
        bookings = Booking.objects.filter(buyer=buyer).order_by(
            "-scheduled_at", "-created_at"
        )
        return Response(BookingSerializer(bookings, many=True).data)

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


class BookingAvailabilityView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = BookingAvailabilityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle = public_vehicle_queryset().filter(id=serializer.validated_data["vehicleId"]).first()
        if not vehicle:
            return Response({"detail": "Public vehicle not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            build_vehicle_booking_availability(
                vehicle,
                from_date=serializer.validated_data.get("fromDate"),
                to_date=serializer.validated_data.get("toDate"),
            )
        )


class AppointmentViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [IsActiveDealerStaff]
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
            from apps.notifications.services import notify_booking_cancelled

            notify_booking_cancelled(appointment.booking)
        appointment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="confirm")
    def confirm(self, request, pk=None):
        appointment = self.get_object()
        if appointment.booking_id:
            was_confirmed = appointment.booking.status == Booking.Status.CONFIRMED
            appointment.booking.status = Booking.Status.CONFIRMED
            appointment.booking.save(update_fields=["status", "updated_at"])
            if not was_confirmed:
                from apps.notifications.services import notify_booking_confirmed

                notify_booking_confirmed(appointment.booking)
        return Response(AppointmentSerializer(appointment, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        appointment = self.get_object()
        raw = request.data.get("scheduledAt")
        if not raw:
            return Response({"detail": "scheduledAt is required."}, status=status.HTTP_400_BAD_REQUEST)
        scheduled_at = parse_datetime(raw) if isinstance(raw, str) else raw
        if not scheduled_at:
            return Response({"detail": "scheduledAt must be a valid ISO datetime."}, status=status.HTTP_400_BAD_REQUEST)
        appointment.scheduled_at = scheduled_at
        appointment.save(update_fields=["scheduled_at", "updated_at"])
        if appointment.booking_id:
            appointment.booking.scheduled_at = scheduled_at
            appointment.booking.status = Booking.Status.RESCHEDULED
            appointment.booking.save(update_fields=["scheduled_at", "status", "updated_at"])
            from apps.notifications.services import notify_booking_rescheduled

            notify_booking_rescheduled(appointment.booking)
        return Response(AppointmentSerializer(appointment, context={"request": request}).data)
