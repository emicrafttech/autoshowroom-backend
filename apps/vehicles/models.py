import uuid

from django.db import models


class VehicleMake(models.Model):
    name = models.CharField(max_length=80, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name


class VehicleModel(models.Model):
    make = models.ForeignKey(
        VehicleMake,
        on_delete=models.CASCADE,
        related_name="models",
    )
    name = models.CharField(max_length=120)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["make", "name"],
                name="unique_vehicle_model_per_make",
            )
        ]

    def __str__(self) -> str:
        return f"{self.make.name} {self.name}"


class Vehicle(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"
        HIDDEN = "hidden", "Hidden"

    class ListingVerificationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Transmission(models.TextChoices):
        AUTOMATIC = "automatic", "Automatic"
        MANUAL = "manual", "Manual"

    class Fuel(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"
        HYBRID = "hybrid", "Hybrid"
        ELECTRIC = "electric", "Electric"

    class BodyType(models.TextChoices):
        SEDAN = "sedan", "Sedan"
        SUV = "suv", "SUV"
        HATCHBACK = "hatchback", "Hatchback"
        PICKUP = "pickup", "Pickup"
        COUPE = "coupe", "Coupe"
        VAN = "van", "Van"
        WAGON = "wagon", "Wagon"
        CONVERTIBLE = "convertible", "Convertible"
        MINIVAN = "minivan", "Minivan"

    class Drivetrain(models.TextChoices):
        FWD = "fwd", "FWD"
        RWD = "rwd", "RWD"
        AWD = "awd", "AWD"
        FOUR_WD = "four_wd", "4WD"

    class ConditionGrade(models.TextChoices):
        EXCELLENT = "excellent", "Excellent"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"

    class ImportType(models.TextChoices):
        TOKUNBO = "tokunbo", "Tokunbo"
        LOCALLY_USED = "locally_used", "Locally used"
        BRAND_NEW = "brand_new", "Brand new"

    class CustomsDutyStatus(models.TextChoices):
        CLEARED = "cleared", "Cleared"
        PENDING = "pending", "Pending"
        UNKNOWN = "unknown", "Unknown"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    class BodyHistory(models.TextChoices):
        FIRST_BODY = "first_body", "First body"
        REPAINT = "repaint", "Repaint"
        ACCIDENT_RECORDED = "accident_recorded", "Accident recorded"
        UNKNOWN = "unknown", "Unknown"

    class PapersStatus(models.TextChoices):
        COMPLETE = "complete", "Complete"
        PARTIAL = "partial", "Partial"
        UNKNOWN = "unknown", "Unknown"

    class ClaimVerificationLevel(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        DEALER_CLAIMED = "dealer_claimed", "Dealer claimed"
        API_VERIFIED = "api_verified", "API verified"
        MANUALLY_VERIFIED = "manually_verified", "Manually verified"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey(
        "dealers.Dealer",
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    location = models.ForeignKey(
        "dealers.DealerLocation",
        on_delete=models.PROTECT,
        related_name="vehicles",
    )
    cover_media = models.ForeignKey(
        "vehicles.VehicleMedia",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    slug = models.SlugField(max_length=160)
    make = models.CharField(max_length=80)
    model = models.CharField(max_length=120)
    year = models.PositiveIntegerField()
    trim = models.CharField(max_length=120)
    price_ngn = models.PositiveBigIntegerField()
    mileage_km = models.PositiveIntegerField()
    transmission = models.CharField(max_length=20, choices=Transmission.choices)
    fuel = models.CharField(max_length=20, choices=Fuel.choices)
    colour = models.CharField(max_length=40)
    body_type = models.CharField(max_length=20, choices=BodyType.choices)
    drivetrain = models.CharField(max_length=20, choices=Drivetrain.choices)
    condition_grade = models.CharField(max_length=20, choices=ConditionGrade.choices)
    negotiable = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)
    vin = models.CharField(max_length=64, null=True, blank=True)
    chassis_number = models.CharField(max_length=64, null=True, blank=True)
    import_type = models.CharField(
        max_length=20,
        choices=ImportType.choices,
        null=True,
        blank=True,
    )
    year_of_manufacture = models.PositiveIntegerField(null=True, blank=True)
    engine_capacity_cc = models.PositiveIntegerField(null=True, blank=True)
    registration_plate = models.CharField(max_length=32, null=True, blank=True)
    registration_state = models.CharField(max_length=80, null=True, blank=True)
    registration_lga = models.CharField(max_length=120, null=True, blank=True)
    customs_duty_status = models.CharField(
        max_length=20,
        choices=CustomsDutyStatus.choices,
        default=CustomsDutyStatus.UNKNOWN,
    )
    customs_reference = models.CharField(max_length=120, null=True, blank=True)
    customs_cleared_at = models.DateTimeField(null=True, blank=True)
    body_history = models.CharField(
        max_length=30,
        choices=BodyHistory.choices,
        default=BodyHistory.UNKNOWN,
    )
    papers_status = models.CharField(
        max_length=20,
        choices=PapersStatus.choices,
        default=PapersStatus.UNKNOWN,
    )
    duty_paid_claim = models.CharField(
        max_length=30,
        choices=ClaimVerificationLevel.choices,
        default=ClaimVerificationLevel.UNVERIFIED,
    )
    duty_paid_verified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.HIDDEN,
    )
    listing_verification_status = models.CharField(
        max_length=30,
        choices=ListingVerificationStatus.choices,
        default=ListingVerificationStatus.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    dealer_attestation_at = models.DateTimeField(null=True, blank=True)
    listing_approved_at = models.DateTimeField(null=True, blank=True)
    listing_rejected_reason = models.TextField(null=True, blank=True)
    feed_ready = models.BooleanField(default=False)
    refreshed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dealer", "slug"],
                name="unique_vehicle_slug_per_dealer",
            )
        ]
        indexes = [
            models.Index(fields=["dealer", "status"]),
            models.Index(fields=["dealer", "location"]),
            models.Index(fields=["listing_verification_status"]),
            models.Index(fields=["make", "model"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return f"{self.year} {self.make} {self.model}"


class VehicleMedia(models.Model):
    class Kind(models.TextChoices):
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"

    class Status(models.TextChoices):
        PENDING_UPLOAD = "pending_upload", "Pending upload"
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="media_items",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    url = models.URLField(max_length=1000)
    thumbnail_url = models.URLField(max_length=1000, null=True, blank=True)
    content_type = models.CharField(max_length=120)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    s3_key = models.CharField(max_length=500, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_UPLOAD,
    )
    sort_order = models.PositiveIntegerField(default=0)
    upload_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        indexes = [
            models.Index(fields=["vehicle", "sort_order"]),
            models.Index(fields=["vehicle", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle} {self.kind} {self.sort_order}"
