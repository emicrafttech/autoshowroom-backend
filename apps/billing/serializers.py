from rest_framework import serializers

from apps.dealers.models import Dealer

from .models import BillingDispute, BillingPlan, EarlyPlanTermination, Invoice, PaymentEvent, Subscription


class BillingPlanSerializer(serializers.ModelSerializer):
    priceNgn = serializers.IntegerField(source="price_ngn", required=False)
    listingLimit = serializers.IntegerField(source="listing_limit", required=False)
    standLimit = serializers.IntegerField(source="stand_limit", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)
    activeDealerCount = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = BillingPlan
        fields = [
            "id",
            "name",
            "priceNgn",
            "listingLimit",
            "standLimit",
            "isActive",
            "activeDealerCount",
            "features",
            "createdAt",
            "updatedAt",
        ]

    def get_activeDealerCount(self, obj):
        active_subscription_dealer_ids = set(
            obj.subscriptions.filter(status=Subscription.Status.ACTIVE).values_list(
                "dealer_id",
                flat=True,
            )
        )
        plan_dealer_ids = set(Dealer.objects.filter(plan_id=obj.id).values_list("id", flat=True))
        return len(active_subscription_dealer_ids | plan_dealer_ids)


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = BillingPlanSerializer(read_only=True)
    pendingPlan = BillingPlanSerializer(source="pending_plan", read_only=True)
    dealerId = serializers.UUIDField(source="dealer_id", read_only=True)
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    planName = serializers.CharField(source="plan.name", read_only=True)
    amountNgn = serializers.IntegerField(source="plan.price_ngn", read_only=True)
    currentPeriodEnd = serializers.DateTimeField(source="current_period_end", read_only=True)
    pendingPlanEffectiveAt = serializers.DateTimeField(source="pending_plan_effective_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "dealerId",
            "dealerName",
            "plan",
            "planName",
            "pendingPlan",
            "pendingPlanEffectiveAt",
            "amountNgn",
            "status",
            "currentPeriodEnd",
            "createdAt",
            "updatedAt",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    amountNgn = serializers.IntegerField(source="amount_ngn", read_only=True)
    pdfUrl = serializers.URLField(source="pdf_url", read_only=True)
    issuedAt = serializers.DateTimeField(source="issued_at", read_only=True)

    class Meta:
        model = Invoice
        fields = ["id", "amountNgn", "status", "pdfUrl", "issuedAt"]


class EarlyPlanTerminationSerializer(serializers.ModelSerializer):
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    planName = serializers.CharField(source="plan.name", read_only=True)
    requestedAt = serializers.DateTimeField(source="requested_at", read_only=True)
    decidedAt = serializers.DateTimeField(source="decided_at", read_only=True)
    decisionNote = serializers.CharField(source="decision_note", required=False, allow_blank=True)

    class Meta:
        model = EarlyPlanTermination
        fields = [
            "id",
            "dealer",
            "dealerName",
            "subscription",
            "plan",
            "planName",
            "reason",
            "status",
            "requestedAt",
            "decidedAt",
            "decisionNote",
        ]
        read_only_fields = ["id", "requestedAt", "decidedAt"]


class CheckoutSerializer(serializers.Serializer):
    planId = serializers.CharField(max_length=64)


class CheckoutCompleteSerializer(serializers.Serializer):
    planId = serializers.CharField(max_length=64)
    reference = serializers.CharField(required=False, allow_blank=True)


class PaymentMethodCompleteSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)


class DowngradeRequestSerializer(serializers.Serializer):
    targetPlanId = serializers.CharField(max_length=64)
    reason = serializers.CharField(required=False, allow_blank=True)


class PaystackWebhookSerializer(serializers.ModelSerializer):
    eventType = serializers.CharField(source="event_type")

    class Meta:
        model = PaymentEvent
        fields = ["id", "provider", "eventType", "reference", "payload", "received_at"]
        read_only_fields = ["id", "received_at"]


class BillingDisputeSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id")
    dealerName = serializers.CharField(source="dealer.name", read_only=True)
    invoiceId = serializers.UUIDField(source="invoice_id", required=False, allow_null=True)
    amountNgn = serializers.IntegerField(source="invoice.amount_ngn", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = BillingDispute
        fields = [
            "id",
            "dealerId",
            "dealerName",
            "invoiceId",
            "amountNgn",
            "reason",
            "note",
            "status",
            "createdAt",
            "updatedAt",
        ]


class RefundSerializer(serializers.Serializer):
    amountNgn = serializers.IntegerField(required=False, min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True)
