import uuid

from django.db import models


class BillingPlan(models.Model):
    class AnalyticsTier(models.TextChoices):
        BASIC = "basic", "Basic"
        FULL = "full", "Full"

    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=120)
    price_ngn = models.PositiveBigIntegerField(default=0)
    price_yearly_ngn = models.PositiveBigIntegerField(default=0)
    listing_limit = models.PositiveIntegerField(null=True, blank=True, default=10)
    stand_limit = models.PositiveIntegerField(null=True, blank=True, default=None)
    staff_limit = models.PositiveIntegerField(null=True, blank=True, default=1)
    feed_priority = models.PositiveSmallIntegerField(default=0)
    videos_per_vehicle = models.PositiveSmallIntegerField(default=5)
    photos_per_vehicle = models.PositiveSmallIntegerField(default=15)
    max_clip_seconds = models.PositiveIntegerField(default=120)
    featured_slots_per_month = models.PositiveSmallIntegerField(default=0)
    bulk_upload = models.BooleanField(default=False)
    follow_up_reminders = models.BooleanField(default=False)
    analytics_tier = models.CharField(
        max_length=20,
        choices=AnalyticsTier.choices,
        default=AnalyticsTier.BASIC,
    )
    is_active = models.BooleanField(default=True)
    features = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_ngn", "name"]

    def __str__(self) -> str:
        return self.name

    @property
    def has_unlimited_listings(self) -> bool:
        return self.listing_limit is None

    @property
    def has_unlimited_staff(self) -> bool:
        return self.staff_limit is None


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"
        PAUSED = "paused", "Paused"

    class BillingInterval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

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
    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
    )
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
    amount_ex_vat_ngn = models.PositiveBigIntegerField(default=0)
    vat_ngn = models.PositiveBigIntegerField(default=0)
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


class EarlyPlanTermination(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="early_plan_terminations")
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="early_terminations")
    plan = models.ForeignKey(BillingPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="early_terminations")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]
