import uuid

from django.db import models


class BillingPlan(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=120)
    price_ngn = models.PositiveBigIntegerField(default=0)
    listing_limit = models.PositiveIntegerField(default=10)
    stand_limit = models.PositiveIntegerField(default=1)
    feed_priority = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    features = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_ngn", "name"]

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"
        PAUSED = "paused", "Paused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(BillingPlan, on_delete=models.PROTECT, related_name="subscriptions")
    pending_plan = models.ForeignKey(
        BillingPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_subscriptions",
    )
    pending_plan_effective_at = models.DateTimeField(null=True, blank=True)
    paystack_authorization_code = models.CharField(max_length=120, blank=True)
    payment_card_brand = models.CharField(max_length=40, blank=True)
    payment_card_last4 = models.CharField(max_length=4, blank=True)
    payment_card_exp_month = models.CharField(max_length=2, blank=True)
    payment_card_exp_year = models.CharField(max_length=4, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PAID = "paid", "Paid"
        OPEN = "open", "Open"
        VOID = "void", "Void"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="invoices")
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    amount_ngn = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    pdf_url = models.URLField(null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]


class PaymentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=40, default="paystack")
    event_type = models.CharField(max_length=120)
    reference = models.CharField(max_length=160, blank=True)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]


class BillingDispute(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="billing_disputes")
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="disputes")
    reason = models.TextField()
    note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
