from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AppointmentViewSet,
    BookingCreateView,
    BookingSummaryView,
)

router = SimpleRouter(trailing_slash=False)
router.register("appointments", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("bookings", BookingCreateView.as_view(), name="booking-create"),
    path("bookings/summaries", BookingSummaryView.as_view(), name="booking-summary"),
    path("", include(router.urls)),
]
