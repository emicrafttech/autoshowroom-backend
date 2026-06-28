from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    BillingPlansView,
    BillingSummaryView,
    CheckoutView,
    CheckoutCompleteView,
    DowngradeRequestView,
    InvoiceDetailView,
    InvoiceListView,
    InvoicePdfView,
    PaymentMethodCompleteView,
    PaymentMethodUpdateView,
    PaystackWebhookView,
    PlatformBillingConfigView,
    PlatformBillingDisputeViewSet,
    PlatformBillingPlanViewSet,
    PlatformSubscriptionViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("platform/billing/plans", PlatformBillingPlanViewSet, basename="platform-billing-plan")
router.register("platform/billing/subscriptions", PlatformSubscriptionViewSet, basename="platform-billing-subscription")
router.register("platform/billing/disputes", PlatformBillingDisputeViewSet, basename="platform-billing-dispute")

urlpatterns = [
    path("", include(router.urls)),
    path("billing/plans", BillingPlansView.as_view(), name="billing-plans"),
    path("billing/summary", BillingSummaryView.as_view(), name="billing-summary"),
    path("billing/invoices", InvoiceListView.as_view(), name="billing-invoices"),
    path("billing/invoices/<uuid:invoice_id>", InvoiceDetailView.as_view(), name="billing-invoice-detail"),
    path("billing/invoices/<uuid:invoice_id>/pdf", InvoicePdfView.as_view(), name="billing-invoice-pdf"),
    path("billing/checkout", CheckoutView.as_view(), name="billing-checkout"),
    path("billing/checkout/complete", CheckoutCompleteView.as_view(), name="billing-checkout-complete"),
    path("billing/downgrade-request", DowngradeRequestView.as_view(), name="billing-downgrade-request"),
    path("billing/payment-method/update", PaymentMethodUpdateView.as_view(), name="billing-payment-method-update"),
    path(
        "billing/payment-method/complete",
        PaymentMethodCompleteView.as_view(),
        name="billing-payment-method-complete",
    ),
    path("billing/webhooks/paystack", PaystackWebhookView.as_view(), name="billing-paystack-webhook"),
    path("platform/billing/config", PlatformBillingConfigView.as_view(), name="platform-billing-config"),
]
