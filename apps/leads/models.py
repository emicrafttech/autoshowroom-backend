import uuid

from django.db import models


class Lead(models.Model):
    class Source(models.TextChoices):
        FEED = "feed", "Feed"
        WHATSAPP = "whatsapp", "WhatsApp"
        CALL = "call", "Call"
        BOOKING = "booking", "Booking"
        NOTIFY_ME = "notify_me", "Notify me"

    class Stage(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        INSPECTION = "inspection", "Inspection"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"
        LOST = "lost", "Lost"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="leads")
    location = models.ForeignKey("dealers.DealerLocation", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=32)
    email = models.EmailField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.FEED)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["dealer", "stage"]),
            models.Index(fields=["vehicle", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.phone}"


class NotifyMeRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=32)
    email = models.EmailField(null=True, blank=True)
    make = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=120, blank=True)
    min_year = models.PositiveIntegerField(null=True, blank=True)
    max_price_ngn = models.PositiveBigIntegerField(null=True, blank=True)
    area = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.phone


class AnalyticsEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    anonymous_id = models.CharField(max_length=120, blank=True)
    buyer = models.ForeignKey("buyers.Buyer", on_delete=models.SET_NULL, null=True, blank=True, related_name="analytics_events")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.SET_NULL, null=True, blank=True, related_name="analytics_events")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["name", "created_at"])]


class GenericUploadRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=80)
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    s3_key = models.CharField(max_length=500, unique=True)
    public_url = models.URLField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
