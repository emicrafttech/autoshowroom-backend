from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .catalog_views import CatalogMakesView, CatalogModelsView
from .chat_views import (
    VehicleChatDetailView,
    VehicleChatListCreateView,
    VehicleChatMessageCreateView,
)
from .views import VehicleViewSet

router = SimpleRouter(trailing_slash=False)
router.register("vehicles", VehicleViewSet, basename="vehicle")

catalog_urlpatterns = [
    path("makes", CatalogMakesView.as_view(), name="catalog-makes"),
    path("models", CatalogModelsView.as_view(), name="catalog-models"),
]

urlpatterns = [
    path("vehicles/<uuid:vehicle_id>/chats", VehicleChatListCreateView.as_view(), name="vehicle-chat-list"),
    path("vehicles/<uuid:vehicle_id>/chats/<uuid:chat_id>", VehicleChatDetailView.as_view(), name="vehicle-chat-detail"),
    path(
        "vehicles/<uuid:vehicle_id>/chats/<uuid:chat_id>/messages",
        VehicleChatMessageCreateView.as_view(),
        name="vehicle-chat-message",
    ),
    path("", include(router.urls)),
]
