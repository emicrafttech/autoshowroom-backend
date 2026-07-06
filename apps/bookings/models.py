import uuid

from django.db import models


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        RESCHEDULED = "rescheduled", "Rescheduled"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="bookings")
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="bookings")
    location = models.ForeignKey("dealers.DealerLocation", on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")
    buyer = models.ForeignKey("buyers.Buyer", on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")
    buyer_name = models.CharField(max_length=160)
    buyer_phone = models.CharField(max_length=32)
    buyer_email = models.EmailField(null=True, blank=True)
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_at"]
        indexes = [
            models.Index(fields=["dealer", "status"]),
            models.Index(fields=["vehicle", "scheduled_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.buyer_name} - {self.vehicle}"


class Appointment(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="appointment", null=True, blank=True)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.CASCADE, related_name="appointments")
    location = models.ForeignKey("dealers.DealerLocation", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    title = models.CharField(max_length=160)
    scheduled_at = models.DateTimeField()
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at"]
