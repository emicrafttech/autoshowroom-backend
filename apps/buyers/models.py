import uuid

from django.db import models
from django.utils import timezone


class Buyer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=32, unique=True)
    email = models.EmailField(null=True, blank=True)
    name = models.CharField(max_length=160, blank=True)
    bio = models.TextField(blank=True, default="")
    location = models.CharField(max_length=160, blank=True, default="")
    photo_url = models.URLField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.phone


class BuyerOtp(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=32)
    code = models.CharField(max_length=8)
    name = models.CharField(max_length=160, blank=True, default="")
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone", "code"])]

    @property
    def is_valid(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()


class SavedVehicle(models.Model):
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name="saved_vehicles")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["buyer", "vehicle"], name="unique_saved_vehicle_per_buyer")
        ]
        ordering = ["-created_at"]


class VehicleVisit(models.Model):
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name="visits")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="visits")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "vehicle"],
                name="unique_buyer_vehicle_visit",
            )
        ]


class BuyerConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name="conversations")
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="buyer_conversations")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="buyer_conversations")
    booking = models.ForeignKey("bookings.Booking", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")
    last_message_at = models.DateTimeField(null=True, blank=True)
    dealer_last_read_at = models.DateTimeField(null=True, blank=True)
    buyer_last_read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "dealer", "vehicle"],
                name="unique_buyer_dealer_vehicle_conversation",
            )
        ]


class BuyerMessage(models.Model):
    class SenderType(models.TextChoices):
        BUYER = "buyer", "Buyer"
        DEALER = "dealer", "Dealer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(BuyerConversation, on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)
    body = models.TextField(blank=True, default="")
    attachment_url = models.URLField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class PriceAlert(models.Model):
    class IconKind(models.TextChoices):
        CAR = "car", "Car"
        CLOCK = "clock", "Clock"
        PULSE = "pulse", "Pulse"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name="price_alerts")
    title = models.CharField(max_length=160)
    body_type = models.CharField(max_length=20, blank=True, default="")
    make = models.CharField(max_length=80, blank=True, default="")
    model = models.CharField(max_length=120, blank=True, default="")
    min_year = models.PositiveIntegerField(null=True, blank=True)
    max_price_ngn = models.PositiveBigIntegerField(null=True, blank=True)
    min_price_ngn = models.PositiveBigIntegerField(null=True, blank=True)
    area = models.CharField(max_length=120, blank=True, default="")
    push_notify = models.BooleanField(default=True)
    icon_kind = models.CharField(
        max_length=20,
        choices=IconKind.choices,
        default=IconKind.CAR,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class BlockedDealer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name="blocked_dealers")
    dealer = models.ForeignKey(
        "dealers.Dealer",
        on_delete=models.CASCADE,
        related_name="blocked_by_buyers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "dealer"],
                name="unique_blocked_dealer_per_buyer",
            )
        ]
        ordering = ["-created_at"]


class BuyerPushDevice(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name="push_devices")
    fcm_token = models.CharField(max_length=512)
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.ANDROID)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "fcm_token"],
                name="unique_buyer_push_token",
            )
        ]
        ordering = ["-last_seen_at"]
