from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AnalyticsEventCreateView,
    GenericUploadCreateView,
    LeadViewSet,
    NotifyMeCreateView,
    PublicReportCreateView,
)

router = SimpleRouter(trailing_slash=False)
router.register("leads", LeadViewSet, basename="lead")

urlpatterns = [
    path("", include(router.urls)),
    path("notify-me", NotifyMeCreateView.as_view(), name="notify-me-create"),
    path("events", AnalyticsEventCreateView.as_view(), name="event-create"),
    path("reports", PublicReportCreateView.as_view(), name="report-create"),
    path("uploads", GenericUploadCreateView.as_view(), name="upload-create"),
]
