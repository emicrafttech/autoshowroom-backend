from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsDealerStaff, has_vehicle_review_permission
from apps.common.views import EnvelopeMixin
from apps.platform.views import IsPlatformStaff, write_audit
from apps.vehicles.models import Vehicle

from .limits import active_listing_count, get_listing_limit
from .models import BillingDispute, BillingPlan, Invoice, PaymentEvent, Subscription
from .serializers import (
    BillingDisputeSerializer,
    BillingPlanSerializer,
    CheckoutSerializer,
    DowngradeRequestSerializer,
    InvoiceSerializer,
    PaystackWebhookSerializer,
    RefundSerializer,
    SubscriptionSerializer,
)


class BillingPlansView(EnvelopeMixin, generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BillingPlanSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return BillingPlan.objects.filter(is_active=True)


class BillingSummaryView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def get(self, request):
        dealer = request.user.dealer
        subscription = (
            Subscription.objects.filter(dealer=dealer)
            .select_related("plan")
            .order_by("-created_at")
            .first()
        )
        return Response(
            {
                "subscription": SubscriptionSerializer(subscription).data if subscription else None,
                "listingLimit": get_listing_limit(dealer),
                "activeListings": active_listing_count(dealer),
                "vehicleCount": Vehicle.objects.filter(dealer=dealer).count(),
            }
        )


class InvoiceListView(EnvelopeMixin, generics.ListAPIView):
    permission_classes = [IsDealerStaff]
    serializer_class = InvoiceSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Invoice.objects.select_related("dealer", "subscription")
        if has_vehicle_review_permission(self.request.user):
            dealer_id = self.request.query_params.get("dealerId")
            return queryset.filter(dealer_id=dealer_id) if dealer_id else queryset
        return queryset.filter(dealer_id=self.request.user.dealer_id)


class InvoiceDetailView(EnvelopeMixin, generics.RetrieveAPIView):
    permission_classes = [IsDealerStaff]
    serializer_class = InvoiceSerializer
    lookup_url_kwarg = "invoice_id"

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Invoice.objects.select_related("dealer", "subscription")
        if has_vehicle_review_permission(self.request.user):
            return queryset
        return queryset.filter(dealer_id=self.request.user.dealer_id)


class InvoicePdfView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def get(self, request, invoice_id):
        queryset = Invoice.objects.all()
        if not has_vehicle_review_permission(request.user):
            queryset = queryset.filter(dealer_id=request.user.dealer_id)
        invoice = get_object_or_404(queryset, id=invoice_id)
        return Response({"pdfUrl": invoice.pdf_url})


class CheckoutView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = get_object_or_404(BillingPlan, id=serializer.validated_data["planId"], is_active=True)
        return Response(
            {
                "planId": plan.id,
                "checkoutUrl": f"https://checkout.paystack.local/autoshowroom/{request.user.dealer_id}/{plan.id}",
            },
            status=status.HTTP_201_CREATED,
        )


class DowngradeRequestView(EnvelopeMixin, APIView):
    permission_classes = [IsDealerStaff]

    def post(self, request):
        serializer = DowngradeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PaymentEvent.objects.create(
            event_type="downgrade.requested",
            reference=str(request.user.dealer_id),
            payload=serializer.validated_data,
        )
        return Response({"status": "received"}, status=status.HTTP_202_ACCEPTED)


class PaystackWebhookView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PaystackWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(provider="paystack")
        return Response({"eventId": str(event.id)}, status=status.HTTP_202_ACCEPTED)


class PlatformBillingConfigView(EnvelopeMixin, APIView):
    permission_classes = [IsPlatformStaff]

    def get(self, request):
        return Response(
            {
                "activePlans": BillingPlan.objects.filter(is_active=True).count(),
                "subscriptions": Subscription.objects.count(),
                "openDisputes": BillingDispute.objects.filter(status=BillingDispute.Status.OPEN).count(),
            }
        )


class PlatformBillingPlanViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    permission_classes = [IsPlatformStaff]
    serializer_class = BillingPlanSerializer
    queryset = BillingPlan.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        plan = serializer.save()
        write_audit(self.request.user, "billing_plan.created", plan)

    def perform_update(self, serializer):
        plan = serializer.save()
        write_audit(self.request.user, "billing_plan.updated", plan)


class PlatformSubscriptionViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsPlatformStaff]
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.select_related("dealer", "plan")

    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        subscription = self.get_object()
        serializer = RefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = PaymentEvent.objects.create(
            event_type="subscription.refund_requested",
            reference=str(subscription.id),
            payload=serializer.validated_data,
        )
        write_audit(request.user, "subscription.refund_requested", subscription)
        return Response({"eventId": str(event.id)}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        return Response(
            {
                "total": Subscription.objects.count(),
                "byStatus": list(Subscription.objects.values("status").annotate(count=Count("id"))),
            }
        )


class PlatformBillingDisputeViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    permission_classes = [IsPlatformStaff]
    serializer_class = BillingDisputeSerializer
    queryset = BillingDispute.objects.select_related("dealer", "invoice")
    http_method_names = ["get", "post", "patch", "head", "options"]

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        dispute = self.get_object()
        dispute.status = BillingDispute.Status.ACCEPTED
        dispute.save(update_fields=["status", "updated_at"])
        write_audit(request.user, "billing_dispute.accepted", dispute)
        return Response(self.get_serializer(dispute).data)

    @action(detail=True, methods=["post"], url_path="decline")
    def decline(self, request, pk=None):
        dispute = self.get_object()
        dispute.status = BillingDispute.Status.DECLINED
        dispute.save(update_fields=["status", "updated_at"])
        write_audit(request.user, "billing_dispute.declined", dispute)
        return Response(self.get_serializer(dispute).data)

    @action(detail=True, methods=["patch"], url_path="note")
    def note(self, request, pk=None):
        dispute = self.get_object()
        dispute.note = request.data.get("note", dispute.note)
        dispute.save(update_fields=["note", "updated_at"])
        write_audit(request.user, "billing_dispute.note_updated", dispute)
        return Response(self.get_serializer(dispute).data)

    @action(detail=True, methods=["post"], url_path="upload-url")
    def upload_url(self, request, pk=None):
        dispute = self.get_object()
        return Response({"disputeId": str(dispute.id), "uploadUrl": None})

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        return Response(
            {
                "total": BillingDispute.objects.count(),
                "byStatus": list(BillingDispute.objects.values("status").annotate(count=Count("id"))),
            }
        )

    @action(detail=False, methods=["get"], url_path="sla")
    def sla(self, request):
        return Response({"openDisputes": BillingDispute.objects.filter(status=BillingDispute.Status.OPEN).count()})
