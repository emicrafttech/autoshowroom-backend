from django.urls import path

from .consumers import VehicleChatConsumer


websocket_urlpatterns = [
    path(
        "ws/vehicles/<uuid:vehicle_id>/chats/<uuid:chat_id>/",
        VehicleChatConsumer.as_asgi(),
    ),
]
