from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AuditExportView,
    AuditLogViewSet,
    ContentReportViewSet,
    DataSubjectRequestViewSet,
    DealerDetailView,
    DealerDirectoryView,
    PlatformDealerDocumentApproveView,
    PlatformDealerDocumentRejectView,
    PlatformDealerMessageView,
    PlatformDealerSuspendView,
    DealerProvisionView,
    DealerQueueView,
    DealerVerificationStatsView,
    DealerSanctionViewSet,
    PlatformLoginView,
    PlatformLocationRejectPremisesView,
    PlatformLocationRequestInfoView,
    PlatformLocationStartReviewView,
    PlatformLocationVerifyPremisesView,
    PlatformLocationView,
    PlatformMeView,
    PlatformMfaView,
    PlatformOverviewView,
    PlatformRefreshView,
    PlatformRoleViewSet,
    PlatformSettingsView,
    PlatformSettingViewSet,
    PlatformUserViewSet,
    SanctionAppealViewSet,
    SecurityIncidentViewSet,
    StatsView,
    WatchlistEntryViewSet,
)
from apps.accounts.models import StaffUser
from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle

from .models import (
    AuditLog,
    ContentReport,
    DataSubjectRequest,
    PlatformRole,
    SanctionAppeal,
    SecurityIncident,
    WatchlistEntry,
)

router = SimpleRouter(trailing_slash=False)
router.register("platform/roles", PlatformRoleViewSet, basename="platform-role")
router.register("platform/reports", ContentReportViewSet, basename="platform-report")
router.register("platform/dsr-requests", DataSubjectRequestViewSet, basename="platform-dsr-request")
router.register("platform/sanctions", DealerSanctionViewSet, basename="platform-sanction")
router.register("platform/appeals", SanctionAppealViewSet, basename="platform-appeal")
router.register("platform/users", PlatformUserViewSet, basename="platform-user")
router.register("platform/settings-records", PlatformSettingViewSet, basename="platform-setting")
router.register("platform/security-incidents", SecurityIncidentViewSet, basename="platform-security-incident")
router.register("platform/watchlists", WatchlistEntryViewSet, basename="platform-watchlist")
router.register("platform/dealers/directory", DealerDirectoryView, basename="platform-dealer-directory")
router.register("platform/audit", AuditLogViewSet, basename="platform-audit")
router.register("platform/audit-trail", AuditLogViewSet, basename="platform-audit-trail")

urlpatterns = [
    path("platform/auth/login", PlatformLoginView.as_view(), name="platform-auth-login"),
    path("platform/auth/me", PlatformMeView.as_view(), name="platform-auth-me"),
    path("platform/auth/refresh", PlatformRefreshView.as_view(), name="platform-auth-refresh"),
    path("platform/auth/mfa/enroll", PlatformMfaView.as_view(), name="platform-mfa-enroll"),
    path("platform/auth/mfa/verify", PlatformMfaView.as_view(), name="platform-mfa-verify"),
    path("platform/overview", PlatformOverviewView.as_view(), name="platform-overview"),
    path(
        "platform/listings/review-queue/stats",
        StatsView.as_view(
            model=Vehicle,
            status_field="listing_verification_status",
            filter_kwargs={"listing_verification_status": Vehicle.ListingVerificationStatus.PENDING_REVIEW},
            required_capability="listing_review.read",
        ),
        name="platform-listing-review-stats",
    ),
    path("platform/settings", PlatformSettingsView.as_view(), name="platform-settings"),
    path("platform/reports/stats", StatsView.as_view(model=ContentReport, required_capability="content_reports.read"), name="platform-report-stats"),
    path("platform/reports/stats/overdue", StatsView.as_view(model=ContentReport, required_capability="content_reports.read"), name="platform-report-overdue-stats"),
    path("platform/dsr-requests/stats", StatsView.as_view(model=DataSubjectRequest, required_capability="settings.read"), name="platform-dsr-stats"),
    path("platform/appeals/stats", StatsView.as_view(model=SanctionAppeal, required_capability="sanctions.read"), name="platform-appeals-stats"),
    path("platform/security-incidents/stats", StatsView.as_view(model=SecurityIncident, required_capability="settings.read"), name="platform-security-stats"),
    path("platform/watchlists/stats", StatsView.as_view(model=WatchlistEntry, required_capability="watchlists.read"), name="platform-watchlist-stats"),
    path("platform/roles/stats", StatsView.as_view(model=PlatformRole, status_field="name", required_capability="platform_users.read"), name="platform-role-stats"),
    path(
        "platform/users/stats",
        StatsView.as_view(model=StaffUser, status_field="is_active", filter_kwargs={"is_staff": True}, required_capability="platform_users.read"),
        name="platform-user-stats",
    ),
    path("platform/audit-trail/export", AuditExportView.as_view(), name="platform-audit-export"),
    path("platform/audit-trail/recent", AuditExportView.as_view(), name="platform-audit-recent"),
    path("platform/audit-trail/stats", StatsView.as_view(model=AuditLog, status_field="action", required_capability="audit.read"), name="platform-audit-stats"),
    path("platform/audit-logs", AuditExportView.as_view(), name="platform-audit-logs"),
    path("platform/dealers/provision", DealerProvisionView.as_view(), name="platform-dealer-provision"),
    path("platform/dealers/verification-queue", DealerQueueView.as_view(), name="platform-dealer-verification-queue"),
    path("platform/dealers/verification-queue/stats", DealerVerificationStatsView.as_view(), name="platform-dealer-verification-stats"),
    path("platform/locations/premises-queue", DealerQueueView.as_view(queue_type="premises"), name="platform-premises-queue"),
    path(
        "platform/locations/premises-queue/stats",
        StatsView.as_view(
            model=DealerLocation,
            status_field="premises_verification_status",
            required_capability="premises.read",
        ),
        name="platform-premises-stats",
    ),
    path("platform/locations/<uuid:location_id>", PlatformLocationView.as_view(), name="platform-location-detail"),
    path("platform/locations/<uuid:location_id>/start-review", PlatformLocationStartReviewView.as_view(), name="platform-location-start-review"),
    path("platform/locations/<uuid:location_id>/verify-premises", PlatformLocationVerifyPremisesView.as_view(), name="platform-location-verify"),
    path("platform/locations/<uuid:location_id>/reject-premises", PlatformLocationRejectPremisesView.as_view(), name="platform-location-reject"),
    path("platform/locations/<uuid:location_id>/request-info", PlatformLocationRequestInfoView.as_view(), name="platform-location-request-info"),
    path("platform/dealers/<uuid:dealer_id>", DealerDetailView.as_view(), name="platform-dealer-detail"),
    path("platform/dealers/<uuid:dealer_id>/message", PlatformDealerMessageView.as_view(), name="platform-dealer-message"),
    path("platform/dealers/<uuid:dealer_id>/suspend", PlatformDealerSuspendView.as_view(), name="platform-dealer-suspend"),
    path(
        "platform/dealer-documents/<uuid:document_id>/approve",
        PlatformDealerDocumentApproveView.as_view(),
        name="platform-dealer-document-approve",
    ),
    path(
        "platform/dealer-documents/<uuid:document_id>/reject",
        PlatformDealerDocumentRejectView.as_view(),
        name="platform-dealer-document-reject",
    ),
    path("", include(router.urls)),
]
