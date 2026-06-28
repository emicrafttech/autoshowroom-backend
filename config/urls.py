from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.urls import auth_urlpatterns, staff_invitation_urlpatterns
from apps.vehicles.urls import catalog_urlpatterns
import apps.common.openapi  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("v1/schema/", SpectacularAPIView.as_view(), name="v1-schema"),
    path("v1/swagger/", SpectacularSwaggerView.as_view(url_name="v1-schema"), name="v1-swagger-ui"),
    path("", include("apps.core.urls")),
    path("v1/auth/", include(auth_urlpatterns)),
    path("v1/staff-invitations/", include(staff_invitation_urlpatterns)),
    path("v1/dealers/", include("apps.dealers.urls")),
    path("v1/catalog/", include(catalog_urlpatterns)),
    path("v1/", include("apps.marketplace.urls")),
    path("v1/", include("apps.leads.urls")),
    path("v1/", include("apps.buyers.urls")),
    path("v1/", include("apps.bookings.urls")),
    path("v1/", include("apps.billing.urls")),
    path("v1/", include("apps.platform.urls")),
    path("v1/", include("apps.notifications.urls")),
    path("v1/", include("apps.vehicles.urls")),
]
