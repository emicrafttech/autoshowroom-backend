from django.urls import path

from .views import (
    BuyerBlockedDealerDetailView,
    BuyerBlockedDealersView,
    BuyerChatAttachmentUploadSessionView,
    BuyerChatDetailView,
    BuyerChatListView,
    BuyerChatMarkReadView,
    BuyerChatMessageView,
    BuyerOpenChatView,
    BuyerPriceAlertDetailView,
    BuyerPriceAlertsView,
    BuyerProfilePhotoUploadSessionView,
    BuyerProfileView,
    BuyerPushTokenView,
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
    path(
        "buyers/profile/photo/upload-session",
        BuyerProfilePhotoUploadSessionView.as_view(),
        name="buyer-profile-photo-upload-session",
    ),
    path("buyers/saved", BuyerSavedVehiclesView.as_view(), name="buyer-saved-list"),
    path("buyers/saved/<uuid:vehicle_id>", BuyerSavedVehicleActionView.as_view(), name="buyer-saved-action"),
    path("buyers/visits", BuyerVisitsView.as_view(), name="buyer-visits"),
    path("buyers/push-token", BuyerPushTokenView.as_view(), name="buyer-push-token"),
    path("buyers/price-alerts", BuyerPriceAlertsView.as_view(), name="buyer-price-alerts"),
    path(
        "buyers/price-alerts/<uuid:alert_id>",
        BuyerPriceAlertDetailView.as_view(),
        name="buyer-price-alert-detail",
    ),
    path("buyers/blocked-dealers", BuyerBlockedDealersView.as_view(), name="buyer-blocked-dealers"),
    path(
        "buyers/blocked-dealers/<slug:dealer_slug>",
        BuyerBlockedDealerDetailView.as_view(),
        name="buyer-blocked-dealer-detail",
    ),
    path("buyers/chat", BuyerChatListView.as_view(), name="buyer-chat-list"),
    path("buyers/chat/vehicles/<uuid:vehicle_id>", BuyerOpenChatView.as_view(), name="buyer-chat-open"),
    path("buyers/chat/conversations/<uuid:conversation_id>", BuyerChatDetailView.as_view(), name="buyer-chat-detail"),
    path(
        "buyers/chat/conversations/<uuid:conversation_id>/read",
        BuyerChatMarkReadView.as_view(),
        name="buyer-chat-mark-read",
    ),
    path(
        "buyers/chat/conversations/<uuid:conversation_id>/attachments/upload-session",
        BuyerChatAttachmentUploadSessionView.as_view(),
        name="buyer-chat-attachment-upload-session",
    ),
    path(
        "buyers/chat/conversations/<uuid:conversation_id>/messages",
        BuyerChatMessageView.as_view(),
        name="buyer-chat-message",
    ),
]
