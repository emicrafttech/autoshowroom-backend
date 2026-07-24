from rest_framework import serializers
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)

from apps.accounts.views import (
    AcceptStaffInvitationView,
    ChangePasswordView,
    DealerSignupPasswordView,
    DealerSignupSetupView,
    DealerSignupStartView,
    DealerSignupVerifyView,
    LoginView,
    RefreshView,
    SessionLocationView,
    StaffInvitationPreviewView,
)
from apps.accounts.serializers import (
    AcceptStaffInvitationSerializer,
    ChangePasswordSerializer,
    DealerSignupPasswordSerializer,
    DealerSignupSetupSerializer,
    DealerSignupStartSerializer,
    DealerSignupVerifySerializer,
    LoginSerializer,
    RefreshSerializer,
    SessionLocationSerializer,
    StaffInvitationPreviewSerializer,
)
from apps.billing.views import (
    BillingPlansView,
    BillingSummaryView,
    CheckoutView,
    DowngradeRequestView,
    InvoiceDetailView,
    InvoiceListView,
    InvoicePdfView,
    PaystackWebhookView,
    PlatformBillingConfigView,
    PlatformBillingDisputeViewSet,
    PlatformBillingPlanViewSet,
    PlatformSubscriptionViewSet,
)
from apps.billing.serializers import (
    BillingPlanSerializer,
    CheckoutSerializer,
    DowngradeRequestSerializer,
    InvoiceSerializer,
    PaystackWebhookSerializer,
    PublicBillingPlanSerializer,
    SubscriptionSerializer,
)
from apps.bookings.views import (
    AppointmentViewSet,
    BookingCreateView,
    BookingSummaryView,
)
from apps.bookings.serializers import (
    BookingSerializer,
    BookingSummarySerializer,
)
from apps.core.views import health_check
from apps.buyers.views import (
    BuyerProfileView,
    BuyerSavedVehicleActionView,
    BuyerSavedVehiclesView,
    BuyerSessionRefreshView,
    BuyerSignInStartView,
    BuyerSignInVerifyView,
    BuyerVisitsView,
)
from apps.buyers.serializers import (
    BuyerConversationSerializer,
    BuyerProfileSerializer,
    BuyerSignInStartSerializer,
    BuyerSignInVerifySerializer,
    OpenConversationSerializer,
    SavedVehicleSerializer,
    VehicleVisitSerializer,
)
from apps.dealers.views import (
    DealerContextView,
    DealerLocationViewSet,
    DealerPrivacyRequestView,
    DealerProfileView,
    DealerSanctionAppealView,
    DealerSanctionStatusView,
    DealerSelfVerificationView,
    DealerStaffViewSet,
    DealerVerificationDocumentView,
    DealerVerificationViewSet,
)
from apps.dealers.serializers import (
    DealerContextLocationSerializer,
    DealerLocationSerializer,
    DealerProfileSerializer,
    DealerSelfServiceRequestSerializer,
    DealerVerificationDocumentSerializer,
    DealerVerificationSerializer,
)
from apps.platform.serializers import PlatformUserSerializer
from apps.leads.views import (
    AnalyticsEventCreateView,
    GenericUploadCreateView,
    LeadViewSet,
    NotifyMeCreateView,
    PublicReportCreateView,
)
from apps.leads.serializers import (
    AnalyticsEventSerializer,
    GenericUploadRequestSerializer,
    NotifyMeRequestSerializer,
)
from apps.marketplace.views import (
    FeedDealerDetailView,
    FeedLocationsView,
    FeedMetaView,
    FeedVehicleDetailView,
    FeedView,
)
from apps.platform.views import (
    AuditExportView,
    AuditLogViewSet,
    ContentReportViewSet,
    DataSubjectRequestViewSet,
    DealerDetailView,
    DealerDirectoryView,
    DealerProvisionView,
    DealerQueueView,
    DealerSanctionViewSet,
    PlatformLoginView,
    PlatformLocationRejectPremisesView,
    PlatformLocationStartReviewView,
    PlatformLocationVerifyPremisesView,
    PlatformLocationView,
    PlatformMeView,
    PlatformMfaView,
    PlatformOverviewView,
    PlatformRefreshView,
    PlatformRoleViewSet,
    PlatformSettingViewSet,
    PlatformSettingsView,
    PlatformUserViewSet,
    SanctionAppealViewSet,
    SecurityIncidentViewSet,
    StatsView,
    WatchlistEntryViewSet,
)
from apps.vehicles.catalog_views import (
    CatalogMakesView,
    CatalogModelsView,
    CatalogTreeView,
    CatalogTrimsView,
)
from apps.vehicles.views import VehicleViewSet
from apps.vehicles.chat_views import (
    VehicleChatDetailView,
    VehicleChatListCreateView,
    VehicleChatMessageCreateView,
)


def example(name, value, request_only=True):
    return OpenApiExample(name, value=value, request_only=request_only)


reason_request = inline_serializer(
    name="ReasonRequest",
    fields={"reason": serializers.CharField()},
)
message_request = inline_serializer(
    name="MessageRequest",
    fields={"message": serializers.CharField(required=False, allow_blank=True)},
)
status_request = inline_serializer(
    name="StatusRequest",
    fields={"status": serializers.CharField()},
)
note_request = inline_serializer(
    name="NoteRequest",
    fields={"note": serializers.CharField()},
)
refund_request = inline_serializer(
    name="RefundRequest",
    fields={
        "amountNgn": serializers.IntegerField(required=False, min_value=1),
        "reason": serializers.CharField(required=False, allow_blank=True),
    },
)
token_pair_response = inline_serializer(
    name="TokenPairResponse",
    fields={
        "accessToken": serializers.CharField(),
        "refreshToken": serializers.CharField(),
    },
)
dealer_signup_start_response = inline_serializer(
    name="DealerSignupStartResponse",
    fields={
        "phone": serializers.CharField(),
        "expiresAt": serializers.DateTimeField(),
        "devCode": serializers.CharField(required=False),
    },
)
login_response = inline_serializer(
    name="LoginResponse",
    fields={
        "accessToken": serializers.CharField(),
        "refreshToken": serializers.CharField(),
        "user": inline_serializer(
            name="AuthUserResponse",
            fields={
                "id": serializers.UUIDField(),
                "dealerId": serializers.UUIDField(),
                "email": serializers.EmailField(),
                "name": serializers.CharField(),
                "role": serializers.CharField(),
                "mustChangePassword": serializers.BooleanField(),
                "locationId": serializers.UUIDField(allow_null=True),
            },
        ),
    },
)
platform_login_response = inline_serializer(
    name="PlatformLoginResponse",
    fields={
        "accessToken": serializers.CharField(),
        "refreshToken": serializers.CharField(),
        "user": PlatformUserSerializer(),
    },
)
platform_login_request = inline_serializer(
    name="PlatformLoginRequest",
    fields={
        "email": serializers.EmailField(),
        "password": serializers.CharField(write_only=True),
    },
)
platform_refresh_request = inline_serializer(
    name="PlatformRefreshRequest",
    fields={"refreshToken": serializers.CharField()},
)
staff_invitation_preview_response = inline_serializer(
    name="StaffInvitationPreviewResponse",
    fields={
        "dealerName": serializers.CharField(),
        "memberName": serializers.CharField(),
        "role": serializers.CharField(),
        "expiresAt": serializers.DateTimeField(),
    },
)
dealer_context_response = inline_serializer(
    name="DealerContextResponse",
    fields={
        "dealerName": serializers.CharField(),
        "activeLocationId": serializers.UUIDField(allow_null=True),
        "locations": DealerContextLocationSerializer(many=True),
    },
)
dealer_sanction_status_response = inline_serializer(
    name="DealerSanctionStatusResponse",
    fields={
        "hasActiveSanction": serializers.BooleanField(),
        "sanctions": serializers.ListField(child=serializers.DictField()),
    },
)
self_service_response = inline_serializer(
    name="DealerSelfServiceResponse",
    fields={
        "id": serializers.UUIDField(),
        "status": serializers.CharField(),
    },
)
ok_response = inline_serializer(
    name="OkResponse",
    fields={"ok": serializers.BooleanField()},
)
buyer_token_response = inline_serializer(
    name="BuyerTokenResponse",
    fields={
        "access": serializers.CharField(),
        "buyer": BuyerProfileSerializer(),
    },
)
checkout_response = inline_serializer(
    name="CheckoutResponse",
    fields={
        "planId": serializers.CharField(),
        "reference": serializers.CharField(),
        "fullyCovered": serializers.BooleanField(),
        "publicKey": serializers.CharField(required=False),
        "email": serializers.EmailField(required=False),
        "amountNgn": serializers.IntegerField(required=False),
        "amountKobo": serializers.IntegerField(required=False),
        "listPriceNgn": serializers.IntegerField(required=False),
        "creditAppliedNgn": serializers.IntegerField(required=False),
        "checkoutKind": serializers.CharField(required=False),
        "currency": serializers.CharField(required=False),
        "callbackUrl": serializers.URLField(required=False),
        "metadata": serializers.DictField(required=False),
    },
)
billing_summary_response = inline_serializer(
    name="BillingSummaryResponse",
    fields={
        "subscription": SubscriptionSerializer(allow_null=True),
        "pendingDowngrade": serializers.DictField(allow_null=True),
        "paymentMethod": serializers.DictField(allow_null=True),
        "listingLimit": serializers.IntegerField(),
        "activeListings": serializers.IntegerField(),
        "canPublish": serializers.BooleanField(),
        "standLimit": serializers.IntegerField(),
        "standCount": serializers.IntegerField(),
        "canAddStand": serializers.BooleanField(),
        "vehicleCount": serializers.IntegerField(),
    },
)
invoice_pdf_response = inline_serializer(
    name="InvoicePdfResponse",
    fields={
        "pdfUrl": serializers.URLField(allow_blank=True),
    },
)
queue_response = inline_serializer(
    name="DealerQueueResponse",
    fields={"results": serializers.ListField(child=serializers.DictField())},
)
booking_summary_response = inline_serializer(
    name="BookingSummaryResponse",
    fields={
        "vehicleId": serializers.UUIDField(),
        "dealerId": serializers.UUIDField(),
        "locationId": serializers.UUIDField(),
        "nextAvailableAt": serializers.DateTimeField(),
        "openBookingCount": serializers.IntegerField(),
    },
)
mfa_response = inline_serializer(
    name="MfaResponse",
    fields={"enabled": serializers.BooleanField()},
)
catalog_makes_response = inline_serializer(
    name="CatalogMakesResponse",
    fields={
        "makes": serializers.ListField(child=serializers.DictField()),
        "source": serializers.CharField(),
    },
)
catalog_models_response = inline_serializer(
    name="CatalogModelsResponse",
    fields={
        "make": serializers.CharField(),
        "year": serializers.IntegerField(allow_null=True),
        "models": serializers.ListField(child=serializers.DictField()),
        "source": serializers.CharField(),
    },
)
catalog_trims_response = inline_serializer(
    name="CatalogTrimsResponse",
    fields={
        "make": serializers.CharField(),
        "model": serializers.CharField(),
        "trims": serializers.ListField(child=serializers.DictField()),
        "source": serializers.CharField(),
    },
)
catalog_tree_response = inline_serializer(
    name="CatalogTreeResponse",
    fields={
        "version": serializers.IntegerField(),
        "updatedAt": serializers.CharField(allow_null=True),
        "makes": serializers.ListField(child=serializers.DictField()),
        "source": serializers.CharField(),
    },
)
feed_meta_response = inline_serializer(
    name="FeedMetaResponse",
    fields={
        "makes": serializers.ListField(child=serializers.DictField()),
        "bodyTypes": serializers.ListField(child=serializers.DictField()),
        "totalVehicles": serializers.IntegerField(),
    },
)
status_response = inline_serializer(
    name="StatusResponse",
    fields={"status": serializers.CharField()},
)
stats_response = inline_serializer(
    name="StatsResponse",
    fields={
        "total": serializers.IntegerField(required=False),
        "byStatus": serializers.ListField(child=serializers.DictField(), required=False),
        "openDisputes": serializers.IntegerField(required=False),
    },
)
platform_overview_response = inline_serializer(
    name="PlatformOverviewResponse",
    fields={
        "dealers": serializers.IntegerField(),
        "vehicles": serializers.IntegerField(),
        "pendingDealerVerifications": serializers.IntegerField(),
        "pendingPremises": serializers.IntegerField(),
        "openReports": serializers.IntegerField(),
    },
)
platform_billing_config_response = inline_serializer(
    name="PlatformBillingConfigResponse",
    fields={
        "activePlans": serializers.IntegerField(),
        "subscriptions": serializers.IntegerField(),
        "openDisputes": serializers.IntegerField(),
    },
)
settings_response = inline_serializer(
    name="PlatformSettingsResponse",
    fields={"marketplace": serializers.DictField(required=False)},
)
upload_response = inline_serializer(
    name="GenericUploadResponse",
    fields={
        "id": serializers.UUIDField(),
        "purpose": serializers.CharField(),
        "fileName": serializers.CharField(),
        "contentType": serializers.CharField(),
        "fileSize": serializers.IntegerField(required=False, allow_null=True),
        "uploadUrl": serializers.CharField(),
        "publicUrl": serializers.URLField(),
        "createdAt": serializers.DateTimeField(),
    },
)


login_example = example(
    "Dealer staff login",
    {"email": "owner@example.com", "password": "strong-pass-123"},
)
dealer_signup_start_example = example(
    "Start dealer phone verification",
    {"phone": "+2348070000000"},
)
dealer_signup_verify_example = example(
    "Verify phone and enter console",
    {
        "phone": "+2348070000000",
        "code": "123456",
    },
)
dealer_signup_setup_example = example(
    "Complete dealership details",
    {
        "dealerName": "Prime Motors",
        "email": "owner@example.com",
        "standName": "Main Stand",
        "districtSlug": "wuse",
        "address": "Plot 12, Wuse, Abuja",
    },
)
dealer_signup_password_example = example(
    "Set secure login password",
    {"password": "strong-pass-123", "confirmPassword": "strong-pass-123"},
)
refresh_example = example("Refresh token", {"refreshToken": "eyJhbGciOi..."})
password_example = example(
    "Change password",
    {"currentPassword": "strong-pass-123", "newPassword": "new-strong-pass-123"},
)
vehicle_example = example(
    "Create vehicle listing",
    {
        "slug": "toyota-camry-2020-xle",
        "make": "Toyota",
        "model": "Camry",
        "year": 2020,
        "trim": "XLE",
        "priceNgn": 15000000,
        "mileageKm": 45000,
        "transmission": "automatic",
        "fuel": "petrol",
        "colour": "Black",
        "bodyType": "sedan",
        "drivetrain": "fwd",
        "conditionGrade": "good",
        "locationId": "00000000-0000-0000-0000-000000000001",
    },
)
vehicle_status_example = example(
    "Publish listing for review",
    {"status": "available", "attestationAccepted": True},
)
media_upload_example = example(
    "Vehicle media upload session",
    {
        "items": [
            {
                "kind": "photo",
                "fileName": "front-view.jpg",
                "contentType": "image/jpeg",
                "fileSize": 204800,
            }
        ]
    },
)
lead_example = example(
    "Lead capture",
    {
        "vehicleId": "00000000-0000-0000-0000-000000000010",
        "name": "Ada Buyer",
        "phone": "+2348080000000",
        "email": "ada@example.com",
        "source": "feed",
        "message": "I want to inspect this car.",
    },
)
notify_example = example(
    "Notify me",
    {"phone": "+2348070000000", "make": "Toyota", "model": "Camry", "maxPriceNgn": 20000000},
)
buyer_start_example = example("Buyer OTP start", {"phone": "+2348090000000"})
buyer_verify_example = example("Buyer OTP verify", {"phone": "+2348090000000", "code": "123456"})
buyer_profile_example = example("Buyer profile update", {"name": "Ada Buyer", "email": "ada@example.com"})
chat_example = example("Open chat", {"message": "Is this vehicle still available?"})
booking_example = example(
    "Create booking",
    {
        "vehicleId": "00000000-0000-0000-0000-000000000010",
        "buyerName": "Ada Buyer",
        "buyerPhone": "+2348080000000",
        "buyerEmail": "ada@example.com",
        "scheduledAt": "2026-07-01T10:00:00Z",
        "notes": "Morning inspection preferred.",
    },
)
appointment_example = example(
    "Create appointment",
    {
        "title": "Camry inspection",
        "vehicleId": "00000000-0000-0000-0000-000000000010",
        "locationId": "00000000-0000-0000-0000-000000000001",
        "scheduledAt": "2026-07-01T10:00:00Z",
    },
)
staff_example = example(
    "Invite dealer staff",
    {"email": "sales@example.com", "name": "Sales User", "role": "sales"},
)
verification_document_example = example(
    "Verification document",
    {"kind": "cac", "title": "CAC certificate", "fileUrl": "https://cdn.example.com/cac.pdf"},
)
generic_upload_example = example(
    "Generic upload",
    {"purpose": "verification", "fileName": "cac.pdf", "contentType": "application/pdf", "fileSize": 102400},
)
analytics_example = example(
    "Analytics event",
    {"name": "vehicle_view", "anonymousId": "web-session-123", "payload": {"source": "feed"}},
)
report_example = example(
    "Report content",
    {
        "vehicleId": "00000000-0000-0000-0000-000000000010",
        "reporterName": "Ada Buyer",
        "reporterContact": "ada@example.com",
        "reason": "Listing details look inconsistent.",
    },
)
billing_plan_example = example(
    "Platform billing plan",
    {"id": "growth", "name": "Growth", "priceNgn": 50000, "listingLimit": 50, "is_active": True, "features": []},
)
dispute_example = example(
    "Billing dispute",
    {
        "dealerId": "00000000-0000-0000-0000-000000000020",
        "invoiceId": "00000000-0000-0000-0000-000000000030",
        "reason": "Invoice amount is incorrect.",
    },
)
platform_user_example = example(
    "Platform user",
    {"email": "reviewer@example.com", "name": "Reviewer", "role": "manager", "is_staff": True},
)
platform_setting_example = example(
    "Platform settings",
    {"marketplace": {"maintenanceMode": False, "featuredDealerLimit": 10}},
)
dealer_profile_example = example(
    "Dealer profile",
    {"name": "Prime Motors", "legalName": "Prime Motors Limited", "area": "Wuse", "phone": "+2348011111111"},
)
dealer_location_example = example(
    "Dealer location",
    {"name": "Wuse Showroom", "address": "12 Ademola Adetokunbo Crescent", "city": "Abuja", "state": "FCT", "phone": "+2348011111111"},
)
role_example = example("Platform role", {"name": "review_manager", "permissions": ["dealers.review", "reports.manage"]})
sanction_example = example(
    "Dealer sanction",
    {"dealerId": "00000000-0000-0000-0000-000000000020", "reason": "Repeated listing policy violations.", "status": "active"},
)
dsr_example = example(
    "DSR request",
    {
        "dealerId": "00000000-0000-0000-0000-000000000020",
        "requesterName": "Ada Buyer",
        "requesterContact": "ada@example.com",
        "requestType": "export",
        "notes": "Export my marketplace data.",
    },
)
incident_example = example(
    "Security incident",
    {"title": "Suspicious login pattern", "severity": "medium", "status": "open", "description": "Multiple failed platform login attempts."},
)
watchlist_example = example(
    "Watchlist entry",
    {"kind": "phone", "value": "+2348011111111", "reason": "Repeated fraudulent lead submissions.", "status": "active"},
)
paystack_webhook_example = example(
    "Paystack webhook",
    {"event": "charge.success", "data": {"reference": "ASR_checkout_123", "amount": 5000000, "status": "success"}},
)

health_check = extend_schema(tags=["Core"], summary="Health check", responses={200: status_response})(health_check)

DealerSignupStartView.post = extend_schema(
    tags=["Auth"],
    summary="Start dealer owner phone verification",
    description="Creates a short-lived phone verification code for a new dealer owner registration.",
    request=DealerSignupStartSerializer,
    responses={201: dealer_signup_start_response},
    examples=[dealer_signup_start_example],
)(DealerSignupStartView.post)
DealerSignupVerifyView.post = extend_schema(
    tags=["Auth"],
    summary="Verify dealer phone and enter console",
    description="Verifies the phone code, creates a provisional dealer account plus owner staff session, and returns dealer staff JWTs.",
    request=DealerSignupVerifySerializer,
    responses={201: login_response},
    examples=[dealer_signup_verify_example],
)(DealerSignupVerifyView.post)
DealerSignupSetupView.patch = extend_schema(
    tags=["Auth"],
    summary="Complete dealer onboarding details",
    description="Updates the provisional dealer account with dealership name, verified email, and initial stand details.",
    request=DealerSignupSetupSerializer,
    responses={200: login_response},
    examples=[dealer_signup_setup_example],
)(DealerSignupSetupView.patch)
DealerSignupPasswordView.patch = extend_schema(
    tags=["Auth"],
    summary="Set secure dealer login password",
    description="Sets the owner password after the dealership details step so future sign-in uses verified email and password.",
    request=DealerSignupPasswordSerializer,
    responses={200: ok_response},
    examples=[dealer_signup_password_example],
)(DealerSignupPasswordView.patch)
LoginView.post = extend_schema(
    tags=["Auth"],
    summary="Log in dealer staff",
    description="Authenticates a dealer staff user and returns access/refresh JWTs plus dealer context.",
    request=LoginSerializer,
    responses={200: login_response},
    examples=[login_example],
)(LoginView.post)
RefreshView.post = extend_schema(
    tags=["Auth"],
    summary="Refresh dealer staff session",
    description="Exchanges a valid refresh token for a new token pair.",
    request=RefreshSerializer,
    responses={200: token_pair_response},
    examples=[refresh_example],
)(RefreshView.post)
ChangePasswordView.patch = extend_schema(
    tags=["Auth"],
    summary="Change dealer staff password",
    description="Changes the authenticated dealer staff password and clears the must-change-password flag.",
    request=ChangePasswordSerializer,
    responses={200: ok_response},
    examples=[password_example],
)(ChangePasswordView.patch)
SessionLocationView.patch = extend_schema(
    tags=["Auth"],
    summary="Switch active dealer location",
    description="Updates the staff user's preferred location and returns refreshed session tokens.",
    request=SessionLocationSerializer,
    responses={200: login_response},
    examples=[example("Switch location", {"locationId": "00000000-0000-0000-0000-000000000001"})],
)(SessionLocationView.patch)
StaffInvitationPreviewView.get = extend_schema(
    tags=["Auth"],
    summary="Preview staff invitation",
    description="Returns dealer and invitee details for a valid staff invitation token.",
    request=StaffInvitationPreviewSerializer,
    responses={200: staff_invitation_preview_response},
)(StaffInvitationPreviewView.get)
AcceptStaffInvitationView.post = extend_schema(
    tags=["Auth"],
    summary="Accept staff invitation",
    description="Sets the invited staff user's password and returns a logged-in session.",
    request=AcceptStaffInvitationSerializer,
    responses={200: login_response},
    examples=[example("Accept invite", {"token": "invite-token", "password": "strong-pass-123"})],
)(AcceptStaffInvitationView.post)

extend_schema_view(
    list=extend_schema(tags=["Vehicles"], summary="List dealer or reviewer-visible vehicles"),
    create=extend_schema(
        tags=["Vehicles"],
        summary="Create vehicle listing",
        description="Creates a dealer-scoped listing. Listing limits are enforced by the dealer plan.",
        examples=[vehicle_example],
    ),
    retrieve=extend_schema(tags=["Vehicles"], summary="Retrieve vehicle listing"),
    partial_update=extend_schema(tags=["Vehicles"], summary="Update vehicle listing", examples=[vehicle_example]),
    status=extend_schema(
        tags=["Vehicles"],
        summary="Change listing status",
        request=inline_serializer(
            name="VehicleStatusRequest",
            fields={
                "status": serializers.ChoiceField(choices=["available", "reserved", "sold", "hidden"]),
                "attestationAccepted": serializers.BooleanField(required=False),
            },
        ),
        examples=[vehicle_status_example],
    ),
    refresh=extend_schema(tags=["Vehicles"], summary="Refresh listing freshness timestamp", request=None),
    create_media_upload_session=extend_schema(
        tags=["Uploads"],
        summary="Create vehicle media upload session",
        description="Creates pending media records and returns presigned S3 PUT URLs for direct upload.",
        examples=[media_upload_example],
    ),
    complete_media_upload=extend_schema(
        tags=["Uploads"],
        summary="Complete vehicle media upload",
        description="Marks a media item uploaded/ready and auto-selects the first photo as cover when needed.",
        examples=[example("Complete media", {"status": "ready", "thumbnailUrl": "https://cdn.example.com/thumb.jpg"})],
    ),
    approve_review=extend_schema(tags=["Vehicles"], summary="Approve listing review", request=None),
    reject_review=extend_schema(
        tags=["Vehicles"],
        summary="Reject listing review",
        request=reason_request,
        examples=[example("Reject listing", {"reason": "Photo quality is too low."})],
    ),
    remove_from_feed=extend_schema(tags=["Vehicles"], summary="Remove approved listing from public feed", request=None),
)(VehicleViewSet)
VehicleChatListCreateView.get = extend_schema(
    tags=["Vehicles"],
    summary="List vehicle chats",
    auth=[{"jwtAuth": []}],
    description=(
        "Lists chat conversations attached to one vehicle. Buyer tokens only see their own conversation "
        "for the vehicle. Dealer staff tokens only see conversations for vehicles owned by their dealer."
    ),
    responses={200: BuyerConversationSerializer(many=True)},
)(VehicleChatListCreateView.get)
VehicleChatListCreateView.post = extend_schema(
    tags=["Vehicles"],
    summary="Open buyer vehicle chat",
    auth=[{"jwtAuth": []}],
    description="Opens or returns the buyer's conversation for this public vehicle and optionally adds the first buyer message.",
    request=OpenConversationSerializer,
    responses={201: BuyerConversationSerializer},
    examples=[chat_example],
)(VehicleChatListCreateView.post)
VehicleChatDetailView.get = extend_schema(
    tags=["Vehicles"],
    summary="Retrieve vehicle chat",
    auth=[{"jwtAuth": []}],
    description=(
        "Returns one conversation attached to the vehicle. Access is limited to the buyer in the conversation "
        "or dealer staff for the vehicle's owning dealer."
    ),
    responses={200: BuyerConversationSerializer},
)(VehicleChatDetailView.get)
VehicleChatMessageCreateView.post = extend_schema(
    tags=["Vehicles"],
    summary="Send vehicle chat message",
    auth=[{"jwtAuth": []}],
    description="Adds a buyer or dealer message to a conversation attached to the vehicle.",
    request=OpenConversationSerializer,
    responses={201: BuyerConversationSerializer},
    examples=[chat_example],
)(VehicleChatMessageCreateView.post)

FeedView.get = extend_schema(
    tags=["Marketplace"],
    summary="List public feed vehicles",
    description="Returns approved, available, feed-ready vehicles with optional make/model/price/year/body/location filters.",
)(FeedView.get)
FeedVehicleDetailView.get = extend_schema(tags=["Marketplace"], summary="Retrieve public vehicle detail")(FeedVehicleDetailView.get)
FeedDealerDetailView.get = extend_schema(tags=["Marketplace"], summary="Retrieve public dealer profile")(FeedDealerDetailView.get)
FeedLocationsView.get = extend_schema(tags=["Marketplace"], summary="List public feed locations")(FeedLocationsView.get)
FeedMetaView.get = extend_schema(tags=["Marketplace"], summary="Get public feed filter metadata", responses={200: feed_meta_response})(FeedMetaView.get)
CatalogTreeView.get = extend_schema(
    tags=["Marketplace"],
    summary="Get full vehicle make/model/trim catalog",
    responses={200: catalog_tree_response},
)(CatalogTreeView.get)
CatalogMakesView.get = extend_schema(tags=["Marketplace"], summary="List vehicle makes", responses={200: catalog_makes_response})(CatalogMakesView.get)
CatalogModelsView.get = extend_schema(tags=["Marketplace"], summary="List models for a make", responses={200: catalog_models_response})(CatalogModelsView.get)
CatalogTrimsView.get = extend_schema(tags=["Marketplace"], summary="List trims for a make and model", responses={200: catalog_trims_response})(CatalogTrimsView.get)

extend_schema_view(
    list=extend_schema(tags=["Leads"], summary="List dealer leads"),
    create=extend_schema(tags=["Leads"], summary="Create public lead", examples=[lead_example]),
    retrieve=extend_schema(tags=["Leads"], summary="Retrieve dealer lead"),
    partial_update=extend_schema(tags=["Leads"], summary="Update dealer lead stage/details", examples=[example("Update lead", {"stage": "contacted"})]),
)(LeadViewSet)
NotifyMeCreateView.post = extend_schema(
    tags=["Leads"],
    summary="Create notify-me request",
    description="Captures a public request to be notified when matching inventory becomes available.",
    request=NotifyMeRequestSerializer,
    examples=[notify_example],
)(NotifyMeCreateView.post)
AnalyticsEventCreateView.post = extend_schema(
    tags=["Leads"],
    summary="Track analytics event",
    description="Records a lightweight public analytics event such as vehicle views, dealer profile views, or CTA clicks.",
    request=AnalyticsEventSerializer,
    examples=[analytics_example],
)(AnalyticsEventCreateView.post)
PublicReportCreateView.post = extend_schema(
    tags=["Platform"],
    summary="Create public content report",
    description="Allows a public user to report a listing or marketplace content issue for platform review.",
    examples=[report_example],
)(PublicReportCreateView.post)
GenericUploadCreateView.post = extend_schema(
    tags=["Uploads"],
    summary="Create generic presigned upload",
    description="Returns a presigned upload URL for non-vehicle files such as verification or dispute documents.",
    request=GenericUploadRequestSerializer,
    responses={201: upload_response},
    examples=[generic_upload_example],
)(GenericUploadCreateView.post)

BuyerSignInStartView.post = extend_schema(
    tags=["Buyers"],
    summary="Start buyer OTP sign-in",
    auth=[],
    request=BuyerSignInStartSerializer,
    responses={200: status_response},
    examples=[buyer_start_example],
)(BuyerSignInStartView.post)
BuyerSignInVerifyView.post = extend_schema(
    tags=["Buyers"],
    summary="Verify buyer OTP and issue token",
    auth=[],
    request=BuyerSignInVerifySerializer,
    responses={200: buyer_token_response},
    examples=[buyer_verify_example],
)(BuyerSignInVerifyView.post)
BuyerSessionRefreshView.post = extend_schema(tags=["Buyers"], summary="Refresh buyer bearer token", auth=[{"jwtAuth": []}], request=None, responses={200: buyer_token_response})(BuyerSessionRefreshView.post)
BuyerProfileView.get = extend_schema(tags=["Buyers"], summary="Get buyer profile", auth=[{"jwtAuth": []}], responses={200: BuyerProfileSerializer})(BuyerProfileView.get)
BuyerProfileView.patch = extend_schema(tags=["Buyers"], summary="Update buyer profile", auth=[{"jwtAuth": []}], request=BuyerProfileSerializer, responses={200: BuyerProfileSerializer}, examples=[buyer_profile_example])(BuyerProfileView.patch)
BuyerSavedVehiclesView.get = extend_schema(tags=["Buyers"], summary="List saved vehicles", auth=[{"jwtAuth": []}], responses={200: SavedVehicleSerializer(many=True)})(BuyerSavedVehiclesView.get)
BuyerSavedVehicleActionView.post = extend_schema(tags=["Buyers"], summary="Save vehicle", auth=[{"jwtAuth": []}], request=None, responses={201: SavedVehicleSerializer})(BuyerSavedVehicleActionView.post)
BuyerSavedVehicleActionView.delete = extend_schema(tags=["Buyers"], summary="Unsave vehicle", auth=[{"jwtAuth": []}], request=None, responses={204: None})(BuyerSavedVehicleActionView.delete)
BuyerVisitsView.get = extend_schema(tags=["Buyers"], summary="List visited vehicles", auth=[{"jwtAuth": []}], responses={200: VehicleVisitSerializer(many=True)})(BuyerVisitsView.get)

BookingCreateView.post = extend_schema(
    tags=["Bookings"],
    summary="Create inspection booking",
    description=(
        "Creates a confirmed inspection booking for an authenticated buyer. "
        "If a visitor is not signed in, complete the buyer OTP flow first, then call this endpoint with the buyer bearer token."
    ),
    auth=[{"jwtAuth": []}],
    request=BookingSerializer,
    responses={201: BookingSerializer},
    examples=[booking_example],
)(BookingCreateView.post)
BookingSummaryView.post = extend_schema(
    tags=["Bookings"],
    summary="Get booking availability summary",
    description="Public availability check for a vehicle before an authenticated buyer creates a booking.",
    auth=[],
    request=BookingSummarySerializer,
    responses={200: booking_summary_response},
    examples=[example("Booking summary", {"vehicleId": "00000000-0000-0000-0000-000000000010"})],
)(BookingSummaryView.post)
extend_schema_view(
    list=extend_schema(tags=["Bookings"], summary="List dealer appointments"),
    create=extend_schema(tags=["Bookings"], summary="Create dealer appointment", examples=[appointment_example]),
    retrieve=extend_schema(tags=["Bookings"], summary="Retrieve dealer appointment"),
    partial_update=extend_schema(tags=["Bookings"], summary="Update dealer appointment", examples=[appointment_example]),
    cancel=extend_schema(tags=["Bookings"], summary="Cancel appointment", request=None),
)(AppointmentViewSet)

DealerProfileView.get = extend_schema(tags=["Dealers"], summary="Get dealer profile", responses={200: DealerProfileSerializer})(DealerProfileView.get)
DealerProfileView.patch = extend_schema(tags=["Dealers"], summary="Update dealer profile", request=DealerProfileSerializer, responses={200: DealerProfileSerializer}, examples=[dealer_profile_example])(DealerProfileView.patch)
DealerContextView.get = extend_schema(tags=["Dealers"], summary="Get dealer session context", responses={200: dealer_context_response})(DealerContextView.get)
extend_schema_view(
    list=extend_schema(tags=["Dealers"], summary="List dealer locations"),
    create=extend_schema(tags=["Dealers"], summary="Create dealer location", examples=[dealer_location_example]),
    retrieve=extend_schema(tags=["Dealers"], summary="Retrieve dealer location"),
    partial_update=extend_schema(tags=["Dealers"], summary="Update dealer location", examples=[dealer_location_example]),
    destroy=extend_schema(tags=["Dealers"], summary="Delete dealer location"),
    set_primary=extend_schema(tags=["Dealers"], summary="Set primary dealer location", request=None),
    request_verification=extend_schema(tags=["Dealers"], summary="Request premises verification", request=None),
)(DealerLocationViewSet)
extend_schema_view(
    list=extend_schema(tags=["Dealers"], summary="List dealer staff"),
    create=extend_schema(tags=["Dealers"], summary="Invite dealer staff", examples=[staff_example]),
    retrieve=extend_schema(tags=["Dealers"], summary="Retrieve dealer staff"),
    partial_update=extend_schema(tags=["Dealers"], summary="Update dealer staff", examples=[staff_example]),
    destroy=extend_schema(tags=["Dealers"], summary="Deactivate dealer staff"),
    resend_invite=extend_schema(tags=["Dealers"], summary="Resend staff invite", request=None),
)(DealerStaffViewSet)
DealerSelfVerificationView.get = extend_schema(tags=["Dealers"], summary="Get dealer verification status", responses={200: DealerVerificationSerializer})(DealerSelfVerificationView.get)
DealerSelfVerificationView.post = extend_schema(tags=["Dealers"], summary="Submit or resubmit dealer verification", request=None, responses={200: DealerVerificationSerializer})(DealerSelfVerificationView.post)
DealerVerificationDocumentView.post = extend_schema(tags=["Dealers"], summary="Add dealer verification document", request=DealerVerificationDocumentSerializer, responses={201: DealerVerificationDocumentSerializer}, examples=[verification_document_example])(DealerVerificationDocumentView.post)
DealerSanctionStatusView.get = extend_schema(tags=["Dealers"], summary="Get dealer sanction status", responses={200: dealer_sanction_status_response})(DealerSanctionStatusView.get)
DealerSanctionAppealView.post = extend_schema(tags=["Dealers"], summary="Submit sanction appeal", request=DealerSelfServiceRequestSerializer, responses={201: self_service_response}, examples=[example("Appeal", {"reason": "We have resolved the policy issue."})])(DealerSanctionAppealView.post)
DealerPrivacyRequestView.post = extend_schema(tags=["Dealers"], summary="Submit dealer privacy request", request=DealerSelfServiceRequestSerializer, responses={201: self_service_response}, examples=[example("Privacy request", {"reason": "Export dealer account data."})])(DealerPrivacyRequestView.post)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List dealers for platform review"),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve dealer for platform review"),
    approve_verification=extend_schema(
        tags=["Platform"],
        summary="Approve dealer verification",
        description="Approves a dealer verification review. This command does not accept a request body.",
        request=None,
    ),
    reject_verification=extend_schema(
        tags=["Platform"],
        summary="Reject dealer verification",
        description="Rejects a dealer verification review. Use `reason` to explain what the dealer must fix.",
        request=reason_request,
        examples=[example("Reject dealer verification", {"reason": "Business documents could not be verified."})],
    ),
)(DealerVerificationViewSet)

BillingPlansView.get = extend_schema(
    tags=["Billing"],
    summary="List billing plans",
    description="Returns active subscription plans available to dealers.",
    responses={200: PublicBillingPlanSerializer(many=True)},
)(BillingPlansView.get)
BillingSummaryView.get = extend_schema(tags=["Billing"], summary="Get dealer billing summary", responses={200: billing_summary_response})(BillingSummaryView.get)
InvoiceListView.get = extend_schema(
    tags=["Billing"],
    summary="List billing invoices",
    description="Lists invoices visible to the authenticated dealer. Platform reviewers can filter by `dealerId`.",
    responses={200: InvoiceSerializer(many=True)},
)(InvoiceListView.get)
InvoiceDetailView.get = extend_schema(
    tags=["Billing"],
    summary="Retrieve billing invoice",
    description="Returns one invoice visible to the authenticated dealer or platform reviewer.",
    responses={200: InvoiceSerializer},
)(InvoiceDetailView.get)
InvoicePdfView.get = extend_schema(tags=["Billing"], summary="Get invoice PDF URL", responses={200: invoice_pdf_response})(InvoicePdfView.get)
CheckoutView.post = extend_schema(tags=["Billing"], summary="Start dealer checkout", request=CheckoutSerializer, responses={200: checkout_response}, examples=[example("Checkout", {"planId": "growth"})])(CheckoutView.post)
DowngradeRequestView.post = extend_schema(tags=["Billing"], summary="Request billing downgrade", request=DowngradeRequestSerializer, responses={200: SubscriptionSerializer}, examples=[example("Downgrade", {"targetPlanId": "free", "reason": "Reducing inventory."})])(DowngradeRequestView.post)
PaystackWebhookView.post = extend_schema(tags=["Billing"], summary="Receive Paystack webhook", request=PaystackWebhookSerializer, responses={200: ok_response}, examples=[paystack_webhook_example])(PaystackWebhookView.post)
PlatformBillingConfigView.get = extend_schema(
    tags=["Billing"],
    summary="Get platform billing config summary",
    responses={200: platform_billing_config_response},
)(PlatformBillingConfigView.get)
extend_schema_view(
    list=extend_schema(tags=["Billing"], summary="List platform billing plans"),
    create=extend_schema(tags=["Billing"], summary="Create platform billing plan", examples=[billing_plan_example]),
    retrieve=extend_schema(tags=["Billing"], summary="Retrieve platform billing plan"),
    partial_update=extend_schema(tags=["Billing"], summary="Update platform billing plan", examples=[billing_plan_example]),
    destroy=extend_schema(tags=["Billing"], summary="Delete platform billing plan"),
)(PlatformBillingPlanViewSet)
extend_schema_view(
    list=extend_schema(tags=["Billing"], summary="List platform subscriptions"),
    retrieve=extend_schema(tags=["Billing"], summary="Retrieve platform subscription"),
    refund=extend_schema(
        tags=["Billing"],
        summary="Request subscription refund",
        request=refund_request,
        examples=[example("Refund", {"amountNgn": 1000, "reason": "Goodwill refund"})],
    ),
    stats=extend_schema(tags=["Billing"], summary="Get subscription stats"),
)(PlatformSubscriptionViewSet)
extend_schema_view(
    list=extend_schema(tags=["Billing"], summary="List billing disputes"),
    create=extend_schema(tags=["Billing"], summary="Create billing dispute", examples=[dispute_example]),
    retrieve=extend_schema(tags=["Billing"], summary="Retrieve billing dispute"),
    partial_update=extend_schema(tags=["Billing"], summary="Update billing dispute", examples=[dispute_example]),
    accept=extend_schema(tags=["Billing"], summary="Accept billing dispute", request=None),
    decline=extend_schema(tags=["Billing"], summary="Decline billing dispute", request=None),
    note=extend_schema(
        tags=["Billing"],
        summary="Update billing dispute note",
        request=note_request,
        examples=[example("Dispute note", {"note": "Awaiting provider response."})],
    ),
    upload_url=extend_schema(tags=["Billing"], summary="Create billing dispute upload URL", request=None),
    stats=extend_schema(tags=["Billing"], summary="Get billing dispute stats"),
    sla=extend_schema(tags=["Billing"], summary="Get billing dispute SLA summary"),
)(PlatformBillingDisputeViewSet)

PlatformLoginView.post = extend_schema(tags=["Platform"], summary="Platform staff login", request=platform_login_request, responses={200: platform_login_response}, examples=[login_example])(PlatformLoginView.post)
PlatformRefreshView.post = extend_schema(tags=["Platform"], summary="Refresh platform staff token", request=platform_refresh_request, responses={200: token_pair_response}, examples=[refresh_example])(PlatformRefreshView.post)
PlatformMeView.get = extend_schema(tags=["Platform"], summary="Get platform staff profile", responses={200: PlatformUserSerializer})(PlatformMeView.get)
PlatformMfaView.post = extend_schema(tags=["Platform"], summary="Enroll or verify platform MFA", request=None, responses={200: mfa_response})(PlatformMfaView.post)
PlatformOverviewView.get = extend_schema(
    tags=["Platform"],
    summary="Get platform overview metrics",
    responses={200: platform_overview_response},
)(PlatformOverviewView.get)
PlatformSettingsView.get = extend_schema(
    tags=["Platform"],
    summary="Get platform settings",
    responses={200: settings_response},
)(PlatformSettingsView.get)
PlatformSettingsView.patch = extend_schema(
    tags=["Platform"],
    summary="Update platform settings",
    request=inline_serializer(
        name="PlatformSettingsRequest",
        fields={"marketplace": serializers.DictField(required=False)},
    ),
    responses={200: settings_response},
    examples=[platform_setting_example],
)(PlatformSettingsView.patch)
StatsView.get = extend_schema(tags=["Platform"], summary="Get resource stats", responses={200: stats_response})(StatsView.get)
AuditExportView.get = extend_schema(
    tags=["Platform"],
    summary="Export or list recent audit entries",
    responses={200: inline_serializer(name="AuditExportResponse", fields={"entries": serializers.ListField(child=serializers.DictField())})},
)(AuditExportView.get)
DealerProvisionView.post = extend_schema(
    tags=["Platform"],
    summary="Provision dealer",
    request=inline_serializer(
        name="DealerProvisionRequest",
        fields={
            "slug": serializers.SlugField(),
            "name": serializers.CharField(),
            "legalName": serializers.CharField(required=False),
            "area": serializers.CharField(required=False),
            "phone": serializers.CharField(required=False),
        },
    ),
    responses={201: DealerProfileSerializer},
    examples=[example("Provision dealer", {"slug": "prime-motors", "name": "Prime Motors", "legalName": "Prime Motors Limited", "area": "Wuse", "phone": "+2348011111111"})],
)(DealerProvisionView.post)
DealerQueueView.get = extend_schema(tags=["Platform"], summary="List dealer or premises review queue", responses={200: queue_response})(DealerQueueView.get)
DealerDetailView.get = extend_schema(tags=["Platform"], summary="Retrieve platform dealer detail", responses={200: DealerVerificationSerializer})(DealerDetailView.get)
PlatformLocationView.get = extend_schema(tags=["Platform"], summary="Retrieve platform location detail", responses={200: DealerLocationSerializer})(PlatformLocationView.get)
PlatformLocationStartReviewView.patch = extend_schema(
    tags=["Platform"],
    summary="Start premises review",
    request=None,
    responses={200: DealerLocationSerializer},
)(PlatformLocationStartReviewView.patch)
PlatformLocationVerifyPremisesView.patch = extend_schema(
    tags=["Platform"],
    summary="Verify premises",
    request=None,
    responses={200: DealerLocationSerializer},
)(PlatformLocationVerifyPremisesView.patch)
PlatformLocationRejectPremisesView.patch = extend_schema(
    tags=["Platform"],
    summary="Reject premises",
    request=reason_request,
    responses={200: DealerLocationSerializer},
    examples=[example("Reject premises", {"reason": "Premises photo does not match the submitted address."})],
)(PlatformLocationRejectPremisesView.patch)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List platform roles"),
    create=extend_schema(tags=["Platform"], summary="Create platform role", examples=[role_example]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve platform role"),
    partial_update=extend_schema(tags=["Platform"], summary="Update platform role", examples=[role_example]),
)(PlatformRoleViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List platform users"),
    create=extend_schema(tags=["Platform"], summary="Create platform user", examples=[platform_user_example]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve platform user"),
    partial_update=extend_schema(tags=["Platform"], summary="Update platform user", examples=[platform_user_example]),
)(PlatformUserViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List platform setting records"),
    create=extend_schema(tags=["Platform"], summary="Create platform setting record", examples=[platform_setting_example]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve platform setting record"),
    partial_update=extend_schema(tags=["Platform"], summary="Update platform setting record", examples=[platform_setting_example]),
)(PlatformSettingViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List content reports"),
    create=extend_schema(tags=["Platform"], summary="Create content report", examples=[report_example]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve content report"),
    partial_update=extend_schema(tags=["Platform"], summary="Update content report", examples=[report_example]),
    assign=extend_schema(tags=["Platform"], summary="Assign content report", request=None),
    case=extend_schema(
        tags=["Platform"],
        summary="Update report case status",
        request=status_request,
        examples=[example("Update report case", {"status": "in_review"})],
    ),
    notes=extend_schema(
        tags=["Platform"],
        summary="Add report note",
        request=inline_serializer(
            name="ReportNoteRequest",
            fields={"body": serializers.CharField()},
        ),
        examples=[example("Report note", {"body": "Contacted dealer for clarification."})],
    ),
    resolve=extend_schema(tags=["Platform"], summary="Resolve content report", request=None),
)(ContentReportViewSet)
extend_schema_view(
    list=extend_schema(
        tags=["Platform"],
        summary="List data subject requests",
        description="Lists privacy/compliance requests such as data export or erasure requests raised by buyers, dealers, or support.",
    ),
    create=extend_schema(
        tags=["Platform"],
        summary="Create data subject request",
        description="Creates a privacy/compliance case for tracking a data export, erasure, or related data-subject request.",
        examples=[dsr_example],
    ),
    retrieve=extend_schema(
        tags=["Platform"],
        summary="Retrieve data subject request",
        description="Returns one privacy/compliance request and its current handling status.",
    ),
    partial_update=extend_schema(
        tags=["Platform"],
        summary="Update data subject request",
        description="Updates the status or notes for a privacy/compliance request.",
        examples=[dsr_example],
    ),
    erase=extend_schema(
        tags=["Platform"],
        summary="Mark data erasure request complete",
        description="Marks a data subject request as completed after the required erasure workflow has been handled.",
        request=None,
    ),
    export=extend_schema(
        tags=["Platform"],
        summary="Export DSR request data",
        description="Returns export metadata for the data subject request.",
    ),
    preview=extend_schema(
        tags=["Platform"],
        summary="Preview DSR request data",
        description="Previews the stored data subject request payload before export or completion.",
    ),
)(DataSubjectRequestViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List dealer sanctions"),
    create=extend_schema(tags=["Platform"], summary="Create dealer sanction", examples=[sanction_example]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve dealer sanction"),
    partial_update=extend_schema(tags=["Platform"], summary="Update dealer sanction", examples=[sanction_example]),
    lift=extend_schema(tags=["Platform"], summary="Lift dealer sanction", request=None),
)(DealerSanctionViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List sanction appeals"),
    create=extend_schema(tags=["Platform"], summary="Create sanction appeal", examples=[example("Sanction appeal", {"dealerId": "00000000-0000-0000-0000-000000000020", "reason": "Dealer submitted corrective documents."})]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve sanction appeal"),
    partial_update=extend_schema(tags=["Platform"], summary="Decide sanction appeal", examples=[example("Decide appeal", {"status": "approved"})]),
)(SanctionAppealViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List security incidents"),
    create=extend_schema(tags=["Platform"], summary="Create security incident", examples=[incident_example]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve security incident"),
    partial_update=extend_schema(tags=["Platform"], summary="Update security incident", examples=[incident_example]),
)(SecurityIncidentViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List watchlist entries"),
    create=extend_schema(tags=["Platform"], summary="Create watchlist entry", examples=[watchlist_example]),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve watchlist entry"),
    partial_update=extend_schema(tags=["Platform"], summary="Update watchlist entry", examples=[watchlist_example]),
)(WatchlistEntryViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List audit records"),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve audit record"),
)(AuditLogViewSet)
extend_schema_view(
    list=extend_schema(tags=["Platform"], summary="List dealer directory"),
    retrieve=extend_schema(tags=["Platform"], summary="Retrieve dealer directory entry"),
)(DealerDirectoryView)
