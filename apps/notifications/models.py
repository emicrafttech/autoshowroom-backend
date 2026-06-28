import uuid

from django.db import models


class DealerNotification(models.Model):
    class Type(models.TextChoices):
        REVIEW_ISSUE = "review_issue", "Review issue"
        PLATFORM_MESSAGE = "platform_message", "Platform message"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey(
        "dealers.Dealer",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        "accounts.StaffUser",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    review_issue = models.ForeignKey(
        "vehicles.VehicleReviewIssue",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=180)
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["dealer", "created_at"]),
        ]

    def __str__(self) -> str:
        return self.title


class PlatformNotification(models.Model):
    class Type(models.TextChoices):
        LISTING_REVIEW_SUBMITTED = "listing_review_submitted", "Listing review submitted"
        DEALER_VERIFICATION_SUBMITTED = "dealer_verification_submitted", "Dealer verification submitted"
        CONTENT_REPORT_FILED = "content_report_filed", "Content report filed"
        SANCTION_APPEAL_SUBMITTED = "sanction_appeal_submitted", "Sanction appeal submitted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        "accounts.StaffUser",
        on_delete=models.CASCADE,
        related_name="platform_notifications",
    )
    dealer = models.ForeignKey(
        "dealers.Dealer",
        on_delete=models.CASCADE,
        related_name="platform_notifications",
        null=True,
        blank=True,
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.CASCADE,
        related_name="platform_notifications",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=40, choices=Type.choices)
    title = models.CharField(max_length=180)
    body = models.TextField()
    href = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.title
