from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    DealerContextView,
    DealerLocationViewSet,
    DealerProfileView,
    DealerPrivacyRequestView,
    DealerSanctionAppealView,
    DealerSanctionStatusView,
    DealerSelfVerificationView,
    DealerStaffViewSet,
    DealerVerificationViewSet,
    DealerVerificationDocumentView,
)

router = SimpleRouter(trailing_slash=False)
router.register(
    "me/locations",
    DealerLocationViewSet,
    basename="dealer-location",
)
router.register("me/staff", DealerStaffViewSet, basename="dealer-staff")
router.register("", DealerVerificationViewSet, basename="dealer")

urlpatterns = [
    path("me", DealerProfileView.as_view(), name="dealer-profile"),
    path("me/context", DealerContextView.as_view(), name="dealer-context"),
    path("me/verification", DealerSelfVerificationView.as_view(), name="dealer-verification"),
    path("me/verification/submit", DealerSelfVerificationView.as_view(), name="dealer-verification-submit"),
    path("me/verification/resubmit", DealerSelfVerificationView.as_view(), name="dealer-verification-resubmit"),
    path(
        "me/verification/documents",
        DealerVerificationDocumentView.as_view(),
        name="dealer-verification-document",
    ),
    path("me/sanction-status", DealerSanctionStatusView.as_view(), name="dealer-sanction-status"),
    path("me/sanction-appeal", DealerSanctionAppealView.as_view(), name="dealer-sanction-appeal"),
    path("me/privacy-request", DealerPrivacyRequestView.as_view(), name="dealer-privacy-request"),
    path("", include(router.urls)),
]
