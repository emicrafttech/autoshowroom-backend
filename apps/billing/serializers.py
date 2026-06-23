from rest_framework import serializers

from .models import BillingDispute, BillingPlan, Invoice, PaymentEvent, Subscription


class BillingPlanSerializer(serializers.ModelSerializer):
    priceNgn = serializers.IntegerField(source="price_ngn")
    listingLimit = serializers.IntegerField(source="listing_limit")

    class Meta:
        model = BillingPlan
        fields = ["id", "name", "priceNgn", "listingLimit", "is_active", "features"]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = BillingPlanSerializer(read_only=True)
    currentPeriodEnd = serializers.DateTimeField(source="current_period_end", read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "plan", "status", "currentPeriodEnd"]


class InvoiceSerializer(serializers.ModelSerializer):
    amountNgn = serializers.IntegerField(source="amount_ngn", read_only=True)
    pdfUrl = serializers.URLField(source="pdf_url", read_only=True)
    issuedAt = serializers.DateTimeField(source="issued_at", read_only=True)

    class Meta:
        model = Invoice
        fields = ["id", "amountNgn", "status", "pdfUrl", "issuedAt"]


class CheckoutSerializer(serializers.Serializer):
    planId = serializers.CharField(max_length=64)


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
    invoiceId = serializers.UUIDField(source="invoice_id", required=False, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = BillingDispute
        fields = [
            "id",
            "dealerId",
            "invoiceId",
            "reason",
            "note",
            "status",
            "createdAt",
            "updatedAt",
        ]


class RefundSerializer(serializers.Serializer):
    amountNgn = serializers.IntegerField(required=False, min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True)
