from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AppointmentViewSet,
    BookingAvailabilityView,
    BookingCreateView,
    BookingSummaryView,
)

router = SimpleRouter(trailing_slash=False)
router.register("appointments", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("bookings", BookingCreateView.as_view(), name="booking-create"),
    path("bookings/summaries", BookingSummaryView.as_view(), name="booking-summary"),
    path("bookings/availability", BookingAvailabilityView.as_view(), name="booking-availability"),
    path("", include(router.urls)),
]
