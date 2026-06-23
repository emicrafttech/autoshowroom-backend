from django.urls import path

from .views import (
    BuyerProfileView,
    BuyerSavedVehicleActionView,
    BuyerSavedVehiclesView,
    BuyerSessionRefreshView,
    BuyerSignInStartView,
    BuyerSignInVerifyView,
    BuyerVisitsView,
)

urlpatterns = [
    path("buyers/sign-in/start", BuyerSignInStartView.as_view(), name="buyer-sign-in-start"),
    path("buyers/sign-in/verify", BuyerSignInVerifyView.as_view(), name="buyer-sign-in-verify"),
    path("buyers/session/refresh", BuyerSessionRefreshView.as_view(), name="buyer-session-refresh"),
    path("buyers/profile", BuyerProfileView.as_view(), name="buyer-profile"),
    path("buyers/saved", BuyerSavedVehiclesView.as_view(), name="buyer-saved-list"),
    path("buyers/saved/<uuid:vehicle_id>", BuyerSavedVehicleActionView.as_view(), name="buyer-saved-action"),
    path("buyers/visits", BuyerVisitsView.as_view(), name="buyer-visits"),
]
