from rest_framework.routers import SimpleRouter

from .views import DealerNotificationViewSet, PlatformNotificationViewSet

router = SimpleRouter(trailing_slash=False)
router.register("notifications", DealerNotificationViewSet, basename="notification")
router.register("platform/notifications", PlatformNotificationViewSet, basename="platform-notification")

urlpatterns = router.urls
