import uuid

from django.db import models


class Dealer(models.Model):
    class EntityType(models.TextChoices):
        REGISTERED_COMPANY = "registered_company", "Registered company"
        SOLE_PROPRIETOR = "sole_proprietor", "Sole proprietor"

    class VerificationStatus(models.TextChoices):
        NOT_SUBMITTED = "not_submitted", "Not submitted"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class OperationalStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        BANNED = "banned", "Banned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=160)
    legal_name = models.CharField(max_length=200)
    entity_type = models.CharField(
        max_length=40,
        choices=EntityType.choices,
        default=EntityType.REGISTERED_COMPANY,
    )
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.NOT_SUBMITTED,
    )
    operational_status = models.CharField(
        max_length=20,
        choices=OperationalStatus.choices,
        default=OperationalStatus.ACTIVE,
    )
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_reason = models.TextField(null=True, blank=True)
    verified_badge = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    area = models.CharField(max_length=120)
    city_slug = models.SlugField(default="abuja")
    district_slug = models.SlugField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    phone = models.CharField(max_length=32)
    whatsapp = models.CharField(max_length=32, null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    hours = models.JSONField(default=dict, blank=True)
    plan_id = models.CharField(max_length=40, default="free")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DealerLocation(models.Model):
    class PremisesVerificationStatus(models.TextChoices):
        NOT_SUBMITTED = "not_submitted", "Not submitted"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey(
        Dealer,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    name = models.CharField(max_length=80)
    area = models.CharField(max_length=120)
    city_slug = models.SlugField(default="abuja")
    district_slug = models.SlugField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    is_primary = models.BooleanField(default=False)
    premises_verification_status = models.CharField(
        max_length=30,
        choices=PremisesVerificationStatus.choices,
        default=PremisesVerificationStatus.NOT_SUBMITTED,
    )
    premises_verified_at = models.DateTimeField(null=True, blank=True)
    premises_rejected_at = models.DateTimeField(null=True, blank=True)
    premises_rejection_reason = models.TextField(null=True, blank=True)
    geo_changed_at = models.DateTimeField(null=True, blank=True)
    pending_geo = models.JSONField(null=True, blank=True)
    premises_rejection_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["dealer"],
                condition=models.Q(is_primary=True),
                name="unique_primary_location_per_dealer",
            )
        ]

    def __str__(self) -> str:
        return f"{self.dealer.name} - {self.name}"


class DealerVerificationDocument(models.Model):
    class Kind(models.TextChoices):
        CAC = "cac", "CAC"
        TAX = "tax", "Tax"
        IDENTITY = "identity", "Identity"
        PREMISES = "premises", "Premises"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey(
        Dealer,
        on_delete=models.CASCADE,
        related_name="verification_documents",
    )
    kind = models.CharField(max_length=40, choices=Kind.choices, default=Kind.OTHER)
    title = models.CharField(max_length=160)
    file_url = models.URLField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.dealer.name} - {self.title}"
