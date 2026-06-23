from django.urls import path

from .views import (
    FeedDealerDetailView,
    FeedLocationsView,
    FeedMetaView,
    FeedVehicleDetailView,
    FeedView,
)

urlpatterns = [
    path("feed", FeedView.as_view(), name="feed"),
    path("feed/vehicles/<uuid:id>", FeedVehicleDetailView.as_view(), name="feed-vehicle-detail"),
    path("feed/dealers/<slug:slug>", FeedDealerDetailView.as_view(), name="feed-dealer-detail"),
    path("feed/locations", FeedLocationsView.as_view(), name="feed-locations"),
    path("feed/meta", FeedMetaView.as_view(), name="feed-meta"),
]
