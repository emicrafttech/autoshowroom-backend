from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
import json

from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsActiveDealerStaff, has_vehicle_review_permission
from apps.common.views import EnvelopeMixin
from apps.platform.views import HasPlatformCapability, write_audit
from apps.vehicles.models import Vehicle

from .checkout import complete_checkout, handle_charge_success
from .payment_method import (
    complete_payment_method_update,
    handle_payment_method_success,
    start_payment_method_update,
    verification_amount_ngn,
)
from .limits import active_listing_count, active_stand_count, can_add_stand, can_publish_listing, get_listing_limit, get_stand_limit
from .models import BillingDispute, BillingPlan, Invoice, PaymentEvent, Subscription
from .paystack import (
    billing_callback_url,
    build_checkout_reference,
    is_configured,
    payment_currency,
    public_key,
    verify_webhook_signature,
)
from .subscriptions import (
    apply_due_plan_changes,
    compute_checkout_quote,
    get_active_subscription,
    payment_method_payload,
    pending_downgrade_payload,
    schedule_downgrade,
)
from .serializers import (
    BillingDisputeSerializer,
    BillingPlanSerializer,
    CheckoutCompleteSerializer,
    CheckoutSerializer,
    DowngradeRequestSerializer,
    InvoiceSerializer,
    PaymentMethodCompleteSerializer,
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
    permission_classes = [IsActiveDealerStaff]

    def get(self, request):
        dealer = request.user.dealer
        apply_due_plan_changes(dealer)
        subscription = get_active_subscription(dealer)
        return Response(
            {
                "subscription": SubscriptionSerializer(subscription).data if subscription else None,
                "pendingDowngrade": pending_downgrade_payload(subscription),
                "paymentMethod": payment_method_payload(subscription),
                "listingLimit": get_listing_limit(dealer),
                "activeListings": active_listing_count(dealer),
                "canPublish": can_publish_listing(dealer),
                "standLimit": get_stand_limit(dealer),
                "standCount": active_stand_count(dealer),
                "canAddStand": can_add_stand(dealer),
                "vehicleCount": Vehicle.objects.filter(dealer=dealer).count(),
            }
        )


class InvoiceListView(EnvelopeMixin, generics.ListAPIView):
    permission_classes = [IsActiveDealerStaff]
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
    permission_classes = [IsActiveDealerStaff]
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
    permission_classes = [IsActiveDealerStaff]

    def get(self, request, invoice_id):
        queryset = Invoice.objects.all()
        if not has_vehicle_review_permission(request.user):
            queryset = queryset.filter(dealer_id=request.user.dealer_id)
        invoice = get_object_or_404(queryset, id=invoice_id)
        return Response({"pdfUrl": invoice.pdf_url})


class CheckoutView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = request.user.dealer
        plan = get_object_or_404(BillingPlan, id=serializer.validated_data["planId"], is_active=True)

        if dealer.plan_id == plan.id:
            raise ValidationError("You are already on this plan.")

        quote = compute_checkout_quote(dealer, plan)
        reference = build_checkout_reference(dealer.id, plan.id)
        callback_url = f"{billing_callback_url()}?checkout={reference}"
        amount_kobo = quote["amount_kobo"]
        amount_ngn = quote["amount_ngn"]

        if amount_ngn <= 0:
            PaymentEvent.objects.create(
                event_type="checkout.initiated",
                reference=reference,
                payload={
                    "dealerId": str(dealer.id),
                    "planId": plan.id,
                    "fullyCovered": True,
                    "amountNgn": amount_ngn,
                    "amountKobo": amount_kobo,
                    "listPriceNgn": quote["list_price_ngn"],
                    "creditAppliedNgn": quote["credit_applied_ngn"],
                    "checkoutKind": quote["checkout_kind"],
                    "preservePeriodEnd": (
                        quote["preserve_period_end"].isoformat()
                        if quote["preserve_period_end"]
                        else None
                    ),
                },
            )
            return Response(
                {
                    "planId": plan.id,
                    "reference": reference,
                    "fullyCovered": True,
                    "publicKey": public_key(),
                    "amountNgn": amount_ngn,
                    "listPriceNgn": quote["list_price_ngn"],
                    "creditAppliedNgn": quote["credit_applied_ngn"],
                    "checkoutKind": quote["checkout_kind"],
                },
                status=status.HTTP_201_CREATED,
            )

        if not is_configured():
            raise ValidationError("Paystack is not configured. Contact support.")

        PaymentEvent.objects.create(
            event_type="checkout.initiated",
            reference=reference,
            payload={
                "dealerId": str(dealer.id),
                "planId": plan.id,
                "amountNgn": amount_ngn,
                "amountKobo": amount_kobo,
                "listPriceNgn": quote["list_price_ngn"],
                "creditAppliedNgn": quote["credit_applied_ngn"],
                "checkoutKind": quote["checkout_kind"],
                "preservePeriodEnd": (
                    quote["preserve_period_end"].isoformat()
                    if quote["preserve_period_end"]
                    else None
                ),
            },
        )

        return Response(
            {
                "planId": plan.id,
                "reference": reference,
                "fullyCovered": False,
                "publicKey": public_key(),
                "email": request.user.email,
                "amountNgn": amount_ngn,
                "amountKobo": amount_kobo,
                "listPriceNgn": quote["list_price_ngn"],
                "creditAppliedNgn": quote["credit_applied_ngn"],
                "checkoutKind": quote["checkout_kind"],
                "currency": payment_currency(),
                "callbackUrl": callback_url,
                "metadata": {
                    "dealer_id": str(dealer.id),
                    "plan_id": plan.id,
                    "expected_amount_kobo": amount_kobo,
                    "checkout_kind": quote["checkout_kind"],
                },
            },
            status=status.HTTP_201_CREATED,
        )


class CheckoutCompleteView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def post(self, request):
        serializer = CheckoutCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = request.user.dealer
        plan = get_object_or_404(BillingPlan, id=serializer.validated_data["planId"], is_active=True)
        reference = serializer.validated_data.get("reference", "").strip()
        if not reference:
            raise ValidationError("Payment reference is required.")

        result = complete_checkout(dealer, plan, reference)
        return Response(result, status=status.HTTP_201_CREATED)


class DowngradeRequestView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def post(self, request):
        serializer = DowngradeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = request.user.dealer
        target_plan = get_object_or_404(
            BillingPlan,
            id=serializer.validated_data["targetPlanId"],
            is_active=True,
        )
        result = schedule_downgrade(
            dealer,
            target_plan,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class PaymentMethodUpdateView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def post(self, request):
        if not is_configured():
            raise ValidationError("Paystack is not configured. Contact support.")

        dealer = request.user.dealer
        session = start_payment_method_update(dealer, request.user.email)
        callback_url = f"{billing_callback_url()}?cardUpdate={session['reference']}"

        return Response(
            {
                "reference": session["reference"],
                "publicKey": public_key(),
                "email": session["email"],
                "amountNgn": session["amountNgn"],
                "amountKobo": session["amountKobo"],
                "verificationAmountNgn": verification_amount_ngn(),
                "currency": payment_currency(),
                "callbackUrl": callback_url,
                "metadata": session["metadata"],
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentMethodCompleteView(EnvelopeMixin, APIView):
    permission_classes = [IsActiveDealerStaff]

    def post(self, request):
        serializer = PaymentMethodCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = request.user.dealer
        reference = serializer.validated_data["reference"].strip()
        result = complete_payment_method_update(dealer, reference)
        return Response(result, status=status.HTTP_201_CREATED)


class PaystackWebhookView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get("X-Paystack-Signature", "")
        if not verify_webhook_signature(request.body, signature):
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError("Invalid webhook payload.") from exc

        event_type = payload.get("event", "unknown")
        data = payload.get("data") or {}
        reference = data.get("reference", "")

        event = PaymentEvent.objects.create(
            provider="paystack",
            event_type=f"paystack.{event_type}",
            reference=reference,
            payload=payload,
        )

        if event_type == "charge.success":
            metadata = data.get("metadata") or {}
            if metadata.get("purpose") == "payment_method_update":
                handle_payment_method_success(reference, metadata)
            else:
                handle_charge_success(reference, metadata)

        return Response({"eventId": str(event.id)}, status=status.HTTP_202_ACCEPTED)


class PlatformBillingConfigView(EnvelopeMixin, APIView):
    permission_classes = [HasPlatformCapability]
    required_capability = "billing.read"

    def get(self, request):
        active_subscriptions = Subscription.objects.filter(status=Subscription.Status.ACTIVE).select_related("plan")
        return Response(
            {
                "activePlans": BillingPlan.objects.filter(is_active=True).count(),
                "subscriptions": Subscription.objects.count(),
                "activeSubscriptions": active_subscriptions.count(),
                "monthlyRecurringRevenue": sum(subscription.plan.price_ngn for subscription in active_subscriptions),
                "openDisputes": BillingDispute.objects.filter(status=BillingDispute.Status.OPEN).count(),
            }
        )


class PlatformBillingPlanViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    permission_classes = [HasPlatformCapability]
    read_capability = "billing.read"
    write_capability = "billing.write"
    serializer_class = BillingPlanSerializer
    queryset = BillingPlan.objects.annotate(
        activeDealerCount=Count("subscriptions", filter=Q(subscriptions__status=Subscription.Status.ACTIVE))
    )
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        plan = serializer.save()
        write_audit(self.request.user, "billing_plan.created", plan)

    def perform_update(self, serializer):
        plan = serializer.save()
        write_audit(self.request.user, "billing_plan.updated", plan)


class PlatformSubscriptionViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [HasPlatformCapability]
    read_capability = "billing.read"
    write_capability = "billing.write"
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
    permission_classes = [HasPlatformCapability]
    read_capability = "billing.read"
    write_capability = "billing.write"
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
